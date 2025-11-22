"""
amazon_scraper.py
Simple Selenium-based Amazon product scraper.
Works on Amazon domains (e.g., amazon.com, amazon.in). 
Saves results to CSV.
"""

import time
import random 
import argparse
from urllib.parse import quote_plus, urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------
# Configuration / utilities
# ---------------------------
DEFAULT_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0.0.0 Safari/537.36")

def random_sleep(a=1.0, b=2.5):
    time.sleep(random.uniform(a, b))

# ---------------------------
# Browser setup
# ---------------------------
def start_driver(headless=True, user_agent=DEFAULT_USER_AGENT):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--user-agent={user_agent}")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # ✅ Correct way for Selenium 4+
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_window_size(1200, 900)
    return driver

# ---------------------------
# Parsing helpers
# ---------------------------
def parse_search_results(html, base_domain):
    soup = BeautifulSoup(html, "html.parser")
    products = []
    results = soup.select('div[data-asin][data-component-type="s-search-result"]')
    for r in results:
        asin = r.get("data-asin", "").strip()
        if not asin:
            continue
        # Title & link
        title_tag = r.select_one("h2 a.a-link-normal.a-text-normal") or r.select_one("h2 a")
        title = title_tag.get_text(strip=True) if title_tag else ""
        link = urljoin(base_domain, title_tag.get("href")) if title_tag and title_tag.get("href") else ""
        # Image
        img = r.select_one("img.s-image")
        img_url = img.get("src") if img else ""
        # Price
        price_whole = r.select_one(".a-price .a-price-whole")
        price_frac = r.select_one(".a-price .a-price-fraction")
        if price_whole:
            price = price_whole.get_text(strip=True) + (("." + price_frac.get_text(strip=True)) if price_frac else "")
        else:
            price_span = r.select_one("span.a-offscreen")
            price = price_span.get_text(strip=True) if price_span else ""
        # Rating & reviews
        rating_tag = r.select_one(".a-icon-alt")
        rating = rating_tag.get_text(strip=True) if rating_tag else ""
        reviews_tag = r.select_one("span.a-size-base")
        reviews = reviews_tag.get_text(strip=True) if reviews_tag else ""
        products.append({
            "asin": asin,
            "title": title,
            "link": link,
            "image": img_url,
            "price": price,
            "rating": rating,
            "reviews": reviews
        })
    return products

# ---------------------------
# Scraper main
# ---------------------------
def scrape_amazon(search_term, pages=1, domain="https://www.amazon.in", headless=True, delay=(2.0,4.0)):
    driver = start_driver(headless=headless)
    all_products = []
    try:
        for page in range(1, pages+1):
            q = quote_plus(search_term)
            search_url = f"{domain}/s?k={q}&page={page}"
            print(f"[+] Loading page {page}: {search_url}")
            driver.get(search_url)
            random_sleep(delay[0], delay[1])
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            random_sleep(0.5, 1.2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            random_sleep(0.5, 1.0)
            html = driver.page_source
            products = parse_search_results(html, domain)
            print(f"  -> Found {len(products)} results on page {page}")
            all_products.extend(products)
            random_sleep(delay[0]+0.5, delay[1]+1.0)
    finally:
        driver.quit()
    # Deduplicate
    seen = set()
    dedup = []
    for p in all_products:
        if p["asin"] and p["asin"] not in seen:
            dedup.append(p)
            seen.add(p["asin"])
    return dedup

# ---------------------------
# CLI / Export
# ---------------------------
def save_to_csv(items, filename="amazon_results.csv"):
    df = pd.DataFrame(items)
    df.to_csv(filename, index=False)
    print(f"[+] Saved {len(items)} items to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Amazon search scraper (Selenium)")
    parser.add_argument("query", help="Search query text (use quotes if spaces)")
    parser.add_argument("--pages", "-p", type=int, default=1, help="Number of search result pages to scrape")
    parser.add_argument("--domain", "-d", default="https://www.amazon.in", help="Amazon base domain")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")

    parser.add_argument("--out", "-o", default="amazon_results.csv", help="Output CSV filename")
    args = parser.parse_args()

    items = scrape_amazon(args.query, pages=args.pages, domain=args.domain, headless=args.headless, delay=(2.0,4.0))
    save_to_csv(items, filename=args.out)

if __name__ == "__main__":
    main()