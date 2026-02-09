import json
import os
import asyncio
import random
from playwright.async_api import async_playwright

def parse_count(text):
    if not text: return 0
    text = text.replace(',', '').replace('Followers', '').replace('フォロワー', '').strip()
    try:
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        return int(''.join(filter(str.isdigit, text)) or 0)
    except: return 0

async def fetch_authors_safe():
    output_file = 'authors.json'
    
    # 1. ターゲットのリストアップ
    if not os.path.exists('collect.json'): return
    with open('collect.json', 'r', encoding='utf-8') as f:
        tweets = json.load(f)

    all_authors = {}
    # 既存データの読み込み
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            all_authors = json.load(f)

    # 新規ターゲット抽出
    targets = []
    for t in tweets:
        url = t.get('url', '')
        if 'x.com/' in url:
            try:
                username = url.split('x.com/')[1].split('/')[0]
                # まだ辞書にない、または値が0のユーザーのみ対象
                if username not in all_authors or all_authors[username] == 0:
                    targets.append(username)
                    if username not in all_authors:
                        all_authors[username] = 0
            except: continue
            
    # 重複排除
    targets = list(set(targets))
    print(f"🎯 残りの取得対象: {len(targets)} 人")

    if not targets:
        print("✅ 全員のフォロワー数取得が完了しています！")
        return

    # 2. 安全運転で取得開始
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_options = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        if os.path.exists('auth.json'):
            context_options["storage_state"] = "auth.json"
            
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        consecutive_errors = 0 # 連続エラーカウンタ

        for i, username in enumerate(targets):
            # 連続エラーが続いたら緊急停止
            if consecutive_errors >= 5:
                print("\n🚨 連続で取得に失敗しました。制限の可能性があるため停止します。")
                print("⏳ 1〜2時間空けてから再開してください。")
                break

            try:
                print(f"[{i+1}/{len(targets)}] Checking: {username} ...", end="", flush=True)
                
                await page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=30000)
                
                # 人間らしくランダムに待つ (10秒〜25秒)
                wait_time = random.uniform(10, 25)
                await asyncio.sleep(2) 
                
                # 少しスクロールして読み込みを促す
                await page.mouse.wheel(0, 300)
                await asyncio.sleep(2)

                # フォロワー数取得
                count_elem = await page.query_selector('a[href*="/followers"] span')
                
                if count_elem:
                    text = await count_elem.inner_text()
                    count = parse_count(text)
                    all_authors[username] = count
                    print(f" ✅ {count:,}")
                    consecutive_errors = 0 # 成功したらリセット
                else:
                    print(" ❌ Not found")
                    consecutive_errors += 1

                # 保存
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_authors, f, indent=2)

                # 次の人に行く前にしっかり休憩
                await asyncio.sleep(wait_time)

            except Exception as e:
                print(f" ⚠️ Error: {e}")
                consecutive_errors += 1
                await asyncio.sleep(30) # エラー時は長めに休む

        await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_authors_safe())