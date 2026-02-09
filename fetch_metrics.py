import json
import os
import asyncio
import random
from playwright.async_api import async_playwright

def parse_metric(text):
    if not text: return 0
    text = text.replace(',', '').replace('Likes', '').replace('Views', '').strip()
    try:
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        return int(''.join(filter(str.isdigit, text)) or 0)
    except: return 0

async def fetch_metrics():
    data_file = 'collect.json'
    if not os.path.exists(data_file): return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 数値が未取得(0)のものを100件抽出
    targets = [item for item in data if item.get('like_count', 0) == 0]
    batch_targets = targets[:100]

    if not batch_targets:
        print("✅ 全データの数値取得が完了しています！")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_options = {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        if os.path.exists('auth.json'):
            context_options["storage_state"] = "auth.json"
        
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        for item in batch_targets:
            try:
                print(f"Accessing: {item['url']}")
                await page.goto(item['url'], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(5, 8)) # じっくり待つ

                # X(Twitter)のいいね数取得
                like_elem = await page.query_selector('[data-testid="like"]')
                if like_elem:
                    aria = await like_elem.get_attribute('aria-label')
                    if aria and "Like" in aria:
                        item['like_count'] = parse_metric(aria.split(' ')[0])
                
                # インプレッション取得
                view_elem = await page.query_selector('a[href*="/analytics"] span')
                if view_elem:
                    item['impression_count'] = parse_metric(await view_elem.inner_text())

            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                continue

        await browser.close()

    # 分析スクリプトを呼び出して analysis.json も更新
    os.system('python analyze_data.py')

    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(fetch_metrics())