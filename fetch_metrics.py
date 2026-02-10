import json
import os
import asyncio
import random
import re
from playwright.async_api import async_playwright
from datetime import datetime

# --- 設定 ---
BATCH_SIZE = 150  # 1回の実行で処理する件数 (増量！)
DATA_FILE = 'collect.json'
AUTH_FILE = 'auth.json'

# 数値変換 (1.5万 -> 15000)
def parse_metric(text):
    if not text: return 0
    text = text.replace(',', '').strip()
    try:
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        # 数字以外を除去して変換
        return int(''.join(filter(str.isdigit, text)) or 0)
    except: return 0

async def fetch_metrics():
    # 1. データの読み込み
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ターゲット選定: 「いいねが無い」または「本文(text)が無い」データ
    # かつ、まだエラーで弾かれていないもの（last_fetchedがない、または古い）
    targets = [d for d in data if d.get('like_count', 0) == 0 or 'text' not in d]
    
    current_batch = targets[:BATCH_SIZE]
    
    print(f"🎯 今回の取得対象: {len(current_batch)} 件 / 残り {len(targets)} 件")

    if not current_batch:
        print("✅ 全データの数値・本文取得が完了しています！")
        return

    # 2. スクレイピング開始
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # ログイン状態があれば使う
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # auth.jsonの中身を直接読み込んでcookiesとして渡す方が確実な場合が多い
        if os.path.exists(AUTH_FILE):
             with open(AUTH_FILE, 'r') as f:
                cookies = json.load(f)
                context = await browser.new_context(**context_options)
                await context.add_cookies(cookies)
        else:
            context = await browser.new_context(**context_options)

        page = await context.new_page()

        processed_count = 0
        for i, item in enumerate(current_batch):
            url = item['url']
            print(f"[{i+1}/{len(current_batch)}] Accessing: {url}")

            try:
                # タイムアウトを少し長めに
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # ツイート本文が表示されるまで待つ（最大10秒）
                try:
                    await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
                except:
                    print("  ⚠️ Tweet content not found (deleted or sensitive?)")

                await asyncio.sleep(random.uniform(1.5, 3.5)) # 待機

                # --- A. 数値取得 ---
                likes = 0
                views = 0
                
                # いいね数: aria-label="150 likes" を狙うのが一番確実
                like_elem = await page.query_selector('[data-testid="like"]')
                if like_elem:
                    aria = await like_elem.get_attribute('aria-label')
                    if aria:
                        match = re.search(r'(\d[\d,.]*[KkMm万]?)', aria)
                        if match: likes = parse_metric(match.group(1))
                
                # インプレッション
                view_elem = await page.query_selector('a[href$="/analytics"]')
                if view_elem:
                    aria = await view_elem.get_attribute('aria-label')
                    if aria:
                        match = re.search(r'(\d[\d,.]*[KkMm万]?)', aria)
                        if match: views = parse_metric(match.group(1))

                # --- B. 本文取得 ---
                text_content = ""
                text_elem = await page.query_selector('[data-testid="tweetText"]')
                if text_elem:
                    text_content = await text_elem.inner_text()
                    text_content = text_content.replace('\n', ' ')

                # --- C. データ更新 ---
                item['like_count'] = likes
                item['impression_count'] = views
                item['text'] = text_content
                item['last_fetched'] = datetime.now().isoformat()

                if text_content:
                    print(f"   ✅ Likes: {likes}, Text: {text_content[:20]}...")
                else:
                    print(f"   ✅ Likes: {likes} (No Text)")

                processed_count += 1
                
                # こまめに保存 (5件ごと)
                if processed_count % 5 == 0:
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"   ❌ Error: {e}")
                # エラー時も空データを入れて更新時刻を記録し、無限ループを防ぐ
                item['like_count'] = 0
                item['text'] = ""
                item['last_fetched'] = datetime.now().isoformat()
                continue

        await browser.close()

    # 最終保存
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✨ バッチ処理完了！ {processed_count} 件更新しました。")

if __name__ == "__main__":
    asyncio.run(fetch_metrics())