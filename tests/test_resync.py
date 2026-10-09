from unittest.mock import MagicMock

from harbor.backend.base import ProxyBackend
from harbor.tasks import resync


def test_resync_calls_every_backend_and_survives_failures(monkeypatch):
    failing, working = MagicMock(), MagicMock()
    failing.resync.side_effect = RuntimeError("boom")
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 2:
            raise SystemExit

    monkeypatch.setattr(resync.time, "sleep", sleep)

    thread = resync.create_resync([failing, working])
    try:
        thread._target()
    except SystemExit:
        pass

    assert failing.resync.call_count == 2
    assert working.resync.call_count == 2
    assert thread.daemon


def test_base_backend_resync_is_a_no_op():
    ProxyBackend().resync()
