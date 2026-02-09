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
        # タイムアウト対策：domcontentloadedで早めに次へ
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3) # 読み込み待ち

        if "login" in page.url:
            print(f"⚠️ Login page detected. Skipping.")
            return []

        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
        except:
            print(f"❌ No tweets found (Timeout).")
            return []

        # 画像を読み込ませるために少しスクロール
        for _ in range(3):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"✅ Found {len(tweets)} tweets in DOM")

        for i, tweet in enumerate(tweets):
            try:
                # ユーザー名
                user_elem = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_elem.inner_text() if user_elem else "Unknown"
                
                # 広告スキップ
                if "プロモーション" in full_name or "Ad" in full_name:
                    continue

                # 本文
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                # 画像抽出の強化：data-testid="tweetPhoto" の中の img を優先的に探す
                images = []
                photo_divs = await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')
                
                for img in photo_divs:
                    src = await img.get_attribute('src')
                    if src: images.append(src)
                
                # もし上記で見つからなければ、汎用的な img タグも探す（プロフ画像等は除外）
                if not images:
                    all_imgs = await tweet.query_selector_all('img')
                    for img in all_imgs:
                        src = await img.get_attribute('src')
                        # メディアサーバー(pbs.twimg.com)の画像で、かつプロフ画像でないもの
                        if src and "pbs.twimg.com/media" in src and "profile_images" not in src:
                            images.append(src)

                # 重複排除
                images = list(set(images))

                # URL取得
                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                # 保存判定
                if images and tweet_url:
                    results.append({
                        "member_id": member.get('id', 'unknown'),
                        "member_name": member['name'],
                        "content": content,
                        "images": images,
                        "url": tweet_url,
                        "collected_at": datetime.now().isoformat()
                    })
                    print(f"  ⭕ Saved tweet from {full_name.splitlines()[0]}: {len(images)} images")
                else:
                    # なぜ保存されなかったかログに出す
                    reason = []
                    if not images: reason.append("No images")
                    if not tweet_url: reason.append("No URL")
                    print(f"  Start analyzing tweet {i+1}... Skip: {', '.join(reason)}")

            except Exception as e:
                print(f"  ❌ Error processing tweet {i+1}: {e}")
                continue

    except Exception as e:
        print(f"❌ Error scraping {member['name']}: {e}")
    
    await page.close()
    return results

async def main():
    if not os.path.exists('members.json'): return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # テスト用：全員やると長いので、最初の3人だけ試すなら以下をコメントアウト解除
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
            
            await asyncio.sleep(random.uniform(2, 4))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print(f"🚀 Finished! Total items in DB: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
