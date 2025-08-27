"""Main application entry point."""

import asyncio
import os
import signal
import sys
from typing import Optional

from dotenv import load_dotenv

from bot.main import bot, dp, db
from scraper.kwork_scraper import KworkScraper

load_dotenv()

# Global variables for graceful shutdown
scraper: Optional[KworkScraper] = None
monitoring_task: Optional[asyncio.Task] = None


async def start_scraper():
    """Start the Kwork scraper."""
    global scraper, monitoring_task
    
    scraper = KworkScraper(db)
    await scraper.start()
    
    # Start monitoring loop in background
    monitoring_task = asyncio.create_task(scraper.run_monitoring_loop())
    print("🔍 Monitoring started")


async def stop_scraper():
    """Stop the Kwork scraper."""
    global scraper, monitoring_task
    
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
    
    if scraper:
        await scraper.stop()


async def shutdown(signal, loop):
    """Graceful shutdown handler."""
    print(f"\n🛑 Received exit signal {signal.name}...")
    
    # Stop scraper
    await stop_scraper()
    
    # Stop bot
    await bot.session.close()
    
    # Stop event loop
    loop.stop()


async def main():
    """Main application function."""
    # Initialize database
    await db.init()
    
    # Add default admins
    admin_ids = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    for admin_id in admin_ids:
        await db.add_admin(admin_id)
    
    # Start scraper if credentials are provided
    if os.getenv("KWORK_LOGIN") and os.getenv("KWORK_PASSWORD"):
        await start_scraper()
    else:
        print("⚠️ Kwork credentials not provided, scraper disabled")
    
    print("🤖 Starting Kwork Auto Offer Bot...")
    
    try:
        # Start bot polling
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    finally:
        await stop_scraper()


def setup_signal_handlers(loop):
    """Setup signal handlers for graceful shutdown."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )


if __name__ == "__main__":
    # Setup event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Setup signal handlers
    setup_signal_handlers(loop)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    finally:
        loop.close()
        print("👋 Application stopped")
