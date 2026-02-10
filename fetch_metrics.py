import json
import os
import asyncio
import random
import re
from playwright.async_api import async_playwright
from datetime import datetime

# --- 設定 ---
BATCH_SIZE = 150
DATA_FILE = 'collect.json'
AUTH_FILE = 'auth.json'
DEBUG_DIR = 'debug_screenshots' # エラー時の写真を保存する場所

# 数値変換
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
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # デバッグ用フォルダ作成
    if not os.path.exists(DEBUG_DIR):
        os.makedirs(DEBUG_DIR)

    targets = [d for d in data if d.get('like_count', 0) == 0 or 'text' not in d]
    current_batch = targets[:BATCH_SIZE]
    
    print(f"🎯 対象: {len(current_batch)} 件 / 残り {len(targets)} 件")
    if not current_batch: return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if os.path.exists(AUTH_FILE):
            context_options["storage_state"] = AUTH_FILE

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        processed_count = 0
        for i, item in enumerate(current_batch):
            url = item['url']
            print(f"[{i+1}/{len(current_batch)}] Accessing: {url}")

            # --- リトライループ (最大2回挑戦) ---
            success = False
            for attempt in range(2): 
                try:
                    # タイムアウト延長 (30秒 -> 60秒)
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # 記事が表示されるまで待つ (10秒 -> 20秒に延長)
                    try:
                        await page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
                    except:
                        # 失敗したら例外を投げてリトライ処理へ
                        raise Exception("Timeout: Tweet content not loaded")

                    await asyncio.sleep(random.uniform(1.5, 3.0))

                    # --- A. 数値取得 ---
                    likes = 0
                    views = 0
                    
                    like_elem = await page.query_selector('[data-testid="like"]')
                    if like_elem:
                        aria = await like_elem.get_attribute('aria-label')
                        if aria:
                            match = re.search(r'(\d[\d,.]*[KkMm万]?)', aria)
                            if match: likes = parse_metric(match.group(1))
                    
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

                    # データ更新
                    item['like_count'] = likes
                    item['impression_count'] = views
                    item['text'] = text_content
                    item['last_fetched'] = datetime.now().isoformat()

                    log_msg = f"   ✅ Likes: {likes}"
                    if text_content: log_msg += f", Text: {text_content[:15]}..."
                    else: log_msg += " (No Text)"
                    print(log_msg)
                    
                    success = True
                    break # 成功したらループを抜ける

                except Exception as e:
                    print(f"   ⚠️ Attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2) # 少し休んでリトライ

            # --- 2回とも失敗した場合 ---
            if not success:
                print(f"   ❌ Failed to fetch. Saving screenshot...")
                # URLから安全なファイル名を生成
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])
                shot_path = f"{DEBUG_DIR}/error_{safe_name}.png"
                try:
                    await page.screenshot(path=shot_path)
                    print(f"   📸 Screenshot saved: {shot_path}")
                except:
                    print("   Could not save screenshot.")
                
                # エラー記録 (スキップ用)
                item['like_count'] = 0
                item['text'] = ""
                item['last_fetched'] = datetime.now().isoformat()

            processed_count += 1
            if processed_count % 5 == 0:
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        await browser.close()

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✨ バッチ処理完了！ {processed_count} 件更新しました。")

if __name__ == "__main__":
    asyncio.run(fetch_metrics())