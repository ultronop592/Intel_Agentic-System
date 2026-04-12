from __future__ import annotations

from datetime import datetime
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def scrape_page(url: str) -> dict[str, Any]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            title = page.title()
            description = page.locator("meta[name='description']").get_attribute("content") or ""
            body_text = page.locator("body").inner_text(timeout=30000)
            content = page.content()
            browser.close()
        return {
            "title": title,
            "description": description,
            "body_text": body_text,
            "html": content,
            "url": url,
            "scraped_at": datetime.utcnow().isoformat(),
        }
    except PlaywrightTimeoutError as exc:
        return {"error": f"Timed out while scraping page: {exc}", "url": url}
    except Exception as exc:
        return {"error": str(exc), "url": url}
