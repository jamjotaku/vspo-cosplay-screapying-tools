import json
import os
import re
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# 数値抽出用の補助関数
def extract_number(text, pattern):
    if not text:
        return "0"
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return "0"

async def scrape_vspo_cosplay(context, member):
    results = []
    page = await context.new_page()

    # 検索URLの構築
    query = f"{member['name']} コスプレ"
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    print(f"Searching for: {member['name']}")
    try:
        await page.goto(url, timeout=60000)
        # ログイン失敗や制限時に備え、少し待機
        await page.wait_for_timeout(5000)
        
        # ツイートが表示されるまで待機
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        for tweet in tweets:
            try:
                user_info = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_info.inner_text() if user_info else "Unknown"
                
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                group_label = await tweet.query_selector('div[role="group"]')
                stats_text = await group_label.get_attribute('aria-label') if group_label else ""

                metrics = {
                    "replies": extract_number(stats_text, r"(\d+)件のリプライ"),
                    "retweets": extract_number(stats_text, r"(\d+)件のリポスト"),
                    "likes": extract_number(stats_text, r"(\d+)件のいいね"),
                    "views": extract_number(stats_text, r"([\d\.]+[万億]?+)件の表示")
                }

                # 画像URLの抽出
                img_elements = await tweet.query_selector_all('img[src*="media"]')
                images = []
                for img in img_elements:
                    src = await img.get_attribute('src')
                    if src and "profile_images" not in src:
                        images.append(src)

                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                if images: # 画像があるツイートのみ保存
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
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error scraping {member['name']}: {e}")
    
    await page.close()
    return results

async def main():
    # 1. メンバーリストの読み込み
    if not os.path.exists('members.json'):
        print("Error: members.json not found")
        return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # 2. 既存データの読み込み
    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except:
                all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    # 3. Playwright実行
    async with async_playwright() as p:
        # GitHub Actions環境では headless=True が必須
        browser = await p.chromium.launch(headless=True)
        
        # auth.json が存在するか確認
        if not os.path.exists('auth.json'):
            print("Error: auth.json not found. Check GitHub Secrets setup.")
            await browser.close()
            return

        context = await browser.new_context(storage_state="auth.json")
        
        for member in members:
            new_tweets = await scrape_vspo_cosplay(context, member)
            for t in new_tweets:
                if t['url'] not in existing_urls:
                    all_data.append(t)
                    existing_urls.add(t['url'])
        
        # 4. 保存
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print(f"Finished! Total items: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
