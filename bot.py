# bot.py

import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import scraper
from config import TELEGRAM_TOKEN
from scheduler import check_and_notify_all_users  # Updated import

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# States for ConversationHandler
COACH, DAYS, START_TIME, END_TIME = range(4)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# --- Helper Functions & Keyboards ---

def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Creates the main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("➕ Create a New Alert", callback_data="main_new_alert")],
        [InlineKeyboardButton("📋 My Alerts", callback_data="main_my_alerts")],
        [InlineKeyboardButton("ℹ️ About This Bot", callback_data="main_about")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_days_keyboard(selected_days: set) -> InlineKeyboardMarkup:
    """Creates an inline keyboard for day selection with checkmarks."""
    keyboard = []
    row = []
    for day in WEEKDAYS:
        text = f"{'✅ ' if day in selected_days else ''}{day}"
        row.append(InlineKeyboardButton(text, callback_data=f"day_{day}"))
        if len(row) == 2:  # Kept at 2 for a cleaner look
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("➡️ Confirm and Continue ➡️", callback_data="day_confirm")])
    return InlineKeyboardMarkup(keyboard)


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Welcome to the Fencing Class Alert Bot!\n\n"
        "I can notify you when a private lesson slot opens up. Choose an option to get started:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=create_main_menu_keyboard())
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=create_main_menu_keyboard())


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "--- About This Bot ---\n\n"
        "This bot helps you find available private fencing lessons by automatically checking the public calendar.\n\n"
        "1. Create an alert for your preferred coach, days, and time range.\n"
        "2. The bot checks the schedule every hour (and once immediately after you create an alert).\n"
        "3. If a class opens up that matches your criteria, you'll get a message instantly!"
    )
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_start")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text)


async def new_alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()

    coaches = scraper.get_all_coaches()
    if not coaches:
        logger.warning("Could not start new alert creation because coach list is empty.")
        message = "Sorry, I couldn't fetch the list of coaches right now. This could be a temporary issue with the website. Please try again later."
        if query:
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_start")]]))
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(coach, callback_data=f"coach_{coach}")] for coach in coaches]
    keyboard.append([InlineKeyboardButton("⬅️ Cancel", callback_data="cancel_action")])
    text = "Let's set up a new alert. First, please choose your preferred coach:"
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return COACH


async def received_coach_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    coach_name = query.data.split('_', 1)[1]
    context.user_data['coach'] = coach_name
    context.user_data['days'] = set()
    keyboard = create_days_keyboard(context.user_data['days'])
    await query.edit_message_text(
        text=f"Great, you've selected **{coach_name}**.\n\nNow, please select your preferred days.",
        reply_markup=keyboard, parse_mode='Markdown'
    )
    return DAYS


async def received_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split('_', 1)[1]

    if action == 'confirm':
        if not context.user_data.get('days'):
            await context.bot.answer_callback_query(query.id, "Please select at least one day.", show_alert=True)
            return DAYS
        await query.edit_message_text("Perfect. Now, what is the *earliest* time you're available? (e.g., 16:00)",
                                      parse_mode='Markdown')
        return START_TIME
    else:
        day = action
        selected_days = context.user_data.get('days', set())
        if day in selected_days:
            selected_days.remove(day)
        else:
            selected_days.add(day)
        context.user_data['days'] = selected_days
        keyboard = create_days_keyboard(selected_days)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return DAYS


async def received_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_input = update.message.text.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', time_input):
        await update.message.reply_text("Invalid format. Please use HH:MM (e.g., 09:00 or 17:30).")
        return START_TIME
    context.user_data['start_time'] = time_input
    await update.message.reply_text(
        f"Okay, starting from {time_input}. What is the *latest* time you're available? (e.g., 19:00)",
        parse_mode='Markdown')
    return END_TIME


async def received_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the alert and triggers an immediate check for classes."""
    end_time = update.message.text.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', end_time):
        await update.message.reply_text("Invalid format. Please use HH:MM (e.g., 21:00).")
        return END_TIME

    start_time = context.user_data['start_time']
    time_range = f"{start_time}-{end_time}"
    coach = context.user_data['coach']
    days = ",".join(sorted(list(context.user_data['days'])))

    db.add_alert(update.message.chat_id, coach, days, time_range)

    await update.message.reply_text(
        f"✅ **Alert Created!**\n\n"
        f"  **Coach:** {coach}\n"
        f"  **Days:** {days}\n"
        f"  **Time Range:** {time_range}\n\n"
        "I'm performing an initial check now. If any classes match your criteria, you'll get a separate notification message shortly.",
        reply_markup=create_main_menu_keyboard(),
        parse_mode='Markdown'
    )

    # --- NEW FEATURE ---
    # Trigger an immediate, non-blocking check for all users.
    context.application.create_task(
        check_and_notify_all_users(context.bot, triggered_by=f"new alert from user {update.effective_chat.id}")
    )

    context.user_data.clear()
    return ConversationHandler.END


async def my_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    alerts = db.get_user_alerts(chat_id)
    text = "Your active alerts:\n"
    keyboard_buttons = []
    if not alerts:
        text = "You have no active alerts."
    else:
        for alert in alerts:
            alert_id, coach, days, time_range = alert
            day_parts = days.split(',')
            short_days = " ".join([day[:2] for day in day_parts])
            button_text = f"❌ {coach} | {short_days} | {time_range}"
            keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"delete_{alert_id}")])

    keyboard_buttons.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_start")])
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons))


async def delete_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    alert_id = int(query.data.split('_')[1])
    db.delete_alert(alert_id)
    await query.answer(text="Alert deleted!", show_alert=True)
    await my_alerts(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Action cancelled.", reply_markup=create_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_alert_start, pattern='^main_new_alert$')],
        states={
            COACH: [CallbackQueryHandler(received_coach_callback, pattern='^coach_')],
            DAYS: [CallbackQueryHandler(received_day_callback, pattern='^day_')],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_start_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_end_time)],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel_action$')],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start, pattern='^main_start$'))
    application.add_handler(CallbackQueryHandler(about, pattern='^main_about$'))
    application.add_handler(CallbackQueryHandler(my_alerts, pattern='^main_my_alerts$'))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("myalerts", my_alerts))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(delete_alert_callback, pattern='^delete_'))

    scheduler = AsyncIOScheduler(timezone="UTC")
    # Updated scheduler to use the new function name
    scheduler.add_job(check_and_notify_all_users, 'interval', hours=1, args=[application.bot, "hourly schedule"])
    scheduler.start()
    logger.info("Scheduler started. Will run checks every hour.")

    application.run_polling()


if __name__ == "__main__":
    main()