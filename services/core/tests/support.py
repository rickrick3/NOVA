from datetime import UTC, datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"
CREDS = {"username": "farel", "password": "correct horse battery"}


class FakeClock:
    def __init__(self, start: datetime = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
