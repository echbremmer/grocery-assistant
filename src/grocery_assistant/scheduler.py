"""Long-running scheduler: one cron job per query."""
import contextlib
import logging
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from grocery_assistant.config import Query
from grocery_assistant.runner import run

log = logging.getLogger(__name__)


def _job(query: Query) -> None:
    # Failures are already logged and reported to Mattermost; keep the scheduler alive.
    with contextlib.suppress(Exception):
        run(query)


def serve(queries: dict[str, Query], tz: str) -> None:
    sched = BackgroundScheduler(timezone=tz)
    for q in queries.values():
        sched.add_job(
            _job,
            CronTrigger.from_crontab(q.schedule, timezone=tz),
            args=[q],
            id=q.name,
            coalesce=True,
            misfire_grace_time=3600,  # still run if the container was down < 1 h
        )
    sched.start()
    for job in sched.get_jobs():
        log.info("scheduled %s (%s), next run %s",
                 job.id, queries[job.id].schedule, job.next_run_time)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):  # docker stop sends SIGTERM
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()
    log.info("stopping")
    sched.shutdown(wait=True)
