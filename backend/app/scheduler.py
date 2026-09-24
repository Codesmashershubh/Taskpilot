import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.agent.orchestrator import Orchestrator
from app.config import get_settings
from app.email_source.factory import get_email_source
from app.llm.factory import get_llm_provider

logger = logging.getLogger("taskpilot.scheduler")

_scheduler = AsyncIOScheduler()


async def _poll_job() -> None:
    settings = get_settings()
    try:
        orchestrator = Orchestrator(llm=get_llm_provider(), email_source=get_email_source())
        run_ids = await orchestrator.poll_and_process(settings.gmail_watch_label)
        if run_ids:
            logger.info("Scheduled poll processed %s email(s): %s", len(run_ids), run_ids)
    except Exception:  # noqa: BLE001 - a bad poll must never kill the scheduler
        logger.exception("Scheduled poll failed")


def start_scheduler() -> None:
    settings = get_settings()
    if _scheduler.running:
        return
    _scheduler.add_job(_poll_job, "interval", seconds=settings.poll_interval_seconds, id="poll_inbox", max_instances=1)
    _scheduler.start()
    logger.info("Scheduler started: polling every %ss", settings.poll_interval_seconds)


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
