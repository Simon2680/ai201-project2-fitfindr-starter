"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.
    """
    listings = load_listings()

    # Step 1: Filter by price and size
    filtered = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.upper() not in item["size"].upper():
            continue
        filtered.append(item)

    # Step 2: Score by keyword overlap with description
    keywords = [kw.lower() for kw in description.split()]

    def score(item: dict) -> int:
        # Build a searchable text blob from the most relevant fields
        blob = " ".join([
            item["title"],
            item["description"],
            " ".join(item["style_tags"]),
            item["category"],
            item.get("brand") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in blob)

    scored = [(score(item), item) for item in filtered]

    # Step 3: Drop zero-score results and sort best-first
    results = [item for s, item in sorted(scored, key=lambda x: x[0], reverse=True) if s > 0]

    return results


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.
    """
    client = _get_groq_client()

    item_summary = (
        f"Title: {new_item.get('title', 'Unknown')}\n"
        f"Description: {new_item.get('description', '')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Category: {new_item.get('category', '')}\n"
        f"Condition: {new_item.get('condition', '')}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        # Empty wardrobe — give general styling advice
        prompt = (
            f"A user just thrifted this item:\n{item_summary}\n\n"
            "They haven't shared their wardrobe. Give them 1-2 general outfit ideas: "
            "what kinds of pieces pair well with this item, what vibe or aesthetic it suits, "
            "and one specific styling tip (e.g. tuck, layer, roll). "
            "Be specific about colors and silhouettes. Write 3-5 sentences, conversational tone."
        )
        prefix = "No wardrobe on file — here's a general styling idea based on the item alone.\n\n"
    else:
        # FIXED: Using safe .get() method to fall back to 'Unknown color' if 'color' isn't found
        wardrobe_text = "\n".join(
            f"- {w.get('name', 'Unknown Item')} ({w.get('color', 'Unknown color')}, styles: {', '.join(w.get('style', []))})"
            for w in wardrobe_items
        )
        prompt = (
            f"A user just thrifted this item:\n{item_summary}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfit combinations using the thrifted item and specific pieces "
            "from their wardrobe. Reference each wardrobe piece by its exact name. "
            "Include one styling tip per outfit (e.g. tuck, cuff, layer). "
            "Write 3-6 sentences, conversational tone — like advice from a friend who loves fashion."
        )
        prefix = ""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        suggestion = response.choices[0].message.content.strip()
        return prefix + suggestion
    except Exception as e:
        return f"Could not generate outfit suggestion. Please try again. (Error: {e})"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    """
    if not outfit or not outfit.strip():
        title = new_item.get("title", "this piece")
        price = new_item.get("price", "?")
        platform = new_item.get("platform", "a thrift app")
        return (
            f"just copped this {title} from {platform} for ${price} 🔥 "
            f"[Fit card simplified — outfit suggestion was unavailable.]"
        )

    title = new_item.get("title", "this piece")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "a thrift app")
    condition = new_item.get("condition", "")
    colors = ", ".join(new_item.get("colors", []))

    prompt = (
        f"Write a 2-3 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"The thrifted item: {title} (${price} from {platform}, condition: {condition}, colors: {colors})\n"
        f"The outfit: {outfit}\n\n"
        "Rules:\n"
        "- Casual first-person voice, like a real OOTD post — NOT a product description\n"
        "- Mention the item name, price, and platform naturally (each once)\n"
        "- Capture the specific vibe of the outfit\n"
        "- Use 1-2 relevant emojis naturally (not at the start of every sentence)\n"
        "- Do NOT use hashtags\n"
        "- Output ONLY the caption text, nothing else"
    )

    client = _get_groq_client()
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=1.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return (
            f"just found this {title} on {platform} for ${price} and i'm obsessed 🖤 "
            f"[Caption generation failed: {e}]"
        )