# Python-Telegram-Bot SDK Guide

A quick reference for `python-telegram-bot` v20+ (async version).

**SDK Version:** python-telegram-bot v22.5  
**Docs:** https://docs.python-telegram-bot.org/

---

## Table of Contents

- [Core Concepts](#core-concepts)
- [Update Object](#update-object)
- [ContextTypes](#contexttypes)
- [Handlers](#handlers)
- [Why Async?](#why-async)
- [Common Patterns](#common-patterns)

---

## Core Concepts

When a user interacts with your bot, this happens:

```
User sends "/start"
       ↓
Telegram servers receive it
       ↓
Telegram sends an Update to your bot
       ↓
python-telegram-bot matches it to a handler
       ↓
Your handler function runs
       ↓
Bot sends response back to user
```

Every handler function receives two parameters:

```python
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #                 ↑                ↑
    #                 │                └── Bot state & utilities
    #                 └── Incoming event data
```

---

## Update Object

`Update` contains **all information about an incoming event** from Telegram.

```python
from telegram import Update
```

### Structure

```python
update
├── .message              # Message object (when user sends text/command)
│   ├── .text             # The message text, e.g., "Hello" or "/start"
│   ├── .chat_id          # Chat ID, e.g., -123456789
│   ├── .from_user        # User object (id, first_name, username, etc.)
│   ├── .date             # When the message was sent
│   └── .reply_text()     # Method to reply to this message
│
├── .callback_query       # CallbackQuery object (when user clicks inline button)
│   ├── .data             # The callback data string, e.g., "sel_act_001"
│   ├── .message          # The original message with the button
│   ├── .from_user        # User who clicked the button
│   └── .answer()         # Acknowledge the button press
│
├── .effective_chat       # The chat where this event happened
│   ├── .id               # Chat ID
│   └── .type             # "private", "group", "supergroup", "channel"
│
└── .effective_user       # The user who triggered this event
    ├── .id               # User ID
    ├── .first_name       # User's first name
    └── .username         # Username (optional)
```

### `effective_user` vs `message.from_user`

Both return the same user, but `effective_user` is a **convenience shortcut** that works across all update types:

```python
# When user sends a message:
update.message.from_user    # ✅ Works
update.effective_user       # ✅ Works (same result)

# When user clicks a button:
update.message              # None! (no message, it's a button click)
update.message.from_user    # ❌ ERROR! Can't access .from_user on None
update.callback_query.from_user  # ✅ Works
update.effective_user       # ✅ Works (shortcut - always works!)
```

| Update Type | Manual Access | Shortcut |
|-------------|---------------|----------|
| Message | `update.message.from_user` | `update.effective_user` |
| Button click | `update.callback_query.from_user` | `update.effective_user` |
| Edited message | `update.edited_message.from_user` | `update.effective_user` |

**Recommendation:** Use `effective_user` and `effective_chat` - they always work regardless of update type.

### Common Usage

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Get info about the user/chat
    user_name = update.effective_user.first_name
    chat_id = update.effective_chat.id
    
    # Reply to the message
    await update.message.reply_text(f"Hello {user_name}!")
```

### Message vs Callback Query

| Event Type | User Action | Access Via |
|------------|-------------|------------|
| Message | User sends text or command | `update.message` |
| Callback Query | User clicks inline button | `update.callback_query` |

```python
# For commands/text messages:
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")

# For inline button clicks:
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Must acknowledge button press!
    
    button_data = query.data  # e.g., "sel_act_001"
    await query.edit_message_text(f"You clicked: {button_data}")
```

---

## ContextTypes

`ContextTypes` is a **type hint helper** that defines the shape of the `context` object.

```python
from telegram.ext import ContextTypes
```

### DEFAULT_TYPE

```python
ContextTypes.DEFAULT_TYPE
# Equivalent to:
CallbackContext[ExtBot[None], dict, dict, dict]
#               ↑             ↑     ↑     ↑
#            bot_data    user_data chat_data callback_data
```

### What's Inside Context

```python
context
├── .bot              # The Bot instance - use to send messages
├── .args             # Command arguments as list
│                     # e.g., "/plan 3 days" → ['3', 'days']
│
├── .user_data        # Dict storage, persisted per user
├── .chat_data        # Dict storage, persisted per chat
├── .bot_data         # Dict storage, shared globally
│
└── .job_queue        # Scheduler for delayed/recurring tasks
```

### Common Usage

**Using `context.bot` to send messages:**
```python
async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Send to a specific chat (not just reply)
    await context.bot.send_message(
        chat_id=123456789,
        text="Hello from the bot!"
    )
```

**Using `context.args` for command arguments:**
```python
# User types: /plan 3
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        num_days = context.args[0]  # "3"
        await update.message.reply_text(f"Planning for {num_days} days!")
```

**Using `context.user_data` for per-user storage:**
```python
async def track_visits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Increment visit count
    count = context.user_data.get('visits', 0) + 1
    context.user_data['visits'] = count
    
    await update.message.reply_text(f"Visit #{count}")
```

### context.user_data vs Custom Storage

| Feature | `context.user_data` | Custom storage (e.g., `storage.py`) |
|---------|---------------------|-------------------------------------|
| Type safety | ❌ Plain dict | ✅ Typed dataclass |
| IDE autocomplete | ❌ No | ✅ Yes |
| Swappable backend | ❌ Harder | ✅ Easy (Redis, SQLite) |
| Setup | Zero | Some boilerplate |

For simple bots, `context.user_data` is fine. For complex state machines, a typed storage module is better.

---

## Handlers

Handlers route incoming updates to your functions.

### What is `app`?

`app` is your **bot application** - the brain that manages everything:

```python
from telegram.ext import Application

# Create the application with your bot token
app = Application.builder().token("YOUR_BOT_TOKEN").build()
```

### What is `add_handler()`?

`add_handler()` **registers what your bot can respond to**. Without handlers, the bot receives messages but does nothing with them.

```python
# Tell the bot: "When you see /start, call the start() function"
app.add_handler(CommandHandler("start", start))

# Tell the bot: "When you see /plan, call the plan() function"
app.add_handler(CommandHandler("plan", plan))

# Tell the bot: "When user clicks any button, call handle_callback()"
app.add_handler(CallbackQueryHandler(handle_callback))
```

**Analogy:** Think of a restaurant. `app` is the restaurant, `add_handler()` is training staff. Without training (handlers), the staff (bot) just stands there when customers (users) arrive!

### Handler Types

```python
from telegram.ext import (
    CommandHandler,      # Matches /commands
    MessageHandler,      # Matches text messages
    CallbackQueryHandler,# Matches inline button clicks
    filters              # Filter criteria for MessageHandler
)
```

### CommandHandler

Triggers on `/commands`. **Commands are case-insensitive** - `/start`, `/START`, and `/Start` all match.

```python
# Matches "/start", "/START", "/Start", "/start@botname"
app.add_handler(CommandHandler("start", start_function))

# The handler function:
async def start_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome!")
```

**Commands always work regardless of bot state** - they're checked based on handler order, not bot state.

### MessageHandler

Triggers on text messages (non-commands):

```python
# Matches any text that's NOT a command
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# The handler function:
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    await update.message.reply_text(f"You said: {user_input}")
```

### CallbackQueryHandler

Triggers when user clicks an inline button. **ONE handler catches ALL button clicks** - you differentiate by checking `callback_data`.

```python
app.add_handler(CallbackQueryHandler(handle_callback))
```

#### Basic Handler

```python
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # REQUIRED: Acknowledge the click
    
    data = query.data  # The callback_data from the button
    
    # Update the message that had the button
    await query.edit_message_text(f"You selected: {data}")
```

#### Routing by callback_data Prefix

When you have multiple button types (activities, food, etc.), use prefixes in `callback_data`:

```python
# When creating buttons, set unique callback_data:
InlineKeyboardButton("Water Park", callback_data="sel_act_001")    # Activity
InlineKeyboardButton("Warung Yeah", callback_data="sel_fod_001")   # Food
InlineKeyboardButton("Done", callback_data="done_act")             # Action

# In your ONE handler, check the prefix to route:
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data  # e.g., "sel_act_001" or "sel_fod_001"
    
    if data.startswith("sel_act_"):
        activity_id = data.replace("sel_act_", "")  # "001"
        # Handle activity selection...
        
    elif data.startswith("sel_fod_"):
        food_id = data.replace("sel_fod_", "")  # "001"
        # Handle food selection...
        
    elif data == "done_act":
        # Handle "done selecting activities"...
```

#### `query.answer()` vs `query.edit_message_text()`

These do completely different things:

| Method | Purpose | What it does |
|--------|---------|--------------|
| `query.answer()` | Acknowledge the click | Tells Telegram "I received this". Removes loading spinner. **Required!** |
| `query.edit_message_text()` | Update the message | Changes the message content that had the button |

```python
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # 1. Acknowledge (required - or user sees "loading" forever)
    await query.answer()                        # Silent acknowledgment
    # OR
    await query.answer("Saved!")                # Show brief toast popup
    # OR  
    await query.answer("Error!", show_alert=True)  # Show alert dialog
    
    # 2. Update the message (optional)
    await query.edit_message_text("You selected: Water Park")
```

**What happens if you skip `query.answer()`?**
- User sees a loading spinner on the button
- After ~30 seconds, Telegram shows "query failed"
- Bad user experience!

#### Visual Timeline

```
┌─────────────────────────────────────────────────────────────┐
│ Chat shows:                                                  │
│ ┌─────────────────────────────────────┐                     │
│ │ Choose an activity:                 │                     │
│ │ [⬜ Water Park] [⬜ Mangrove Tour]  │ ← Inline buttons    │
│ └─────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼ User clicks "Water Park"
                         
┌─────────────────────────────────────────────────────────────┐
│ Your code runs:                                              │
│                                                              │
│   query = update.callback_query                              │
│                                                              │
│   await query.answer()  ───────► Tells Telegram "Got it!"   │
│                                  (removes loading spinner)   │
│                                                              │
│   await query.edit_message_text( ──► Changes the message    │
│       "You selected: Water Park"                             │
│   )                                                          │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Chat now shows:                                              │
│ ┌─────────────────────────────────────┐                     │
│ │ You selected: Water Park            │ ← Updated message   │
│ └─────────────────────────────────────┘   (buttons gone)    │
└─────────────────────────────────────────────────────────────┘
```

#### Multiple Users in Group Chat

Each button click triggers the handler **separately** for each user:

```
User A clicks "Water Park" → handle_callback() runs for User A
User B clicks "Mangrove"   → handle_callback() runs for User B
User C clicks "Water Park" → handle_callback() runs for User C
```

Each `query.answer()` only acknowledges THAT user's click.

### Handler Order Matters (First Match Wins)

Handlers are checked **in the order you add them**. Once a handler matches, the rest are **skipped**.

```python
# Order matters!
app.add_handler(CommandHandler("start", start))        # Checked 1st
app.add_handler(CommandHandler("help", help_cmd))      # Checked 2nd
app.add_handler(CallbackQueryHandler(handle_callback)) # Checked 3rd
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))  # Checked 4th
```

#### Example: How matching works

```
User sends "/start"
       ↓
Check Handler 1: CommandHandler("start")
  → Is it "/start"? YES → Call start() → STOP (don't check others)

User sends "/help"
       ↓
Check Handler 1: CommandHandler("start")
  → Is it "/start"? NO
       ↓
Check Handler 2: CommandHandler("help")
  → Is it "/help"? YES → Call help_cmd() → STOP

User sends "hello" (plain text)
       ↓
Check Handler 1: Is it "/start"? NO
Check Handler 2: Is it "/help"? NO
Check Handler 3: Is it a button click? NO
Check Handler 4: Is it text and not a command? YES → Call handle_text() → STOP
```

#### Common Mistake: Wrong order

```python
# ❌ BAD: General handler BEFORE specific handler
app.add_handler(MessageHandler(filters.TEXT, handle_all_text))  # Catches everything!
app.add_handler(CommandHandler("start", start))  # Never reached for /start!

# Why? "/start" is text too! MessageHandler catches it first.
```

```python
# ✅ GOOD: Specific handlers BEFORE general handlers
app.add_handler(CommandHandler("start", start))  # Specific
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text))  # General
#                                         ↑
#                          Exclude commands from this handler!
```

**Rule of thumb:** Specific handlers first, general handlers last.

---

## Why Async?

Python-telegram-bot v20+ uses `asyncio` for **non-blocking I/O**.

### The Problem with Sync Code

```python
# Synchronous (blocking) - BAD for bots
def handle_message(update, context):
    response = call_telegram_api()  # Bot FREEZES here
    # Can't handle other users while waiting!
```

### The Async Solution

```python
# Asynchronous (non-blocking) - GOOD for bots
async def handle_message(update, context):
    response = await call_telegram_api()  # Yields control while waiting
    # Other users can be handled during the wait!
```

### Simple Rule

- Mark handler functions with `async def`
- Use `await` before any I/O operation (sending messages, API calls)

```python
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello!")     # await for I/O
    await context.bot.send_message(chat_id, msg)  # await for I/O
```

---

## Common Patterns

### Pattern 1: Basic Command Handler

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! Use /help for commands.")
```

### Pattern 2: Inline Keyboard Buttons

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def show_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Option A", callback_data="opt_a")],
        [InlineKeyboardButton("Option B", callback_data="opt_b")],
    ])
    await update.message.reply_text("Choose:", reply_markup=keyboard)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "opt_a":
        await query.edit_message_text("You chose A!")
    elif query.data == "opt_b":
        await query.edit_message_text("You chose B!")
```

### Pattern 3: State-Based Text Handling

```python
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    session = get_session(chat_id)  # Your storage
    
    if session.state == BotState.WAITING_FOR_NAME:
        session.name = text
        session.state = BotState.WAITING_FOR_EMAIL
        save_session(session)
        await update.message.reply_text("Got it! Now enter your email:")
    
    elif session.state == BotState.WAITING_FOR_EMAIL:
        session.email = text
        session.state = BotState.DONE
        save_session(session)
        await update.message.reply_text(f"Thanks {session.name}!")
```

### Pattern 4: Full Application Setup

```python
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

def main():
    # Create application
    app = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Add handlers (order matters!)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Start polling
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## Quick Reference

| What you want | Code |
|---------------|------|
| Get message text | `update.message.text` |
| Get chat ID | `update.effective_chat.id` |
| Get user's name | `update.effective_user.first_name` |
| Reply to user | `await update.message.reply_text("Hi!")` |
| Send to specific chat | `await context.bot.send_message(chat_id, "Hi!")` |
| Get button click data | `update.callback_query.data` |
| Acknowledge button | `await update.callback_query.answer()` |
| Edit button message | `await update.callback_query.edit_message_text("New text")` |
| Get command args | `context.args` → `['arg1', 'arg2']` |
| Store per-user data | `context.user_data['key'] = value` |

---

## Resources

- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Examples Repository](https://github.com/python-telegram-bot/python-telegram-bot/tree/master/examples)