# shopify/products_by_category.py
from core.utils import gentle_scroll, save_debug

async def extract_products_from_category(page, category: dict, limit: int = 30):
    category_name = category["name"]
    category_url = category["url"]
    category_desc = category.get("description", "")

    await page.goto(category_url, timeout=60000)
    await page.wait_for_timeout(2500)
    await gentle_scroll(page, steps=5, pause_ms=700)

    # 1) Find the H2 that starts with "Recommended"
    h2 = page.locator("h2.tw-text-heading-xl", has_text="Recommended").first
    if await h2.count() == 0:
        await save_debug(page, f"shopify_no_recommended_h2_{category_name}")
        print("[WARN] Could not find 'Recommended ... apps' header. Debug saved.")
        return []

    # 2) Container around that header
    container = h2.locator("xpath=ancestor::section[1]")
    if await container.count() == 0:
        container = h2.locator("xpath=..")

    # 3) Find app links inside container
    links = container.locator("a[href^='https://apps.shopify.com/']")

    if await links.count() == 0:
        sibling_section = h2.locator("xpath=ancestor::section[1]/following-sibling::*[1]")
        links = sibling_section.locator("a[href^='https://apps.shopify.com/']")

    if await links.count() == 0:
        await save_debug(page, f"shopify_no_links_in_recommended_{category_name}")
        print("[WARN] Found 'Recommended' header but no app links under it. Debug saved.")
        return []


    category_name = (category.get("name") or "").strip()
    category_url = (category.get("url") or "").strip()
    category_desc = (category.get("description") or "").strip()

    count_links = await links.count()
    seen = set()
    rows = []

    for i in range(count_links):
        a = links.nth(i)
        href = (await a.get_attribute("href")) or ""
        if not href.startswith("https://apps.shopify.com/"):
            continue

        slug_part = href.replace("https://apps.shopify.com/", "").split("?")[0].strip("/")
        slug = slug_part.split("/")[0].strip()

        if not slug or slug in {"categories", "pricing", "blog", "partners"}:
            continue

        product_url = f"https://apps.shopify.com/{slug}"
        if product_url in seen:
            continue
        seen.add(product_url)

        name = (await a.inner_text()) or ""
        name = name.strip()
        if not name or len(name) < 2:
            name = slug.replace("-", " ").title()

        rows.append({
            "Apps category": category_name,
            "apps_url": category_url,
            "description": category_desc,
            "Recommended products": name,
            "products_url": product_url,
            "Product_description": "",
            "Price": "",
            "rating": "",
            "reviews_count": ""
        })

        if len(rows) >= limit:
            break

    return rows
