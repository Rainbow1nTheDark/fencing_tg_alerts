# scheduler.py

from telegram import Bot
from scraper import get_available_classes
from database import get_all_alerts, add_sent_notification, has_notification_been_sent  # Updated import
from datetime import datetime
import logging

# Get the logger
logger = logging.getLogger(__name__)


def is_time_in_range(time_str: str, time_range_str: str) -> bool:
    """Checks if a time (HH:MM) is within a given range (e.g., '16:00-18:00')."""
    try:
        slot_time = datetime.strptime(time_str.split('-')[0].strip(), "%H:%M").time()
        start_str, end_str = time_range_str.split('-')
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        return start_time <= slot_time <= end_time
    except (ValueError, IndexError):
        return False


async def check_and_notify_all_users(bot: Bot, triggered_by: str = "scheduled check"):
    """
    Fetches classes, checks against user alerts, and sends notifications
    only if they haven't been sent before.
    """
    logger.info(f"Running check for classes, triggered by: {triggered_by}...")

    available_slots = get_available_classes()
    if not available_slots:
        logger.info("Check complete: No available slots found on the website.")
        return

    all_alerts = get_all_alerts()
    if not all_alerts:
        logger.info("Check complete: No user alerts are currently set in the database.")
        return

    notifications_sent = 0
    for alert in all_alerts:
        alert_id, chat_id, coach, days, time_range = alert

        for slot in available_slots:
            if (coach.lower() in slot['coach'].lower() and
                    slot['day'] in days and
                    is_time_in_range(slot['time'], time_range)):

                # Create a unique key for the notification to prevent duplicates.
                notification_key = f"{slot['coach']}-{slot['date']}-{slot['time']}"

                # --- NEW DUPLICATE CHECK ---
                if not has_notification_been_sent(chat_id, notification_key):
                    message = (
                        f"🔔 **Class Available!**\n\n"
                        f"**Coach:** {slot['coach']}\n"
                        f"**Day:** {slot['day']}, {slot['date']}\n"
                        f"**Time:** {slot['time']}\n\n"
                        f"This matches your alert for `{coach}` on `{days}` between `{time_range}`."
                    )
                    try:
                        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                        # Record that this notification was sent successfully.
                        add_sent_notification(chat_id, notification_key)
                        notifications_sent += 1
                        logger.info(f"Sent NEW notification to {chat_id} for {slot['coach']}.")
                    except Exception as e:
                        logger.error(f"Failed to send message to {chat_id}: {e}")

    if notifications_sent > 0:
        logger.info(f"Check complete. Sent {notifications_sent} new notifications.")
    else:
        logger.info("Check complete. No new matching slots found for any users.")