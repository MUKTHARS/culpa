"""Test environment: isolated SQLite file, no network credentials, inline queue, no background worker."""

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="culpa-test-"))
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite:///{(_tmp / 'test.db').as_posix()}",
    "REDIS_URL": "",
    "QUEUE_MODE": "inline",
    "RUN_WORKERS_IN_PROCESS": "false",
    "PAYPAL_CLIENT_ID": "",
    "PAYPAL_CLIENT_SECRET": "",
    "PAYPAL_WEBHOOK_ID": "",
    "ALLOW_UNVERIFIED_WEBHOOKS": "true",
    "ANTHROPIC_API_KEY": "",
    "ANALYST_USERNAME": "",
    "ANALYST_PASSWORD": "",
    "AUTO_SETTLE": "false",
    "RECONCILE_INTERVAL_S": "100000",
    "BENCH_DIR": str(_tmp / "bench"),
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture(scope="session")
def client():
    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def drain():
    from workers.runner import Runner

    def _drain():
        Runner().drain()

    return _drain
