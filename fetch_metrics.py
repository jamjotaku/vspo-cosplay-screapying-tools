import json
import os
import asyncio
import random
from playwright.async_api import async_playwright
from datetime import datetime

# 数値変換 (1.5万 -> 15000)
def parse_metric(text):
    if not text: return 0
    text = text.replace(',', '').strip()
    try:
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        return int(''.join(filter(str.isdigit, text)) or 0)
    except: return 0

async def fetch_metrics():
    # 1. データの読み込み
    if not os.path.exists('collect.json'): return
    with open('collect.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ターゲット選定: 「いいねが無い」または「本文(text)が無い」データ
    # ※ すでに優先順位(prioritize.py)で並んでいる前提で、上から順に処理
    targets = [d for d in data if d.get('like_count', 0) == 0 or not d.get('text')]
    
    # 欲張らず、1回の実行で処理する件数 (例: 50件)
    # 制限回避のため少なめに設定
    batch_size = 50
    current_batch = targets[:batch_size]
    
    print(f"🎯 今回の取得対象: {len(current_batch)} 件 / 残り {len(targets)} 件")

    if not current_batch:
        print("✅ 全データの数値・本文取得が完了しています！")
        return

    # 2. スクレイピング開始
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # ログイン状態があれば使う
        context_options = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if os.path.exists('auth.json'):
            context_options["storage_state"] = "auth.json"
        
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        for i, item in enumerate(current_batch):
            url = item['url']
            print(f"[{i+1}/{len(current_batch)}] Accessing: {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(2, 5)) # 待機

                # --- A. 数値取得 (既存) ---
                likes = 0
                views = 0
                
                # いいね数 (aria-label または testid から取得)
                like_elem = await page.query_selector('[data-testid="like"] span, [data-testid="unlike"] span')
                if not like_elem: # ログインしていない場合など
                    # 別のセレクタを試す
                    like_elem = await page.query_selector('a[href$="/likes"] span')

                if like_elem:
                    like_text = await like_elem.inner_text()
                    likes = parse_metric(like_text)

                # インプレッション
                view_elem = await page.query_selector('a[href$="/analytics"] span div')
                if not view_elem:
                    view_elem = await page.query_selector('[data-testid="app-text-transition-container"] span')
                
                if view_elem:
                    view_text = await view_elem.inner_text()
                    views = parse_metric(view_text)

                # --- B. 本文取得 (新機能！) ---
                text_content = ""
                text_elem = await page.query_selector('[data-testid="tweetText"]')
                if text_elem:
                    text_content = await text_elem.inner_text()
                    # 改行コードなどを整理
                    text_content = text_content.replace('\n', ' ')

                # --- C. データ更新 ---
                # 元のリスト内の該当データを直接書き換え
                item['like_count'] = likes
                item['impression_count'] = views
                if text_content:
                    item['text'] = text_content
                    print(f"   ✅ Likes: {likes}, Text: {text_content[:20]}...")
                else:
                    print(f"   ✅ Likes: {likes} (Textなし/画像のみ)")

                item['last_fetched'] = datetime.now().isoformat()

                # こまめに保存 (クラッシュ対策)
                if i % 5 == 0:
                    with open('collect.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"   ❌ Error: {e}")
                continue

        await browser.close()

    # 最終保存
    with open('collect.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✨ バッチ処理完了！")

if __name__ == "__main__":
    asyncio.run(fetch_metrics())