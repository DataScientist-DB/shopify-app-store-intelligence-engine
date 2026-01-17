from __future__ import annotations

import io
import json
import re
import hashlib
import inspect
import os
from datetime import datetime
from pathlib import Path
from typing import Any, List

import pandas as pd
from apify import Actor

from core.browser import launch_browser
from shopify.products_by_category import extract_products_from_category
from shopify.product_detail import enrich_product_row


# -------------------------
# Paths (robust)
# -------------------------
SRC_DIR = Path(__file__).resolve().parent               # .../project/src
PROJECT_ROOT = SRC_DIR.parent                          # .../project
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_DIR = PROJECT_ROOT / "config"


# -------------------------
# Deploy / fingerprint
# -------------------------
def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def _print_fingerprint() -> None:
    try:
        marker_path = PROJECT_ROOT / "DEPLOY_MARKER.txt"
        if marker_path.exists():
            print("[DEPLOY]", marker_path.read_text(encoding="utf-8").strip())
        else:
            print("[DEPLOY] DEPLOY_MARKER.txt missing")
    except Exception:
        print("[DEPLOY] DEPLOY_MARKER.txt missing")

    print("[DEPLOY] main.py loaded")

    print("=== CLOUD FINGERPRINT START ===")
    print("CWD:", Path().resolve())
    print("SRC_DIR:", SRC_DIR)
    print("PROJECT_ROOT:", PROJECT_ROOT)

    mp = SRC_DIR / "main.py"
    try:
        print(
            "main.py lines=",
            mp.read_text(encoding="utf-8", errors="replace").count("\n") + 1,
            "sha12=",
            sha12(mp),
        )
    except Exception:
        pass

    py_files = sorted(SRC_DIR.rglob("*.py"))
    print("py files under src/:", len(py_files))
    for p in py_files[:30]:
        try:
            rel = p.relative_to(PROJECT_ROOT)
            lines = p.read_text(encoding="utf-8", errors="replace").count("\n") + 1
            print(f"- {rel} lines={lines} sha12={sha12(p)}")
        except Exception:
            pass

    print("=== CLOUD FINGERPRINT END ===")


_print_fingerprint()


# -------------------------
# Env helpers
# -------------------------
def _is_apify_env() -> bool:
    # True on Apify cloud and usually also inside `apify run` container
    return bool(os.getenv("APIFY_CONTAINER_PORT") or os.getenv("APIFY_IS_AT_HOME") or os.getenv("ACTOR_RUN_ID"))


def _force_headless_on_apify(inp: dict) -> dict:
    # Apify containers do not have a display → headless must be True.
    if _is_apify_env() or Actor.is_at_home():
        inp["headless"] = True
    return inp


def _get_int(d: dict, *keys, default: int) -> int:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            pass
    return int(default)


def _get_bool(d: dict, *keys, default: bool) -> bool:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("true", "1", "yes", "y"):
            return True
        if s in ("false", "0", "no", "n"):
            return False
    return bool(default)


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "category"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------
# NAV config
# -------------------------
def load_categories_from_nav(nav_config_path: Path) -> list[dict]:
    if not nav_config_path.exists():
        raise FileNotFoundError(
            f"Nav config not found: {nav_config_path}. "
            f"Expected config/shopify_nav.json under project root."
        )

    data = json.loads(nav_config_path.read_text(encoding="utf-8"))
    cats = data.get("categories") or []
    if not isinstance(cats, list) or not cats:
        raise ValueError(
            f"Nav config is invalid/empty: {nav_config_path}. Expected JSON like "
            f"{{'categories':[{{'name':'...', 'url':'...'}}]}}"
        )

    out: list[dict] = []
    for c in cats:
        name = (c.get("name") or "").strip()
        url = (c.get("url") or "").strip()
        desc = (c.get("description") or "").strip()
        if name and url:
            out.append({"name": name, "url": url, "description": desc})

    if not out:
        raise ValueError(f"No valid categories found in {nav_config_path}. Check name/url fields.")

    return out


