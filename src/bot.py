"""
Trip Planner Bot - Entry Point and Handlers.

A Telegram bot that helps families plan kid-friendly getaways.
Uses Tavily for web search and Ollama/Qwen3 for LLM processing.
"""  # Noqa: E501

import logging
import textwrap
from telegram import Update, Message
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import (
    TELEGRAM_BOT_TOKEN,
    PLACE,
    START_DATE,
    END_DATE,
    TELEGRAM_MAX_LEN,
    CHUNK_LEN
)
from models import Activity, BotState, UserSession
from storage import get_session, save_session, clear_session
from services import (
    search_activities,
    search_food,
    parse_hotel,
    generate_itinerary
)
from keyboards import (
    build_activity_keyboard,
    build_food_keyboard,
    build_days_keyboard,
    build_confirm_keyboard,
    build_itinerary_keyboard
)

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
        f"I'm powered by Qwen LLM and Tavily API.\n\n"
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
        "1️⃣ I'll show activities & eateries\n"
        "2️⃣ Tap ✅ to select what interests you\n"
        "3️⃣ Pick number of days\n"
        "4️⃣ Tell me your hotel\n"
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

    session.start_date = START_DATE
    session.end_date = END_DATE
    save_session(session)

    await update.message.reply_text(
        f"🗓️ Planning your {PLACE} trip ({START_DATE} - {END_DATE})...\n\n"
        "🔎 Searching for kid-friendly activities...\n"
        "⏳ This may take a moment. Please wait..."
    )

    # Delegate to step starter
    await _start_activity_selection(update.message, session)


