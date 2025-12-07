"""
Configuration settings for Bintan Trip Planner Bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === API Keys (from .env) ===
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Trip Configuration (change these per trip) ===
PLACE = "Bintan"
START_DATE = "17 December 2025"
END_DATE = "20 December 2025"

# === User Preferences ===
PREFERENCES = [
    "outdoor activities",
    "low-cost or free",
    "suitable for young children (5-8 years old)",
    "family-friendly"
]

# === LLM Settings ===
LLM_MODEL = "qwen3:8b"

# === Telegram Limits ===
TELEGRAM_MAX_LEN = 4096
CHUNK_LEN = 3500  # Stay safely below the hard limit