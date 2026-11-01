"""Worker loop: outbox relay + job consumer + periodic reconciliation.

Run standalone with `python -m workers.runner`, or in-process with the API (RUN_WORKERS_IN_PROCESS=true).
- redis mode:  relay publishes due outbox ids to a Redis Stream; consumers in a group process them.
- inline mode: no Redis; the relay runs the handler directly. Same retries and dead-lettering.
"""

from __future__ import annotations

import os
import signal
import socket
import threading
import time

from core.config import get_settings
from core.database import SessionLocal, init_db
from core.logging import configure_logging, correlation_id, get_logger
from core import queue
from models import Outbox
from services import outbox_service, reconcile_service, store_service
from workers.handlers import HANDLERS

log = get_logger(__name__)


def _run_job(outbox_id: int) -> None:
    """Load the outbox row, run its handler in its own transaction, then mark done / retry / dead-letter."""
    with SessionLocal() as db:
        row = db.get(Outbox, outbox_id)
        if row is None or row.status in ("done", "dead"):
            return
        topic, payload = row.topic, dict(row.payload)
    correlation_id.set(f"job-{outbox_id}")
    handler = HANDLERS.get(topic)
    error: str | None = None
    if handler is None:
        error = f"no handler for topic {topic}"
    else:
        db = SessionLocal()
        try:
            handler(db, payload)
            db.commit()
        except Exception as exc:
            db.rollback()
            error = f"{type(exc).__name__}: {exc}"
            log.warning("job_failed", topic=topic, outbox_id=outbox_id, error=error)
        finally:
            db.close()
    with SessionLocal() as db:
        row = db.get(Outbox, outbox_id)
        if row is None:
            return
        if error is None:
            outbox_service.mark_done(db, row)
        elif outbox_service.fail(db, row, error):
            log.error("job_dead_lettered", topic=topic, outbox_id=outbox_id, error=error)
        db.commit()


class Runner:
    def __init__(self):
        self.consumer = f"{socket.gethostname()}-{os.getpid()}"
        self.mode = queue.queue_mode()
        self.last_reconcile = 0.0
        self.interval = get_settings().reconcile_interval_s
        if self.mode == "redis":
            queue.ensure_group()
        log.info("worker_started", mode=self.mode, consumer=self.consumer)

    def relay_once(self) -> int:
        """Claim due outbox rows. Inline: run them now. Redis: publish ids for consumers."""
        with SessionLocal() as db:
            rows = outbox_service.claim_due(db)
            ids = [(r.id, r.topic) for r in rows]
            for r in rows:
                outbox_service.mark_dispatched(db, r)  # other relays skip it; stale ones are reclaimed after 5 min
            db.commit()
        if self.mode == "redis":
            for oid, topic in ids:
                try:
                    queue.publish(oid, topic)
                except Exception as exc:
                    log.warning("publish_failed_falling_back_inline", error=str(exc))
                    _run_job(oid)
        else:
            for oid, _ in ids:
                _run_job(oid)
        return len(ids)

    def consume_once(self, block_ms: int = 500) -> int:
        if self.mode != "redis":
            return 0
        messages = queue.claim_stale(self.consumer) + queue.read(self.consumer, block_ms=block_ms)
        for msg_id, fields in messages:
            try:
                _run_job(int(fields["outbox_id"]))
            finally:
                queue.ack(msg_id)
        return len(messages)

    def reconcile_if_due(self) -> None:
        now = time.time()
        if now - self.last_reconcile < self.interval:
            return
        self.last_reconcile = now
        with SessionLocal() as db:
            try:
                created = reconcile_service.missed_disputes(db)
                requeued = reconcile_service.stuck_settlements(db)
                if created or requeued:
                    log.info("reconciled", disputes_created=created, settlements_requeued=requeued)
            except Exception as exc:
                db.rollback()
                log.warning("reconcile_failed", error=str(exc))

    def tick(self) -> int:
        n = self.relay_once()
        n += self.consume_once()
        self.reconcile_if_due()
        return n

    def drain(self, max_rounds: int = 50) -> None:
        """Process until no work is left (used by tests and scripts)."""
        for _ in range(max_rounds):
            if self.tick() == 0:
                return

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                worked = self.tick()
            except Exception as exc:
                log.error("worker_tick_failed", error=str(exc))
                worked = 0
            if not worked and self.mode != "redis":
                stop.wait(0.5)


def start_background() -> tuple[threading.Thread, threading.Event]:
    """In-process worker for single-process deployments. Rows a previous process left 'dispatched' are reset."""
    stop = threading.Event()
    if queue.queue_mode() == "inline":
        with SessionLocal() as db:
            outbox_service.reset_stuck_dispatched(db)
            db.commit()
    runner = Runner()
    thread = threading.Thread(target=runner.run_forever, args=(stop,), name="culpa-worker", daemon=True)
    thread.start()
    return thread, stop


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    init_db()
    with SessionLocal() as db:
        store_service.seed(db)
        db.commit()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    Runner().run_forever(stop)


if __name__ == "__main__":
    main()
