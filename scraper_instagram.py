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

# ■■■ 設定：CLIPモデル ■■■
MODEL_ID = "openai/clip-vit-base-patch32"
print("🚀 Loading Local AI (CLIP)...")
try:
    model = CLIPModel.from_pretrained(MODEL_ID)
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
except:
    model = None

def check_image_locally(image_url, member_name):
    if model is None: return True
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code != 200: return False
        
        image = Image.open(BytesIO(response.content)).convert("RGB")
        labels = [
            f"a cosplay photo of {member_name}",
            "game screenshot or text",
            "random object"
        ]
        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        
        return outputs.logits_per_image.softmax(dim=1).argmax().item() == 0
    except:
        return True

async def scrape_instagram_tag(context, member):
    results = []
    page = await context.new_page()
    tag = f"{member['name']}コスプレ"
    url = f"https://www.instagram.com/explore/tags/{tag}/"
    
    print(f"--- [Insta] Searching: #{tag} ---")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(6, 10))

        if "login" in page.url:
            print(f"⚠️ Login required/Cookie expired")
            return []

        posts = await page.query_selector_all('a[href*="/p/"]')
        print(f"   Found {len(posts)} posts")

        for post in posts[:10]:
            try:
                post_url = f"https://www.instagram.com{await post.get_attribute('href')}"
                img_elem = await post.query_selector('img')
                if not img_elem: continue
                
                img_src = await img_elem.get_attribute('src')
                alt_text = await img_elem.get_attribute('alt')
                caption = alt_text if alt_text else ""

                if img_src and post_url:
                    if check_image_locally(img_src, member['name']):
                        results.append({
                            "member_name": member['name'],
                            "author_name": "InstagramUser",
                            "content": caption,
                            "images": [img_src],
                            "url": post_url,
                            "source": "Instagram",
                            "collected_at": datetime.now().isoformat()
                        })
                        print(f"   ✅ Saved: {post_url}")
                    else:
                        print(f"   🗑️ Rejected by AI")
            except: continue

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
        
        if not os.path.exists('auth_instagram.json'):
            print("Error: auth_instagram.json not found.")
            await browser.close()
            return

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
            
            await asyncio.sleep(random.uniform(5, 10))
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        print("🎉 Instagram Scraping Finished!")

if __name__ == "__main__":
    asyncio.run(main())