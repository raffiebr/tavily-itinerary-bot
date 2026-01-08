"""
Inline keyboard builders for Trip Planner Bot.

Supports multi-user vote tracking with vote count display.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from models import Activity, UserSession


def build_activity_keyboard(
    activities: list[Activity],
    session: UserSession,
    current_user_id: int
) -> InlineKeyboardMarkup:
    """
    Build keyboard for activity selection with vote counts.

    Args:
        activities: List of Activity objects to display
        session: UserSession containing vote information
        current_user_id: ID of the user viewing the keyboard

    Returns:
        InlineKeyboardMarkup with toggle buttons showing vote counts
    """
    keyboard = []

    for act in activities:
        vote_count = session.get_activity_vote_count(act.id)
        user_voted = session.has_activity_vote(act.id, current_user_id)

        # Show checkmark if current user voted, box if not
        icon = "✅" if user_voted else "⬜"

        # Show vote count if more than 0
        if vote_count > 0:
            text = f"{icon} {act.name} ({vote_count})"
        else:
            text = f"{icon} {act.name}"

        # Truncate if too long (Telegram button text limit)
        if len(text) > 40:
            text = text[:37] + "..."

        # Callback: sel to add vote, des to remove vote
        prefix = "des" if user_voted else "sel"
        callback_data = f"{prefix}_act_{act.id}"

        keyboard.append([
            InlineKeyboardButton(text, callback_data=callback_data)
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➡️ Done Selecting Activities", callback_data="done_act"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


def build_food_keyboard(
    eateries: list[Activity],
    session: UserSession,
    current_user_id: int
) -> InlineKeyboardMarkup:
    """
    Build keyboard for food/restaurant selection with vote counts.

    Args:
        eateries: List of Activity objects (type="food") to display
        session: UserSession containing vote information
        current_user_id: ID of the user viewing the keyboard

    Returns:
        InlineKeyboardMarkup with toggle buttons showing vote counts
    """
    keyboard = []

    for eatery in eateries:
        vote_count = session.get_eatery_vote_count(eatery.id)
        user_voted = session.has_eatery_vote(eatery.id, current_user_id)

        icon = "✅" if user_voted else "⬜"

        if vote_count > 0:
            text = f"{icon} {eatery.name} ({vote_count})"
        else:
            text = f"{icon} {eatery.name}"

        if len(text) > 40:
            text = text[:37] + "..."

        prefix = "des" if user_voted else "sel"
        callback_data = f"{prefix}_fod_{eatery.id}"

        keyboard.append([
            InlineKeyboardButton(text, callback_data=callback_data)
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➡️ Done Selecting Eateries", callback_data="done_fod"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


def build_days_keyboard() -> InlineKeyboardMarkup:
    """
    Build keyboard for selecting number of trip days (1-5).

    Returns:
        InlineKeyboardMarkup with buttons for 1-5 days
    """
    buttons = [
        InlineKeyboardButton(
            f"{i} Day{'s' if i > 1 else ''}",
            callback_data=f"days_{i}"
        )
        for i in range(1, 6)
    ]

    return InlineKeyboardMarkup([buttons])


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Build Yes/No confirmation keyboard (used for hotel confirmation).

    Returns:
        InlineKeyboardMarkup with Yes and No buttons
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes", callback_data="htl_yes"),
        InlineKeyboardButton("❌ No, let me re-enter", callback_data="htl_no")
    ]])


def build_itinerary_keyboard() -> InlineKeyboardMarkup:
    """
    Build Regenerate/Accept keyboard for itinerary review.

    Returns:
        InlineKeyboardMarkup with Regenerate and Looks good buttons
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Regenerate", callback_data="itin_regen"),
        InlineKeyboardButton("✅ Looks good!", callback_data="itin_ok")
    ]])