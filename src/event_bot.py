from tavily import TavilyClient
import re
import ollama
import requests
import textwrap
import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PLACE = "Bintan"
START_DATE = "17 December 2025"
END_DATE = "20 December 2025"

PREFERENCES = [
    "outdoor activities",
    "low-cost or free",
    "suitable for young children (5-8 years old)",
    "family-friendly"
]

TELEGRAM_MAX_LEN = 4096
CHUNK_LEN = 3500  # stay safely below the hard limit


def search_events():
    client = TavilyClient(api_key=TAVILY_API_KEY)
    results = client.search(
        query=(
            f"kid-friendly events and activities in {PLACE} "
            f"from {START_DATE} to {END_DATE} "
            "suitable for families with young children"
        ),
        max_results=10,
        search_depth="advanced"
    )
    events_text = ""
    for result in results.get("results", []):
        # keep Tavily content concise to reduce LLM/Telegram size issues
        snippet = (result.get("content") or "").strip()
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "…"
        events_text += (
            f"Title: {result.get('title')}\n"
            f"URL: {result.get('url')}\n"
            f"Content: {snippet}\n\n"
        )
    return events_text.strip()


def filter_with_llm(events_text):
    prompt = f"""
You are a helpful assistant that curates events and activities for families with young children going to
{PLACE} from {START_DATE} to {END_DATE}.

Here are some events I found:

{events_text}

My preferences: {", ".join(PREFERENCES)}

Please:
1. Select the top 4-5 most relevant events based on my preferences
2. Format each event/activity exactly like this: (keep each event under 400 characters total):

   📌 Event Name:
   📍 Location:
   📅 Date/Time:
   Brief Description (1-2 sentences)
   🔗 url
   
   or
   
   📌 Activity Name:
   📍 Location:
   Brief Description (1-2 sentences)
   🔗 url

3. Skip events that don't match my preferences
4. If dates aren't clear, mention "Check website for dates"
5. Keep each entry short and concise

Return ONLY the formatted numbered list, no thinking, no commentary. /no_think
""".strip()  # Noqa E501

    response = ollama.chat(
        model="qwen3:8b",
        messages=[{"role": "user", "content": prompt}],
        options={"num_predict": 700}  # keep output reasonable
    )
    content = response["message"]["content"].strip()
    content = re.sub(
        r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

    return content


def split_into_chunks(text, max_len=CHUNK_LEN):
    """
    Split text into chunks not exceeding max_len,
    preferably at paragraph breaks.
    """
    if len(text) <= max_len:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for p in paragraphs:
        candidate = (current + "\n\n" + p).strip() if current else p
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If single paragraph is too long, hard-wrap it
            if len(p) > max_len:
                wrapped = textwrap.wrap(
                    p,
                    width=max_len,
                    replace_whitespace=False,
                    drop_whitespace=False
                )
                chunks.extend(wrapped[:-1])
                current = wrapped[-1] if wrapped else ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


def send_to_telegram(message):
    """Send message to Telegram channel, chunking if needed."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Header goes in the first chunk only
    header = "🎉 Kid-Friendly Activities & Events for a Bintan Getaway 🎉\n\n"

    if len(header) + len(message) <= TELEGRAM_MAX_LEN:
        chunks = [header + message]
    else:
        body_chunks = split_into_chunks(message, max_len=CHUNK_LEN)
        # prepend header to the first one
        if body_chunks:
            body_chunks[0] = header + body_chunks[0]
        chunks = body_chunks

    results = []
    for idx, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True
        }
        r = requests.post(url, json=payload, timeout=30)
        try:
            resp = r.json()
        except Exception:
            resp = {"ok": False, "status_code": r.status_code, "text": r.text}
        if not resp.get("ok"):
            print(f"❌ Telegram error on chunk {idx}/{len(chunks)}: {resp}")
        results.append(resp)
    return results


def main():
    print("🔍 Searching for events...")
    events = search_events()

    print(f"ℹ️ Tavily text length: {len(events)} chars")

    print("🤖 Filtering with LLM...")
    curated = filter_with_llm(events)
    print(f"ℹ️ LLM output length: {len(curated)} chars")

    print("📤 Sending to Telegram...")
    results = send_to_telegram(curated)

    if results and all(r.get("ok") for r in results):
        print("✅ Done! Check your Telegram channel.")
    else:
        print("⚠️ Some chunks failed. See logs above.")


if __name__ == "__main__":
    main()
