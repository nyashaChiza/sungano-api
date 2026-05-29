"""
APScheduler setup for background jobs
Runs auto-confirmation, default detection, and reminder dispatch tasks
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = AsyncIOScheduler(
    jobstores={'default': MemoryJobStore()},
    executors={
        'default': AsyncIOExecutor(),
        'threadpool': ThreadPoolExecutor(max_workers=3)
    },
    job_defaults={
        'coalesce': False,
        'max_instances': 1
    }
)


def start_scheduler():
    """Start the APScheduler scheduler"""
    if not scheduler.running:
        from app.jobs.auto_confirm import run_auto_confirm
        from app.jobs.default_detection import run_default_detection
        from app.jobs.reminder_dispatch import run_reminder_dispatch
        
        # Auto-confirm payments after 72 hours - runs every hour
        scheduler.add_job(
            run_auto_confirm,
            'interval',
            hours=1,
            id='auto_confirm',
            name='Auto-confirm payments after 72 hours',
        )
        
        # Detect defaults - runs daily at 8 AM
        scheduler.add_job(
            run_default_detection,
            'cron',
            hour=8,
            minute=0,
            id='default_detection',
            name='Detect defaults and update trust scores',
        )
        
        # Dispatch reminders - runs daily at 8 AM
        scheduler.add_job(
            run_reminder_dispatch,
            'cron',
            hour=8,
            minute=0,
            id='reminder_dispatch',
            name='Dispatch scheduled reminders',
        )
        
        scheduler.start()
        logger.info("Background job scheduler started")


def stop_scheduler():
    """Stop the APScheduler scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background job scheduler stopped")
