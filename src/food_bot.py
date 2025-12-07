from tavily import TavilyClient
import ollama
import requests
import re
import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


PLACE = "Bintan"


def search_food():
    client = TavilyClient(api_key=TAVILY_API_KEY)
    results = client.search(
        query=(
            f"halal dining options in {PLACE} "
            "family-friendly restaurants, eateries and cafes"
        ),
        max_results=10,
        search_depth="advanced"
    )

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
    return food_text.strip()


def filter_with_llm(food_text):
    prompt = f"""
You are a helpful assistant that curates halal dining options for families visiting {PLACE}.

Here are some places I found:

{food_text}

Please:
1. Select the top 4-5 halal-friendly restaurants or cafes
2. Format each exactly like this:

1. Restaurant Name
📍 Location/Area
🍽️ Cuisine type (e.g., Indonesian, Malay, Seafood)
Brief 1-sentence description.
🔗 url

3. Prioritize family-friendly places
4. Keep each entry short and concise

Return ONLY the formatted numbered list, no commentary. /no_think
""".strip() # Noqa E501

    response = ollama.chat(
        model="qwen3:8b",
        messages=[{"role": "user", "content": prompt}],
        options={"num_predict": 700}
    )

    content = response["message"]["content"].strip()
    content = re.sub(
        r'<think>.*?</think>', '', content, flags=re.DOTALL
    ).strip()
    return content


def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": (
            "🍽️ Halal Dining Options in Bintan 🍽️\n"
            "(Recommended by Qwen LLM)\n\n" + message
        ),
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload, timeout=30)
    return response.json()


def main():
    print("🔍 Searching for halal food...")
    food = search_food()

    print("🤖 Filtering with LLM...")
    curated = filter_with_llm(food)

    print("📤 Sending to Telegram...")
    result = send_to_telegram(curated)

    if result.get("ok"):
        print("✅ Done! Check your Telegram.")
    else:
        print(f"❌ Error: {result}")


if __name__ == "__main__":
    main()
