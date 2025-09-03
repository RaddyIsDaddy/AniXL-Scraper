import json
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# === Setup ===
INPUT_FILE = "input.json"
OUTPUT_FILE = "output.json"
DRIVER_PATH = r"C:\Users\Administrator\Desktop\chromedriver-win64\chromedriver.exe"
BASE_URL = "https://anixl.to"

# === Chrome options (headless, no log spam) ===
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--log-level=3")
options.add_experimental_option("excludeSwitches", ["enable-logging"])

# === Load input JSON ===
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    anime_urls = json.load(f)["skipped_due_to_selenium"]

# === Helper Functions ===
def extract_info_from_page(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Get image URL
    img_tag = soup.find("img", {"alt": True, "src": True, "title": True})
    image_url = urljoin(BASE_URL, img_tag["src"]) if img_tag else None

    # Get episode links
    links = []
    buttons = soup.find_all("a", class_="btn", href=True)
    for btn in buttons:
        href = btn["href"]
        if re.match(r"^/title/\d+-[^/]+/\d+-", href):
            full_url = urljoin(BASE_URL, href)
            if full_url not in links:
                links.append(full_url)

    # Get anime title (last part of the URL, cleaned)
    match = re.search(r"/title/\d+-([a-z0-9\-]+)", driver.current_url)
    title_key = match.group(1).replace("-", "_") if match else "unknown_title"

    return title_key, image_url, links

def get_all_episodes(driver, url):
    driver.get(url)
    time.sleep(2.5)
    all_episodes = []
    clicked_labels = set()

    def extract():
        _, _, eps = extract_info_from_page(driver)
        for ep in eps:
            if ep not in all_episodes:
                all_episodes.append(ep)

    extract()

    # Paginate through batches
    while True:
        pagination_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[class*="btn-outline"]')
        found = False
        for btn in pagination_buttons:
            label = btn.text.strip()
            if "-" in label and label not in clicked_labels:
                clicked_labels.add(label)
                try:
                    btn.click()
                    time.sleep(2.5)
                    extract()
                    found = True
                    break
                except Exception:
                    continue
        if not found:
            break

    return all_episodes

# === Main scraping logic ===
driver = webdriver.Chrome(service=Service(DRIVER_PATH), options=options)
results = {}

for url in anime_urls:
    print(f"Scraping: {url}")
    try:
        driver.get(url)
        time.sleep(2.5)
        title_key, image_url, _ = extract_info_from_page(driver)
        episodes = get_all_episodes(driver, url)
        results[title_key] = {
            "main_url": url,
            "image_url": image_url,
            "episodes": episodes
        }
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")

driver.quit()

# === Save results ===
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Done. Output saved to: {OUTPUT_FILE}")
