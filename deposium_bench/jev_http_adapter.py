"""Explicit Jev HTTPS transport. Imports and initialization never make requests."""
from __future__ import annotations

import copy
import hashlib
from http.client import HTTPSConnection, HTTPException
import json
import math
import os
from pathlib import Path
import re
import socket
import ssl
import sys
import threading
import time

from .choice_protocol import CONTEXT_CHOICE_CONTRACT, validate_choice_input
from .http_budget import HTTPBudget, BudgetError

ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
HOST = 'api.typesafe.ai'
PATH = '/v1/systemone'
CREDENTIAL_ENV = 'TYPESAFE_API_KEY'
MAX_RESPONSE_BYTES = 1024 * 1024
MODEL_FIELDS = {'endpoint', 'model_id', 'credential_env', 'budget_ledger', 'max_requests',
                'max_input_tokens', 'reserved_input_tokens_per_request', 'max_request_bytes', 'min_interval_seconds'}


class JevProfileError(ValueError):
    """Invalid non-secret HTTP profile settings."""


class _Failure(ValueError):
    pass


def _finite(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def validate_model_profile(profile):
    model = profile.get('model')
    if not isinstance(model, dict) or set(model) != MODEL_FIELDS:
        raise JevProfileError('jev_profile_fields_invalid')
    if (profile.get('adapter') != 'jev_http' or profile.get('qualification') != 'model_isolated'
            or profile.get('capabilities') != [CONTEXT_CHOICE_CONTRACT]
            or profile.get('revision') is not None or profile.get('recordings') is not None):
        raise JevProfileError('jev_profile_contract_invalid')
    if (model['endpoint'] != ENDPOINT or model['credential_env'] != CREDENTIAL_ENV
            or not isinstance(model['model_id'], str)
            or not re.fullmatch(r'jev-[0-9]+\.[0-9]+\.[0-9]+', model['model_id'])):
        raise JevProfileError('jev_profile_endpoint_or_version_invalid')
    if (not isinstance(model['budget_ledger'], str) or not model['budget_ledger'].strip()
            or '\x00' in model['budget_ledger']):
        # Relative ../ locators are accepted by the framework after absolute rebasing.
        raise JevProfileError('jev_profile_budget_path_invalid')
    for key, ceiling in (('max_requests', 800), ('max_input_tokens', 2_000_000), ('max_request_bytes', 131072)):
        if type(model[key]) is not int or not 1 <= model[key] <= ceiling:
            raise JevProfileError('jev_profile_budget_invalid')
    if type(model['reserved_input_tokens_per_request']) is not int or model['reserved_input_tokens_per_request'] != 65536:
        raise JevProfileError('jev_profile_reservation_invalid')
    if not _finite(model['min_interval_seconds'], .1):
        raise JevProfileError('jev_profile_interval_invalid')
    timeout = profile.get('timeout_seconds')
    if not _finite(timeout) or not 0 < timeout <= 30:
        raise JevProfileError('jev_profile_timeout_invalid')


def _encode(value, *, ordered=False):
    return json.dumps(value, ensure_ascii=False, sort_keys=not ordered, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise _Failure('jev_response_invalid')
            result[key] = value
        return result
    if len(data) > MAX_RESPONSE_BYTES:
        raise _Failure('jev_response_too_large')
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        # Reject overflowed JSON numbers and invalid Unicode before retaining diagnostics.
        _encode(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise _Failure('jev_response_invalid') from None


def _envelope(status, output=None, raw=None, error=None):
    return {'status': status, 'output': output, 'raw_output': raw, 'error': error}


def _stat(path):
    info = path.stat()
    return (str(path.resolve()), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _contains(value, secret):
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(_contains(key, secret) or _contains(item, secret) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains(item, secret) for item in value)
    return False


class JevHTTPAdapter:
    capabilities = (CONTEXT_CHOICE_CONTRACT,)
    validate_profile = staticmethod(validate_model_profile)
    host = HOST
    path = PATH
    credential_env = CREDENTIAL_ENV
    request_id_header = 'x-typesafe-request-id'
    source_files = ()

    def __init__(self, profile, profile_path):
        self.validate_profile(profile)
        self._model = copy.deepcopy(profile['model'])
        self._timeout = float(profile['timeout_seconds'])
        self._lock = threading.Lock()
        self._connection = None
        self._closed = False
        self._failure = None
        self._sources = {}
        hashes = {}
        for name, path in (('adapter_sha256', Path(__file__)),
                           ('budget_helper_sha256', Path(__file__).with_name('http_budget.py')),
                           ('choice_protocol_sha256', Path(__file__).with_name('choice_protocol.py'))) + self.source_files:
            before = _stat(path)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if before != _stat(path):
                raise JevProfileError('jev_source_changed')
            self._sources[path] = before
        self._policy = {key: value for key, value in self._model.items() if key not in {'budget_ledger','credential_env'}}
        self._policy['timeout_seconds'] = self._timeout
        ledger = Path(self._model['budget_ledger'])
        if not ledger.is_absolute():
            ledger = Path(profile_path).absolute().parent / ledger
        # Do not resolve symlinks: the budget helper rejects them before opening.
        self._budget = HTTPBudget(Path(os.path.abspath(ledger)), self._policy)
        settings = {**self._policy, 'retry_policy': 'none', 'tls_verify': True, 'redirects': False, 'proxy': False}
        self.provenance = {'profile_sha256': _digest(profile), **hashes, 'adapter': profile['adapter'],
                           'qualification': 'model_isolated', 'model': copy.deepcopy(self._model),
                           'capabilities': list(self.capabilities), 'available': False,
                           'transport': 'https_post_json', 'input_protocol': 'context_choice',
                           'runtime': {'python': sys.version.split()[0], 'openssl': ssl.OPENSSL_VERSION},
                           'settings': settings, 'budget_policy_sha256': _digest(self._policy)}
        identity = copy.deepcopy(self.provenance)
        identity.pop('profile_sha256')
        identity.pop('available')
        identity['model'].pop('budget_ledger')
        self.provenance['identity_sha256'] = _digest(identity)
        self._key = os.environ.get(self.credential_env)
        if not self._key:
            self._fail('missing', 'jev_credential_missing')
        elif (not self._key.isascii() or any(ord(char) <= 32 or ord(char) >= 127 for char in self._key)):
            self._fail('error', 'jev_credential_invalid')
        else:
            self.provenance['available'] = True

    def _guard(self):
        if any(_stat(path) != saved for path, saved in self._sources.items()):
            raise _Failure('jev_source_changed')

    def _fail(self, status, code, raw=None):
        # Error identifiers are fixed strings; provider text is never propagated.
        if self._key and raw is not None and _contains(raw, self._key):
            raw = None
        self._failure = _envelope(status, raw=raw, error=code)
        self.provenance.update(available=False, availability_error=code)
        self.close()
        return copy.deepcopy(self._failure)

    def close(self):
        self._closed = True
        connection = self._connection
        self._connection = None
        if connection is not None:
            try: connection.close()
            except (OSError, HTTPException): pass

    def _http(self, body):
        """One bounded HTTPS request, with socket shutdown at the total deadline."""
        started = time.monotonic()
        deadline = started + self._timeout
        connection = HTTPSConnection(self.host, port=443, timeout=self._timeout, context=ssl.create_default_context())
        self._connection = connection
        stopped = threading.Event()
        sockets = []
        def expire():
            stopped.set()
            for sock in sockets:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            try: connection.close()
            except (OSError, HTTPException): pass
        timer = threading.Timer(self._timeout, expire)
        timer.daemon = True
        timer.start()
        response = None
        def remaining():
            left = deadline - time.monotonic()
            if stopped.is_set() or left <= 0:
                raise TimeoutError()
            if connection.sock is not None:
                connection.sock.settimeout(left)
            return left
        try:
            connection.connect()
            if connection.sock is not None:
                sockets.append(connection.sock)
            remaining()
            connection.request('POST', self.path, body=body,
                               headers={'Authorization': 'Bearer '+self._key, 'Content-Type': 'application/json',
                                        'Accept': 'application/json'})
            remaining()
            response = connection.getresponse()
            remaining()
            status = response.status
            if type(status) is not int or not 100 <= status <= 599:
                raise _Failure('jev_http_protocol_invalid')
            request_id = response.getheader(self.request_id_header)
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', request_id):
                request_id = None
            length = response.getheader('content-length')
            if length is not None and (not re.fullmatch(r'[0-9]+', length) or int(length) > MAX_RESPONSE_BYTES):
                raise _Failure('jev_response_too_large')
            chunks, size = [], 0
            while True:
                remaining()
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                remaining()
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise _Failure('jev_response_too_large')
                chunks.append(chunk)
            return status, request_id, b''.join(chunks), (time.monotonic()-started)*1000
        except (OSError, HTTPException):
            if stopped.is_set() or time.monotonic() >= deadline:
                raise TimeoutError() from None
            raise
        finally:
            timer.cancel()
            timer.join()
            if response is not None:
                try: response.close()
                except OSError: pass
            connection.close()
            self._connection = None

    def _response(self, data, value, raw):
        native = _decode(data)
        if self._key and _contains(native, self._key):
            raise _Failure('jev_response_secret_rejected')
        raw['native_result'] = native
        if not isinstance(native, dict) or set(native) != {'model','answers','usage'}:
            raise _Failure('jev_response_invalid')
        if native['model'] != self._model['model_id']:
            raise _Failure('jev_model_version_mismatch')
        answers = native['answers']
        if not isinstance(answers, dict) or set(answers) != {'answer'}:
            raise _Failure('jev_response_invalid')
        answer = answers['answer']
        if not isinstance(answer, dict) or set(answer) != {'type','choice','probabilities','confidence'} or answer['type'] != 'choice':
            raise _Failure('jev_response_invalid')
        descriptions = {option['description']: option['id'] for option in value['options']}
        probabilities = answer['probabilities']
        if (not isinstance(probabilities, dict) or set(probabilities) != set(descriptions)
                or any(not _finite(probability) or probability > 1 for probability in probabilities.values())):
            raise _Failure('jev_response_invalid')
        probability_sum = sum(probabilities.values())
        hundredth_grid = all(abs(probability*100-round(probability*100)) <= 1e-8
                             for probability in probabilities.values())
        tolerance = max(1e-5, .005*len(descriptions)+1e-12) if hundredth_grid else 1e-5
        raw.update(probability_sum=probability_sum, probability_sum_tolerance=tolerance,
                   rounding_assumption='hundredth_grid' if hundredth_grid else 'none')
        if (abs(probability_sum-1) > tolerance
                or not _finite(answer['confidence']) or answer['confidence'] > 1
                or not isinstance(answer['choice'], str) or answer['choice'] not in descriptions
                or not math.isclose(probabilities[answer['choice']], max(probabilities.values()),
                                    rel_tol=0.0, abs_tol=4 * math.ulp(max(probabilities.values())))):
            raise _Failure('jev_response_invalid')
        usage = native['usage']
        if (not isinstance(usage, dict) or set(usage) != {'input_tokens','output_tokens'}
                or type(usage['input_tokens']) is not int or not 0 <= usage['input_tokens'] <= 65536
                or type(usage['output_tokens']) is not int or usage['output_tokens'] < 0):
            raise _Failure('jev_usage_invalid')
        return native, {'choice_id': descriptions[answer['choice']]}

    def _body(self, value):
        return {'model': self._model['model_id'], 'state': value['context'],
                'questions': {'answer': {'type': 'choice', 'instructions': value['question'],
                                        'criteria': {option['description']: None for option in value['options']}}}}

    def _error_response(self, data, raw):
        """Provider-specific optional diagnostics; legacy Jev keeps status only."""
        return

    def predict(self, request):
        if not isinstance(request, dict) or request.get('contract_id') != CONTEXT_CHOICE_CONTRACT:
            return _envelope('unsupported', error='unsupported_contract')
        with self._lock:
            if self._failure is not None:
                cached = copy.deepcopy(self._failure)
                if cached['raw_output'] is not None:
                    cached['raw_output'] = {'http_attempted': False, 'cached_failure': True,
                                            'cause_attempt_id': cached['raw_output'].get('attempt_id')}
                return cached
            if self._closed:
                return _envelope('error', error='jev_adapter_closed')
            value = request.get('input')
            try:
                validate_choice_input(value)
                input_digest = _digest(value)
                if _contains(value, self._key):
                    return _envelope('error', error='jev_input_secret_rejected')
                body = _encode(self._body(value), ordered=True)
            except (ValueError, TypeError, UnicodeError, RecursionError):
                return _envelope('error', error='jev_input_invalid')
            if len(body) > self._model['max_request_bytes']:
                return _envelope('unsupported', error='jev_request_body_too_large')
            raw = None
            try:
                self._guard()
                with self._budget.reserve() as attempt:
                    raw = {'http_attempted': True, 'cached_failure': False, 'native_result': None, 'input_sha256': input_digest,
                           'request_body_sha256': hashlib.sha256(body).hexdigest(), 'response_sha256': None,
                           'http_ms': None, 'requested_model': self._model['model_id'], 'observed_model': None,
                           'usage': None, 'request_id': None, 'http_status': None, 'attempt_id': attempt.attempt_id}
                    self._guard()
                    started = time.monotonic()
                    try:
                        status, request_id, data, elapsed = self._http(body)
                    finally:
                        raw['http_ms'] = (time.monotonic()-started)*1000
                    raw.update(http_status=status, request_id=request_id, response_sha256=hashlib.sha256(data).hexdigest(), http_ms=elapsed)
                    if status != 200:
                        self._error_response(data, raw)
                        code = {401:'jev_http_unauthorized',403:'jev_http_forbidden',429:'jev_http_rate_limited',
                                529:'jev_http_overloaded',422:'jev_http_unprocessable'}.get(status, 'jev_http_status_'+str(status))
                        raise _Failure(code)
                    native, output = self._response(data, value, raw)
                    self._guard()
                    raw.update(native_result=native, observed_model=native['model'], usage=native['usage'])
                    if _contains(raw, self._key):
                        raise _Failure('jev_response_secret_rejected')
                    attempt.settle(native['usage'])
                    return _envelope('ok', output=output, raw=raw)
            except TimeoutError:
                return self._fail('timeout', 'jev_http_timeout', raw)
            except ssl.SSLCertVerificationError:
                return self._fail('error', 'jev_tls_verification_failed', raw)
            except BudgetError as error:
                return self._fail('error', str(error), raw)
            except _Failure as error:
                return self._fail('error', str(error), raw)
            except (OSError, HTTPException):
                return self._fail('error', 'jev_http_network_error', raw)
            except (ValueError, TypeError, KeyError, OverflowError):
                return self._fail('error', 'jev_http_protocol_invalid', raw)
            except BaseException:
                self._fail('error', 'jev_http_interrupted', raw)
                raise
