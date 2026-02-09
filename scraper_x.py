import json
import os
import re
from playwright.async_api import async_playwright

async def scrape_vspo_cosplay(member):
    results = []
    async with async_playwright() as p:
        # ローカルで作成した auth.json を読み込む
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="auth.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 検索URLの構築（「話題」ではなく「最新」を狙う場合は f=live を追加）
        query = f"{member['name']} コスプレ"
        url = f"https://x.com/search?q={query}&src=typed_query&f=live"
        
        await page.goto(url)
        # コンテンツの読み込み待機
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)

        # 1ページ分（約10-20件）のツイートを取得
        tweets = await page.query_selector_all('article[data-testid="tweet"]')

        for tweet in tweets:
            try:
                # ユーザー情報と本文
                user_info = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_info.inner_text()
                
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                # 統計データ (ARIAラベルから抽出)
                # Xの統計は "123件のリプライ、456件のリポスト、789件のいいね、1.2万件の表示" のような1つの文字列で管理されている
                group_label = await tweet.query_selector('div[role="group"]')
                stats_text = await group_label.get_attribute('aria-label') if group_label else ""

                # 正規表現で数値を抽出
                metrics = {
                    "replies": extract_number(stats_text, r"(\d+)件のリプライ"),
                    "retweets": extract_number(stats_text, r"(\d+)件のリポスト"),
                    "likes": extract_number(stats_text, r"(\d+)件のいいね"),
                    "views": extract_number(stats_text, r"([\d\.]+[万億]?+)件の表示"),
                    "bookmarks": extract_number(stats_text, r"(\d+)件のブックマーク")
                }

                # 画像URLの抽出
                media_container = await tweet.query_selector('[data-testid="tweetPhoto"]')
                images = []
                if media_container:
                    img_elements = await tweet.query_selector_all('img[src*="media"]')
                    images = [await img.get_attribute('src') for img in img_elements if "profile_images" not in await img.get_attribute('src')]

                # ツイートURL
                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                results.append({
                    "member_id": member['id'],
                    "member_name": member['name'],
                    "author_name": full_name.split("\n")[0],
                    "author_id": full_name.split("\n")[1] if "\n" in full_name else "",
                    "content": content,
                    "metrics": metrics,
                    "images": list(set(images)), # 重複削除
                    "url": tweet_url,
                    "source": "X",
                    "collected_at": "2026-02-09T14:00:00" # 本来は現在時刻
                })
            except Exception as e:
                print(f"Error skipping tweet: {e}")
                continue

        await browser.close()
    return results

def extract_number(text, pattern):
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return "0"
