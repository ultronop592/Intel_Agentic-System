from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def discover_pages(html: str, base_url: str) -> list[dict]:
    """
    Extract internal links from HTML and classify them into page types.
    Returns a list of dicts: [{"url": "...", "type": "..."}, ...]
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    
    discovered_urls = set()
    results = []

    keywords_mapping = {
        "pricing": ["pricing", "plans", "cost"],
        "features": ["features", "product", "platform", "capabilities"],
        "blog": ["blog", "news", "articles", "resources"],
        "about": ["about", "company", "team", "mission"],
        "careers": ["careers", "jobs", "hiring"],
    }

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        try:
            full_url = urljoin(base_url, href)
            parsed_full = urlparse(full_url)
            
            # Only internal links
            if parsed_full.netloc != base_domain:
                continue
                
            clean_url = f"{parsed_full.scheme}://{parsed_full.netloc}{parsed_full.path}"
            
            if clean_url in discovered_urls or clean_url == base_url:
                continue
                
            discovered_urls.add(clean_url)
            
            # Sub-page categorization
            path_lower = parsed_full.path.lower()
            page_type = "other"
            
            for p_type, keywords in keywords_mapping.items():
                if any(kw in path_lower for kw in keywords):
                    page_type = p_type
                    break
            
            if page_type != "other" or len(discovered_urls) < 15: # Arbitrary limit for high-value pages
                results.append({"url": clean_url, "type": page_type})
                
        except Exception:
            continue

    return results
