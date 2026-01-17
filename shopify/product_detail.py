# shopify/product_detail.py
import re
from datetime import datetime

from core.utils import gentle_scroll


def _to_float(s: str):
    if s is None:
        return None
    s = str(s).strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", "."))
    return float(m.group(1)) if m else None


def _to_int(s: str):
    if s is None:
        return None
    s = str(s).strip()
    s2 = s.replace(",", "").replace(" ", "")
    m = re.search(r"(\d+)", s2)
    return int(m.group(1)) if m else None


async def _safe_text(loc, default=""):
    try:
        return (await loc.first.inner_text()).strip()
    except Exception:
        return default


async def _safe_attr(loc, attr, default=""):
    try:
        v = await loc.first.get_attribute(attr)
        return v.strip() if v else default
    except Exception:
        return default


async def _extract_developer_info(page):
    developer_name = None
    developer_website = None

    try:
        dt = page.locator("dt", has_text="Developer").first
        if await dt.count() == 0:
            return None, None

        dd = dt.locator("xpath=following-sibling::dd[1]").first
        if await dd.count() == 0:
            return None, None

        a = dd.locator("a").first
        if await a.count() > 0:
            developer_name = (await _safe_text(a, "") or "").strip() or None
            developer_website = await a.get_attribute("href")
        else:
            developer_name = (await _safe_text(dd, "") or "").strip() or None

    except Exception:
        return None, None

    return developer_name, developer_website


async def _extract_shopify_rating_and_reviews(page):
    rating = None
    reviews_count = None

    try:
        aria = await _safe_attr(page.locator("[aria-label*='out of 5'], [aria-label*='stars']"), "aria-label")
        if aria:
            rating = _to_float(aria)
    except Exception:
        pass

    candidate_selectors = [
        "main",
        "header",
        "[data-testid*='reviews']",
        "[class*='Reviews']",
        "[class*='reviews']",
        "[class*='rating']",
    ]

    texts = []
    for sel in candidate_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                t = await loc.inner_text(timeout=1500)
                if t:
                    texts.append(t)
        except Exception:
            pass

    blob = "\n".join(texts)

    m = re.search(r"(\d(?:\.\d)?)\s*\(\s*([\d,\s]+)\s*(?:reviews|review)?\s*\)", blob, re.IGNORECASE)
    if m:
        rating = rating if rating is not None else _to_float(m.group(1))
        reviews_count = _to_int(m.group(2))

    if reviews_count is None:
        m2 = re.search(r"([\d,\s]+)\s*reviews?\b", blob, re.IGNORECASE)
        if m2:
            reviews_count = _to_int(m2.group(1))

    return rating, reviews_count


async def _extract_price(page) -> str:
    if await page.locator("text=Free to install").count():
        return "Free to install"
    if await page.locator("text=Free plan").count():
        return "Free plan"

    try:
        txt = await page.locator("main").first.inner_text()
    except Exception:
        return ""

    m = re.search(r"(From\s*)?\$\s*\d+(?:\.\d+)?\s*(?:/|\sper\s)\s*(month|mo|year|yr)", txt, re.IGNORECASE)
    if m:
        return m.group(0).strip()

    m2 = re.search(r"(From\s*)?\$\s*\d+(?:\.\d+)?", txt, re.IGNORECASE)
    if m2:
        return m2.group(0).strip()

    return ""


async def _extract_description(page) -> str:
    meta = page.locator("meta[name='description']")
    if await meta.count():
        c = await meta.first.get_attribute("content") or ""
        c = c.strip()
        if c:
            return c

    p = page.locator("main p").first
    return await _safe_text(p, "")


async def enrich_product_row(page, row: dict, time_budget_sec: int = 12) -> dict:
    await page.goto(row["products_url"], timeout=60000)
    await page.wait_for_timeout(1800)
    await gentle_scroll(page, steps=2, pause_ms=500)

    # Developer info
    try:
        developer_name, developer_website = await _extract_developer_info(page)
        row["developer_name"] = developer_name
        row["developer_website"] = developer_website
    except Exception:
        row["developer_name"] = None
        row["developer_website"] = None

    # Reviews
    try:
        rating, reviews_count = await _extract_shopify_rating_and_reviews(page)
        row["rating"] = rating
        row["reviews_count"] = reviews_count
        row["reviews_source"] = "shopify_app_store"
        row["reviews_scraped_at"] = datetime.utcnow().isoformat() + "Z"
    except Exception as e:
        row["rating"] = None
        row["reviews_count"] = None
        row["reviews_source"] = "shopify_app_store"
        row["reviews_scrape_error"] = repr(e)

    # Basic details
    row["Product_description"] = await _extract_description(page)
    row["Price"] = await _extract_price(page)

    return row
