"""
tests/test_tools.py

Pytest tests for all three FitFindr tools.
Tests cover:
  - Happy-path behavior (expected results)
  - Each tool's specific failure mode (no results, empty wardrobe, missing outfit)
  - Edge cases (price boundary, None filters, whitespace-only outfit)

Run with:  pytest tests/
"""

import pytest
from unittest.mock import patch, MagicMock

from tools import search_listings, suggest_outfit, create_fit_card


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "L001",
    "title": "Faded Band Tee",
    "description": "Vintage-style faded graphic band tee with distressed edges.",
    "category": "tops",
    "style_tags": ["vintage", "graphic", "band tee", "grunge", "oversized"],
    "size": "M",
    "condition": "Good",
    "price": 22.0,
    "colors": ["black", "grey"],
    "brand": "Unknown",
    "platform": "Depop",
}

SAMPLE_WARDROBE = {
    "items": [
        {"name": "wide-leg jeans", "color": "light blue", "style": ["casual", "streetwear"]},
        {"name": "chunky white sneakers", "color": "white", "style": ["streetwear", "casual"]},
        {"name": "platform boots", "color": "black", "style": ["grunge", "edgy"]},
    ]
}

EMPTY_WARDROBE = {"items": []}

SAMPLE_OUTFIT = (
    "Pair this faded band tee with your wide-leg jeans and chunky white sneakers "
    "for a relaxed 90s grunge look. Tuck the front corner slightly for shape."
)


def _mock_groq_response(text: str):
    """Return a mock Groq API response object containing `text`."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = text
    return mock_response


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: search_listings
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchListings:

    def test_returns_results_for_matching_query(self):
        """A broad search for a common item should return at least one result."""
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_returns_list_of_dicts_with_expected_fields(self):
        """Each result should contain the required listing fields."""
        results = search_listings("tee", size=None, max_price=100)
        assert len(results) > 0
        required_fields = {"id", "title", "description", "price", "platform", "size"}
        for item in results:
            assert required_fields.issubset(item.keys()), f"Missing fields in: {item}"

    def test_failure_mode_returns_empty_list_not_exception(self):
        """Impossible query should return [] — never raise an exception."""
        results = search_listings("designer ballgown encrusted diamonds", size="XXS", max_price=1)
        assert results == []

    def test_price_filter_respected(self):
        """No returned item should exceed max_price."""
        results = search_listings("jacket", size=None, max_price=10)
        assert all(item["price"] <= 10 for item in results)

    def test_price_boundary_inclusive(self):
        """An item priced exactly at max_price should be included."""
        # Find the cheapest matching item, then set max_price to exactly that price
        all_results = search_listings("tee", size=None, max_price=9999)
        assert len(all_results) > 0, "Need at least one result to test boundary"
        boundary_price = min(item["price"] for item in all_results)
        results = search_listings("tee", size=None, max_price=boundary_price)
        assert any(item["price"] == boundary_price for item in results)

    def test_size_filter_respected(self):
        """All returned items should match the requested size."""
        results = search_listings("top", size="S", max_price=100)
        for item in results:
            assert "S" in item["size"].upper(), f"Size mismatch: {item['size']}"

    def test_size_none_skips_size_filter(self):
        """Passing size=None should not filter out any sizes."""
        results_no_filter = search_listings("tee", size=None, max_price=100)
        sizes = {item["size"] for item in results_no_filter}
        assert len(sizes) >= 1  # At minimum, results aren't artificially constrained

    def test_results_sorted_best_match_first(self):
        """The first result should be the most relevant to the query."""
        results = search_listings("vintage graphic tee", size=None, max_price=100)
        assert len(results) >= 2
        # The top result should contain more of the keywords than later ones
        # (We just verify the list is non-empty and first item has "graphic"/"vintage" signals)
        first_blob = (
            results[0]["title"] + " " +
            " ".join(results[0]["style_tags"])
        ).lower()
        assert "graphic" in first_blob or "vintage" in first_blob

    def test_zero_score_results_excluded(self):
        """Items with no keyword overlap should not appear in results."""
        results = search_listings("floral midi skirt", size=None, max_price=100)
        # None of these should be a cargo pant or denim jacket
        titles = [r["title"].lower() for r in results]
        assert not any("cargo" in t for t in titles)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: suggest_outfit
# ─────────────────────────────────────────────────────────────────────────────

class TestSuggestOutfit:

    def test_returns_string_with_filled_wardrobe(self):
        """Should return a non-empty string when wardrobe has items."""
        mock_text = "Pair this with your wide-leg jeans and chunky white sneakers for a 90s look."
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_text)
            )
            result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_filled_wardrobe_references_wardrobe_pieces(self):
        """Suggestion should mention specific wardrobe piece names."""
        mock_text = "Wear this with your wide-leg jeans and platform boots. Tuck the front."
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_text)
            )
            result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)

        # At least one wardrobe piece name should appear in the suggestion
        wardrobe_names = [w["name"] for w in SAMPLE_WARDROBE["items"]]
        assert any(name in result for name in wardrobe_names), (
            f"No wardrobe piece names found in suggestion: {result}"
        )

    def test_failure_mode_empty_wardrobe_returns_string(self):
        """Empty wardrobe should produce a string, not an exception or empty string."""
        mock_text = "This tee would look great with high-waisted trousers and chunky sneakers."
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_text)
            )
            result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_wardrobe_includes_disclaimer(self):
        """Empty wardrobe path should include a note explaining the general advice."""
        mock_text = "Great with wide-leg pants or baggy jeans."
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_text)
            )
            result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)

        assert "wardrobe" in result.lower() or "general" in result.lower(), (
            f"Expected disclaimer about missing wardrobe in: {result}"
        )

    def test_llm_error_returns_error_string_not_exception(self):
        """If the LLM call fails, return an error string — never crash."""
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.side_effect = (
                Exception("API timeout")
            )
            result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should communicate the failure, not be a normal suggestion
        assert "could not" in result.lower() or "error" in result.lower() or "try again" in result.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: create_fit_card
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateFitCard:

    def test_returns_string_for_valid_inputs(self):
        """Happy path: should return a non-empty string."""
        mock_caption = "thrifted this faded band tee off Depop for $22 and it's everything 🖤"
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_caption)
            )
            result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_caption_mentions_price_and_platform(self):
        """Fit card should reference the item's price and platform."""
        mock_caption = "found this band tee on Depop for $22 and honestly it slaps 🖤"
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.return_value = (
                _mock_groq_response(mock_caption)
            )
            result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)

        assert "22" in result or "$22" in result, f"Price not in caption: {result}"
        assert "Depop" in result or "depop" in result, f"Platform not in caption: {result}"

    def test_failure_mode_empty_outfit_returns_string_not_exception(self):
        """Empty outfit string should return a fallback caption, not crash."""
        result = create_fit_card("", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_failure_mode_whitespace_only_outfit(self):
        """Whitespace-only outfit string triggers the same fallback as empty."""
        result = create_fit_card("   ", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fallback_caption_includes_item_details(self):
        """Fallback caption (no outfit) should still mention title, price, platform."""
        result = create_fit_card("", SAMPLE_ITEM)
        assert "Depop" in result or "depop" in result
        assert "22" in result or "$22" in result

    def test_llm_error_returns_fallback_string(self):
        """LLM failure should return a fallback string, not raise."""
        with patch("tools._get_groq_client") as mock_client_fn:
            mock_client_fn.return_value.chat.completions.create.side_effect = (
                Exception("Rate limit")
            )
            result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)

        assert isinstance(result, str)
        assert len(result) > 0