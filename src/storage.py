"""
In-memory session storage for Bintan Trip Planner Bot.

Note: Data is lost on bot restart. This is fine for MVP.
Upgrade to Redis/SQLite for production persistence.
"""

from models import UserSession, BotState


_sessions: dict[int, UserSession] = {}


def get_session(chat_id: int) -> UserSession:
    """
    Get or create a session for the given chat ID.

    Args:
        chat_id: Telegram chat ID

    Returns:
        UserSession for this chat
    """
    if chat_id not in _sessions:
        _sessions[chat_id] = UserSession(chat_id=chat_id)
    return _sessions[chat_id]


def save_session(session: UserSession) -> None:
    """
    Save a session back to storage.

    Args:
        session: UserSession to save
    """
    _sessions[session.chat_id] = session


def clear_session(chat_id: int) -> None:
    """
    Delete a session (e.g., when user starts over with /plan).

    Args:
        chat_id: Telegram chat ID to clear
    """
    if chat_id in _sessions:
        del _sessions[chat_id]


def get_all_sessions() -> dict[int, UserSession]:
    """
    Get all active sessions (for debugging).

    Returns:
        Dict of chat_id -> UserSession
    """
    return _sessions.copy()
