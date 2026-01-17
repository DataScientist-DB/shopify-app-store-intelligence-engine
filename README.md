# Shopify App Store Scraper & Intelligence Engine

Scrape the Shopify App Store by category and generate a structured, analytics-ready dataset of Shopify apps, enriched with business and intelligence signals such as developer details, pricing, ratings, and review metadata.
This Actor is Apify-safe, non-interactive, and designed for automation, market research, and competitive analysis.
 
🚀 What this Actor does
For selected Shopify App Store categories, the Actor:
•	Crawls category listing pages
•	Extracts app-level metadata
•	Enriches records with business and review signals
•	Normalizes results into a clean tabular dataset
•	Exports results to Apify Dataset, CSV, and XLSX
No scraping knowledge required — configure inputs and run.
________________________________________
🎯 Typical use cases
•	Shopify app market research
•	Competitive intelligence & benchmarking
•	Shopify ecosystem analysis
•	Lead discovery for agencies and SaaS companies
•	Trend, pricing, and category analysis
________________________________________
⚡ Quick start (default run)
Run the Actor with default settings (safe and fast):
{}
This will:
•	Scrape a small subset of Shopify categories
•	Extract basic app metadata
•	Create an Apify Dataset
•	Export OUTPUT.csv and OUTPUT.xlsx
________________________________________
🧭 How category selection works (IMPORTANT)
Category source (single source of truth)
All available categories are defined internally in:
config/shopify_nav.json
The Actor always reads categories from this file.
________________________________________
Category list (current)
The Shopify App Store categories are mapped as follows:
1) Sales channels
2) Selling products apps
3) Store design apps
4) Store management apps
5) Finding products apps
6) Orders and shipping apps
7) Marketing and conversion apps
You do not edit this list in the input.
You choose from it using numbers.
________________________________________
Two inputs control category scraping
You control category scraping using two complementary inputs:
1️⃣ shopify.selected_categories → Which categories
A list of category numbers from the list above.
2️⃣ limits.maxCategories → How many categories (quantity cap)
A hard limit on how many categories will be processed in this run.
This prevents accidental large runs.
________________________________________
🧪 Example inputs (most important section)
Example 1 — Scrape first 2 categories (no selection)
{
  "limits": {
    "maxCategories": 2
  },
  "shopify": {
    "selected_categories": []
  }
}
➡️ Result: categories 1 and 2 are scraped.
________________________________________
Example 2 — Scrape specific categories (by number)
{
  "limits": {
    "maxCategories": 2
  },
  "shopify": {
    "selected_categories": [3, 7]
  }
}
➡️ Result:
•	Store design apps
•	Marketing and conversion apps
Only 2 categories, even if more are listed.
________________________________________
Example 3 — Scrape one category with more apps
{
  "limits": {
    "maxCategories": 1
  },
  "shopify": {
    "selected_categories": [5],
    "products_per_category": 20
  }
}
➡️ Result:
•	Only Finding products apps
•	Up to 20 apps from that category
________________________________________
Example 4 — Safety behavior (important)
{
  "limits": {
    "maxCategories": 1
  },
  "shopify": {
    "selected_categories": [2, 4, 6]
  }
}
➡️ Result:
Only the first category from the selection is scraped (2).
________________________________________
⚙️ Input configuration overview
Input block	Purpose
shopify	Select categories and per-category volume
limits	Safety limits for total categories
output	Export format (CSV / XLSX)
proxySettings	Proxy configuration (recommended)
________________________________________
⚙️ shopify block
Controls Shopify App Store scraping behavior.
{
  "shopify": {
    "nav_config_path": "config/shopify_nav.json",
    "products_per_category": 10,
    "selected_categories": [1, 3]
  }
}
Parameters
Field	Description
nav_config_path	Path to category navigation config (usually keep default)
products_per_category	Maximum apps to scrape per category
selected_categories	Category numbers to scrape (empty = first maxCategories)
________________________________________
⚙️ limits block
Controls how many categories are processed.
{
  "limits": {
    "maxCategories": 2
  }
}
Field	Description
maxCategories	Maximum number of categories to scrape in this run
________________________________________
📤 Outputs
✅ Apify Dataset (primary output)
Each scraped app is saved as one dataset item.
Example:
{
  "category": "Store design apps",
  "app_name": "PageFly Landing Page Builder",
  "app_url": "https://apps.shopify.com/pagefly",
  "short_description": "Create high-converting landing pages",
  "developer_name": "PageFly",
  "developer_website": "https://pagefly.io",
  "price": "Free plan available",
  "rating": 4.9,
  "reviews_count": 6500,
  "reviews_source": "Shopify App Store",
  "scraped_at": "2026-01-06T14:32:11Z"
}
Dataset items can be:
•	Viewed in Apify Console
•	Exported to JSON / CSV / XLSX via UI or API
________________________________________
✅ Key-Value Store exports
At the end of each run, the Actor also saves:
File	Description
OUTPUT.csv	Tabular app data (CSV)
OUTPUT.xlsx	Excel-formatted output
These files are downloadable directly from the Key-Value Store.
________________________________________
📑 Output fields
Typical fields include (availability depends on app):
•	category
•	app_name
•	app_url
•	short_description
•	full_description
•	developer_name
•	developer_website
•	price
•	rating
•	reviews_count
•	reviews_source
•	scraped_at
Missing values are left empty if data is not publicly available.
________________________________________
▶️ How to run
On Apify
1.	Open the Actor in Apify Console
2.	Click Run
3.	Adjust input (categories & limits)
4.	Wait for completion
5.	Download results from Dataset or Key-Value Store
Locally (optional)
apify run
 
🧠 Technical notes
•	Built with Python + Playwright
•	Uses Apify SDK Dataset for structured output
•	Uses Key-Value Store for CSV / XLSX exports
•	Designed to be:
o	non-interactive
o	automation-safe
o	Apify Store–ready
 
⚠️ Limitations
•	Shopify UI and selectors may change over time
•	Rate limits or bot detection may affect coverage
•	Some apps do not expose all metadata
•	Results are best-effort based on public Shopify data
 
📜 License & usage
Use responsibly and in compliance with:
•	Shopify Terms of Service
•	Local data protection regulations
Maintained by Adinfosys Labs.

