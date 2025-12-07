"""
Trip Planner Bot - Entry Point and Handlers.

A Telegram bot that helps families plan kid-friendly getaways.
Uses Tavily for web search and Ollama/Qwen3 for LLM processing.
"""  # Noqa: E501

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import TELEGRAM_BOT_TOKEN, PLACE, START_DATE, END_DATE
from models import BotState
from storage import get_session, save_session, clear_session

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command - Welcome message.
    """
    await update.message.reply_text(
        f"👋 Welcome to {PLACE} Trip Planner!\n\n"
        f"I help families plan kid-friendly {PLACE} getaways.\n\n"
        "🔹 /plan - Start planning your trip\n"
        "🔹 /help - See all commands\n\n"
        "Ready? Tap /plan to begin!"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command - Show available commands.
    """
    await update.message.reply_text(
        f"📖 *{PLACE} Trip Planner - Help*\n\n"
        "*Commands:*\n"
        "/start - Welcome message\n"
        "/plan - Start or restart trip planning\n"
        "/help - Show this help message\n\n"
        "*How it works:*\n"
        "1️⃣ I'll show activities & restaurants\n"
        "2️⃣ Tap ✅ to select what interests you\n"
        "3️⃣ Tell me your hotel\n"
        "4️⃣ Pick number of days\n"
        "5️⃣ Get your personalized itinerary!\n\n"
        "💡 Tip: Use /plan anytime to start over.",
        parse_mode="Markdown"
    )


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /plan command - Start or restart trip planning.

    This clears any existing session and restarts the planning flow.
    """
    chat_id = update.effective_chat.id

    clear_session(chat_id)
    session = get_session(chat_id)

    session.state = BotState.SELECTING_ACTIVITIES
    session.start_date = START_DATE
    session.end_date = END_DATE
    save_session(session)

    await update.message.reply_text(
        f"🗓️ Planning your {PLACE} trip ({START_DATE} - {END_DATE})...\n\n"
        "⏳ Searching for kid-friendly activities..."
    )

    # TODO: Phase 2 - Call services.search_activities() and send with keyboards
    # For now, just confirm the state transition worked
    await update.message.reply_text(
        "✅ Bot is ready!\n\n"
        "📋 Current state: SELECTING_ACTIVITIES\n\n"
        "🔧 *Phase 1 Complete* - Core handlers working.\n"
        "Next: Implement services.py and keyboards.py for full flow.",
        parse_mode="Markdown"
    )


async def handle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline buttons (callback queries).

    Callback data format:
    - sel_act_001 / des_act_001 - Select/deselect activity
    - sel_fod_001 / des_fod_001 - Select/deselect food
    - done_act / done_fod - Done selecting
    - htl_yes / htl_no - Hotel confirmation
    - days_N - Select N days
    - itin_regen / itin_ok - Itinerary actions
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    chat_id = query.message.chat_id
    data = query.data
    session = get_session(chat_id)

    logger.info(
        f"Callback from {chat_id}: {data} "
        f"(state: {session.state.value})"
    )

    # TODO: Phase 2 - Implement callback handling for each button type
    # For now, just log and acknowledge
    await query.edit_message_text(
        f"🔧 Callback received: `{data}`\n"
        f"State: `{session.state.value}`\n\n"
        "Full callback handling coming in Phase 2.",
        parse_mode="Markdown"
    )

    save_session(session)


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle text messages.
    Add handle AFTER command handlers to avoid conflicts.

    Used primarily for:
    - Hotel name input (when in WAITING_FOR_HOTEL state)
    """
    chat_id = update.effective_chat.id
    text = update.message.text
    session = get_session(chat_id)

    logger.info(
        f"Text from {chat_id}: {text[:40]}... (state: {session.state.value})"
    )

    if session.state == BotState.WAITING_FOR_HOTEL:
        # TODO: Phase 2 - Call services.parse_hotel() and confirm
        await update.message.reply_text(
            f"🏨 Got it! You entered: *{text}*\n\n"
            "Hotel parsing coming in Phase 2.",
            parse_mode="Markdown"
        )
    elif session.state == BotState.IDLE:
        # User sent text but hasn't started planning
        await update.message.reply_text(
            "👋 Hi! Use /plan to start planning your trip, "
            "or /help to see available commands."
        )
    else:
        # Unexpected text in other states
        await update.message.reply_text(
            f"🤔 I wasn't expecting text input right now.\n"
            f"Current state: {session.state.value}\n\n"
            "Use /plan to start over or /help for guidance."
        )

    save_session(session)


async def error_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Log errors"""
    logger.error(f"Update {update} caused error: {context.error}")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set! "
            "Create a .env file with your bot token."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers - order matters!
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    app.add_error_handler(error_handler)

    # Start polling
    logger.info(f"🤖 {PLACE} Trip Planner Bot starting...")
    logger.info(f"📍 Destination: {PLACE}")
    logger.info(f"📅 Dates: {START_DATE} - {END_DATE}")
    print("\n🤖 Bot is running! Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
