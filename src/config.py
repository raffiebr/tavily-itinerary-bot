"""
Configuration settings
"""

import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PLACE = "Bintan"
START_DATE = "17 December 2025"
END_DATE = "20 December 2025"

# === Search Settings ===
MAX_SEARCH_RESULTS = 15   # Max results to fetch from Tavily
DEFAULT_SELECTION_COUNT = 3

# === LLM Settings ===
LLM_MODEL = "qwen3:8b"

# === Telegram Limits ===
TELEGRAM_MAX_LEN = 4096
CHUNK_LEN = 3500  # Stay safely below the Telegram hard limit

# === User Preferences ===
PREFERENCES = [
    "outdoor activities",
    "low-cost or free",
    "suitable for young children (5-8 years old)",
    "family-friendly"
]

def get_activity_recommendation_count(num_days: int) -> int:
    """
    Calculate number of activity recommendations based on trip length.
    
    Logic:
    - Need ~1 activity per day (morning slot)
    - Provide ~2x options for voting/choice variety
    - Cap at reasonable limits
    
    Args:
        num_days: Number of days in the trip (1-5)
    
    Returns:
        Number of activities to recommend
    """
    if num_days <= 2:
        return num_days * 2 + 2
    else:
        return min(num_days * 2, 10)


def get_food_recommendation_count(num_days: int) -> int:
    """
    Calculate number of food/eatery recommendations based on trip length.
    
    Logic:
    - Need lunch + dinner per day = 2 meals/day
    - Add buffer for variety
    - Cap at 10 for manageability
    
    Args:
        num_days: Number of days in the trip (1-5)
    
    Returns:
        Number of eateries to recommend
    """
    meals_needed = num_days * 2  # lunch + dinner
    return min(meals_needed + 2, 10)


def get_default_selection_count(num_days: int, selection_type: str = "activity") -> int:
    """
    Get default selection count based on trip length.
    
    Used when user makes no selections - auto-pick reasonable number.
    
    Args:
        num_days: Number of days in the trip
        selection_type: "activity" or "food"
    
    Returns:
        Number of items to auto-select as defaults
    """
    if selection_type == "activity":
        return max(2, min(num_days, 4))
    else:
        return max(3, min(num_days * 2, 6))