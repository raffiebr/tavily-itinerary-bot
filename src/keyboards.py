"""
Inline keyboard builders for Trip Planner Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from models import Activity


def build_activity_keyboard(
    activities: list[Activity],
    selected_ids: list[str]
) -> InlineKeyboardMarkup:
    """
    Build keyboard for activity selection.

    Args:
        activities: List of Activity objects to display
        selected_ids: List of activity IDs that are currently selected

    Returns:
        InlineKeyboardMarkup with toggle buttons for each activity
    """
    keyboard = []

    for act in activities:
        is_selected = act.id in selected_ids

        icon = "✅" if is_selected else "⬜"
        text = f"{icon} {act.name}"

        prefix = "des" if is_selected else "sel"
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
    restaurants: list[Activity],
    selected_ids: list[str]
) -> InlineKeyboardMarkup:
    """
    Build keyboard for food/restaurant selection.

    Args:
        restaurants: List of Activity objects (type="food") to display
        selected_ids: List of restaurant IDs that are currently selected

    Returns:
        InlineKeyboardMarkup with toggle buttons for each restaurant
    """
    keyboard = []

    for rest in restaurants:
        is_selected = rest.id in selected_ids
        icon = "✅" if is_selected else "⬜"
        text = f"{icon} {rest.name}"

        prefix = "des" if is_selected else "sel"
        callback_data = f"{prefix}_fod_{rest.id}"

        keyboard.append([
            InlineKeyboardButton(text, callback_data=callback_data)
        ])

    keyboard.append([
        InlineKeyboardButton(
            "➡️ Done Selecting Restaurants", callback_data="done_fod"
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
