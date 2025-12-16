"""
Services for Trip Planner Bot.

Handles external API calls:
- Tavily for web search (activities, food)
- Ollama/Qwen3 for LLM processing
"""

import re
import json
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
from models import Activity, HotelInfo

logger = logging.getLogger(__name__)


def search_activities() -> list[Activity]:
    """
    Search for kid-friendly activities using Tavily and LLM.

    Returns:
        List of Activity objects
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

    # Step 3: Use LLM to extract structured eateries
    eateries = _parse_food_with_llm(food_text)

    logger.info(f"Parsed {len(eateries)} eateries")
    return eateries


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

Extract the top {MAX_RECOMMENDATIONS - 2}-{MAX_RECOMMENDATIONS} most relevant halal-friendly restaurants or cafes. For EACH place, output EXACTLY this format (one per line, pipe-separated):

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

    eateries = []
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
            eateries.append(restaurant)

            if len(eateries) >= MAX_RECOMMENDATIONS:
                break

    return eateries


def parse_hotel(user_input: str) -> HotelInfo:
    """
    Parse user's hotel input using LLM to extract name and area.

    The LLM uses its knowledge of the destination's geography to infer
    the area/neighborhood without hardcoded zone mappings.

    Args:
        user_input: Raw text the user typed (e.g., "bintan lagoon")

    Returns:
        HotelInfo with parsed name, area, and confidence level
    """
    logger.info(f"Parsing hotel input: {user_input}")

    prompt = f"""
You are a travel assistant helping identify hotels in {PLACE}.

The user entered: "{user_input}"

Your task:
1. Identify the most likely hotel name from the input
2. Determine which area/neighborhood of {PLACE} this hotel is located in
3. Rate your confidence (high/medium/low)

Use your knowledge of {PLACE}'s geography and hotels. Common areas in {PLACE} include resort areas, beach zones, and town centers - use whatever area names are most accurate for this destination.

Respond ONLY with valid JSON in this exact format (no other text):
{{"name": "Full Hotel Name", "area": "Area/Neighborhood Name", "confidence": "high"}}

Rules:
- "name": The official/common hotel name (capitalize properly)
- "area": The general area or neighborhood (e.g., "Lagoi", "North Coast", "Town Center")
- "confidence":
  - "high" if you're certain about both name and area
  - "medium" if you recognize the hotel but unsure about exact area
  - "low" if you're guessing based on partial information

Examples:
- Input: "bintan lagoon" → {{"name": "Bintan Lagoon Resort", "area": "Lagoi", "confidence": "high"}}
- Input: "angsana" → {{"name": "Angsana Bintan", "area": "Lagoi Bay", "confidence": "high"}}
- Input: "some random place" → {{"name": "Some Random Place", "area": "Unknown", "confidence": "low"}}

/no_think
""".strip()  # Noqa: E501

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 200}
        )

        content = response["message"]["content"].strip()
        content = re.sub(
            r'<think>.*?</think>', '', content, flags=re.DOTALL
        ).strip()

        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            content = json_match.group()

        logger.debug(f"LLM hotel response: {content}")

        parsed = json.loads(content)

        hotel_info = HotelInfo(
            raw_input=user_input,
            name=parsed.get("name", user_input.title()),
            area=parsed.get("area", "Unknown"),
            confidence=parsed.get("confidence", "low")
        )

        logger.info(
            f"Parsed hotel: {hotel_info.name} in {hotel_info.area} "
            f"(confidence: {hotel_info.confidence})"
        )
        return hotel_info

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse hotel JSON: {e}")
        # Fallback: use input as-is with low confidence
        return HotelInfo(
            raw_input=user_input,
            name=user_input.title(),
            area="Unknown",
            confidence="low"
        )
    except Exception as e:
        logger.error(f"Error parsing hotel: {e}")
        # Fallback: use input as-is with low confidence
        return HotelInfo(
            raw_input=user_input,
            name=user_input.title(),
            area="Unknown",
            confidence="low"
        )


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
