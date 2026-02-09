import json
import os
import re
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

def extract_number(text, pattern):
    if not text: return "0"
    match = re.search(pattern, text)
    return match.group(1) if match else "0"

async def scrape_vspo_cosplay(context, member):
    results = []
    page = await context.new_page()
    await page.set_viewport_size({"width": 1280, "height": 800})

    query = f"{member['name']} コスプレ"
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    print(f"--- Searching for: {member['name']} ---")
    try:
        # 【修正点】networkidle (通信完了待ち) をやめ、domcontentloaded (表示待ち) に変更
        # これにより、無限ロードによるタイムアウトを防ぎます
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # 読み込みの余韻として少しだけ待つ
        await asyncio.sleep(3)

        # ログインチェック
        if "login" in page.url:
            print(f"⚠️ ログインが解除されています。")
            return []

        # ツイートが表示されるかチェック（最大10秒）
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
        except:
            print(f"❌ ツイートが見つかりません（検索結果0件、または読込エラー）")
            # デバッグ用にスクショを保存
            await page.screenshot(path=f"error_{member['id']}.png")
            return []

        # 少しスクロールしてデータを読み込ませる
        await page.mouse.wheel(0, 1000)
        await asyncio.sleep(1)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"✅ Found {len(tweets)} tweets")

        for tweet in tweets:
            try:
                user_info = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_info.inner_text() if user_info else "Unknown"
                
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                # 広告ツイートを除外
                if "プロモーション" in full_name or "Ad" in full_name:
                    continue

                group_label = await tweet.query_selector('div[role="group"]')
                stats_text = await group_label.get_attribute('aria-label') if group_label else ""

                metrics = {
                    "replies": extract_number(stats_text, r"(\d+)件のリプライ"),
                    "retweets": extract_number(stats_text, r"(\d+)件のリポスト"),
                    "likes": extract_number(stats_text, r"(\d+)件のいいね"),
                    "views": extract_number(stats_text, r"([\d\.]+[万億]?+)件の表示")
                }

                img_elements = await tweet.query_selector_all('img[src*="media"]')
                images = []
                for img in img_elements:
                    src = await img.get_attribute('src')
                    if src and "profile_images" not in src:
                        images.append(src)

                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                if images and tweet_url:
                    results.append({
                        "member_id": member.get('id', 'unknown'),
                        "member_name": member['name'],
                        "content": content,
                        "metrics": metrics,
                        "images": list(set(images)),
                        "url": tweet_url,
                        "source": "X",
                        "collected_at": datetime.now().isoformat()
                    })
            except:
                continue
    except Exception as e:
        print(f"❌ Error scraping {member['name']}: {e}")
    
    await page.close()
    return results

async def main():
    if not os.path.exists('members.json'): return

    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # 動作確認のため、最初の3人だけテストしたい場合はここを有効に
    # members = members[:3] 

    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try: all_data = json.load(f)
            except: all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        if not os.path.exists('auth.json'):
            print("Error: auth.json not found.")
            await browser.close()
            return

        context = await browser.new_context(
            storage_state="auth.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        for member in members:
            new_tweets = await scrape_vspo_cosplay(context, member)
            count = 0
            for t in new_tweets:
                if t['url'] not in existing_urls:
                    all_data.append(t)
                    existing_urls.add(t['url'])
                    count += 1
            if count > 0:
                print(f"✨ Added {count} new items for {member['name']}")
            
            # 連続アクセス対策の休憩（2〜4秒）
            await asyncio.sleep(random.uniform(2, 4))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print(f"🚀 Finished! Total items: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
