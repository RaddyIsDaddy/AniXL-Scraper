import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import json
import os
import signal
import sys

BASE_URL = "https://anixl.to/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT_JSON = "anime_episodes.json"

session = requests.Session()
session.headers.update(HEADERS)

anime_data = {}
seen_anime = set()
current_page = 1
SAVE_EVERY_N_PAGES = 2  # Save after every N pages

def save_data():
    with open(OUTPUT_JSON, "w", encoding="utf-8") as jf:
        json.dump(anime_data, jf, indent=2, ensure_ascii=False)
    print("\n💾 Saved current progress to JSON.")

def handle_exit(signum, frame):
    print("\n🛑 Interrupted. Saving progress...")
    save_data()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

def get_anime_links(page_number):
    url = f"{BASE_URL}?page={page_number}"
    res = session.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    links = [
        "https://anixl.to" + a["href"]
        for a in soup.find_all("a", class_="link-hover link-pri line-clamp-2", href=True)
        if a["href"].startswith("/title/")
    ]
    return links

def get_anime_title_and_image_url(soup):
    img_tag = soup.find("img", class_="w-full not-prose shadow-md shadow-black/50")
    title = img_tag.get("title") if img_tag else None
    if img_tag and title:
        src = img_tag.get("src")
        img_url = "https://anixl.to" + src if src and src.startswith("/media") else src
        return title.strip(), img_url
    title_tag = soup.find("h1")
    return (title_tag.text.strip() if title_tag else "Unknown Anime"), None

def should_use_selenium(soup):
    return soup.find("button", string=lambda s: s and "-" in s)

def get_episode_links_requests(anime_url):
    res = session.get(anime_url)
    soup = BeautifulSoup(res.text, "html.parser")
    base_path = anime_url.replace("https://anixl.to", "")
    episode_links = [
        "https://anixl.to" + a["href"]
        for a in soup.find_all("a", href=True)
        if (
            a["href"].startswith("/title/")
            and base_path in a["href"]
            and len(a["href"].split("/")) == 4
            and "?" not in a["href"]
        )
    ]
    return episode_links, soup

def process_anime(anime_url, index):
    if anime_url in seen_anime:
        return
    seen_anime.add(anime_url)

    print(f"📺 Anime #{index} on page {current_page}: {anime_url}")
    try:
        episode_links, soup = get_episode_links_requests(anime_url)
        anime_name, image_url = get_anime_title_and_image_url(soup)
        if should_use_selenium(soup):
            print("🚫 Skipping (Selenium needed):", anime_url)
            anime_data["skipped_due_to_selenium"].append(anime_url)
            return
        anime_key = anime_name.replace(" ", "_")
        anime_data[anime_key] = {
            "main_url": anime_url,
            "image_url": image_url,
            "episodes": episode_links
        }
    except Exception as e:
        print(f"⚠️ Failed to fetch {anime_url}: {e}")

def main():
    global current_page
    anime_data["skipped_due_to_selenium"] = anime_data.get("skipped_due_to_selenium", [])

    while True:
        print(f"\n📄 Getting anime list from search page {current_page}...")
        anime_links = get_anime_links(current_page)
        if not anime_links:
            print("✅ No more anime found. Ending.")
            break

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(process_anime, url, idx) for idx, url in enumerate(anime_links, start=1)]
            for _ in as_completed(futures):
                pass  # Just wait for all to complete

        if current_page % SAVE_EVERY_N_PAGES == 0:
            save_data()

        current_page += 1

    save_data()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        save_data()
