from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def _scrape_with_httpx(url: str, timeout: int) -> dict[str, Any]:
    """Fast scrape using httpx — no browser needed."""
    response = httpx.get(
        url,
        headers=HEADERS,
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    html = response.text

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"]

    # Extract visible text
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    body_text = soup.body.get_text(separator=" ", strip=True) if soup.body else soup.get_text(separator=" ", strip=True)
    body_text = " ".join(body_text.split())[:4000]

    return {
        "title": title,
        "description": description,
        "body_text": body_text,
        "html": html[:100_000],  # Cap HTML to 100KB to save memory
        "url": url,
        "screenshot_path": "",
        "scraped_at": datetime.utcnow().isoformat(),
    }


def _capture_screenshot_playwright(url: str, competitor_id: int) -> str:
    """Optional: take a screenshot using Playwright (only when enabled)."""
    try:
        from playwright.sync_api import sync_playwright

        screenshot_dir = os.path.join(settings.MEDIA_ROOT, "screenshots", str(competitor_id))
        os.makedirs(screenshot_dir, exist_ok=True)
        filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(screenshot_dir, filename)
        relative_path = f"screenshots/{competitor_id}/{filename}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.screenshot(path=filepath, full_page=True)
            browser.close()
        logger.info("Screenshot saved: %s", filepath)
        return relative_path
    except Exception as exc:
        logger.warning("Screenshot capture failed for %s: %s", url, exc)
        return ""


def _scrape_with_playwright(url: str, timeout: int) -> dict[str, Any]:
    """Fallback scrape using Playwright (useful for pages that block standard HTTP requests)."""
    from playwright.sync_api import sync_playwright

    logger.info("SCRAPER: Attempting Playwright fallback for %s", url)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        # Bypassing Cloudflare/WAF block headers
        page.set_extra_http_headers(HEADERS)
        
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        html = page.content()
        title = page.title().strip() if page.title() else ""

        soup = BeautifulSoup(html, "html.parser")
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = meta_desc["content"]

        # Extract visible text
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        body_text = soup.body.get_text(separator=" ", strip=True) if soup.body else soup.get_text(separator=" ", strip=True)
        body_text = " ".join(body_text.split())[:4000]

        browser.close()

    return {
        "title": title,
        "description": description,
        "body_text": body_text,
        "html": html[:100_000],  # Cap HTML to 100KB to save memory
        "url": url,
        "screenshot_path": "",
        "scraped_at": datetime.utcnow().isoformat(),
    }


def scrape_page(url: str, competitor_id: int = 0) -> dict[str, Any]:
    """
    Scrape a competitor page.
    Uses httpx (fast, lightweight) by default.
    Optionally captures screenshots via Playwright if ENABLE_SCREENSHOTS=True.
    Falls back to Playwright if httpx is blocked (e.g. 403) or encounters an error.
    """
    timeout = getattr(settings, "SCRAPER_TIMEOUT", 15)

    try:
        result = _scrape_with_httpx(url, timeout)
        logger.info("SCRAPER: scraped %d chars from %s", len(result["body_text"]), url)

        # Optional screenshot (only if enabled — requires Playwright)
        if competitor_id and getattr(settings, "ENABLE_SCREENSHOTS", False):
            result["screenshot_path"] = _capture_screenshot_playwright(url, competitor_id)

        return result

    except httpx.HTTPStatusError as exc:
        logger.error("HTTP %s from %s using httpx. Trying Playwright fallback...", exc.response.status_code, url)
        try:
            result = _scrape_with_playwright(url, timeout)
            logger.info("SCRAPER (Playwright fallback): scraped %d chars from %s", len(result["body_text"]), url)
            if competitor_id and getattr(settings, "ENABLE_SCREENSHOTS", False):
                result["screenshot_path"] = _capture_screenshot_playwright(url, competitor_id)
            return result
        except Exception as fallback_exc:
            logger.error("Playwright fallback also failed: %s", fallback_exc)
            return {"error": f"HTTP {exc.response.status_code}: {exc}. Playwright fallback also failed: {fallback_exc}", "url": url}
    except Exception as exc:
        logger.warning("Error scraping %s with httpx: %s. Trying Playwright fallback...", url, exc)
        try:
            result = _scrape_with_playwright(url, timeout)
            logger.info("SCRAPER (Playwright fallback): scraped %d chars from %s", len(result["body_text"]), url)
            if competitor_id and getattr(settings, "ENABLE_SCREENSHOTS", False):
                result["screenshot_path"] = _capture_screenshot_playwright(url, competitor_id)
            return result
        except Exception as fallback_exc:
            logger.error("Playwright fallback also failed for %s: %s", url, fallback_exc)
            return {"error": f"Scraping failed: {exc}. Playwright fallback also failed: {fallback_exc}", "url": url}