def select_categories(all_categories: list[dict], selected_categories: list[Any], max_categories: int) -> list[dict]:
    if selected_categories:
        by_index = all(isinstance(x, int) for x in selected_categories)
        if by_index:
            picked: list[dict] = []
            for idx in selected_categories:
                i0 = idx - 1  # 1-based
                if 0 <= i0 < len(all_categories):
                    picked.append(all_categories[i0])
            cats = picked
        else:
            wanted = {str(x).strip().lower() for x in selected_categories}
            cats = [c for c in all_categories if c["name"].strip().lower() in wanted]
    else:
        cats = list(all_categories)

    if max_categories and max_categories > 0:
        cats = cats[:max_categories]

    return cats


def interactive_pick_categories(nav_path: Path) -> tuple[list[Any], int]:
    """
    Returns (selected_categories, max_categories).
    - max_categories is how many categories to scrape.
    - selected_categories can be [] meaning "take first N".
    """
    cats = load_categories_from_nav(nav_path)

    print("\n=== Shopify categories ===")
    for i, c in enumerate(cats, 1):
        desc = (c.get("description") or "").strip()
        if desc:
            print(f"{i}. {c['name']} — {desc}")
        else:
            print(f"{i}. {c['name']}")

    # Ask for max categories (N)
    while True:
        s = input("\nHow many categories do you want to scrape? (e.g., 1-7) : ").strip()
        if not s:
            # default to 1 if user just presses Enter
            n = 1
            break
        if s.isdigit() and int(s) > 0:
            n = int(s)
            break
        print("Please enter a positive number (e.g., 1, 2, 3...).")

    print("\nNow choose WHICH categories (optional):")
    print(" - Press Enter to scrape the FIRST N categories")
    print(" - Or type one number (e.g., 3)")
    print(" - Or multiple comma-separated (e.g., 1,3,7)")
    print(" - Or type names (exact match), comma-separated\n")

    s2 = input("Your choice (optional): ").strip()
    if not s2:
        return [], n  # empty => take first N

    parts = [p.strip() for p in s2.split(",") if p.strip()]
    out: list[Any] = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
        else:
            out.append(p)

    # Cap to N
    if len(out) > n:
        out = out[:n]
    return out, n

# Export helpers
# -------------------------
async def export_run_summary_to_kv(summary: dict, key: str = "RUN_SUMMARY.json") -> None:
    await Actor.set_value(
        key,
        json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / key).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Actor.log.info(f"[SUMMARY] Uploaded to KV Store and wrote local file: {OUTPUT_DIR / key}")


