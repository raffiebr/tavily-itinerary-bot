"""
Services for Trip Planner Bot.

Handles external API calls:
- Tavily for web search (activities, food)
- Ollama/Qwen3 for LLM processing

Includes comprehensive error handling and multi-user vote support.
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
    MAX_RECOMMENDATIONS,
    DEFAULT_SELECTION_COUNT
)
from models import Activity, HotelInfo, UserSession

logger = logging.getLogger(__name__)


# === Custom Exceptions ===

class TavilySearchError(Exception):
    """Raised when Tavily search fails."""
    pass


class LLMError(Exception):
    """Raised when LLM call fails."""
    pass


class ServiceError(Exception):
    """Base exception for service errors."""
    pass


# === Search Functions ===

def search_activities() -> list[Activity]:
    """
    Search for kid-friendly activities using Tavily and LLM.

    Returns:
        List of Activity objects

    Raises:
        TavilySearchError: If Tavily API call fails
        LLMError: If LLM parsing fails
    """
    logger.info(f"Searching for activities in {PLACE}...")

    try:
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
    except Exception as e:
        logger.error(f"Tavily search failed for activities: {e}")
        raise TavilySearchError(
            f"Failed to search for activities: {str(e)}"
        ) from e

    # Format results for LLM
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

    result_count = len(results.get('results', []))
    logger.info(f"Tavily returned {result_count} activity results")

    if result_count == 0:
        logger.warning("No results from Tavily for activities")
        return []

    # Parse with LLM
    try:
        activities = _parse_activities_with_llm(events_text)
    except Exception as e:
        logger.error(f"LLM parsing failed for activities: {e}")
        raise LLMError(
            f"Failed to parse activities with LLM: {str(e)}"
        ) from e

    logger.info(f"Parsed {len(activities)} activities successfully")
    return activities


def search_food() -> list[Activity]:
    """
    Search for halal dining options using Tavily and LLM.

    Returns:
        List of Activity objects

    Raises:
        TavilySearchError: If Tavily API call fails
        LLMError: If LLM parsing fails
    """
    logger.info(f"Searching for halal food in {PLACE}...")

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(
            query=(
                f"halal dining options in {PLACE} "
                "family-friendly restaurants, eateries and cafes"
            ),
            max_results=MAX_SEARCH_RESULTS,
            search_depth="advanced"
        )
    except Exception as e:
        logger.error(f"Tavily search failed for food: {e}")
        raise TavilySearchError(
            f"Failed to search for eateries: {str(e)}"
        ) from e

    # Format results for LLM
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

    result_count = len(results.get('results', []))
    logger.info(f"Tavily returned {result_count} food results")

    if result_count == 0:
        logger.warning("No results from Tavily for food")
        return []

    # Parse with LLM
    try:
        eateries = _parse_food_with_llm(food_text)
    except Exception as e:
        logger.error(f"LLM parsing failed for food: {e}")
        raise LLMError(
            f"Failed to parse eateries with LLM: {str(e)}"
        ) from e

    logger.info(f"Parsed {len(eateries)} eateries successfully")
    return eateries


def _parse_activities_with_llm(events_text: str) -> list[Activity]:
    """
    Use LLM to parse raw search results into structured Activity objects.

    Raises:
        LLMError: If LLM call or parsing fails
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
""".strip()

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 1200}
        )
    except Exception as e:
        logger.error(f"Ollama chat failed: {e}")
        raise LLMError(f"LLM call failed: {str(e)}") from e

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
    Use LLM to parse search results into structured eatery objects.

    Raises:
        LLMError: If LLM call or parsing fails
    """
    prompt = f"""
You are extracting halal dining options for families visiting {PLACE}.

Here are search results:

{food_text}

Extract the top {MAX_RECOMMENDATIONS - 2}-{MAX_RECOMMENDATIONS} most relevant halal-friendly restaurants or cafes. Include at least 1 cafe if it exists in the search results. For EACH place, output EXACTLY this format (one per line, pipe-separated):

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
""".strip()

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 1200}
        )
    except Exception as e:
        logger.error(f"Ollama chat failed: {e}")
        raise LLMError(f"LLM call failed: {str(e)}") from e

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


