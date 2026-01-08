"""
Trip Planner Bot - Entry Point and Handlers.

A Telegram bot that helps families plan kid-friendly getaways.
Uses Tavily for web search and Ollama/Qwen3 for LLM processing.
"""

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
from telegram.error import TelegramError

from config import (
    TELEGRAM_BOT_TOKEN,
    PLACE,
    START_DATE,
    END_DATE,
    TELEGRAM_MAX_LEN,
    CHUNK_LEN,
    get_activity_recommendation_count,
    get_food_recommendation_count
)
from models import Activity, BotState, UserSession
from storage import get_session, save_session, clear_session
from services import (
    search_activities,
    search_food,
    parse_hotel,
    generate_itinerary,
    apply_default_selections,
    get_prioritized_selections,
    TavilySearchError,
    LLMError
)
from keyboards import (
    build_activity_keyboard,
    build_food_keyboard,
    build_days_keyboard,
    build_confirm_keyboard,
    build_itinerary_keyboard
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# === Command Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command - Welcome message.
    """
    user_name = update.effective_user.first_name or "there"
    logger.info(
        f"/start from user {update.effective_user.id} "
        f"in chat {update.effective_chat.id}"
    )

    await update.message.reply_text(
        f"👋 Welcome {user_name} to {PLACE} Trip Planner!\n\n"
        f"I help families plan kid-friendly {PLACE} getaways.\n\n"
        "🤖 Powered by Qwen LLM and Tavily API.\n\n"
        "🔹 /plan - Start planning your trip\n"
        "🔹 /help - See all commands\n\n"
        "Ready? Tap /plan to begin!"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command - Show available commands.
    """
    logger.info(
        f"/help from user {update.effective_user.id} "
        f"in chat {update.effective_chat.id}"
    )

    await update.message.reply_text(
        f"📖 *{PLACE} Trip Planner - Help*\n\n"
        "*Commands:*\n"
        "/start - Welcome message\n"
        "/plan - Start or restart trip planning\n"
        "/help - Show this help message\n\n"
        "*How it works:*\n"
        "1️⃣ Tell me your hotel\n"
        "2️⃣ Pick number of days\n"
        "3️⃣ I'll show activities & eateries tailored to your trip length\n"
        "4️⃣ Tap ✅ to vote for what interests you\n"
        "5️⃣ In groups, everyone can vote!\n"
        "6️⃣ Get your personalized itinerary!\n\n"
        "💡 Tip: Use /plan anytime to start over.",
        parse_mode="Markdown"
    )


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /plan command - Start or restart trip planning.
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    logger.info(
        f"/plan from user {user_id} in chat {chat_id} - "
        "clearing session and starting fresh"
    )

    # Clear and create new session
    clear_session(chat_id)
    session = get_session(chat_id)
    session.start_date = START_DATE
    session.end_date = END_DATE
    save_session(session)

    await update.message.reply_text(
        f"🗓️ Planning your {PLACE} trip ({START_DATE} - {END_DATE})...\n\n"
        "Let's start with some basics!"
    )

    await _start_hotel_input(update.message, session)


# === Callback Handler ===

async def handle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline buttons (callback queries).

    Callback data format:
    - htl_yes / htl_no - Hotel confirmation
    - days_N - Select N days
    - sel_act_001 / des_act_001 - Select/deselect activity
    - sel_fod_001 / des_fod_001 - Select/deselect food
    - done_act / done_fod - Done selecting
    - itin_regen / itin_ok - Itinerary actions
    """
    query = update.callback_query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data
    session = get_session(chat_id)

    logger.info(
        f"Callback '{data}' from user {user_id} in chat {chat_id} "
        f"(state: {session.state.value})"
    )

    try:
        # Route to appropriate handlers
        if data in ("htl_yes", "htl_no"):
            await _handle_hotel_confirmation(query, session, data)
        elif data.startswith("days_"):
            await _handle_days_selection(query, session, data)
        elif data.startswith("sel_act_") or data.startswith("des_act_"):
            await _handle_selection(query, session, data, "activity", user_id)
        elif data.startswith("sel_fod_") or data.startswith("des_fod_"):
            await _handle_selection(query, session, data, "food", user_id)
        elif data == "done_act":
            await _handle_done_activities(query, session, user_id)
        elif data == "done_fod":
            await _handle_done_food(query, session, user_id)
        elif data in ("itin_regen", "itin_ok"):
            await _handle_itinerary_action(query, session, data)
        else:
            logger.warning(f"Unknown callback data: {data}")
            await query.answer("Unknown action", show_alert=True)

        save_session(session)

    except TelegramError as e:
        logger.error(f"Telegram error handling callback: {e}")
        await query.answer("Something went wrong. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error handling callback {data}: {e}")
        await query.answer("An error occurred. Please try /plan to restart.")


# === Text Message Handler ===

async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle text messages (non-commands).

    Used primarily for:
    - Hotel name input (when in WAITING_FOR_HOTEL state)
    - Guidance messages for other states
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    session = get_session(chat_id)

    logger.info(
        f"Text from user {user_id} in chat {chat_id}: "
        f"'{text[:40]}...' (state: {session.state.value})"
    )

    if session.state == BotState.WAITING_FOR_HOTEL:
        await _handle_hotel_input(update, session, text)

    elif session.state == BotState.IDLE:
        await update.message.reply_text(
            "👋 Hi! Use /plan to start planning your trip, "
            "or /help to see available commands."
        )

    elif session.state == BotState.CONFIRMING_HOTEL:
        await update.message.reply_text(
            "👆 Please use the buttons above to confirm your hotel,\n"
            "or tap 'No' to re-enter."
        )

    elif session.state == BotState.SELECTING_DAYS:
        await update.message.reply_text(
            "👆 Please use the buttons above to select the number of days."
        )

    elif session.state in (
        BotState.SELECTING_ACTIVITIES, BotState.SELECTING_FOOD
    ):
        await update.message.reply_text(
            "👆 Please use the buttons above to make selections.\n"
            "Tap ✅ to select, then tap 'Done' when finished."
        )

    elif session.state == BotState.REVIEWING_ITINERARY:
        await update.message.reply_text(
            "👆 Please use the buttons above to accept or regenerate\n"
            "your itinerary."
        )

    elif session.state == BotState.GENERATING:
        await update.message.reply_text(
            "⏳ Please wait - I'm generating your itinerary..."
        )

    else:
        await update.message.reply_text(
            "🤔 I wasn't expecting text input right now.\n\n"
            "Use /plan to start over or /help for guidance."
        )

    save_session(session)


async def _handle_hotel_input(
    update: Update, session: UserSession, text: str
) -> None:
    """Handle hotel name text input."""
    await update.message.reply_text("🔍 Looking up your hotel...")

    try:
        hotel_info = parse_hotel(text)
        session.hotel = hotel_info
        session.state = BotState.CONFIRMING_HOTEL
        save_session(session)

        # Build confidence text
        if hotel_info.confidence == "high":
            confidence_text = ""
        elif hotel_info.confidence == "medium":
            confidence_text = "\n_(I'm fairly confident about this)_"
        else:
            confidence_text = "\n_(I'm not entirely sure - please verify)_"

        keyboard = build_confirm_keyboard()
        await update.message.reply_text(
            f"🔍 Got it! I found:\n\n"
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

    except LLMError as e:
        logger.error(f"LLM error parsing hotel: {e}")
        await update.message.reply_text(
            "❌ I had trouble understanding that hotel.\n"
            "The AI service may be temporarily unavailable.\n\n"
            "Please try typing the hotel name again, or use /plan to restart."
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing hotel: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong.\n"
            "Please try typing the hotel name again."
        )


# === Step Starters ===

async def _start_hotel_input(
    message: Message, session: UserSession
) -> None:
    """
    Prompt user for hotel name.
    This is the FIRST step in theflow.
    """
    session.state = BotState.WAITING_FOR_HOTEL
    save_session(session)

    await message.reply_text(
        f"🏨 *Where are you staying in {PLACE}?*\n\n"
        "Please type your hotel name or address.\n"
        "_(e.g., \"Bintan Lagoon Resort\" or \"Four Points by Sheraton\")_",
        parse_mode="Markdown"
    )

    logger.info(f"Started hotel input for chat {session.chat_id}")


async def _start_days_selection(
    message: Message, session: UserSession
) -> None:
    """
    Prompt user to select number of days.

    This is the SECOND step, after hotel confirmation.
    """
    session.state = BotState.SELECTING_DAYS
    save_session(session)

    keyboard = build_days_keyboard()
    await message.reply_text(
        f"📅 *How many days in {PLACE}?*\n\n"
        "Select the number of days for your itinerary:\n"
        "_(This will determine how many activities and eateries I recommend)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    logger.info(f"Started days selection for chat {session.chat_id}")


async def _start_activity_selection(
    message: Message, session: UserSession
) -> None:
    """
    Search for activities and display selection keyboard.

    This is the THIRD step, after days selection.
    Uses dynamic count based on num_days.
    """
    # Calculate dynamic recommendation count
    activity_count = get_activity_recommendation_count(session.num_days)

    await message.reply_text(
        f"🔎 Searching for kid-friendly activities...\n"
        f"_(Looking for {activity_count} options based on "
        f"your {session.num_days}-day trip)_"
    )

    try:
        activities = search_activities(max_results=activity_count)
    except TavilySearchError as e:
        logger.error(f"Tavily error: {e}")
        await message.reply_text(
            "❌ Sorry, I couldn't search for activities right now.\n"
            "The search service may be temporarily unavailable.\n\n"
            "Please try again with /plan in a few moments."
        )
        return
    except LLMError as e:
        logger.error(f"LLM error processing activities: {e}")
        await message.reply_text(
            "❌ Sorry, I had trouble processing the search results.\n"
            "The AI service may be temporarily unavailable.\n\n"
            "Please try again with /plan in a few moments."
        )
        return
    except Exception as e:
        logger.error(f"Unexpected error in activity search: {e}")
        await message.reply_text(
            "❌ An unexpected error occurred.\n"
            "Please try again with /plan."
        )
        return

    if not activities:
        await message.reply_text(
            f"😕 I couldn't find any activities in {PLACE}.\n"
            "This might be a temporary issue.\n\n"
            "Please try /plan again in a few moments."
        )
        return

    # Update session
    session.activities = activities
    session.state = BotState.SELECTING_ACTIVITIES
    save_session(session)

    # Format message and keyboard (user_id 0 for initial display)
    activities_text = _format_reco_message(
        activities, "activities", session.num_days
    )
    keyboard = build_activity_keyboard(activities, session, 0)

    try:
        await message.reply_text(
            activities_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except TelegramError as e:
        logger.error(f"Telegram error sending activities: {e}")
        await message.reply_text(
            "❌ Sorry, I couldn't display the activities.\n"
            "Please try /plan again."
        )
        return

    logger.info(
        f"Started activity selection with {len(activities)} activities "
        f"(based on {session.num_days}-day trip)"
    )


async def _start_food_selection(
    message: Message, session: UserSession
) -> None:
    """
    Search for eateries and display selection keyboard.

    This is the FOURTH step, after activity selection.
    Uses dynamic count based on num_days.
    """
    # Calculate dynamic recommendation count
    food_count = get_food_recommendation_count(session.num_days)

    await message.reply_text(
        f"🔎 Now searching for eateries...\n"
        f"_(Looking for {food_count} options for your "
        f"{session.num_days} days of meals)_"
    )

    try:
        eateries = search_food(max_results=food_count)
    except TavilySearchError as e:
        logger.error(f"Tavily error: {e}")
        await message.reply_text(
            "❌ Sorry, I couldn't search for eateries right now.\n"
            "The search service may be temporarily unavailable.\n\n"
            "Please try again with /plan in a few moments."
        )
        return
    except LLMError as e:
        logger.error(f"LLM error processing food: {e}")
        await message.reply_text(
            "❌ Sorry, I had trouble processing the search results.\n"
            "The AI service may be temporarily unavailable.\n\n"
            "Please try again with /plan in a few moments."
        )
        return
    except Exception as e:
        logger.error(f"Unexpected error in food search: {e}")
        await message.reply_text(
            "❌ An unexpected error occurred.\n"
            "Please try again with /plan."
        )
        return

    if not eateries:
        await message.reply_text(
            f"😕 I couldn't find any eateries in {PLACE}.\n"
            "This might be a temporary issue.\n\n"
            "Please try /plan again in a few moments."
        )
        return

    # Update session
    session.eateries = eateries
    session.state = BotState.SELECTING_FOOD
    save_session(session)

    # Format message and keyboard
    food_text = _format_reco_message(eateries, "eateries", session.num_days)
    keyboard = build_food_keyboard(eateries, session, 0)

    try:
        await message.reply_text(
            food_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except TelegramError as e:
        logger.error(f"Telegram error sending eateries: {e}")
        await message.reply_text(
            "❌ Sorry, I couldn't display the eateries.\n"
            "Please try /plan again."
        )
        return

    logger.info(
        f"Started food selection with {len(eateries)} eateries "
        f"(based on {session.num_days}-day trip)"
    )


async def _start_itinerary_generation(
    message: Message, session: UserSession
) -> None:
    """
    Generate itinerary and display with review keyboard.

    This is the FIFTH/FINAL step, after food selection.
    """
    session.state = BotState.GENERATING
    save_session(session)

    # Get counts for status message
    act_count = session.get_total_activity_votes()
    eat_count = session.get_total_eatery_votes()
    hotel_area = session.hotel.area if session.hotel else "Unknown"

    status_msg = await message.reply_text(
        "⏳ *Generating your personalized itinerary...*\n\n"
        "I'm considering:\n"
        f"• {act_count} activities selected\n"
        f"• {eat_count} eateries selected\n"
        f"• Your hotel location ({hotel_area})\n"
        "• Travel times between locations\n\n"
        "_This may take a moment. LLM is thinking..._",
        parse_mode="Markdown"
    )

    try:
        # Get selections prioritized by vote count
        selected_activities = get_prioritized_selections(session, "activity")
        selected_eateries = get_prioritized_selections(session, "food")

        # Build vote count dicts for LLM context
        activity_votes = {
            act.name: session.get_activity_vote_count(act.id)
            for act in selected_activities
        }
        eatery_votes = {
            eat.name: session.get_eatery_vote_count(eat.id)
            for eat in selected_eateries
        }

        logger.info(
            f"Generating itinerary with {len(selected_activities)} activities "
            f"and {len(selected_eateries)} eateries"
        )

        itinerary = generate_itinerary(
            selected_activities=selected_activities,
            selected_eateries=selected_eateries,
            hotel_name=session.hotel.name if session.hotel else "Hotel",
            hotel_area=session.hotel.area if session.hotel else "Unknown",
            num_days=session.num_days,
            activity_votes=activity_votes,
            eatery_votes=eatery_votes
        )

        session.current_itinerary = itinerary
        session.state = BotState.REVIEWING_ITINERARY
        save_session(session)

        # Delete status message
        try:
            await status_msg.delete()
        except TelegramError:
            pass  # Ignore if can't delete

        # Send itinerary (with chunking if needed)
        await _send_itinerary(message, itinerary)

        logger.info("Itinerary generated and sent successfully")

    except LLMError as e:
        logger.error(f"LLM error generating itinerary: {e}")
        session.state = BotState.SELECTING_FOOD
        save_session(session)

        await message.reply_text(
            "❌ Sorry, I had trouble generating your itinerary.\n"
            "The AI service may be temporarily unavailable.\n\n"
            "Please try selecting eateries again or use /plan to start over."
        )
    except Exception as e:
        logger.error(f"Unexpected error generating itinerary: {e}")
        session.state = BotState.SELECTING_FOOD
        save_session(session)

        await message.reply_text(
            "❌ An unexpected error occurred "
            "while generating your itinerary.\n\n"
            "Please try again or use /plan to start over."
        )


# === Callback Handlers ===

async def _handle_hotel_confirmation(
    query, session: UserSession, data: str
) -> None:
    """
    Handle hotel confirmation buttons (htl_yes / htl_no).

    After hotel confirmed, goes to DAYS selection
    """
    if session.state != BotState.CONFIRMING_HOTEL:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    if data == "htl_yes":
        hotel_name = session.hotel.name if session.hotel else "Unknown"
        hotel_area = session.hotel.area if session.hotel else "Unknown"

        await query.edit_message_text(
            f"✅ *Hotel Confirmed!*\n"
            f"🏨 {hotel_name} ({hotel_area})\n\n"
            "Great! Now let's figure out your trip duration...",
            parse_mode="Markdown"
        )

        logger.info(
            f"Hotel confirmed: {hotel_name}. Moving to days selection."
        )

        await _start_days_selection(query.message, session)

    else:
        # Reset to hotel input
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


async def _handle_days_selection(
    query, session: UserSession, data: str
) -> None:
    """
    Handle days selection button.

    After days selected, goes to ACTIVITY search.
    """
    if session.state != BotState.SELECTING_DAYS:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    num_days = int(data.split("_")[1])
    session.num_days = num_days
    save_session(session)

    # Calculate what they'll see
    activity_count = get_activity_recommendation_count(num_days)
    food_count = get_food_recommendation_count(num_days)

    await query.edit_message_text(
        f"✅ *Trip Duration:* {num_days} day{'s' if num_days > 1 else ''}\n\n"
        f"Perfect! I'll show you:\n"
        f"• ~{activity_count} activities to choose from\n"
        f"• ~{food_count} eateries for your meals\n\n"
        "Let's find some fun activities!",
        parse_mode="Markdown"
    )

    logger.info(
        f"Chat {session.chat_id} selected {num_days} days. "
        f"Will show {activity_count} activities, {food_count} eateries."
    )

    await _start_activity_selection(query.message, session)


async def _handle_selection(
    query, session: UserSession, data: str, selection_type: str, user_id: int
) -> None:
    """
    Handle select/deselect toggle for activities or food.

    Tracks which user made the selection for group chat support.
    """
    if selection_type == "activity":
        expected_state = BotState.SELECTING_ACTIVITIES
        items = session.activities
        keyboard_builder = build_activity_keyboard
        header_type = "activities"
    else:
        expected_state = BotState.SELECTING_FOOD
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

    # Toggle vote
    if action == "sel":
        if selection_type == "activity":
            session.add_activity_vote(item_id, user_id)
        else:
            session.add_eatery_vote(item_id, user_id)
        await query.answer("✅ Vote added!")
    else:
        if selection_type == "activity":
            session.remove_activity_vote(item_id, user_id)
        else:
            session.remove_eatery_vote(item_id, user_id)
        await query.answer("Vote removed")

    # Update message in-place with new vote counts
    text = _format_reco_message(items, header_type, session.num_days)
    keyboard = keyboard_builder(items, session, user_id)

    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except TelegramError as e:
        # Message might not have changed (same content)
        if "message is not modified" not in str(e).lower():
            logger.error(f"Error updating selection message: {e}")


async def _handle_done_activities(
    query, session: UserSession, user_id: int
) -> None:
    """
    Handle 'Done Selecting Activities' button.

    Applies default selections if none were made.
    Shows summary, then moves to FOOD selection.
    """
    if session.state != BotState.SELECTING_ACTIVITIES:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    # Check if defaults needed
    defaults_applied = False
    default_names = []

    if not session.selected_activities:
        count, default_names = apply_default_selections(session, "activity")
        if count > 0:
            defaults_applied = True
            logger.info(f"Applied {count} default activity selections")

    # Build summary with vote counts
    summary = _build_selection_summary_with_votes(
        session.activities,
        session
    )

    if defaults_applied:
        summary_text = (
            f"ℹ️ *No activities selected!*\n"
            f"I've picked {len(default_names)} popular options for you:\n"
            f"{', '.join(default_names)}\n\n"
        )
    else:
        summary_text = f"✅ *Activities Selected:*\n{summary}\n\n"

    await query.edit_message_text(
        summary_text + "Now let's pick some places to eat!",
        parse_mode="Markdown"
    )

    # Delegate to food selection
    await _start_food_selection(query.message, session)


async def _handle_done_food(
    query, session: UserSession, user_id: int
) -> None:
    """
    Handle 'Done Selecting Eateries' button.

    After food selection, goes DIRECTLY to itinerary generation
    (hotel and days were already collected).
    """
    if session.state != BotState.SELECTING_FOOD:
        await query.answer("Please use /plan to start over.", show_alert=True)
        return
    await query.answer()

    # Check if defaults needed
    defaults_applied = False
    default_names = []

    if not session.selected_eateries:
        count, default_names = apply_default_selections(session, "food")
        if count > 0:
            defaults_applied = True
            logger.info(f"Applied {count} default eatery selections")

    # Build summary with vote counts
    summary = _build_selection_summary_with_votes(
        session.eateries,
        session,
        selection_type="food"
    )

    if defaults_applied:
        summary_text = (
            f"ℹ️ *No eateries selected!*\n"
            f"I've picked {len(default_names)} popular options for you:\n"
            f"{', '.join(default_names)}\n\n"
        )
    else:
        summary_text = f"✅ *Eateries Selected:*\n{summary}\n\n"

    # Build final summary before generation
    hotel_name = session.hotel.name if session.hotel else "Unknown"
    act_count = session.get_total_activity_votes()
    eat_count = session.get_total_eatery_votes()

    await query.edit_message_text(
        summary_text +
        f"*Your Trip Summary:*\n"
        f"• 📅 Duration: {session.num_days} days\n"
        f"• 🏨 Hotel: {hotel_name}\n"
        f"• 🎯 Activities: {act_count} selected\n"
        f"• 🍽️ Eateries: {eat_count} selected\n\n"
        "Now generating your personalized itinerary!",
        parse_mode="Markdown"
    )

    await _start_itinerary_generation(query.message, session)


async def _handle_itinerary_action(
    query, session: UserSession, data: str
) -> None:
    """
    Handle itinerary action buttons (itin_regen / itin_ok).
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

    else:  # itin_ok
        session.state = BotState.IDLE
        save_session(session)

        # Remove buttons from message
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass

        await query.message.reply_text(
            "🎉 *Perfect! Your itinerary is ready.*\n\n"
            f"Have a wonderful trip to {PLACE}! 🏝️\n\n"
            "💡 *Tips:*\n"
            "• Screenshot or copy the itinerary above\n"
            "• Use /plan anytime to create a new trip\n"
            "• Use /help if you need assistance\n\n"
            "_Safe travels! 👋_",
            parse_mode="Markdown"
        )

        logger.info("User accepted itinerary - flow complete")


# === Helper Functions ===

def _build_selection_summary_with_votes(
    items: list[Activity],
    session: UserSession,
    selection_type: str = "activity"
) -> str:
    """
    Build selection summary with vote counts for display.
    """
    if selection_type == "activity":
        votes_by_id = session.get_activities_by_votes()
    else:
        votes_by_id = session.get_eateries_by_votes()

    if not votes_by_id:
        return "None"

    # Create lookup
    items_by_id = {item.id: item for item in items}

    # Build summary lines
    lines = []
    for item_id, vote_count in votes_by_id:
        if item_id in items_by_id:
            name = items_by_id[item_id].name
            if vote_count > 1:
                lines.append(f"• {name} ({vote_count} votes)")
            else:
                lines.append(f"• {name}")

    return "\n".join(lines) if lines else "None"


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _format_reco_message(
    items: list, item_type: str, num_days: int = 0
) -> str:
    """
    Format the header message for activities or eateries.
    """
    days_text = f" (for your {num_days}-day trip)" if num_days > 0 else ""

    if item_type == "activities":
        header = f"🎉 <b>Kid-Friendly Activities in {PLACE}</b> 🎉\n\n"
        header += f"Found {len(items)} activities{days_text}! Tap to vote:\n\n"

        for i, act in enumerate(items, start=1):
            header += (
                f"<b>{i}. {_escape_html(act.name)}</b>\n"
                f"📍 {_escape_html(act.location)} | "
                f"📅 {_escape_html(act.date_time)}\n"
                f"<i>{_escape_html(act.description)}</i>\n"
                f"🔗 {act.url}\n\n"
            )

        header += (
            "👆 <b>Select activities above, then tap 'Done'</b>\n"
            "💡 <i>In group chats, everyone can vote!</i>"
        )
    else:
        header = f"🍽️ <b>Halal Dining/Cafe Options in {PLACE}</b> 🍽️\n\n"
        header += f"Found {len(items)} eateries{days_text}! Tap to vote:\n\n"

        for i, rest in enumerate(items, start=1):
            header += (
                f"<b>{i}. {_escape_html(rest.name)}</b>\n"
                f"📍 {_escape_html(rest.location)} | "
                f"🍴 {_escape_html(rest.cuisine)}\n"
                f"<i>{_escape_html(rest.description)}</i>\n"
                f"🔗 {rest.url}\n\n"
            )

        header += (
            "👆 <b>Select eateries above, then tap 'Done'</b>\n"
            "💡 <i>In group chats, everyone can vote!</i>"
        )

    return header


async def _send_itinerary(message: Message, itinerary: str) -> None:
    """
    Send itinerary to chat, chunking if necessary.
    """
    keyboard = build_itinerary_keyboard()

    if len(itinerary) <= TELEGRAM_MAX_LEN - 100:
        # Single message with keyboard
        await message.reply_text(
            itinerary,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        # Split into chunks
        chunks = _split_into_chunks(itinerary)

        # Send all but last without keyboard
        for i, chunk in enumerate(chunks[:-1]):
            await message.reply_text(
                chunk,
                disable_web_page_preview=True
            )
            logger.info(f"Sent itinerary chunk {i+1}/{len(chunks)}")

        # Last chunk with keyboard
        await message.reply_text(
            chunks[-1],
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        logger.info(f"Sent final itinerary chunk {len(chunks)}/{len(chunks)}")


def _split_into_chunks(text: str, max_len: int = CHUNK_LEN) -> list[str]:
    """
    Split text into chunks not exceeding max_len.
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


# === Error Handler ===

async def error_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Log errors and notify user if possible."""
    logger.error(f"Update {update} caused error: {context.error}")

    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "❌ An unexpected error occurred.\n"
                    "Please try /plan to restart, or /help for assistance."
                )
            )
        except TelegramError:
            pass


# === Main Entry Point ===

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set! "
            "Create a .env file with your bot token."
        )

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers (order matters!)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    # Register error handler
    app.add_error_handler(error_handler)

    # Start polling
    logger.info(f"🤖 {PLACE} Trip Planner Bot starting...")
    logger.info(f"📍 Destination: {PLACE}")
    logger.info(f"📅 Dates: {START_DATE} - {END_DATE}")
    logger.info("📋 Flow: Hotel → Days → Activities → Food → Generate")
    print(f"\n🤖 {PLACE} Trip Planner Bot is running!")
    print("📋 Flow: Hotel → Days → Activities → Food → Generate")
    print("Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
