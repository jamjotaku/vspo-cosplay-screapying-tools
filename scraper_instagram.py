import json
import os
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

# ■■■ 設定 ■■■
# InstagramはHTML構造が複雑なので、比較的安定しているクラスや属性を狙います
TAG_URL_BASE = "https://www.instagram.com/explore/tags/"

async def scrape_instagram_tag(context, member):
    results = []
    page = await context.new_page()
    
    # ハッシュタグの生成（例: 一ノ瀬うるはコスプレ）
    tag = f"{member['name']}コスプレ"
    url = f"{TAG_URL_BASE}{tag}/"
    
    print(f"--- [Instagram] Searching for: #{tag} ---")
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # 読み込み待ち（Instagramは重いので長めに）
        await asyncio.sleep(random.uniform(5, 8))

        # ログイン画面に飛ばされたかチェック
        if "login" in page.url:
            print(f"⚠️ Redirected to login page. Cookie might be expired.")
            return []

        # 投稿のリンク（<a>タグ）を探す
        # Instagramのハッシュタグページは、hrefが "/p/..." のリンクが投稿
        try:
            await page.wait_for_selector('a[href*="/p/"]', timeout=15000)
        except:
            print(f"❌ No posts found or layout changed.")
            return []

        # スクロールして少し読み込む
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(3)

        # 投稿要素を取得（上位9件くらいに制限してBANリスクを下げる）
        posts = await page.query_selector_all('a[href*="/p/"]')
        print(f"✅ Found {len(posts)} posts in view")

        for i, post in enumerate(posts[:9]): 
            try:
                post_url = f"https://www.instagram.com{await post.get_attribute('href')}"
                
                # サムネイル画像を取得
                img_elem = await post.query_selector('img')
                if not img_elem: continue
                
                img_src = await img_elem.get_attribute('src')
                # imgのalt属性に本文が入っていることが多い
                alt_text = await img_elem.get_attribute('alt')
                caption = alt_text if alt_text else "No caption"

                if img_src and post_url:
                    results.append({
                        "member_id": member.get('id', 'unknown'),
                        "member_name": member['name'],
                        "author_name": "InstagramUser", # 一覧画面からは投稿者名が取りにくいので仮置き
                        "content": caption,
                        "images": [img_src],
                        "url": post_url,
                        "source": "Instagram", # 情報源を区別
                        "collected_at": datetime.now().isoformat()
                    })
                    print(f"  ⭕ Found post: {post_url}")

            except Exception as e:
                print(f"  ❌ Error processing post {i}: {e}")
                continue

    except Exception as e:
        print(f"❌ Error scraping {member['name']}: {e}")
    
    await page.close()
    return results

async def main():
    if not os.path.exists('members.json'): return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # テスト用：最初の1人だけ
    # members = members[:1]

    data_file = 'collect.json'
    all_data = []
    
    # 既存データを読み込み
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try: all_data = json.load(f)
            except: all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Instagram用の認証ファイル
        if not os.path.exists('auth_instagram.json'):
            print("Error: auth_instagram.json not found.")
            await browser.close()
            return

        context = await browser.new_context(
            storage_state="auth_instagram.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        for member in members:
            new_posts = await scrape_instagram_tag(context, member)
            count = 0
            for post in new_posts:
                if post['url'] not in existing_urls:
                    all_data.append(post)
                    existing_urls.add(post['url'])
                    count += 1
            
            if count > 0:
                print(f"✨ Added {count} new items for {member['name']}")
            
            # Instagramは連続アクセスに厳しいので長めに休憩
            await asyncio.sleep(random.uniform(5, 10))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
            
        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
