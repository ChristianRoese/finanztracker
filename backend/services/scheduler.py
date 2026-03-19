import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from backend.database import engine
from backend.services.etf_service import refresh_all_prices

logger = logging.getLogger(__name__)


def _daily_price_refresh() -> None:
    try:
        with Session(engine) as session:
            updated = refresh_all_prices(session)
            logger.info(f"Scheduler: ETF-Preise aktualisiert für {len(updated)} Positionen")
    except Exception as e:
        logger.error(f"Scheduler: Fehler beim Preis-Refresh: {e}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _daily_price_refresh,
        "cron",
        hour=18,
        minute=0,
        id="daily_price_refresh",
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler gestartet (täglicher ETF-Preis-Refresh um 18:00)")
    return scheduler
