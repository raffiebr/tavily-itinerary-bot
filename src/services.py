"""
Services for Trip Planner Bot.

Handles external API calls:
- Tavily for web search (activities, food)
- Ollama/Qwen3 for LLM processing
"""

import re
import logging
import ollama
from tavily import TavilyClient

from config import (
    TAVILY_API_KEY,
    PLACE,
    START_DATE,
    END_DATE,
    PREFERENCES,
    LLM_MODEL,
    MAX_SEARCH_RESULTS,
    MAX_RECOMMENDATIONS
)
from models import Activity

logger = logging.getLogger(__name__)


def search_activities() -> list[Activity]:
    """
    Search for kid-friendly activities using Tavily and LLM.

    Returns:
        List of Activity objects (8-10 activities)
    """
    logger.info(f"Searching for activities in {PLACE}...")

    # Step 1: Search with Tavily
    client = TavilyClient(api_key=TAVILY_API_KEY)
    results = client.search(
        query=(
            f"kid-friendly events and activities in {PLACE} "
            f"from {START_DATE} to {END_DATE} "
            "suitable for families with young children"
        ),
        max_results=MAX_SEARCH_RESULTS,
        search_depth="advanced"
    )

    # Step 2: Format results for LLM
    events_text = ""
    for result in results.get("results", []):
        snippet = (result.get("content") or "").strip()
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "…"
        events_text += (
            f"Title: {result.get('title')}\n"
            f"URL: {result.get('url')}\n"
            f"Content: {snippet}\n\n"
        )

    logger.info(f"Tavily returned {len(results.get('results', []))} results")

    # Step 3: Use LLM to extract structured activities
    activities = _parse_activities_with_llm(events_text)

    logger.info(f"Parsed {len(activities)} activities")
    return activities


def search_food() -> list[Activity]:
    """
    Search for halal dining options using Tavily and LLM.

    Returns:
        List of Activity objects
    """
    logger.info(f"Searching for halal food in {PLACE}...")

    # Step 1: Search with Tavily
    client = TavilyClient(api_key=TAVILY_API_KEY)
    results = client.search(
        query=(
            f"halal dining options in {PLACE} "
            "family-friendly restaurants, eateries and cafes"
        ),
        max_results=MAX_SEARCH_RESULTS,
        search_depth="advanced"
    )

    # Step 2: Format results for LLM
    food_text = ""
    for result in results.get("results", []):
        snippet = (result.get("content") or "").strip()
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "…"
        food_text += (
            f"Title: {result.get('title')}\n"
            f"URL: {result.get('url')}\n"
            f"Content: {snippet}\n\n"
        )

    logger.info(f"Tavily returned {len(results.get('results', []))} results")

    # Step 3: Use LLM to extract structured restaurants
    restaurants = _parse_food_with_llm(food_text)

    logger.info(f"Parsed {len(restaurants)} restaurants")
    return restaurants


def _parse_activities_with_llm(events_text: str) -> list[Activity]:
    """
    Use LLM to parse raw search results into structured Activity objects.
    """
    prompt = f"""
You are extracting kid-friendly activities for families visiting {PLACE} from {START_DATE} to {END_DATE}.

Here are search results:

{events_text}

Preferences: {", ".join(PREFERENCES)}

Extract the top {MAX_RECOMMENDATIONS - 2}-{MAX_RECOMMENDATIONS} most relevant activities. For EACH activity, output EXACTLY this format (one per line, pipe-separated):

NAME|LOCATION|DATE_TIME|DESCRIPTION|URL

Rules:
- NAME: Activity or attraction name (short, clear)
- LOCATION: Area/neighborhood in {PLACE}
- DATE_TIME: Operating hours or "Check website"
- DESCRIPTION: One sentence, under 100 chars
- URL: The source URL

Example output:
Treasure Bay Water Park|Lagoi Bay|Daily 9am-6pm|Family water park with kid zones and wave pools.|https://example.com
Mangrove Discovery Tour|Sebung Village|Check website|Boat tour through mangroves to see fireflies.|https://example.com

Output ONLY the pipe-separated lines, nothing else. /no_think
""".strip()  # Noqa: E501

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"num_predict": 1200}
    )

    content = response["message"]["content"].strip()
    content = re.sub(
        r'<think>.*?</think>', '', content, flags=re.DOTALL
    ).strip()

    activities = []
    for idx, line in enumerate(content.split("\n"), start=1):
        line = line.strip()
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) >= 5:
            activity = Activity(
                id=f"{idx:03d}",
                name=parts[0].strip(),
                location=parts[1].strip(),
                date_time=parts[2].strip(),
                description=parts[3].strip(),
                url=parts[4].strip(),
                activity_type="activity"
            )
            activities.append(activity)

            if len(activities) >= MAX_RECOMMENDATIONS:
                break

    return activities


def _parse_food_with_llm(food_text: str) -> list[Activity]:
    """
    Use LLM to parse search results into structured eateries objects.
    """
    prompt = f"""
You are extracting halal dining options for families visiting {PLACE}.

Here are search results:

{food_text}

Extract the top 8-10 most relevant halal-friendly restaurants or cafes. For EACH place, output EXACTLY this format (one per line, pipe-separated):

NAME|LOCATION|CUISINE|DESCRIPTION|URL

Rules:
- NAME: Restaurant or cafe name
- LOCATION: Area/neighborhood in {PLACE}
- CUISINE: Type of food (Indonesian, Malay, Seafood, etc.)
- DESCRIPTION: One sentence, under 100 chars, mention if family-friendly
- URL: The source URL

Example output:
Warung Yeah!|Lagoi Bay|Indonesian|Casual family dining with local favorites and kid menu.|https://example.com
Kelong Seafood|Trikora Beach|Seafood|Fresh halal seafood in a waterfront setting.|https://example.com

Output ONLY the pipe-separated lines, nothing else. /no_think
""".strip()  # Noqa: E501

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"num_predict": 1200}
    )

    content = response["message"]["content"].strip()
    content = re.sub(
        r'<think>.*?</think>', '', content, flags=re.DOTALL
    ).strip()

    restaurants = []
    for idx, line in enumerate(content.split("\n"), start=1):
        line = line.strip()
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) >= 5:
            restaurant = Activity(
                id=f"{idx:03d}",
                name=parts[0].strip(),
                location=parts[1].strip(),
                date_time="",
                cuisine=parts[2].strip(),
                description=parts[3].strip(),
                url=parts[4].strip(),
                activity_type="food"
            )
            restaurants.append(restaurant)

            if len(restaurants) >= MAX_RECOMMENDATIONS:
                break

    return restaurants


def format_activity_message(activity: Activity) -> str:
    """
    Format a single activity for display in Telegram message.
    """
    if activity.activity_type == "activity":
        return (
            f"📌 *{activity.name}*\n"
            f"📍 {activity.location}\n"
            f"📅 {activity.date_time}\n"
            f"{activity.description}\n"
            f"🔗 {activity.url}"
        )
    else:
        return (
            f"🍽️ *{activity.name}*\n"
            f"📍 {activity.location}\n"
            f"🍴 {activity.cuisine}\n"
            f"{activity.description}\n"
            f"🔗 {activity.url}"
        )


def format_activities_list(activities: list[Activity]) -> str:
    """
    Format a list of activities for display in Telegram.
    """
    lines = []
    for i, act in enumerate(activities, start=1):
        lines.append(f"{i}. {format_activity_message(act)}")
    return "\n\n".join(lines)
