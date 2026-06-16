# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset and returns items that match the user's description, size, and maximum price. Results are scored and sorted by relevance based on how well the item's title, description, and style_tags match the search query.

**Input parameters:**
- `description` (str): A natural language description of the item the user is looking for (e.g. "vintage graphic tee", "floral midi skirt")
- `size` (str): The clothing size to filter by (e.g. "XS", "S", "M", "L", "XL"). Only listings matching this size are returned.
- `max_price` (float): The maximum price the user is willing to pay. Only listings with price <= max_price are returned.

**What it returns:**
A list of matching listing dictionaries sorted by relevance score (highest first). Each dict contains:
`id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list of str),
`size` (str), `condition` (str), `price` (float), `colors` (list of str), `brand` (str), `platform` (str).
Returns an empty list if no listings match all three filters.

**What happens if it fails or returns nothing:**
The agent tells the user: "No listings found for '[description]' in size [size] under $[max_price].
Try a broader description, a different size, or raise your budget." The agent stops — it does NOT
proceed to suggest_outfit with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrifted item and the user's current wardrobe, uses the LLM to suggest one or more
complete outfit combinations and explains how to style them, referencing specific wardrobe pieces by name.

**Input parameters:**
- `new_item` (dict): The listing dictionary returned by search_listings (must include title, description, colors, style_tags, category)
- `wardrobe` (dict): The user's wardrobe loaded from wardrobe_schema.json, containing keys: tops, bottoms, shoes, accessories — each a list of item dicts with name, color, and style fields

**What it returns:**
A string containing one or more outfit suggestions with specific styling advice. Each suggestion
references actual wardrobe pieces by name (e.g. "pair with your white high-waist jeans and Docs").
Returns a generic suggestion string if wardrobe is empty.

**What happens if it fails or returns nothing:**
If wardrobe is empty, the agent generates a general styling suggestion based only on the new item's
colors and style_tags, and informs the user: "No wardrobe provided — here's a general styling idea."
If the LLM call fails, the agent returns: "Could not generate outfit suggestion. Please try again."

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, casual, shareable caption describing a complete outfit — the kind of text someone
would post on Instagram or TikTok alongside an outfit photo. Every call with different inputs must
produce a different caption.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by suggest_outfit
- `new_item` (dict): The listing dict so the caption can reference the item's price, platform, title, and condition

**What it returns:**
A single string of 1–3 sentences written in casual first-person social media style. Must reference
the price and platform of the new_item. Must sound like something a real person would post, not a
product description.

**What happens if it fails or returns nothing:**
If outfit is missing or empty, the agent generates a minimal fit card using only the new_item fields:
"just copped this [title] from [platform] for $[price] 🔥". Informs user: "Fit card is simplified
because outfit suggestion was unavailable."

---

### Additional Tools (if any)

None for required features. See stretch features section if adding price comparison tool.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a sequential planning loop with conditional branches at each step:

```
Step 1: Parse the user query to extract description, size, max_price, and wardrobe info.
        Load wardrobe using get_example_wardrobe() if user described their wardrobe,
        or get_empty_wardrobe() if they did not.

Step 2: Call search_listings(description, size, max_price)
        → If results == [] :
              Set session["error"] = "No listings found"
              Return error message to user. STOP.
        → If results is not empty:
              Set session["selected_item"] = results[0]
              Continue to Step 3.

Step 3: Call suggest_outfit(session["selected_item"], session["wardrobe"])
        → If wardrobe is empty:
              Generate generic suggestion. Set session["outfit_suggestion"] = generic text.
              Continue to Step 4 with warning.
        → If LLM call fails:
              Set session["error"] = "Outfit suggestion failed"
              Return error message to user. STOP.
        → If success:
              Set session["outfit_suggestion"] = suggestion text.
              Continue to Step 4.

Step 4: Call create_fit_card(session["outfit_suggestion"], session["selected_item"])
        → If outfit_suggestion is missing:
              Generate minimal fit card from new_item only.
        → If success:
              Set session["fit_card"] = fit card text.
              Continue to Step 5.

Step 5: Return all session data to user:
        - Top listing details (title, price, platform, condition)
        - Outfit suggestion
        - Fit card
        Agent is DONE.
