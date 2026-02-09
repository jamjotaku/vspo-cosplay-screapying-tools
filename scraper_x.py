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
    # 画面サイズを固定して、モバイル版へのリダイレクトを防ぐ
    await page.set_viewport_size({"width": 1280, "height": 800})

    query = f"{member['name']} コスプレ"
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    print(f"--- Searching for: {member['name']} ---")
    try:
        # 1. ページ移動（ネットワークが落ち着くまで待機）
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # 2. 人間らしくランダムに待機
        wait_time = random.uniform(5000, 8000)
        await page.wait_for_timeout(wait_time)

        # 3. ログイン画面に飛ばされていないかチェック
        if "login" in page.url:
            print(f"⚠️ ログインが解除されています。Cookieを更新してください。")
            await page.screenshot(path="login_error.png")
            return []

        # 4. ツイートが表示されるまで最大20秒待機
        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
        except:
            print(f"❌ ツイートが見つかりません（検索結果0件、またはブロック）")
            await page.screenshot(path=f"not_found_{member['id']}.png")
            return []

        # 5. スクロールして読み込みを促す
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(2)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"✅ Found {len(tweets)} potential tweets")

        for tweet in tweets:
            try:
                # ユーザー情報
                user_info = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_info.inner_text() if user_info else "Unknown"
                
                # 本文
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                # 統計
                group_label = await tweet.query_selector('div[role="group"]')
                stats_text = await group_label.get_attribute('aria-label') if group_label else ""

                metrics = {
                    "replies": extract_number(stats_text, r"(\d+)件のリプライ"),
                    "retweets": extract_number(stats_text, r"(\d+)件のリポスト"),
                    "likes": extract_number(stats_text, r"(\d+)件のいいね"),
                    "views": extract_number(stats_text, r"([\d\.]+[万億]?+)件の表示")
                }

                # 画像（プロフィール画像を除外して抽出）
                img_elements = await tweet.query_selector_all('img[src*="media"]')
                images = []
                for img in img_elements:
                    src = await img.get_attribute('src')
                    if src and "profile_images" not in src:
                        images.append(src)

                # ツイートURL
                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                if images and tweet_url:
                    results.append({
                        "member_id": member.get('id', 'unknown'),
                        "member_name": member['name'],
                        "author_name": full_name.split("\n")[0],
                        "author_id": full_name.split("\n")[1] if "\n" in full_name else "",
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
    if not os.path.exists('members.json'):
        print("Error: members.json not found")
        return

    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except:
                all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    async with async_playwright() as p:
        # 海外サーバーからのアクセスを怪しまれないよう、言語設定等を指定
        browser = await p.chromium.launch(headless=True)
        
        if not os.path.exists('auth.json'):
            print("Error: auth.json not found.")
            await browser.close()
            return

        context = await browser.new_context(
            storage_state="auth.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        
        # 連続アクセスでのロックを避けるため、1人ずつゆっくり処理
        for member in members:
            new_tweets = await scrape_vspo_cosplay(context, member)
            added_count = 0
            for t in new_tweets:
                if t['url'] not in existing_urls:
                    all_data.append(t)
                    existing_urls.add(t['url'])
                    added_count += 1
            print(f"✨ Added {added_count} new items for {member['name']}")
            await asyncio.sleep(random.uniform(2, 5))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print(f"🚀 All process finished! Total database: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
