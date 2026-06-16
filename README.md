# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.


## README

# FitFindr — Secondhand Shopping & Outfit Coordinator

FitFindr is an orchestration-driven AI agent designed to streamline the secondhand shopping and fashion coordination experience. The system accepts natural language shopping queries, matches them against a local mock item catalog, cross-references findings with the user's available wardrobe, and generates automated social media style captions ("fit cards").

---

## 🛠️ Tool Inventory

FitFindr orchestrates three discrete backend tools, which communicate explicitly through a centralized state configuration:

### 1. `search_listings`
* **Inputs:** * `description` (`str`): Target clothing characteristics or keywords.
  * `size` (`str | None`, optional): Desired size dimension (e.g., `"M"`).
  * `max_price` (`float | None`, optional): Strict price ceiling.
* **Outputs:** `list[dict]` (A scored and filtered array of matched product dictionaries).
* **Purpose:** Queries the internal JSON catalog database, filters parameters sequentially (by price ceiling and item size), and uses keyword vector counting across titles, descriptions, and tag structures to calculate relevance scores.

### 2. `suggest_outfit`
* **Inputs:**
  * `new_item` (`dict`): Product dictionary isolated by the search tool.
  * `wardrobe` (`dict`): The target user's current inventory dictionary.
* **Outputs:** `str` (Custom markdown-formatted styling recommendation text).
* **Purpose:** Calls the Large Language Model (`llama-3.3-70b-versatile`) to form contextual outfit combinations by explicitly naming matching wardrobe items.

### 3. `create_fit_card`
* **Inputs:**
  * `outfit` (`str`): Text generation produced from `suggest_outfit`.
  * `new_item` (`dict`): Original product listing metadata dictionary.
* **Outputs:** `str` (Social-ready presentation caption).
* **Purpose:** Synthesizes the overall styling recommendation text into a 2–3 sentence social media caption utilizing high-temperature settings for distinct lexical variety.

---

## 🔄 How the Planning Loop Works

The system architecture utilizes a sequential execution track guarded by strict early-exit conditional branching.

# FitFindr Processing Flow

```text
[User Input Query]
        |
        v
+------------------+
|  _parse_query()  |
+------------------+
        |----------------------> Extracts Parameters
        |
        v
+------------------+
| search_listings  |
+------------------+
        |----------------------> Evaluates Catalog Results
        |
        v
   +-------------------+
   | Results Returned? |
   +-------------------+
      /           \
     /             \
 Empty []       Matches Found
    |                |
    v                v
+----------------+   +-----------------------------+
| Record Error   |   | selected_item = array[0]   |
| & HALT         |   +-----------------------------+
+----------------+
    |
    v
Early Return
Interrupt

                 |
                 v
+------------------+
| suggest_outfit   |
+------------------+
        |
        |----------------------> Evaluates Wardrobe State
        |
        v
+------------------+
| create_fit_card  |
+------------------+
        |
        |----------------------> Generates Caption Content
        |
        v
[Compile Session]
```

---

## Pipeline Summary

1. **Extraction:** The user's query string is processed into structured parameters.
2. **Evaluation:** `search_listings` applies filters and retrieves catalog matches.
3. **Conditional Guard:**
   - **If the results list is empty (`[]`):**
     - Record an error.
     - Halt execution.
     - Return early.
   - **If results contain matches:**
     - Select the highest-ranked catalog entry.
     - Assign it to `selected_item = array[0]`.
4. **Outfit Generation:** `suggest_outfit` evaluates the user's wardrobe state and generates a recommendation.
5. **Fit Card Creation:** `create_fit_card` produces the final caption and presentation content.
6. **Session Compilation:** All generated artifacts are stored in the session state.

---

## State Management Approach

FitFindr manages workflow state through a centralized session dictionary:

```python
session = {
    "query": str,            # Original natural-language user search string
    "parsed": dict,          # Parsed description, size, and budget constraints
    "search_results": list,  # Catalog matches returned from search_listings
    "selected_item": dict,   # Highest-ranked listing passed downstream
    "wardrobe": dict,        # Current user wardrobe/inventory state
    "outfit_suggestion": str,# Recommendation generated by suggest_outfit
    "fit_card": str,         # Final formatted caption/content
    "error": str | None      # Error tracking and containment
}
```

### State Lifecycle

```text
query
  ↓
parsed
  ↓
search_results
  ↓
selected_item
  ↓
outfit_suggestion
  ↓
fit_card
  ↓
compiled session
```

### Error Handling

```text
search_results == []
        |
        v
session["error"] = "No matching catalog entries found"
        |
        v
HALT
```

### Success Path

```text
search_results != []
        |
        v
selected_item = search_results[0]
        |
        v
suggest_outfit()
        |
        v
create_fit_card()
        |
        v
session compiled successfully
```