async def export_files_to_kv(
    results: list[dict],
    csv_key: str,
    xlsx_key: str,
    export_csv: bool,
    export_xlsx: bool,
) -> None:
    if not results:
        Actor.log.info("[EXPORT] No results -> skip file export")
        return

    df = pd.DataFrame(results)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if export_csv:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        await Actor.set_value(csv_key, csv_bytes, content_type="text/csv")
        (OUTPUT_DIR / csv_key).write_bytes(csv_bytes)

    if export_xlsx:
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="apps")

        await Actor.set_value(
            xlsx_key,
            xlsx_buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        (OUTPUT_DIR / xlsx_key).write_bytes(xlsx_buf.getvalue())

    Actor.log.info(f"[EXPORT] Done (csv={export_csv}, xlsx={export_xlsx}) keys=({csv_key}, {xlsx_key})")


# -------------------------
# Scraping logic
# -------------------------
async def scrape_shopify_category(page, category: dict, products_per_category: int) -> list[dict]:
    Actor.log.info(f"=== SHOPIFY CATEGORY: {category['name']} ===")
    rows = await extract_products_from_category(page, category, limit=products_per_category)

    out: list[dict] = []
    for row in rows:
        try:
            enriched = await enrich_product_row(page=page, row=row)
            out.append(enriched)
        except Exception as e:
            row2 = dict(row)
            row2["enrich_error"] = str(e)
            out.append(row2)
    return out


async def run_shopify_actor(inp: dict) -> None:
    inp = _force_headless_on_apify(inp)

    # ---- config merge (do NOT overwrite after merge) ----
    shopify_cfg_in = inp.get("shopify") or {}
    defaults = _load_json(CONFIG_DIR / "shopify.json")
    shopify_cfg = {**defaults, **shopify_cfg_in}

    limits_cfg = inp.get("limits") or {}
    output_cfg = inp.get("output") or {}

    # nav path (always project-root-relative)
    nav_path_str = shopify_cfg.get("nav_config_path") or shopify_cfg.get("navConfigPath") or "config/shopify_nav.json"
    nav_path = (PROJECT_ROOT / nav_path_str).resolve()
    shopify_cfg["nav_config_path"] = str(nav_path)

    nav_data = _load_json(nav_path) if nav_path.exists() else {}

    # effective settings
    headless = _get_bool(inp, "headless", default=_get_bool(nav_data, "headless", default=True))

    products_per_category = _get_int(
        shopify_cfg,
        "products_per_category",
        "productsPerCategory",
        default=_get_int(
            limits_cfg,
            "products_per_category",
            "productsPerCategory",
            default=_get_int(nav_data, "products_per_category", default=30),
        ),
    )

    max_categories = _get_int(limits_cfg, "maxCategories", "max_categories", default=1)

    selected_categories = (
        shopify_cfg.get("selected_categories")
        or shopify_cfg.get("selectedCategories")
        or []
    )

    export_csv = _get_bool(output_cfg, "export_csv", "exportCsv", default=True)
    export_xlsx = _get_bool(output_cfg, "export_xlsx", "exportXlsx", default=True)

    # proxy
    proxy_settings = inp.get("proxySettings") or inp.get("proxy_settings") or None
    proxy_cfg = None
    if proxy_settings:
        try:
            proxy_cfg = await Actor.create_proxy_configuration(proxy_settings)
        except Exception as e:
            Actor.log.warning(f"[PROXY] Failed to create proxy configuration: {e}")
            proxy_cfg = None

    Actor.log.info(f"[NAV] Loading categories from {nav_path}")
    all_categories = load_categories_from_nav(nav_path)
    categories = select_categories(all_categories, selected_categories, max_categories=max_categories)

    Actor.log.info(f"[NAV] selected_by_user={selected_categories}")
    Actor.log.info(
        f"[LIMITS] max_categories={max_categories} products_per_category={products_per_category} headless={headless}"
    )

    # output keys
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_csv_key = f"OUTPUT_{ts}.csv"
    combined_xlsx_key = f"OUTPUT_{ts}.xlsx"
    Actor.log.info(f"[OUTPUT] combined csv_key={combined_csv_key} xlsx_key={combined_xlsx_key}")

    # run
    pushed = 0
    seen_urls: set[str] = set()
    skipped_dupes = 0

    all_results_for_files: list[dict] = []
    category_stats: list[dict] = []
    generated_files: list[str] = []

    if (Actor.is_at_home() or _is_apify_env()) and inp.get("headless") is False:
        Actor.log.warning("[INPUT] headless=false provided; Apify requires headless=true. Forcing headless=true.")

    # launch browser (supports both signatures: with/without proxy_configuration)
    launch_params = inspect.signature(launch_browser).parameters
    kwargs = {"headless": headless}
    if "proxy_configuration" in launch_params:
        kwargs["proxy_configuration"] = proxy_cfg

    p = browser = context = page = None
    p, browser, context, page = await launch_browser(**kwargs)

    try:
        for cat in categories:
            apps = await scrape_shopify_category(page, cat, products_per_category)

            per_cat_results: list[dict] = []
            cat_slug = _slug(cat.get("name") or "category")

            for app_record in apps:
                url = (app_record.get("products_url") or app_record.get("product_url") or "").strip()
                if url:
                    if url in seen_urls:
                        skipped_dupes += 1
                        continue
                    seen_urls.add(url)

                await Actor.push_data(app_record)
                pushed += 1

                per_cat_results.append(app_record)
                all_results_for_files.append(app_record)

            # export per category
            if (export_csv or export_xlsx) and per_cat_results:
                per_cat_csv = f"OUTPUT_{cat_slug}_{ts}.csv"
                per_cat_xlsx = f"OUTPUT_{cat_slug}_{ts}.xlsx"

                await export_files_to_kv(
                    per_cat_results,
                    csv_key=per_cat_csv,
                    xlsx_key=per_cat_xlsx,
                    export_csv=export_csv,
                    export_xlsx=export_xlsx,
                )

                if export_csv:
                    generated_files.append(per_cat_csv)
                if export_xlsx:
                    generated_files.append(per_cat_xlsx)

                category_stats.append(
                    {
                        "category": cat.get("name"),
                        "items_exported": len(per_cat_results),
                        "csv": per_cat_csv if export_csv else None,
                        "xlsx": per_cat_xlsx if export_xlsx else None,
                    }
                )

        # combined export
        if (export_csv or export_xlsx) and all_results_for_files:
            await export_files_to_kv(
                all_results_for_files,
                csv_key=combined_csv_key,
                xlsx_key=combined_xlsx_key,
                export_csv=export_csv,
                export_xlsx=export_xlsx,
            )
            if export_csv:
                generated_files.append(combined_csv_key)
            if export_xlsx:
                generated_files.append(combined_xlsx_key)

    finally:
        try:
            if context:
                await context.close()
        except Exception:
            pass
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if p:
                await p.stop()
        except Exception:
            pass

    summary = {
        "timestamp": ts,
        "categories_selected": [c.get("name") for c in categories],
        "limits": {
            "max_categories": max_categories,
            "products_per_category": products_per_category,
        },
        "browser": {"headless_effective": True if (_is_apify_env() or Actor.is_at_home()) else headless},
        "dedupe": {"skipped_duplicates": skipped_dupes},
        "pushed_to_dataset": pushed,
        "per_category": category_stats,
        "combined": {
            "items_exported": len(all_results_for_files),
            "csv": combined_csv_key if export_csv else None,
            "xlsx": combined_xlsx_key if export_xlsx else None,
        },
        "files_generated": generated_files,
    }

    await export_run_summary_to_kv(summary, key=f"RUN_SUMMARY_{ts}.json")
    await export_run_summary_to_kv(summary, key="RUN_SUMMARY.json")

    Actor.log.info(f"[DEDUPE] skipped_duplicates={skipped_dupes}")
    Actor.log.info(f"[DONE] pushed_to_dataset={pushed}")
    Actor.log.info(f"[NAV] effective_categories={[c.get('name') for c in categories]}")


async def main() -> None:
    import sys

    async with Actor:
        inp = await Actor.get_input() or {}

        # local fallback: input.json at project root
        if not inp:
            p = PROJECT_ROOT / "input.json"
            if p.exists():
                inp = json.loads(p.read_text(encoding="utf-8"))
                Actor.log.info("[INPUT] Loaded local input.json fallback")

        # force safe mode on Apify
        inp = _force_headless_on_apify(inp)

        Actor.log.info(f"[INPUT] keys={list(inp.keys())}")

        # 🔹 ALWAYS ASK LOCALLY (never on Apify)
        if (not _is_apify_env()) and sys.stdin.isatty():
            shopify_cfg = inp.get("shopify") or {}
            nav_path_str = shopify_cfg.get("nav_config_path", "config/shopify_nav.json")
            nav_path = (PROJECT_ROOT / nav_path_str).resolve()

            picked, n = interactive_pick_categories(nav_path)

            inp.setdefault("shopify", {})
            inp["shopify"]["selected_categories"] = picked

            inp.setdefault("limits", {})
            inp["limits"]["maxCategories"] = int(n)

            Actor.log.info(
                f"[INTERACTIVE] maxCategories={n} selected_categories={picked}"
            )

        await run_shopify_actor(inp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
