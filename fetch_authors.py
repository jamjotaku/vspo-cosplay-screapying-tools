import json
import os
import asyncio
import random
from playwright.async_api import async_playwright

AUTH_FILE = 'auth.json'
DATA_FILE = 'collect.json'

async def fetch_authors():
    if not os.path.exists(DATA_FILE): return
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # フォロワー数が未取得のユニークなユーザーを抽出
    authors = list(set([d['member'] for d in data if d.get('follower_count', 0) == 0 and d.get('member') != 'Unknown']))
    print(f"🎯 残りの取得対象: {len(authors)} 人")

    if not authors: return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_options = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if os.path.exists(AUTH_FILE):
            context_options["storage_state"] = AUTH_FILE
        
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        for i, author in enumerate(authors):
            url = f"https://x.com/{author}"
            print(f"[{i+1}/{len(authors)}] Checking: {author} ...", end="", flush=True)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))

                # フォロワー数の要素を探す
                # 複数のセレクタ候補で試行
                selectors = [
                    f'a[href="/{author}/verified_followers"] span span',
                    f'a[href="/{author}/followers"] span span',
                    'span:has-text("フォロワー")'
                ]
                
                follower_count = 0
                for sel in selectors:
                    elem = await page.query_selector(sel)
                    if elem:
                        text = await elem.inner_text()
                        # "1.5万" などの数値をパース (前のparse_metricを流用)
                        from fetch_metrics import parse_metric
                        follower_count = parse_metric(text)
                        if follower_count > 0: break

                if follower_count > 0:
                    print(f" ✅ {follower_count}")
                    # 全データの中の該当ユーザーのフォロワー数を更新
                    for d in data:
                        if d.get('member') == author:
                            d['follower_count'] = follower_count
                else:
                    print(" ❌ Not found")

            except Exception as e:
                print(f" ❌ Error: {e}")

        await browser.close()

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(fetch_authors())