import pytest

from tools.retry import with_retry


def test_succeeds_after_failures():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("nope")
        return "ok"

    assert with_retry(flaky, sleep=sleeps.append) == "ok"
    assert sleeps == [1.0, 2.0]


def test_raises_after_exhausted():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_retry(always_fails, sleep=lambda s: None)
    assert len(calls) == 3
