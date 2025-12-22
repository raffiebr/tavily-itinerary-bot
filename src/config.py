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
MAX_RECOMMENDATIONS = 10  # Max activities/restaurants to suggest

# === LLM Settings ===
LLM_MODEL = "qwen3:8b"

# === Telegram Limits ===
TELEGRAM_MAX_LEN = 4096
CHUNK_LEN = 3500  # Stay safely below the hard limit

# === User Preferences ===
PREFERENCES = [
    "outdoor activities",
    "low-cost or free",
    "suitable for young children (5-8 years old)",
    "family-friendly"
]
