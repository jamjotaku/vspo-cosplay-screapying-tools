import json
import os
import re
import asyncio
import base64
import random
from datetime import datetime
from playwright.async_api import async_playwright
import google.generativeai as genai

# ■■■ 設定：ノイズ除去キーワード（AI前の門番） ■■■
EXCLUDE_KEYWORDS = [
    "譲渡", "買取", "交換", "グッズ", "回収", "同行", "代行", 
    "検索用", "求)", "出)", "譲)", "定価", "取引", "入荷", "完売"
]

# APIキーの読み込み
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def extract_number(text, pattern):
    if not text: return "0"
    match = re.search(pattern, text)
    return match.group(1) if match else "0"

# --- AI判定関数 ---
async def check_image_with_gemini(page, image_url, member_name):
    # APIキーがない場合は判定をスルーして「合格」とする
    if not GEMINI_API_KEY:
        return True
    
    print(f"   🤖 AI Checking: Is this {member_name}?")
    try:
        # 1. 画像データをダウンロード (メモリ上で行う)
        response = await page.request.get(image_url)
        if response.status != 200:
            return False
        image_bytes = await response.body()

        # 2. AIモデルの準備 (Gemini 1.5 Flash は高速で安価)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 3. 質問内容（プロンプト）
        # 「これは[キャラ名]のコスプレですか？ 他のキャラならFalseを返して」と指示
        prompt = f"""
        Look at this image. Is this a cosplay of the VTuber "{member_name}" (from VSPO/Buisupo)?
        
        Strict rules:
        - If it is clearly {member_name}, answer "TRUE".
        - If it is a completely different character (e.g. Genshin Impact, Hololive, generic anime girl), answer "FALSE".
        - If it is just a wig, clothes without a person, or text/screenshot, answer "FALSE".
        - Only return "TRUE" or "FALSE".
        """

        # 4. 送信
        # Geminiにバイナリを渡すための形式
        image_parts = [{"mime_type": "image/jpeg", "data": image_bytes}]
        
        result = await model.generate_content_async([prompt, image_parts[0]])
        answer = result.text.strip().upper()

        if "TRUE" in answer:
            print("   ✅ AI Pass: Looks like target character.")
            return True
        else:
            print(f"   🗑️ AI Reject: {answer} (Probably different character)")
            return False

    except Exception as e:
        print(f"   ⚠️ AI Error: {e} (Allowing by default)")
        return True # エラー時はとりあえず通す（または厳しくFalseにするかはお好みで）

async def scrape_vspo_cosplay(context, member):
    results = []
    page = await context.new_page()
    await page.set_viewport_size({"width": 1280, "height": 800})

    query = f"{member['name']} コスプレ"
    url = f"https://x.com/search?q={query}&src=typed_query&f=live"
    
    print(f"--- Searching for: {member['name']} ---")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        if "login" in page.url:
            print(f"⚠️ Login page detected. Skipping.")
            return []

        try:
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
        except:
            print(f"❌ No tweets found (Timeout).")
            return []

        for _ in range(3):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        print(f"✅ Found {len(tweets)} tweets in DOM")

        for i, tweet in enumerate(tweets):
            try:
                user_elem = await tweet.query_selector('[data-testid="User-Name"]')
                full_name = await user_elem.inner_text() if user_elem else "Unknown"
                
                if "プロモーション" in full_name or "Ad" in full_name: continue

                content_elem = await tweet.query_selector('[data-testid="tweetText"]')
                content = await content_elem.inner_text() if content_elem else ""

                # テキストフィルター
                if any(k in content for k in EXCLUDE_KEYWORDS):
                    print(f"  ⏩ Skip: Noise keyword detected.")
                    continue

                images = []
                photo_divs = await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')
                for img in photo_divs:
                    src = await img.get_attribute('src')
                    if src: images.append(src)
                
                if not images:
                    # 代替手段
                    all_imgs = await tweet.query_selector_all('img')
                    for img in all_imgs:
                        src = await img.get_attribute('src')
                        if src and "pbs.twimg.com/media" in src and "profile_images" not in src:
                            images.append(src)

                images = list(set(images))

                link_elem = await tweet.query_selector('a[href*="/status/"]')
                tweet_url = f"https://x.com{await link_elem.get_attribute('href')}" if link_elem else ""

                if images and tweet_url:
                    # ★★★ ここでAI判定を実行！ ★★★
                    # 最初の1枚だけチェックして判断する（節約と高速化のため）
                    is_valid = await check_image_with_gemini(page, images[0], member['name'])
                    
                    if is_valid:
                        results.append({
                            "member_id": member.get('id', 'unknown'),
                            "member_name": member['name'],
                            "author_name": full_name.split("\n")[0],
                            "content": content,
                            "images": images,
                            "url": tweet_url,
                            "collected_at": datetime.now().isoformat(),
                            "source": "X"
                        })
                        print(f"  ⭕ Saved tweet: {len(images)} images")
                    else:
                        print(f"  ❌ Skipped by AI (Wrong character)")

                else:
                    pass # 画像なし

            except Exception as e:
                print(f"  ❌ Error processing tweet {i+1}: {e}")
                continue

    except Exception as e:
        print(f"❌ Error scraping {member['name']}: {e}")
    
    await page.close()
    return results

async def main():
    if not os.path.exists('members.json'): return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    # テスト時は人数を絞る
    # members = members[:2]

    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try: all_data = json.load(f)
            except: all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
            if count > 0:
                print(f"✨ Added {count} new items for {member['name']}")
            
            await asyncio.sleep(random.uniform(2, 4))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print(f"🚀 Finished! Total items in DB: {len(all_data)}")

if __name__ == "__main__":
    asyncio.run(main())
