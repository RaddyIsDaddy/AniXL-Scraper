import re
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

session = requests.Session()

def extract_links_from_script(html):
    match = re.search(r'<script[^>]+type=["\']qwik/json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return "", "", ""
    json_text = match.group(1)

    sub_match = re.search(r'"sub"\s*,\s*"(?P<link>https?://[^\s"\']+\.m3u8)"', json_text)
    dub_match = re.search(r'"dub"\s*,\s*"(?P<link>https?://[^\s"\']+\.m3u8)"', json_text)

    pattern = re.compile(
        r'"(English|eng|english)"\s*,\s*(?:"[^"]*"\s*,\s*)?"[^"]*\.vtt"\s*,\s*"(?P<vtt_url>https?://[^"]+\.vtt)"',
        re.IGNORECASE
    )

    match = pattern.search(json_text)
    subtitle = match.group("vtt_url") if match else ""

    sub = sub_match.group("link") if sub_match else ""
    dub = dub_match.group("link") if dub_match else ""

    return sub, dub, subtitle

def fetch_episode_data(ep_url, idx):
    print(f"  → Fetching [{idx}] {ep_url}")
    try:
        response = session.get(ep_url, timeout=10)
        response.raise_for_status()
        html = response.text

        sub, dub, subtitle = extract_links_from_script(html)

        if sub:
            print(f"    → Sub video: {sub}")
        if dub:
            print(f"    → Dub video: {dub}")
        if subtitle:
            print(f"    → Subtitle: {subtitle}")

        return idx, {
            "video": sub,
            "subtitle": subtitle,
            "dub": dub
        }
    except Exception as e:
        print(f"    → Episode fetch error: {e}")
        return idx, {
            "video": "",
            "subtitle": "",
            "dub": ""
        }

def process_anime_json(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        anime_data = json.load(f)

    # Load existing output if resuming
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}

    for anime_title, data in anime_data.items():
        print(f"\nProcessing: {anime_title}")
        episode_urls = data["episodes"]
        image_url = data.get("image_url", "")
        existing_eps = existing_data.get(anime_title, {}).get("episodes", [])

        # Prepare results list with existing episodes if available
        results = existing_eps + [None] * (len(episode_urls) - len(existing_eps))

        def handle_result(future):
            idx, result = future.result()
            results[idx] = result
            anime_data[anime_title]["episodes"] = results
            if image_url:
                anime_data[anime_title]["image_url"] = image_url
            with open(output_file, "w", encoding="utf-8") as f_out:
                json.dump(anime_data, f_out, indent=2)

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = []
            for idx, url in enumerate(episode_urls):
                if idx < len(existing_eps) and existing_eps[idx] is not None and existing_eps[idx].get("video"):
                    print(f"  → Skipping already processed episode {idx}")
                    continue
                future = executor.submit(fetch_episode_data, url, idx)
                future.add_done_callback(handle_result)
                futures.append(future)

            for future in as_completed(futures):
                pass  # Just wait for all to finish

if __name__ == "__main__":
    input_file = "input.json"
    output_file = "output.json"
    process_anime_json(input_file, output_file)
