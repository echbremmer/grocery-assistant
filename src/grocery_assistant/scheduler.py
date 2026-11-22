"""Long-running scheduler: one cron job per query."""
import contextlib
import logging
import re
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from grocery_assistant.config import Query
from grocery_assistant.runner import run

log = logging.getLogger(__name__)


CRON_DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # cron: 0 and 7 = Sunday


def cron_trigger(expr: str, tz: str) -> CronTrigger:
    """Standard 5-field cron, with cron's weekday numbers (0/7 = Sunday).

    APScheduler 3's CronTrigger.from_crontab() treats weekday numbers as
    0 = Monday, so "0 8 * * 1" would run on Tuesday. Numbers are translated to
    day names, which mean the same thing in both.
    """
    minute, hour, day, month, dow = expr.split()
    dow = re.sub(r"\d", lambda m: CRON_DAYS[int(m.group())], dow)
    return CronTrigger(minute=minute, hour=hour, day=day, month=month,
                       day_of_week=dow, timezone=tz)


def _job(query: Query) -> None:
    # Failures are already logged and reported to Mattermost; keep the scheduler alive.
    with contextlib.suppress(Exception):
        run(query)


def serve(queries: dict[str, Query], tz: str) -> None:
    sched = BackgroundScheduler(timezone=tz)
    for q in queries.values():
        sched.add_job(
            _job,
            cron_trigger(q.schedule, tz),
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