```

The agent never calls suggest_outfit or create_fit_card if search_listings returned nothing.
Each step only runs if the previous step succeeded or has a defined fallback.

---

## State Management

**How does information from one tool get passed to the next?**

The agent maintains a single session dictionary throughout the interaction. It is initialized at
the start and updated after each tool call:

```python
session = {
    "query": str,              # original user query string
    "description": str,        # extracted search description
    "size": str,               # extracted size
    "max_price": float,        # extracted max price
    "wardrobe": dict,          # loaded at session start, passed to suggest_outfit
    "search_results": list,    # full list returned by search_listings
    "selected_item": dict,     # results[0] — passed to suggest_outfit and create_fit_card
    "outfit_suggestion": str,  # returned by suggest_outfit — passed to create_fit_card
    "fit_card": str,           # returned by create_fit_card — shown to user
    "error": None              # set to error string if any tool fails
}
```

No tool receives raw user input directly after Step 1. All tools read from and write to session.
This ensures that if the user does not re-enter their wardrobe, it persists from the initial load.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "No listings found for '[description]' in size [size] under $[max_price]. Try a broader description or raise your budget." Agent stops — does not proceed to suggest_outfit. |
| suggest_outfit | Wardrobe is empty | Generate a general styling suggestion based only on the item's colors and style_tags. Inform user: "No wardrobe on file — here's a general styling idea based on the item alone." |
| create_fit_card | Outfit input is missing or incomplete | Generate a minimal caption using only new_item fields: title, price, platform. Inform user: "Fit card is simplified because outfit suggestion was unavailable." |

---

## Architecture

```
User Query (natural language)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                        Planning Loop                         │
│                                                             │
│  1. Parse query → extract description, size, max_price      │
│  2. Load wardrobe → session["wardrobe"]                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
            search_listings(description, size, max_price)
                           │
              ┌────────────┴────────────┐
              │                         │
         results=[]               results=[item,...]
              │                         │
    "No listings found"        session["selected_item"]
       → STOP                           │
                                        ▼
                      suggest_outfit(selected_item, wardrobe)
                                        │
                         ┌──────────────┴──────────────┐
                         │                              │
                  wardrobe={}                      wardrobe filled
                         │                              │
              generic suggestion               specific suggestion
                         │                              │
                         └──────────────┬──────────────┘
                                        │
                              session["outfit_suggestion"]
                                        │
                                        ▼
                    create_fit_card(outfit_suggestion, selected_item)
                                        │
                                        ▼
                              session["fit_card"]
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │         Final Output           │
                        │  - Listing: title, price,      │
                        │    platform, condition          │
                        │  - Outfit suggestion            │
                        │  - Fit card caption             │
                        └───────────────────────────────┘

Session State (shared across all steps):
{ query, description, size, max_price, wardrobe,
  search_results, selected_item, outfit_suggestion,
  fit_card, error }
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I will use Claude for all three tool implementations, giving it one tool at a time.

For `search_listings`: I will give Claude the Tool 1 spec (inputs, return value, failure mode) and
the data loader section, and ask it to implement the function using `load_listings()`. I will verify
by testing with 3 queries: one that returns results, one with no size match, and one where max_price
filters everything out.

For `suggest_outfit`: I will give Claude the Tool 2 spec and wardrobe_schema.json structure, and ask
it to implement the function using a Groq LLM call. I will verify by testing with a real wardrobe,
an empty wardrobe, and confirming the output references specific wardrobe pieces by name.

For `create_fit_card`: I will give Claude the Tool 3 spec and ask it to implement the function using
a Groq LLM call with a casual social media tone. I will verify that two different outfit inputs
produce two different captions, and that the price and platform of the item appear in the output.

**Milestone 4 — Planning loop and state management:**

I will give Claude the Planning Loop section, the State Management session dict, and the Architecture
ASCII diagram, and ask it to implement the main agent loop that calls tools in sequence and updates
session state. I will verify by running the complete interaction example end to end and checking that:
(1) state flows correctly between tools, (2) the agent stops early when search returns nothing, and
(3) the final output includes all three results.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Agent parses the query. Extracts: description="vintage graphic tee", size not specified (default to
no size filter or ask user), max_price=30.0. Detects wardrobe description: "baggy jeans and chunky
sneakers" → loads get_example_wardrobe() and notes those items. Calls:
`search_listings("vintage graphic tee", size=None, max_price=30.0)`
Returns 3 listings sorted by relevance. Sets session["selected_item"] = results[0]:
{"title": "Faded Band Tee", "price": 22.0, "platform": "Depop", "condition": "Good", ...}

**Step 2:**
Agent calls: `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`
Wardrobe contains baggy jeans, chunky sneakers, and other items.
Returns: "Pair this faded band tee with your wide-leg jeans and chunky sneakers for a 90s grunge
look. Roll the sleeves once and tuck the front corner slightly for shape."
Sets session["outfit_suggestion"] = above string.

**Step 3:**
Agent calls: `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`
Returns: "thrifted this faded band tee off depop for $22 and it was literally made for my wide-legs
🖤 full look in my stories"
Sets session["fit_card"] = above string.

**Final output to user:**
```
🔍 Found: Faded Band Tee — $22 on Depop (Good condition)

👗 How to style it:
Pair this faded band tee with your wide-leg jeans and chunky sneakers for a 90s grunge look.
Roll the sleeves once and tuck the front corner slightly for shape.

📱 Your fit card:
"thrifted this faded band tee off depop for $22 and it was literally made for my wide-legs 🖤
full look in my stories"
```
