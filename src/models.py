"""
Data models for Trip Planner Bot.

Supports multi-user selection tracking for group chats.
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
    """
    User session state for the conversation flow.

    Multi-user support:
    - selected_activities and selected_eateries are dicts
    - Key: item ID, Value: set of user IDs who voted for it
    - This allows tracking who selected what in group chats
    """
    chat_id: int
    state: BotState = BotState.IDLE

    # Recommendations sent to user
    activities: list[Activity] = field(default_factory=list)
    eateries: list[Activity] = field(default_factory=list)

    # User selections: {item_id: {user_id1, user_id2, ...}}
    selected_activities: dict[str, set[int]] = field(default_factory=dict)
    selected_eateries: dict[str, set[int]] = field(default_factory=dict)

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

    # --- Multi-user helper methods ---

    def add_activity_vote(self, item_id: str, user_id: int) -> None:
        """Add a user's vote for an activity."""
        if item_id not in self.selected_activities:
            self.selected_activities[item_id] = set()
        self.selected_activities[item_id].add(user_id)

    def remove_activity_vote(self, item_id: str, user_id: int) -> None:
        """Remove a user's vote for an activity."""
        if item_id in self.selected_activities:
            self.selected_activities[item_id].discard(user_id)
            # Clean up empty sets
            if not self.selected_activities[item_id]:
                del self.selected_activities[item_id]

    def has_activity_vote(self, item_id: str, user_id: int) -> bool:
        """Check if a user has voted for an activity."""
        return (
            item_id in self.selected_activities and
            user_id in self.selected_activities[item_id]
        )

    def get_activity_vote_count(self, item_id: str) -> int:
        """Get the number of votes for an activity."""
        return len(self.selected_activities.get(item_id, set()))

    def add_eatery_vote(self, item_id: str, user_id: int) -> None:
        """Add a user's vote for an eatery."""
        if item_id not in self.selected_eateries:
            self.selected_eateries[item_id] = set()
        self.selected_eateries[item_id].add(user_id)

    def remove_eatery_vote(self, item_id: str, user_id: int) -> None:
        """Remove a user's vote for an eatery."""
        if item_id in self.selected_eateries:
            self.selected_eateries[item_id].discard(user_id)
            if not self.selected_eateries[item_id]:
                del self.selected_eateries[item_id]

    def has_eatery_vote(self, item_id: str, user_id: int) -> bool:
        """Check if a user has voted for an eatery."""
        return (
            item_id in self.selected_eateries and
            user_id in self.selected_eateries[item_id]
        )

    def get_eatery_vote_count(self, item_id: str) -> int:
        """Get the number of votes for an eatery."""
        return len(self.selected_eateries.get(item_id, set()))

    def get_selected_activity_ids(self) -> list[str]:
        """Get list of activity IDs that have at least one vote."""
        return list(self.selected_activities.keys())

    def get_selected_eatery_ids(self) -> list[str]:
        """Get list of eatery IDs that have at least one vote."""
        return list(self.selected_eateries.keys())

    def get_activities_by_votes(self) -> list[tuple[str, int]]:
        """
        Get activities sorted by vote count (highest first).

        Returns:
            List of (item_id, vote_count) tuples, sorted descending by votes
        """
        return sorted(
            [(k, len(v)) for k, v in self.selected_activities.items()],
            key=lambda x: x[1],
            reverse=True
        )

    def get_eateries_by_votes(self) -> list[tuple[str, int]]:
        """
        Get eateries sorted by vote count (highest first).

        Returns:
            List of (item_id, vote_count) tuples, sorted descending by votes
        """
        return sorted(
            [(k, len(v)) for k, v in self.selected_eateries.items()],
            key=lambda x: x[1],
            reverse=True
        )

    def get_total_activity_votes(self) -> int:
        """Get total number of activity selections."""
        return len(self.selected_activities)

    def get_total_eatery_votes(self) -> int:
        """Get total number of eatery selections."""
        return len(self.selected_eateries)