from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


def _is_apify_env() -> bool:
    # Works in Apify cloud + also when running via `apify run` locally
    return bool(os.getenv("APIFY_CONTAINER_PORT")) or bool(os.getenv("APIFY_IS_AT_HOME"))


async def launch_browser(headless: bool = True) -> Tuple[Playwright, Browser, BrowserContext, Page]:
    """
    Safe Chromium launcher for local + Apify:
    - Forces headless=True on Apify (no GUI in containers).
    - Adds container-friendly flags.
    """
    p = await async_playwright().start()

    effective_headless = True if _is_apify_env() else bool(headless)

    launch_kwargs: Dict[str, Any] = {
        "headless": effective_headless,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }

    browser = await p.chromium.launch(**launch_kwargs)
    context = await browser.new_context()
    page = await context.new_page()
    return p, browser, context, page


async def close_browser(p: Playwright, browser: Browser) -> None:
    try:
        await browser.close()
    finally:
        await p.stop()