# === Hotel Parsing ===

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
""".strip()

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
        return HotelInfo(
            raw_input=user_input,
            name=user_input.title(),
            area="Unknown",
            confidence="low"
        )
    except Exception as e:
        logger.error(f"Error parsing hotel: {e}")
        return HotelInfo(
            raw_input=user_input,
            name=user_input.title(),
            area="Unknown",
            confidence="low"
        )


# === Selection Helpers ===

def apply_default_selections(
    session: UserSession,
    selection_type: str,
    system_user_id: int = 0
) -> tuple[int, list[str]]:
    """
    Apply default selections if user(s) made no selections.

    Selects the top N items from the available list.

    Args:
        session: UserSession to update
        selection_type: "activity" or "food"
        system_user_id: User ID to use for default votes (0 = system)

    Returns:
        Tuple of (count of defaults applied, list of default item names)
    """
    if selection_type == "activity":
        items = session.activities
        selected = session.selected_activities
    else:
        items = session.eateries
        selected = session.selected_eateries

    # Only apply defaults if no selections were made
    if selected:
        return 0, []

    # Select top N items
    count = min(DEFAULT_SELECTION_COUNT, len(items))
    default_names = []

    for item in items[:count]:
        if selection_type == "activity":
            session.add_activity_vote(item.id, system_user_id)
        else:
            session.add_eatery_vote(item.id, system_user_id)
        default_names.append(item.name)

    logger.info(
        f"Applied {count} default {selection_type} selections: "
        f"{', '.join(default_names)}"
    )

    return count, default_names


def get_prioritized_selections(
    session: UserSession,
    selection_type: str
) -> list[Activity]:
    """
    Get selected items sorted by vote count (most votes first).

    Args:
        session: UserSession containing selections
        selection_type: "activity" or "food"

    Returns:
        List of Activity objects, sorted by vote count descending
    """
    if selection_type == "activity":
        items = session.activities
        votes_by_id = session.get_activities_by_votes()
    else:
        items = session.eateries
        votes_by_id = session.get_eateries_by_votes()

    # Create lookup dict
    items_by_id = {item.id: item for item in items}

    # Return items in vote order
    result = []
    for item_id, vote_count in votes_by_id:
        if item_id in items_by_id:
            result.append(items_by_id[item_id])

    return result


# === Formatting Helpers ===

def format_activity_message(activity: Activity) -> str:
    """Format a single activity for display in Telegram message."""
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
    """Format a list of activities for display in Telegram."""
    lines = []
    for i, act in enumerate(activities, start=1):
        lines.append(f"{i}. {format_activity_message(act)}")
    return "\n\n".join(lines)


# === Itinerary Generation ===

def generate_itinerary(
    selected_activities: list[Activity],
    selected_eateries: list[Activity],
    hotel_name: str,
    hotel_area: str,
    num_days: int,
    activity_votes: dict[str, int] = None,
    eatery_votes: dict[str, int] = None
) -> str:
    """
    Generate daily itinerary using LLM.

    Items are listed in priority order (most votes first).

    Args:
        selected_activities: List of selected Activity objects (priority order)
        selected_eateries: List of selected eatery Activity objects (priority order)
        hotel_name: Name of the hotel
        hotel_area: Area/neighborhood of the hotel
        num_days: Number of days for the trip
        activity_votes: Optional dict of {name: vote_count} for display
        eatery_votes: Optional dict of {name: vote_count} for display

    Returns:
        Formatted itinerary string

    Raises:
        LLMError: If LLM call fails
    """
    logger.info(
        f"Generating {num_days}-day itinerary with "
        f"{len(selected_activities)} activities and "
        f"{len(selected_eateries)} eateries"
    )

    # Build activities text with vote info if available
    activities_text = ""
    for i, act in enumerate(selected_activities, start=1):
        vote_info = ""
        if activity_votes and act.name in activity_votes:
            votes = activity_votes[act.name]
            if votes > 1:
                vote_info = f" [{votes} votes - high priority]"
            elif votes == 1:
                vote_info = " [1 vote]"

        activities_text += (
            f"{i}. {act.name}{vote_info}\n"
            f"   Location: {act.location}\n"
            f"   Hours: {act.date_time}\n"
            f"   Description: {act.description}\n\n"
        )

    if not activities_text:
        activities_text = (
            "No specific activities selected - suggest popular "
            f"kid-friendly options in {PLACE}."
        )

    # Build eateries text with vote info
    eateries_text = ""
    for i, eat in enumerate(selected_eateries, start=1):
        vote_info = ""
        if eatery_votes and eat.name in eatery_votes:
            votes = eatery_votes[eat.name]
            if votes > 1:
                vote_info = f" [{votes} votes - high priority]"
            elif votes == 1:
                vote_info = " [1 vote]"

        eateries_text += (
            f"{i}. {eat.name}{vote_info}\n"
            f"   Location: {eat.location}\n"
            f"   Cuisine: {eat.cuisine}\n"
            f"   Description: {eat.description}\n\n"
        )

    if not eateries_text:
        eateries_text = (
            "No specific eateries selected - suggest halal-friendly "
            "options near activities."
        )

    prompt = f"""
