import json
import os
import asyncio
import random
import requests
from io import BytesIO
from datetime import datetime
from playwright.async_api import async_playwright
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

# ■■■ 設定：CLIPモデル（CPUでも動く軽量版） ■■■
MODEL_ID = "openai/clip-vit-base-patch32"
print("🚀 Loading Local AI (CLIP)... This takes a moment.")
try:
    model = CLIPModel.from_pretrained(MODEL_ID)
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    print("✅ CLIP Model Loaded!")
except Exception as e:
    print(f"⚠️ Failed to load CLIP: {e}")
    model = None

def check_image_locally(image_url, member_name):
    """
    画像URLをダウンロードし、CLIPで「そのキャラのコスプレか？」を判定する
    """
    if model is None: return True # モデル読み込み失敗時はスルーして保存
    
    try:
        # 画像ダウンロード（タイムアウト設定付き）
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code != 200: return False
        
        image = Image.open(BytesIO(response.content)).convert("RGB")
        
        # 判定ラベル（英語のほうが精度が良い）
        # 0番目が「正解」の基準
        labels = [
            f"a cosplay photo of {member_name}",
            "a screenshot of a video game or anime",
            "text or merchandise or random object"
        ]

        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        
        probs = outputs.logits_per_image.softmax(dim=1)
        top_index = probs.argmax().item()
        
        # 0番目の確率が一番高ければ合格
        if top_index == 0:
            return True
        else:
            return False

    except Exception:
        return True # エラー時は安全のため残す

async def scrape_vspo_cosplay(context, member):
    results = []
    page = await context.new_page()
    
    # 検索クエリ（画像フィルタ付き）
    query = f"{member['name']} コスプレ"
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    print(f"--- [X] Searching: {member['name']} ---")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5) # 読み込み待ち

        # ツイート取得
        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"   Found {len(tweets)} tweets")

        for tweet in tweets[:15]: # 1人あたり最大15件チェック
            try:
                # 本文取得
                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""
                
                # ノイズキーワード除外
                if any(x in content for x in ["譲渡", "買取", "交換", "グッズ"]): continue

                # 画像URL取得
                images = []
                photo_divs = await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')
                for img in photo_divs:
                    src = await img.get_attribute('src')
                    if src: images.append(src)
                
                # リンク取得
                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                if images and tweet_url:
                    # ★AI判定（1枚目だけチェック）
                    if check_image_locally(images[0], member['name']):
                        results.append({
                            "member_name": member['name'],
                            "content": content,
                            "images": images,
                            "url": tweet_url,
                            "source": "X",
                            "collected_at": datetime.now().isoformat()
                        })
                        print(f"   ✅ Saved: {member['name']}")
                    else:
                        print(f"   🗑️ Rejected by AI")
            except Exception:
                continue

    except Exception as e:
        print(f"❌ Error: {e}")
    
    await page.close()
    return results

async def main():
    # メンバーリスト読み込み
    if not os.path.exists('members.json'): return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # 既存データ読み込み
    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try: all_data = json.load(f)
            except: all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    # ブラウザ起動
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # auth.json がない場合は終了
        if not os.path.exists('auth.json'):
            print("Error: auth.json not found.")
            await browser.close()
            return

        context = await browser.new_context(
            storage_state="auth.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        for member in members:
            new_tweets = await scrape_vspo_cosplay(context, member)
            count = 0
            for t in new_tweets:
                if t['url'] not in existing_urls:
                    all_data.append(t)
                    existing_urls.add(t['url'])
                    count += 1
            
            await asyncio.sleep(random.uniform(3, 6)) # BAN対策の休憩
        
        # 保存
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print("🎉 X Scraping Finished!")

if __name__ == "__main__":
    asyncio.run(main())