async def handle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline buttons (callback queries).

    Callback data format:
    - sel_act_001 / des_act_001 - Select/deselect activity
    - sel_fod_001 / des_fod_001 - Select/deselect food
    - done_act / done_fod - Done selecting
    - days_N - Select N days
    - htl_yes / htl_no - Hotel confirmation (Phase 3)
    - itin_regen / itin_ok - Itinerary actions (Phase 4)
    """
    query = update.callback_query

    chat_id = query.message.chat_id
    data = query.data
    session = get_session(chat_id)

    logger.info(
        f"Callback from {chat_id}: {data} "
        f"(state: {session.state.value})"
    )

    # Route to appropriate handler
    if data.startswith("sel_act_") or data.startswith("des_act_"):
        await _handle_selection(query, session, data, "activity")
    elif data.startswith("sel_fod_") or data.startswith("des_fod_"):
        await _handle_selection(query, session, data, "food")
    elif data == "done_act":
        await _handle_done_activities(query, session)
    elif data == "done_fod":
        await _handle_done_food(query, session)
    elif data.startswith("days_"):
        await _handle_days_selection(query, session, data)
    elif data in ("htl_yes", "htl_no"):
        await _handle_hotel_confirmation(query, session, data)
    elif data in ("itin_regen", "itin_ok"):
        await _handle_itinerary_action(query, session, data)
    else:
        await query.answer("Unknown action", show_alert=True)

    save_session(session)


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle text messages.
    Add handler AFTER command handlers to avoid conflicts.

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
        await update.message.reply_text(
            "🔍 Looking up your hotel..."
        )
        try:
            hotel_info = parse_hotel(text)
            session.hotel = hotel_info
            session.state = BotState.CONFIRMING_HOTEL
            save_session(session)

            if hotel_info.confidence == "high":
                confidence_text = ""
            elif hotel_info.confidence == "medium":
                confidence_text = "\n_(I'm fairly confident about this)_"
            else:
                confidence_text = "\n_(I'm not entirely sure - please verify)_"

            keyboard = build_confirm_keyboard()
            await update.message.reply_text(
                f"📍 Got it! I found:\n\n"
                f"*{hotel_info.name}*\n"
                f"📍 Area: {hotel_info.area}"
                f"{confidence_text}\n\n"
                "Is this correct?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            logger.info(
                f"Hotel parsed: {hotel_info.name} in {hotel_info.area} "
                f"(confidence: {hotel_info.confidence})"
            )

        except Exception as e:
            logger.error(f"Error parsing hotel: {e}")
            await update.message.reply_text(
                "❌ Sorry, I had trouble understanding that hotel.\n"
                "Please try typing the hotel name again."
            )
    elif session.state == BotState.IDLE:
        await update.message.reply_text(
            "👋 Hi! Use /plan to start planning your trip, "
            "or /help to see available commands."
        )
    elif session.state in (
        BotState.SELECTING_ACTIVITIES, BotState.SELECTING_FOOD
    ):
        await update.message.reply_text(
            "👆 Please use the buttons above to make selections.\n"
            "Tap ✅ to select, then tap 'Done' when finished."
        )
    elif session.state == BotState.CONFIRMING_HOTEL:
        await update.message.reply_text(
            "👆 Please use the buttons above to confirm your hotel,\n"
            "or tap 'No' to re-enter."
        )
    elif session.state == BotState.REVIEWING_ITINERARY:
        await update.message.reply_text(
            "👆 Please use the buttons above to accept or regenerate\n"
            "your itinerary."
        )
    else:
        await update.message.reply_text(
            f"🤔 I wasn't expecting text input right now.\n"
            f"Current state: {session.state.value}\n\n"
            "Use /plan to start over or /help for guidance."
        )

    save_session(session)


async def _start_activity_selection(
    message: Message, session: UserSession
) -> None:
    """
    Search for activities and display selection keyboard.
    """
    try:
        activities = search_activities()
    except Exception as e:
        logger.error(f"Error searching activities: {e}")
        await message.reply_text(
            "❌ Sorry, I had trouble searching for activities.\n"
            "Please try again with /plan."
        )
        return

    if not activities:
        await message.reply_text(
            "😕 I couldn't find any activities. Please try /plan again."
        )
        return

    # Update session
    session.activities = activities
    session.state = BotState.SELECTING_ACTIVITIES
    save_session(session)

    activities_text = _format_reco_message(activities, "activities")
    keyboard = build_activity_keyboard(activities, session.selected_activities)

    await message.reply_text(
        activities_text,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    logger.info(
        f"Started activity selection with {len(activities)} activities"
    )


async def _start_food_selection(
    message: Message, session: UserSession
) -> None:
    """
    Search for eateries and display selection keyboard.
    """
    try:
        eateries = search_food()
    except Exception as e:
        logger.error(f"Error searching eateries: {e}")
        await message.reply_text(
            "❌ Sorry, I had trouble searching for eateries.\n"
            "Please try again with /plan."
        )
        return

    if not eateries:
        await message.reply_text(
            "😕 I couldn't find any eateries. Please try /plan again."
        )
        return

    # Update session
    session.eateries = eateries
    session.state = BotState.SELECTING_FOOD
    save_session(session)

    food_text = _format_reco_message(eateries, "eateries")
    keyboard = build_food_keyboard(eateries, session.selected_eateries)

    await message.reply_text(
        food_text,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    logger.info(
        f"Started food selection with {len(eateries)} eateries"
    )


async def _start_days_selection(
    message: Message, session: UserSession
) -> None:
    """
    Prompt user to select number of days.
    """
    session.state = BotState.SELECTING_DAYS
    save_session(session)

    keyboard = build_days_keyboard()
    await message.reply_text(
        f"📅 *How many days in {PLACE}?*\n\n"
        "Select the number of days for your itinerary:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    logger.info("Started days selection")


async def _start_hotel_input(
    message: Message, session: UserSession
) -> None:
    """
    Prompt user for hotel name.
    """
    session.state = BotState.WAITING_FOR_HOTEL
    save_session(session)

    await message.reply_text(
        f"🏨 *Where are you staying in {PLACE}?*\n\n"
        "Please type your hotel name or address and we will make an inference.\n"  # Noqa E501
        "_(e.g., \"Bintan Lagoon Resort\" or \"Four Points by Sheraton\")_",
        parse_mode="Markdown"
    )

    logger.info("Started hotel input")


async def _start_itinerary_generation(
    message: Message, session: UserSession
) -> None:
    """
    Generate itinerary and display with review keyboard.
    """
    session.state = BotState.GENERATING
    save_session(session)

    status_msg = await message.reply_text(
        "⏳ *Generating your personalized itinerary...*\n\n"
        "I'm considering:\n"
        f"• {len(session.selected_activities)} activities you selected\n"
        f"• {len(session.selected_eateries)} eateries you selected\n"
        f"• Your hotel location ({session.hotel.area if session.hotel else 'Unknown'})\n"  # Noqa E501
        f"• Travel times between locations\n\n"
        "_This may take a moment. LLM is thinking..._",
        parse_mode="Markdown"
    )

    try:
        selected_activities = [
            act for act in session.activities
            if act.id in session.selected_activities
        ]
        selected_eateries = [
            eat for eat in session.eateries
            if eat.id in session.selected_eateries
        ]
        itinerary = generate_itinerary(
            selected_activities=selected_activities,
            selected_eateries=selected_eateries,
            hotel_name=session.hotel.name if session.hotel else "Hotel",
            hotel_area=session.hotel.area if session.hotel else "Unknown",
            num_days=session.num_days
        )
        session.current_itinerary = itinerary
        session.state = BotState.REVIEWING_ITINERARY
        save_session(session)

        try:
            await status_msg.delete()
        except Exception:
            pass  # Ignore if we can't delete

        # Send itinerary (with chunking if needed)
        await _send_itinerary(message, itinerary)

        logger.info("Itinerary generated and sent successfully")

    except Exception as e:
        logger.error(f"Error generating itinerary: {e}")
        session.state = BotState.CONFIRMING_HOTEL
        save_session(session)

        await message.reply_text(
            "❌ Sorry, I had trouble generating your itinerary.\n"
            "Please try confirming your hotel again or "
            "use /plan to start over."
        )


async def _handle_selection(
    query, session: UserSession, data: str, selection_type: str
) -> None:
    """
    Handle select/deselect toggle for activities or food.

    Args:
        selection_type: "activity" or "food"
    """
    if selection_type == "activity":
        expected_state = BotState.SELECTING_ACTIVITIES
        selected_ids = session.selected_activities
        items = session.activities
        keyboard_builder = build_activity_keyboard
        header_type = "activities"
    else:
        expected_state = BotState.SELECTING_FOOD
        selected_ids = session.selected_eateries
        items = session.eateries
        keyboard_builder = build_food_keyboard
        header_type = "eateries"

    if session.state != expected_state:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return

    # Parse callback: "sel_act_001" or "des_fod_001"
    parts = data.split("_")
    action = parts[0]  # "sel" or "des"
    item_id = parts[2]  # "001"

    if action == "sel":
        if item_id not in selected_ids:
            selected_ids.append(item_id)
            await query.answer("✅ Selected!")
    else:
        if item_id in selected_ids:
            selected_ids.remove(item_id)
            await query.answer("Deselected")

    # Update message in-place
    text = _format_reco_message(items, header_type)
    keyboard = keyboard_builder(items, selected_ids)

    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def _handle_done_activities(query, session: UserSession) -> None:
    """
    Handle 'Done Selecting Activities' button.
    Show summary, then delegate to food step.
    """
    if session.state != BotState.SELECTING_ACTIVITIES:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    count, summary = _build_selection_summary(
        session.activities,
        session.selected_activities
    )

    await query.edit_message_text(
        f"✅ *Activities Selected ({count}):*\n"
        f"{summary}\n\n"
        "🔎 Now searching for eateries..."
        "⏳ This may take a moment. Please wait...",
        parse_mode="Markdown"
    )

    # Delegate to next step
    await _start_food_selection(query.message, session)


async def _handle_done_food(query, session: UserSession) -> None:
    """
    Handle 'Done Selecting Eateries' button
    Show summary, then delegate to days step.
    """
    if session.state != BotState.SELECTING_FOOD:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    count, summary = _build_selection_summary(
        session.eateries,
        session.selected_eateries
    )

    await query.edit_message_text(
        f"✅ *Eateries Selected ({count}):*\n"
        f"{summary}\n\n"
        "Great choices! Now let's finalize your trip.",
        parse_mode="Markdown"
    )

    # Delegate to next step
    await _start_days_selection(query.message, session)


async def _handle_days_selection(
    query, session: UserSession, data: str
) -> None:
    """
    Handle days selection button
    Save selection, then delegate to hotel input step.
    """
    if session.state != BotState.SELECTING_DAYS:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    num_days = int(data.split("_")[1])
    session.num_days = num_days

    await query.edit_message_text(
        f"✅ *Trip Duration:* {num_days} day{'s' if num_days > 1 else ''}\n\n"
        "One last thing...",
        parse_mode="Markdown"
    )

    # Delegate to next step
    await _start_hotel_input(query.message, session)

    logger.info(f"Chat {query.message.chat_id} selected {num_days} days")


async def _handle_hotel_confirmation(
    query, session: UserSession, data: str
) -> None:
    """
    Handle hotel confirmation buttons (htl_yes / htl_no).

    - htl_yes: Confirm hotel and move to GENERATING state (Phase 4 placeholder)
    - htl_no: Reset to WAITING_FOR_HOTEL and ask again
    """
    if session.state != BotState.CONFIRMING_HOTEL:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    if data == "htl_yes":
        session.state = BotState.GENERATING
        save_session(session)

        act_count = len(session.selected_activities)
        rest_count = len(session.selected_eateries)
        hotel_name = session.hotel.name if session.hotel else "Unknown"
        hotel_area = session.hotel.area if session.hotel else "Unknown"

        await query.edit_message_text(
            f"✅ *Hotel Confirmed!*\n"
            f"🏨 {hotel_name} ({hotel_area})\n\n"
            f"*Your Trip Summary:*\n"
            f"• 📅 Duration: {session.num_days} days\n"
            f"• 🎯 Activities: {act_count} selected\n"
            f"• 🍽️ Eateries: {rest_count} selected\n"
            f"• 🏨 Hotel: {hotel_name}",
            parse_mode="Markdown"
        )

        logger.info(
            f"Hotel confirmed: {hotel_name}. Starting itinerary generation."
        )

        # Delegate to itinerary generation
        await _start_itinerary_generation(query.message, session)

    else:
        session.hotel = None
        session.state = BotState.WAITING_FOR_HOTEL
        save_session(session)

        await query.edit_message_text(
            "No problem! Let's try again.\n\n"
            f"🏨 *Where are you staying in {PLACE}?*\n\n"
            "Please type your hotel name or address.",
            parse_mode="Markdown"
        )

        logger.info("User rejected hotel - asking again")


async def _handle_itinerary_action(
    query, session: UserSession, data: str
) -> None:
    """
    Handle itinerary action buttons (itin_regen / itin_ok).

    - itin_regen: Regenerate the itinerary
    - itin_ok: Accept and complete the flow
    """
    if session.state != BotState.REVIEWING_ITINERARY:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    if data == "itin_regen":
        await query.edit_message_text(
            "🔄 *Regenerating your itinerary...*\n\n"
            "_Creating a fresh plan for your trip..._",
            parse_mode="Markdown"
        )

        logger.info("User requested itinerary regeneration")

        await _start_itinerary_generation(query.message, session)

    else:
        session.state = BotState.IDLE
        save_session(session)

        await query.edit_message_text(
            "🎉 *Perfect! Your itinerary is saved.*\n\n"
            f"Have a wonderful trip to {PLACE}! 🏝️\n\n"
            "💡 *Tips:*\n"
            "• Screenshot or copy the itinerary above\n"
            "• Use /plan anytime to create a new trip\n"
            "• Use /help if you need assistance\n\n"
            "_Safe travels! 👋_",
            parse_mode="Markdown"
        )

        logger.info("User accepted itinerary - flow complete")


def _build_selection_summary(
    items: list[Activity], selected_ids: list[str]
) -> tuple[int, str]:
    """Build selection summary for display."""
    selected_names = [item.name for item in items if item.id in selected_ids]
    summary = ", ".join(selected_names) if selected_names else "None"
    return len(selected_ids), summary


def _escape_markdown(text: str) -> str:
    """Escape special Markdown characters."""
    # Characters that need escaping in Telegram Markdown
    special_chars = [
        '_', '*', '[', ']', '(', ')',
        '~', '`', '>', '#', '+', '-',
        '=', '|', '{', '}', '.', '!'
    ]
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def _format_reco_message(items: list, item_type: str) -> str:
    """Format the header message for activities or eateries."""
    if item_type == "activities":
        header = f"🎉 *Kid-Friendly Activities in {PLACE}* 🎉\n\n"
        header += f"Found {len(items)} activities! Tap to select:\n\n"

        for i, act in enumerate(items, start=1):
            header += (
                f"*{i}. {_escape_markdown(act.name)}*\n"
                f"📍 {_escape_markdown(act.location)} | 📅 {_escape_markdown(act.date_time)}\n"  # Noqa E501
                f"_{_escape_markdown(act.description)}_\n"
                f"🔗 {act.url}\n\n"
            )

        header += "👆 *Select activities above, then tap 'Done'*"
    else:
        header = f"🍽️ *Halal Dining/Cafe Options in {PLACE}* 🍽️\n\n"
        header += f"Found {len(items)} eateries! Tap to select:\n\n"

        for i, rest in enumerate(items, start=1):
            header += (
                f"*{i}. {_escape_markdown(rest.name)}*\n"
                f"📍 {_escape_markdown(rest.location)} | 🍴 {_escape_markdown(rest.cuisine)}\n"  # Noqa E501
                f"_{_escape_markdown(rest.description)}_\n"
                f"🔗 {rest.url}\n\n"
            )

        header += "👆 *Select eateries above, then tap 'Done'*"

    return header


async def _send_itinerary(message: Message, itinerary: str) -> None:
    """
    Send itinerary to chat, chunking if necessary.
    The last chunk includes the action keyboard.
    """
    keyboard = build_itinerary_keyboard()

    if len(itinerary) <= TELEGRAM_MAX_LEN - 100:
        # Send as single message with keyboard
        await message.reply_text(
            itinerary,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        # Split into chunks
        chunks = _split_into_chunks(itinerary)

        # Send all but the last chunk without keyboard
        for i, chunk in enumerate(chunks[:-1]):
            await message.reply_text(
                chunk,
                disable_web_page_preview=True
            )
            logger.info(f"Sent itinerary chunk {i+1}/{len(chunks)}")

        # Send last chunk with keyboard
        await message.reply_text(
            chunks[-1],
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        logger.info(f"Sent final itinerary chunk {len(chunks)}/{len(chunks)}")


def _split_into_chunks(text: str, max_len: int = CHUNK_LEN) -> list[str]:
    """
    Split text into chunks not exceeding max_len,
    preferably at paragraph breaks.
    """
    if len(text) <= max_len:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for p in paragraphs:
        candidate = (current + "\n\n" + p).strip() if current else p
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)

            if len(p) > max_len:
                wrapped = textwrap.wrap(
                    p,
                    width=max_len,
                    replace_whitespace=False,
                    drop_whitespace=False
                )
                chunks.extend(wrapped[:-1])
                current = wrapped[-1] if wrapped else ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


async def error_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Log errors."""
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
