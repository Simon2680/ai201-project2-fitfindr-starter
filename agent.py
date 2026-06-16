"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import os
import json
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Use the LLM to extract description, size, and max_price from a natural
    language query. Falls back to regex if the LLM call fails.

    Returns a dict with keys:
        description (str)        -- what the user is looking for
        size        (str | None) -- clothing size, or None if not mentioned
        max_price   (float|None) -- price ceiling, or None if not mentioned
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            client = Groq(api_key=api_key)
            prompt = (
                "Extract search parameters from this thrift shopping query. "
                "Reply ONLY with a valid JSON object — no explanation, no markdown fences.\n\n"
                f'Query: "{query}"\n\n'
                "JSON format:\n"
                '{"description": "...", "size": "..." or null, "max_price": number or null}\n\n'
                "Rules:\n"
                "- description: the clothing item being searched for (2-5 words)\n"
                "- size: one of XS/S/M/L/XL/XXL, or null if not mentioned\n"
                "- max_price: numeric price ceiling (e.g. 30.0), or null if not mentioned"
            )
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip("`\n ")
            parsed = json.loads(raw)
            return {
                "description": parsed.get("description", query),
                "size": parsed.get("size") or None,
                "max_price": float(parsed["max_price"]) if parsed.get("max_price") else None,
            }
        except Exception:
            pass  # Fall through to regex fallback

    # Regex fallback — works without an API key or if LLM fails
    size_match = re.search(r"\b(XS|S|M|L|XL|XXL)\b", query, re.IGNORECASE)
    price_match = re.search(r"\$?(\d+(?:\.\d+)?)", query)
    description = re.sub(r"\b(XS|S|M|L|XL|XXL)\b", "", query, flags=re.IGNORECASE)
    description = re.sub(
        r"(under|below|less than|max|up to)?\s*\$?\d+(\.\d+)?", "", description
    )
    description = re.sub(r"\b(size|sz)\b", "", description, flags=re.IGNORECASE)
    description = re.sub(r"\s{2,}", " ", description).strip(" ,.")

    return {
        "description": description or query,
        "size": size_match.group(1).upper() if size_match else None,
        "max_price": float(price_match.group(1)) if price_match else None,
    }


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
        wardrobe: User's wardrobe dict

    Returns:
        The session dict. Check session["error"] first — if not None,
        the interaction ended early and outfit_suggestion/fit_card will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query → description, size, max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed
    description = parsed.get("description", query)
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    # Step 3: Search listings — branch here if nothing found
    results = search_listings(description, size=size, max_price=max_price)
    session["search_results"] = results

    if not results:
        size_str = f" in size {size}" if size else ""
        price_str = f" under ${max_price}" if max_price else ""
        session["error"] = (
            f"No listings found for '{description}'{size_str}{price_str}. "
            "Try a broader description, a different size, or raise your budget."
        )
        return session  # STOP — do not call suggest_outfit or create_fit_card

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit using selected item + wardrobe
    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
    session["outfit_suggestion"] = outfit

    # Step 6: Create fit card using outfit suggestion + selected item
    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = fit_card

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        item = session["selected_item"]
        print(f"Found:    {item['title']} — ${item['price']} on {item['platform']} ({item['condition']})")
        print(f"Parsed:   {session['parsed']}")
        print(f"\nOutfit:   {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is:   {session2['fit_card']}")   # Must be None