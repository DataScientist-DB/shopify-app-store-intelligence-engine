# shopify/apps_extractor.py
from core.utils import gentle_scroll, save_debug

def extract_shopify_apps_from_category(page, category_url: str, limit: int = 20):
    page.goto(category_url, timeout=60000)
    page.wait_for_timeout(2500)
    gentle_scroll(page, steps=5, pause_ms=700)

    apps = []
    seen = set()

    links = page.locator("a[href^='https://apps.shopify.com/']")
    total = links.count()

    if total == 0:
        save_debug(page, f"shopify_no_links_{category_url}")
        print("[WARN] Found 0 Shopify app links. Debug saved.")
        return []

    for i in range(total):
        a = links.nth(i)

        href = a.get_attribute("href") or ""
        if not href.startswith("https://apps.shopify.com/"):
            continue

        # Extract slug
        slug_part = href.replace("https://apps.shopify.com/", "").split("?")[0].strip("/")
        slug = slug_part.split("/")[0].strip()

        # Skip non-app urls
        if not slug or slug in {"categories", "pricing", "blog", "partners"}:
            continue

        app_url = f"https://apps.shopify.com/{slug}"
        if app_url in seen:
            continue
        seen.add(app_url)

        # Get visible text if any
        name = (a.inner_text() or "").strip()

        # Fallback name from slug
        if not name:
            name = slug.replace("-", " ").title()

        # shopify/apps_extractor.py (inside the loop where you append apps)

        # derive a readable category from the category URL
        category = category_url.split("/categories/")[-1].strip("/").replace("-", " ").title()

        # shopify/apps_extractor.py (inside the loop where you append apps)

        # derive a readable category from the category URL
        category = category_url.split("/categories/")[-1].strip("/").replace("-", " ").title()

        apps.append({
            "platform": "shopify",
            "category_url": category_url,
            "category": category,  # ✅ NEW
            "app_name": name,
            "app_url": app_url,
            "price": ""  # ✅ placeholder (will be filled later)
        })

        if len(apps) >= limit:
            break

    return apps
