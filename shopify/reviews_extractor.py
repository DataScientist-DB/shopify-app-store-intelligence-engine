# shopify/reviews_extractor.py
import json

import time
from core.utils import gentle_scroll, save_debug

import re

def extract_shopify_price(page) -> str:
    # Fast signals
    if page.locator("text=Free to install").count():
        return "Free to install"
    if page.locator("text=Free plan").count():
        return "Free plan"

    # Look for common pricing patterns in visible text (bounded)
    try:
        txt = page.locator("main").first.inner_text()
    except Exception:
        return ""

    m = re.search(r"(From\s*)?\$\s*\d+(?:\.\d+)?\s*(?:/|\sper\s)\s*(month|mo|year|yr)", txt, re.IGNORECASE)
    if m:
        return m.group(0).strip()

    m2 = re.search(r"(From\s*)?\$\s*\d+(?:\.\d+)?", txt, re.IGNORECASE)
    if m2:
        return m2.group(0).strip()

    return ""

def _safe_text(loc, default=""):
    try:
        return loc.first.inner_text().strip()
    except Exception:
        return default

def _extract_json_ld_reviews(page):
    """
    Many Shopify app pages include JSON-LD with aggregateRating and sometimes reviews.
    This is best-effort; not all pages include review objects.
    """
    out = []
    scripts = page.locator("script[type='application/ld+json']")
    for i in range(min(10, scripts.count())):
        raw = scripts.nth(i).inner_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        # JSON-LD can be dict or list
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            # reviews sometimes stored as "review"
            rv = it.get("review")
            if not rv:
                continue
            rv_list = rv if isinstance(rv, list) else [rv]
            for r in rv_list:
                if not isinstance(r, dict):
                    continue
                author = ""
                if isinstance(r.get("author"), dict):
                    author = r["author"].get("name", "") or ""
                elif isinstance(r.get("author"), str):
                    author = r.get("author", "") or ""

                rating = ""
                if isinstance(r.get("reviewRating"), dict):
                    rating = str(r["reviewRating"].get("ratingValue", "") or "")

                out.append({
                    "review_title": r.get("name", "") or "",
                    "review_text": r.get("reviewBody", "") or "",
                    "review_date": r.get("datePublished", "") or "",
                    "reviewer": author,
                    "rating": rating,
                    "source": "jsonld"
                })
    return out

def _click_reviews_tab_if_exists(page):
    # Try common buttons/links that bring reviews into view
    candidates = [
        "a[href*='#reviews']",
        "button:has-text('Reviews')",
        "a:has-text('Reviews')",
    ]
    for sel in candidates:
        loc = page.locator(sel)
        if loc.count():
            try:
                loc.first.click(timeout=2500)
                page.wait_for_timeout(1200)
                return True
            except Exception:
                pass
    return False

def extract_shopify_reviews(page, app, max_reviews=20, max_pages=3, time_budget_sec=25):
    reviews = []
    seen = set()
    start = time.time()

    try:
        page.goto(app["app_url"], timeout=60000)
        page.wait_for_timeout(2000)

        # ✅ Fill price once per app (so APPS gets it)
        if not app.get("price"):
            app["price"] = extract_shopify_price(page)

        # Ensure name
        if not app.get("app_name") or app["app_name"].strip() == "":
            app["app_name"] = _safe_text(page.locator("h1"), default="(unknown app)")

        # 1) JSON-LD first (fast)
        jsonld_reviews = _extract_json_ld_reviews(page)
        for r in jsonld_reviews:
            key = (r.get("review_title","") + "|" + r.get("review_text","")[:80]).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            reviews.append({
                "platform": "shopify",
                "app_name": app.get("app_name",""),
                "app_url": app.get("app_url",""),
                "category_url": app.get("category_url",""),
                "review_title": r.get("review_title",""),
                "review_text": r.get("review_text",""),
                "review_date": r.get("review_date",""),
                "reviewer": r.get("reviewer",""),
                "rating": r.get("rating",""),
                "source": r.get("source","jsonld"),
            })
            if len(reviews) >= max_reviews:
                return reviews

        # 2) Bring reviews into view (tab/anchor)
        _click_reviews_tab_if_exists(page)

        # 3) DOM fallback (bounded)
        gentle_scroll(page, steps=8, pause_ms=650)

        # try to narrow to reviews section
        scope = None
        scope_candidates = [
            "section:has-text('Reviews')",
            "[id*='reviews']",
            "div:has-text('Reviews')",
        ]
        for sel in scope_candidates:
            loc = page.locator(sel)
            if loc.count():
                scope = loc.first
                break

        for pidx in range(max_pages):
            if time.time() - start > time_budget_sec:
                print(f"  [TIMEOUT] Reviews time budget reached for: {app['app_name']}")
                break

            gentle_scroll(page, steps=3, pause_ms=600)

            base = scope if scope else page
            # tighter card guess: look for blocks containing star text + paragraph
            cards = base.locator("article, li, div").filter(has=base.locator("p"))

            scan_limit = min(120, cards.count())
            if scan_limit == 0 and pidx == 0 and not reviews:
                save_debug(page, f"shopify_no_review_cards_{app['app_name']}")
                break

            for i in range(scan_limit):
                if time.time() - start > time_budget_sec:
                    break

                c = cards.nth(i)
                body = _safe_text(c.locator("p"))
                if len(body) < 40:
                    continue

                title = _safe_text(c.locator("h3, h4"))
                date = _safe_text(c.locator("time"))
                reviewer = _safe_text(c.locator("strong, b, a"))
                rating = ""
                # read aria-label stars if present
                aria = ""
                try:
                    aria = c.locator("[aria-label*='out of 5'], [aria-label*='stars']").first.get_attribute("aria-label") or ""
                except Exception:
                    pass
                m = re.search(r"([0-5](?:\.\d)?)", aria)
                if m:
                    rating = m.group(1)

                key = (title + "|" + body[:90]).strip()
                if not key or key in seen:
                    continue
                seen.add(key)

                reviews.append({
                    "platform": "shopify",
                    "app_name": app.get("app_name",""),
                    "app_url": app.get("app_url",""),
                    "category_url": app.get("category_url",""),
                    "review_title": title,
                    "review_text": body,
                    "review_date": date,
                    "reviewer": reviewer,
                    "rating": rating,
                    "source": "dom",
                })

                if len(reviews) >= max_reviews:
                    return reviews

            # If there is a "Load more" inside reviews, click it (common)
            load_more = page.locator("button:has-text('Load more'), a:has-text('Load more')").first
            # if no “Reviews” keyword visible quickly, skip DOM scan
            if page.locator("text=Reviews").count() == 0:
                return reviews

            if load_more.count():
                try:
                    load_more.click(timeout=3000)
                    page.wait_for_timeout(1500)
                    continue
                except Exception:
                    pass

            # Next page (rare)
            next_btn = page.locator("a:has-text('Next'), button:has-text('Next')").first
            if next_btn.count() == 0:
                break
            try:
                next_btn.click(timeout=3000)
                page.wait_for_timeout(1500)
            except Exception:
                break

        return reviews

    except Exception:
        save_debug(page, f"shopify_reviews_error_{app.get('app_name','app')}")
        return reviews