You are a family travel planner creating a detailed {num_days}-day itinerary for {PLACE}.

HOTEL INFORMATION:
- Hotel: {hotel_name}
- Area: {hotel_area}

SELECTED ACTIVITIES (in priority order - items with more votes should be scheduled first):
{activities_text}

SELECTED EATERIES (in priority order - items with more votes should be used first):
{eateries_text}

IMPORTANT SCHEDULING RULES:

**Day 1 (Arrival Day) - Special Schedule:**
- ~12:00 PM: Arrive at hotel, drop bags
- 12:30-2:00 PM: Lunch at nearby eatery
- 2:00-3:00 PM: Explore nearby area / wait for check-in
- 3:00 PM: Hotel check-in
- 3:00-4:30 PM: Rest and settle in
- 4:30-6:00 PM: Beach/pool at hotel
- 6:00-7:00 PM: Freshen up
- 7:30 PM+: Dinner

**Day 2 onwards (Normal Schedule):**
- 8:00-9:30 AM: Breakfast at hotel
- 9:30-10:00 AM: Prepare and travel to activity
- 10:00 AM-1:00 PM: Morning activity
- 1:00-2:00 PM: Lunch (MUST be near morning activity location!)
- 2:00-2:30 PM: Travel back to hotel
- 2:30-4:30 PM: Nap time (2 hours - critical for young kids!)
- 4:30-6:00 PM: Beach/pool at hotel
- 6:00-7:00 PM: Freshen up
- 7:30 PM+: Dinner

GENERATION RULES:
1. Schedule higher-priority items (more votes) on earlier/better days
2. If more activities than available days, prioritize by vote count
3. Cluster activities geographically to minimize travel time
4. Match lunch spots to morning activity locations
5. Include transport method AND estimated cost for each trip
6. Use "Day 1", "Day 2" format - NOT specific dates
7. Keep family-friendly pace - no rushing

FORMAT YOUR RESPONSE EXACTLY LIKE THIS (use plain text, no markdown):

================================================
DAY 1 - Arrival Day
================================================

12:00 PM | Arrive at Hotel
   {hotel_name}
   Drop bags at reception

12:30-2:00 PM | Lunch
   [Restaurant Name]
   Location: [Area]
   Cuisine: [Type]
   Transport: [How to get there from hotel + cost]

... continue with rest of day ...

================================================
DAY 2
================================================

8:00-9:30 AM | Breakfast
   {hotel_name}

... continue for remaining days ...

Keep response under 2800 characters total. Be concise but complete.

/no_think
""".strip()

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 2500}
        )

        content = response["message"]["content"].strip()
        content = re.sub(
            r'<think>.*?</think>', '', content, flags=re.DOTALL
        ).strip()

        logger.info(f"Generated itinerary: {len(content)} chars")
        return content

    except Exception as e:
        logger.error(f"Error generating itinerary: {e}")
        raise LLMError(f"Failed to generate itinerary: {str(e)}") from e