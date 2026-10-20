from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import schedule

import agent


@pytest.fixture(autouse=True)
def clear_jobs():
    schedule.clear()
    yield
    schedule.clear()


def test_daily_job_uses_config_timezone(monkeypatch):
    def stop(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(agent.time, "sleep", stop)
    agent.run_scheduler({"schedule_mode": "daily", "schedule_time": "16:30"}, {"timezone": "Asia/Tokyo"})
    assert str(schedule.jobs[0].at_time_zone) == "Asia/Tokyo"


def test_interval_mode_uses_now(monkeypatch):
    fixed = datetime(2026, 10, 20, 18, 5, tzinfo=ZoneInfo("UTC"))

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz)

    monkeypatch.setattr(agent, "datetime", FakeDatetime)
    rules = {"schedule_mode": "interval", "schedule_time": "16:10"}
    assert agent.target_time_for(rules, ZoneInfo("UTC")) == "18:05"


def test_daily_mode_uses_schedule_time():
    rules = {"schedule_mode": "daily", "schedule_time": "16:10"}
    assert agent.target_time_for(rules, ZoneInfo("UTC")) == "16:10"
