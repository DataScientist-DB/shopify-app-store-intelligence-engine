# core/utils.py
from pathlib import Path
import re

def ensure_dirs():
    Path("debug/html").mkdir(parents=True, exist_ok=True)
    Path("debug/screenshots").mkdir(parents=True, exist_ok=True)
    Path("output").mkdir(parents=True, exist_ok=True)

def slugify(text: str) -> str:
    text = re.sub(r"\s+", "-", (text or "").strip().lower())
    text = re.sub(r"[^a-z0-9\-]+", "", text)
    return text[:90] if text else "item"

async def save_debug(page, name: str):
    ensure_dirs()
    s = slugify(name)
    try:
        html = await page.content()
        Path(f"debug/html/{s}.html").write_text(html, encoding="utf-8")
    except Exception:
        pass
    try:
        await page.screenshot(path=f"debug/screenshots/{s}.png", full_page=True)
    except Exception:
        pass

async def gentle_scroll(page, steps=6, pause_ms=800):
    for _ in range(steps):
        await page.mouse.wheel(0, 1400)
        await page.wait_for_timeout(pause_ms)
