"""Durable, serial HTTP attempt budget; importing never touches the ledger."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import uuid

POLICY_VERSION = 'deposium.http-budget/v1'
EVENT_VERSION = 'deposium.http-budget-event/v1'
MAX_LEDGER_BYTES = 4 * 1024 * 1024


class BudgetError(ValueError):
    """A fixed identifier, without filesystem or provider exception details."""


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))+'\n').encode()


def _decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BudgetError('jev_budget_ledger_invalid')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise BudgetError('jev_budget_ledger_invalid') from None


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _safe_path(path):
    if not path.is_absolute() or '..' in path.parts:
        raise BudgetError('jev_budget_path_invalid')
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise BudgetError('jev_budget_path_invalid')


def _parents(path):
    return tuple((str(parent), parent.stat().st_dev, parent.stat().st_ino) for parent in path.parents)


def _guard(path, fd, parents=None):
    _safe_path(path)
    if parents is not None and _parents(path) != parents:
        raise BudgetError('jev_budget_ledger_changed')
    opened, present = os.fstat(fd), path.stat()
    if (not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (present.st_dev, present.st_ino)):
        raise BudgetError('jev_budget_ledger_changed')


def _append(path, fd, record, parents=None):
    _guard(path, fd, parents)
    payload = _encode(record)
    if os.fstat(fd).st_size + len(payload) > MAX_LEDGER_BYTES:
        raise BudgetError('jev_budget_ledger_invalid')
    os.lseek(fd, 0, os.SEEK_END)
    while payload:
        written = os.write(fd, payload)
        if written <= 0:
            raise OSError('budget_write_failed')
        payload = payload[written:]
    os.fsync(fd)
    _guard(path, fd, parents)


def _read(path, fd, policy, parents=None):
    _guard(path, fd, parents)
    if os.fstat(fd).st_size > MAX_LEDGER_BYTES:
        raise BudgetError('jev_budget_ledger_invalid')
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while chunk := os.read(fd, 65536):
        chunks.append(chunk)
        if sum(map(len, chunks)) > MAX_LEDGER_BYTES:
            raise BudgetError('jev_budget_ledger_invalid')
    data = b''.join(chunks)
    header = {'schema_version': POLICY_VERSION, 'kind': 'policy', 'policy': policy,
              'policy_sha256': hashlib.sha256(_encode(policy)).hexdigest()}
    if not data:
        _append(path, fd, header, parents)
        # Persist the directory entry as well as the newly created file bytes.
        # Newly created parent directories also need their parent entries persisted.
        for parent in path.parents:
            directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try: os.fsync(directory)
            finally: os.close(directory)
        _guard(path, fd, parents)
        return {}, {}, None
    if not data.endswith(b'\n'):
        raise BudgetError('jev_budget_ledger_invalid')
    records = [_decode(line) for line in data.splitlines()]
    if _encode(records[0]) != _encode(header):
        raise BudgetError('jev_budget_policy_mismatch')
    reservations, settlements = {}, {}
    last_start = None
    charged = 0
    for record in records[1:]:
        if not isinstance(record, dict) or record.get('schema_version') != EVENT_VERSION:
            raise BudgetError('jev_budget_ledger_invalid')
        attempt = record.get('attempt_id')
        if not isinstance(attempt, str):
            raise BudgetError('jev_budget_ledger_invalid')
        try:
            if str(uuid.UUID(attempt)) != attempt:
                raise ValueError()
        except ValueError:
            raise BudgetError('jev_budget_ledger_invalid') from None
        if record.get('kind') == 'reservation':
            if (set(record) != {'schema_version','kind','attempt_id','request_number','reserved_input_tokens','started_at'}
                    or attempt in reservations or type(record['request_number']) is not int
                    or record['request_number'] != len(reservations)+1
                    or type(record['reserved_input_tokens']) is not int
                    or record['reserved_input_tokens'] != policy['reserved_input_tokens_per_request']
                    or not _number(record['started_at']) or len(reservations) >= policy['max_requests']):
                raise BudgetError('jev_budget_ledger_invalid')
            if (charged + record['reserved_input_tokens'] > policy['max_input_tokens']
                    or (last_start is not None and record['started_at'] < last_start)):
                raise BudgetError('jev_budget_ledger_invalid')
            charged += record['reserved_input_tokens']
            reservations[attempt] = record
            last_start = record['started_at']
        elif record.get('kind') == 'settlement':
            if (set(record) != {'schema_version','kind','attempt_id','input_tokens','output_tokens','settled_at'}
                    or attempt not in reservations or attempt in settlements
                    or type(record['input_tokens']) is not int or not 0 <= record['input_tokens'] <= policy['reserved_input_tokens_per_request']
                    or type(record['output_tokens']) is not int or record['output_tokens'] < 0
                    or not _number(record['settled_at']) or record['settled_at'] < reservations[attempt]['started_at']):
                raise BudgetError('jev_budget_ledger_invalid')
            charged -= policy['reserved_input_tokens_per_request'] - record['input_tokens']
            settlements[attempt] = record
        else:
            raise BudgetError('jev_budget_ledger_invalid')
    return reservations, settlements, last_start


class Attempt:
    def __init__(self, path, fd, attempt_id, started_at, reserved, parents=None):
        self.attempt_id = attempt_id
        self._path, self._fd, self._started_at, self._reserved = path, fd, started_at, reserved
        self._parents = parents
        self._settled = False

    def settle(self, usage):
        if (self._settled or not isinstance(usage, dict) or set(usage) != {'input_tokens','output_tokens'}
                or type(usage['input_tokens']) is not int or not 0 <= usage['input_tokens'] <= self._reserved
                or type(usage['output_tokens']) is not int or usage['output_tokens'] < 0):
            raise BudgetError('jev_usage_invalid')
        record = {'schema_version': EVENT_VERSION, 'kind': 'settlement', 'attempt_id': self.attempt_id,
                  **usage, 'settled_at': max(time.time(), self._started_at)}
        _append(self._path, self._fd, record, self._parents)
        self._settled = True


class HTTPBudget:
    """All instances share the append-only ledger and hold its lock across HTTP."""
    def __init__(self, path: Path, policy: dict):
        self.path = Path(path)
        self.policy = json.loads(_encode(policy))

    @contextmanager
    def reserve(self):
        _safe_path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _safe_path(self.path)
        parents = _parents(self.path)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
        try:
            _guard(self.path, fd, parents)
            lock_deadline = time.monotonic() + self.policy['timeout_seconds']
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    remaining = lock_deadline - time.monotonic()
                    if remaining <= 0:
                        raise BudgetError('jev_budget_lock_timeout') from None
                    time.sleep(min(.05, remaining))
            reservations, settlements, last_start = _read(self.path, fd, self.policy, parents)
            used = sum(settlements[attempt]['input_tokens'] if attempt in settlements else record['reserved_input_tokens']
                       for attempt, record in reservations.items())
            reserved = self.policy['reserved_input_tokens_per_request']
            if len(reservations) >= self.policy['max_requests']:
                raise BudgetError('jev_request_budget_exhausted')
            if used + reserved > self.policy['max_input_tokens']:
                raise BudgetError('jev_input_budget_exhausted')
            if last_start is not None:
                now = time.time()
                if not _number(now) or now < last_start:
                    raise BudgetError('jev_budget_clock_invalid')
                delay = self.policy['min_interval_seconds'] - (now - last_start)
                if delay > 0:
                    time.sleep(delay)
            started_at = time.time()
            if not _number(started_at):
                raise BudgetError('jev_budget_clock_invalid')
            attempt_id = str(uuid.uuid4())
            _append(self.path, fd, {'schema_version': EVENT_VERSION, 'kind': 'reservation',
                                   'attempt_id': attempt_id,'request_number':len(reservations)+1,
                                   'reserved_input_tokens': reserved, 'started_at': started_at}, parents)
            yield Attempt(self.path, fd, attempt_id, started_at, reserved, parents)
        finally:
            try: fcntl.flock(fd, fcntl.LOCK_UN)
            finally: os.close(fd)
