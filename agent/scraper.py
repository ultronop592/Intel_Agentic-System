from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from django.conf import settings
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def capture_screenshot(url: str, competitor_id: int) -> str:
    """Take a full-page screenshot and return the relative path from MEDIA_ROOT."""
    screenshot_dir = os.path.join(settings.MEDIA_ROOT, "screenshots", str(competitor_id))
    os.makedirs(screenshot_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(screenshot_dir, filename)
    relative_path = f"screenshots/{competitor_id}/{filename}"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=filepath, full_page=True)
            browser.close()
        logger.info("Screenshot saved: %s", filepath)
        return relative_path
    except Exception as exc:
        logger.warning("Screenshot capture failed for %s: %s", url, exc)
        return ""


def scrape_page(url: str, competitor_id: int = 0) -> dict[str, Any]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = page.title()
            
            description = ""
            try:
                description = page.locator("meta[name='description']").get_attribute("content") or ""
            except Exception:
                pass
                
            content = page.content()
            
            # Capture screenshot in the same browser session
            screenshot_path = ""
            if competitor_id:
                try:
                    screenshot_dir = os.path.join(settings.MEDIA_ROOT, "screenshots", str(competitor_id))
                    os.makedirs(screenshot_dir, exist_ok=True)
                    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                    filepath = os.path.join(screenshot_dir, filename)
                    page.screenshot(path=filepath, full_page=True)
                    screenshot_path = f"screenshots/{competitor_id}/{filename}"
                    logger.info("Screenshot saved: %s", filepath)
                except Exception as exc:
                    logger.warning("Screenshot failed: %s", exc)

            try:
                body_text = page.inner_text('body', timeout=10000)
            except Exception:
                logger.warning("inner_text failed, falling back to BeautifulSoup")
                soup = BeautifulSoup(content, 'html.parser')
                body_text = soup.body.get_text(separator=' ', strip=True) if soup.body else soup.get_text(separator=' ', strip=True)

            browser.close()
            
        body_text = body_text[:4000]
        print(f"SCRAPER: len(scraped_text) = {len(body_text)}")
        
        return {
            "title": title,
            "description": description,
            "body_text": body_text,
            "html": content,
            "url": url,
            "screenshot_path": screenshot_path,
            "scraped_at": datetime.utcnow().isoformat(),
        }
    except PlaywrightTimeoutError as exc:
        logger.error(f"Timed out while scraping page {url}: {exc}")
        return {"error": f"Timed out while scraping page: {exc}", "url": url}
    except Exception as exc:
        logger.error(f"Error while scraping page {url}: {exc}")
        return {"error": str(exc), "url": url}
