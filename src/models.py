"""
Data models for Tavily Trip Planner Bot.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class BotState(Enum):
    """Machine states for the bot conversation flow."""
    IDLE = "idle"
    SELECTING_ACTIVITIES = "selecting_activities"
    SELECTING_FOOD = "selecting_food"
    SELECTING_DAYS = "selecting_days"
    WAITING_FOR_HOTEL = "waiting_for_hotel"
    CONFIRMING_HOTEL = "confirming_hotel"
    GENERATING = "generating"
    REVIEWING_ITINERARY = "reviewing_itinerary"


@dataclass
class HotelInfo:
    """Parsed hotel information from user input."""
    raw_input: str          # What user typed
    name: str               # Parsed hotel name
    area: str               # LLM-inferred area/neighborhood
    confidence: str         # high / medium / low


@dataclass
class Activity:
    """Activity or restaurant recommendation."""
    id: str                 # Unique ID for button callbacks
    name: str               # Name of the activity
    location: str           # Location description from search
    date_time: str          # Date/time info (or "Check website")
    description: str        # Brief description
    url: str                # Source URL
    activity_type: str      # "activity" | "food"
    cuisine: str = ""       # For food only


@dataclass
class UserSession:
    """User session state for the conversation flow."""
    chat_id: int
    state: BotState = BotState.IDLE

    # Recommendations sent to user
    activities: list[Activity] = field(default_factory=list)
    eateries: list[Activity] = field(default_factory=list)

    # User selections
    selected_activities: list[str] = field(default_factory=list)
    selected_eateries: list[str] = field(default_factory=list)
    # Hotel info
    hotel: Optional[HotelInfo] = None

    # Trip details
    num_days: int = 0
    start_date: str = ""
    end_date: str = ""

    # Generated itinerary
    current_itinerary: str = ""

    # Timestamps
    created_at: str = ""
    updated_at: str = ""
