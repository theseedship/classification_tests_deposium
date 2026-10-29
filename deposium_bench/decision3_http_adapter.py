"""Opt-in Decision 3 API, sharing Jev's bounded transport and durable budget.

Imports/initialization do not call the service or create a key. Model metadata
is requested on every call; a mutable hosted release is never a pinned runtime.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .jev_http_adapter import (
    JevHTTPAdapter, JevProfileError, _Failure, _contains, _decode, _encode,
    validate_model_profile as validate_jev_profile,
)

ENDPOINT = 'https://decision.vllm-sr.ai/v1/systemone'
MODEL_ID = 'vllm-sr/d3-turbo'


def validate_model_profile(profile):
    if not isinstance(profile, dict) or not isinstance(profile.get('model'), dict):
        raise JevProfileError('decision3_profile_invalid')
    model = profile['model']
    if (profile.get('adapter') != 'decision3_http'
            or model.get('endpoint') != ENDPOINT or model.get('model_id') != MODEL_ID
            or model.get('credential_env') != 'DECISION_API_KEY'):
        raise JevProfileError('decision3_endpoint_or_model_invalid')
    # Reuse the existing exact field/contract, timeout and budget validation.
    translated = deepcopy(profile)
    translated['adapter'] = 'jev_http'
    translated['model'].update(endpoint='https://api.typesafe.ai/v1/systemone',
                               model_id='jev-1.13.0', credential_env='TYPESAFE_API_KEY')
    validate_jev_profile(translated)


class Decision3HTTPAdapter(JevHTTPAdapter):
    validate_profile = staticmethod(validate_model_profile)
    host = 'decision.vllm-sr.ai'
    credential_env = 'DECISION_API_KEY'
    request_id_header = 'x-request-id'
    source_files = (('decision3_adapter_sha256', Path(__file__)),)

    def _body(self, value):
        body = super()._body(value)
        body['options'] = {'return_meta': True}
        return body

    def _error_response(self, data, raw):
        try:
            native = _decode(data)
        except ValueError:
            return
        if self._key and _contains(native, self._key):
            raise _Failure('decision3_response_secret_rejected')
        raw['provider_error'] = native

    def _response(self, data, value, raw):
        native = _decode(data)
        if self._key and _contains(native, self._key):
            raise _Failure('decision3_response_secret_rejected')
        raw['native_result'] = native
        if not isinstance(native, dict) or set(native) != {'model', 'answers', 'usage', 'meta'}:
            raise _Failure('decision3_response_invalid')
        meta = native['meta']
        if (not isinstance(meta, dict) or meta.get('model_id') != MODEL_ID
                or not isinstance(meta.get('revision'), str)
                or not re.fullmatch(r'[a-f0-9]{40}', meta['revision'])
                or not isinstance(meta.get('model_sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', meta['model_sha256'])):
            raise _Failure('decision3_runtime_identity_missing')
        # Jev validates exact answer keys, finite probabilities, argmax and usage.
        try:
            _, output = super()._response(_encode({k: v for k, v in native.items() if k != 'meta'}), value, raw)
        finally:
            raw['native_result'] = native
        if native['usage']['output_tokens'] != 0:
            raise _Failure('decision3_unexpected_generated_tokens')
        raw['runtime_meta'] = meta
        return native, output
