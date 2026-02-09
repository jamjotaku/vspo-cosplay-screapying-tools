import json
import os
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright
import google.generativeai as genai

# ■■■ AI設定 ■■■
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def check_image_with_gemini(page, image_url, member_name):
    if not GEMINI_API_KEY:
        return True
    
    print(f"   🤖 [Insta AI] Checking: Is this {member_name}?")
    try:
        response = await page.request.get(image_url)
        if response.status != 200: return False
        image_bytes = await response.body()

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Look at this Instagram post image. Is this a cosplay of the VTuber "{member_name}" from VSPO (Buisupo)?
        Answer "TRUE" only if it is clearly that character. 
        If it's a different character (e.g. Genshin, Hololive) or not a person, answer "FALSE".
        Only return "TRUE" or "FALSE".
        """

        image_parts = [{"mime_type": "image/jpeg", "data": image_bytes}]
        result = await model.generate_content_async([prompt, image_parts[0]])
        answer = result.text.strip().upper()

        if "TRUE" in answer:
            print("   ✅ AI Pass")
            return True
        else:
            print(f"   🗑️ AI Reject: {answer}")
            return False
    except Exception as e:
        print(f"   ⚠️ AI Error: {e}")
        return True

async def scrape_instagram_tag(context, member):
    results = []
    page = await context.new_page()
    tag = f"{member['name']}コスプレ"
    url = f"https://www.instagram.com/explore/tags/{tag}/"
    
    print(f"--- [Instagram] Searching for: #{tag} ---")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(5, 8))

        if "login" in page.url:
            print(f"⚠️ Cookie expired.")
            return []

        # 投稿リンクの取得
        posts = await page.query_selector_all('a[href*="/p/"]')
        print(f"✅ Found {len(posts)} posts in view")

        for i, post in enumerate(posts[:8]): # BAN対策で件数を絞る
            try:
                post_url = f"https://www.instagram.com{await post.get_attribute('href')}"
                img_elem = await post.query_selector('img')
                if not img_elem: continue
                
                img_src = await img_elem.get_attribute('src')
                alt_text = await img_elem.get_attribute('alt')
                caption = alt_text if alt_text else "No caption"

                if img_src and post_url:
                    # ★★★ ここでAI判定 ★★★
                    is_valid = await check_image_with_gemini(page, img_src, member['name'])
                    
                    if is_valid:
                        results.append({
                            "member_id": member.get('id', 'unknown'),
                            "member_name": member['name'],
                            "author_name": "InstagramUser",
                            "content": caption,
                            "images": [img_src],
                            "url": post_url,
                            "source": "Instagram",
                            "collected_at": datetime.now().isoformat()
                        })
                        print(f"  ⭕ Saved: {post_url}")
                    else:
                        print(f"  ❌ AI Skipped (Wrong character)")

            except Exception: continue

    except Exception as e:
        print(f"❌ Error: {e}")
    
    await page.close()
    return results

async def main():
    if not os.path.exists('members.json'): return
    with open('members.json', 'r', encoding='utf-8') as f:
        members = json.load(f)

    data_file = 'collect.json'
    all_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try: all_data = json.load(f)
            except: all_data = []
    
    existing_urls = {item['url'] for item in all_data}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
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
            if count > 0: print(f"✨ Added {count} from Instagram for {member['name']}")
            await asyncio.sleep(random.uniform(5, 10))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
