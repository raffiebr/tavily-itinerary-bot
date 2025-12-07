# 🏝️ Trip Planner Bot

An interactive Telegram bot that helps families plan kid-friendly getaways. Built with Python, Tavily (web search), and Ollama/Qwen3 (local LLM).

## Features

- 🎯 **Interactive Planning** - Select activities and restaurants via inline buttons
- 🏨 **Smart Hotel Parsing** - Type your hotel name, LLM identifies location and area
- 🗓️ **Multi-day Itineraries** - Generate 1-5 day plans with realistic scheduling
- 👶 **Kid-friendly Focus** - Built-in nap time, relaxed pacing, family activities
- 🚐 **Transport Suggestions** - Includes travel times and transport options
- 🍽️ **Halal Dining** - Filters for halal-friendly restaurants

## How It Works

```
/plan → Select Activities → Select Food → Enter Hotel → Pick Days → Get Itinerary
```

1. User triggers `/plan` command
2. Bot searches for activities and food via Tavily
3. User selects preferences using ✅ buttons
4. User enters hotel name (LLM parses and confirms)
5. User picks number of days
6. LLM generates personalized itinerary with transport info

## Daily Schedule Template

| Time | Activity | Duration |
|------|----------|----------|
| 8:00 - 9:30 AM | Hotel breakfast | 1.5 hrs |
| 9:30 - 10:00 AM | Prepare / travel | 30 min |
| 10:00 AM - 1:00 PM | Morning activity | 3 hrs |
| 1:00 - 2:00 PM | Lunch (nearby) | 1 hr |
| 2:00 - 2:30 PM | Travel back | 30 min |
| 2:30 - 4:30 PM | Rest / Nap time | 2 hrs |
| 4:30 - 6:00 PM | Beach / Pool | 1.5 hrs |
| 6:00 - 7:00 PM | Freshen up | 1 hr |
| 7:30 PM onwards | Dinner | - |

## Setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed with `qwen3:8b` model
- Telegram bot token (from [@BotFather](https://t.me/botfather))
- [Tavily API key](https://tavily.com/)

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/trip-planner-bot.git
cd trip-planner-bot

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment variables
cp .env.example .env
```

### Environment Variables

Create a `.env` file:

```env
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNO...
TELEGRAM_CHAT_ID=-4902643452
```

### Pull the LLM Model

```bash
ollama pull qwen3:8b
```

### Run the Bot

```bash
python bot.py
```

## Configuration

To plan a trip to a different destination, edit `config.py`:

```python
# Change these for a new trip
PLACE = "Bintan"                    # → "Bali", "Phuket", etc.
START_DATE = "17 December 2025"
END_DATE = "20 December 2025"

PREFERENCES = [
    "outdoor activities",
    "low-cost or free",
    "suitable for young children (5-8 years old)",
    "family-friendly"
]
```

No other changes needed - the LLM handles geography automatically!

## Project Structure

```
trip-planner-bot/
├── bot.py              # Entry point + all handlers
├── config.py           # Settings & env vars
├── models.py           # BotState + dataclasses
├── storage.py          # Session persistence (in-memory)
├── keyboards.py        # Inline keyboard builders
├── services.py         # Tavily search + LLM + planner
├── requirements.txt
├── .env.example
└── README.md
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/plan` | Start or restart trip planning |
| `/help` | Show available commands |

### Register Commands with BotFather

```
/setcommands

start - Start the bot and see welcome message
plan - Start planning your trip
help - Show available commands and how to use the bot
```

## Tech Stack

- **[python-telegram-bot](https://python-telegram-bot.org/)** - Telegram Bot API wrapper
- **[Tavily](https://tavily.com/)** - Web search API for activities/restaurants
- **[Ollama](https://ollama.ai/)** - Local LLM runtime
- **[Qwen3:8b](https://ollama.ai/library/qwen3)** - LLM for hotel parsing & itinerary generation

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session storage | In-memory | Simple for MVP, upgrade to Redis later |
| LLM | Local Ollama | Free, private, no API costs |
| Geography | LLM-inferred | No hardcoded zones, works for any destination |
| Selection | Collective | All group members can select activities |
| Itinerary edits | Regenerate only | Simple UX for MVP |

## Limitations

- Session data is lost on bot restart (in-memory storage)
- Requires local Ollama installation
- Transport estimates are LLM-generated (not real-time)
- Single destination per config (change `PLACE` for new destination)

## Future Enhancements

- [ ] Scheduled recommendations (push every 2 days)
- [ ] Persistent storage (Redis/SQLite)
- [ ] Cloud hosting (Railway/Render)
- [ ] Google Maps API for accurate transport times
- [ ] Multi-destination support in single config

## Related Files

- [Architecture Doc](./bintan_bot_architecture.md) - Detailed architecture & code patterns
- [Conversation Flow](./conversation_flow.mermaid) - State diagram

## License

MIT

## Acknowledgments

Built for planning family trips with young kids 👨‍👩‍👧 🏖️