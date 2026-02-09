import json
import os
import asyncio
import time
import requests
import google.generativeai as genai

# APIキーの設定
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def check_image_with_ai(image_url, member_name):
    if not GEMINI_API_KEY: return True
    
    print(f"🤖 Checking {member_name}...", end=" ")
    try:
        # 最新モデルを使用
        model = genai.GenerativeModel('gemini-2.5-flash-image')
        
        # 画像ダウンロード
        resp = requests.get(image_url, timeout=15)
        if resp.status_code != 200:
            print("❌ Image Load Fail")
            return False
            
        image_bytes = resp.content
        
        # プロンプト（判定基準をより具体化）
        prompt = f"""
        Is the person in this photo cosplaying the VTuber "{member_name}" from the group "VSPO!"?
        Return "TRUE" if it is highly likely to be {member_name}.
        Return "FALSE" if it is a different character, just a person in normal clothes, or goods.
        Strictly answer only "TRUE" or "FALSE".
        """
        
        image_parts = [{"mime_type": "image/jpeg", "data": image_bytes}]
        result = await model.generate_content_async([prompt, image_parts[0]])
        answer = result.text.strip().upper()
        
        if "TRUE" in answer:
            print("✅ OK")
            return True
        else:
            print(f"🗑️ REJECT")
            return False

    except Exception as e:
        print(f"⚠️ Error: {e}")
        return True

async def main():
    data_file = 'collect.json'
    if not os.path.exists(data_file): return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"🔍 Items to check: {len(data)}")
    
    cleaned_data = []
    removed_count = 0

    for item in data:
        # 千燈ゆうひや一ノ瀬うるはなど、特定の推しを優先的に残すようAIに判断させます
        is_valid = await check_image_with_ai(item['images'][0], item['member_name'])
        
        if is_valid:
            cleaned_data.append(item)
        else:
            removed_count += 1
        
        # Rate limit 対策
        await asyncio.sleep(2)

    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"\n✨ Finished! Removed {removed_count} noise items.")

if __name__ == "__main__":
    asyncio.run(main())