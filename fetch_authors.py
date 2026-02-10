import json
import os
import asyncio
import random
import re
from playwright.async_api import async_playwright

AUTH_FILE = 'auth.json'
DATA_FILE = 'collect.json'

def parse_metric(text):
    if not text: return 0
    text = text.replace(',', '').strip()
    try:
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        return int(''.join(filter(str.isdigit, text)) or 0)
    except: return 0

# URLからユーザーIDを抜き出す関数
def extract_user_id(url):
    # https://x.com/user_id/status/12345... から user_id を抽出
    match = re.search(r'(?:twitter|x)\.com/([^/]+)/status', url)
    if match:
        return match.group(1)
    return None

async def fetch_authors():
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. 全データからURLを使ってユーザーIDを洗い出す
    #    (フォロワー数がまだ0の人だけをリストアップ)
    target_users = set()
    
    print("🔍 URLからユーザーIDを抽出中...")
    for d in data:
        user_id = extract_user_id(d.get('url', ''))
        if user_id:
            # ついでにmemberキーを正規化（データを綺麗にする）
            d['member'] = user_id 
            
            # フォロワー未取得ならターゲットに追加
            if d.get('follower_count', 0) == 0:
                target_users.add(user_id)

    target_list = list(target_users)
    print(f"🎯 取得対象: {len(target_list)} 人 (URL解析完了)")

    if not target_list:
        print("✅ 全てのフォロワー数が取得済みです。")
        # データの正規化（memberキーの統一）だけ保存しておく
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return

    # 2. スクレイピング開始
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if os.path.exists(AUTH_FILE):
            context_options["storage_state"] = AUTH_FILE
        
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        for i, user_id in enumerate(target_list):
            url = f"https://x.com/{user_id}"
            print(f"[{i+1}/{len(target_list)}] Checking: {user_id} ... ", end="", flush=True)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                follower_count = 0
                # 複数のセレクタ候補
                selectors = [
                    f'a[href="/{user_id}/verified_followers"]',
                    f'a[href="/{user_id}/followers"]',
                    'a[href$="/followers"]'
                ]
                
                for sel in selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        match = re.search(r'([\d,.]+[万KMk]?)', text)
                        if match:
                            follower_count = parse_metric(match.group(1))
                            if follower_count > 0: break

                if follower_count > 0:
                    print(f"✅ {follower_count}")
                    # 3. 取得した数値を、そのユーザーIDを持つ全データに反映
                    count_updated = 0
                    for d in data:
                        # ここでもURLからIDを確認して一致判定する（確実性重視）
                        u_id = extract_user_id(d.get('url', ''))
                        if u_id == user_id:
                            d['follower_count'] = follower_count
                            d['member'] = user_id # 念のため更新
                            count_updated += 1
                else:
                    print("❌ Not found")

            except Exception as e:
                print(f"❌ Error: {e}")

            # こまめに保存
            if i % 5 == 0:
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        await browser.close()

    # 最終保存
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✨ フォロワー数の更新完了！データ構造も正規化されました。")

if __name__ == "__main__":
    asyncio.run(fetch_authors())