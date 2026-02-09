import json
import os
import asyncio
import time
import google.generativeai as genai
from datetime import datetime

# APIキーの設定
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def check_image_with_ai(image_url, member_name):
    if not GEMINI_API_KEY: return True # キーがない場合は削除しない
    
    print(f"🤖 Checking: {member_name} ...", end=" ")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 簡易チェックのため、画像URLを直接渡すのではなく
        # ここでは「画像データ」をダウンロードする処理を省略し、
        # 以前のスクリプト同様に実際の運用ではPlaywright等で画像バイナリを取得するのが確実ですが、
        # 簡易的に「既に集めたデータ」をチェックする場合、実は画像URLだけではAIが見れない場合があります。
        # (Geminiは公開URLを直接見に行けない場合があるため)
        
        # ★重要★
        # 既存データのクリーニングは「画像バイナリ」が必要なため、
        # 簡易的なrequestsライブラリを使って画像をダウンロードして渡します。
        import requests
        
        # 画像ダウンロード
        resp = requests.get(image_url, timeout=10)
        if resp.status_code != 200:
            print("❌ Image Load Error (Skip)")
            return False # 画像が見れないなら削除対象にするか迷いますが、一旦Falseで
            
        image_bytes = resp.content
        
        prompt = f"""
        Look at this image. Is this a cosplay of the VTuber "{member_name}" (from VSPO/Buisupo)?
        
        Strict rules:
        - If it is clearly {member_name}, answer "TRUE".
        - If it is a completely different character (e.g. Genshin Impact, Hololive, Anime character), answer "FALSE".
        - If it is text only, screenshot of game UI, or goods/merch, answer "FALSE".
        - Only return "TRUE" or "FALSE".
        """
        
        image_parts = [{"mime_type": "image/jpeg", "data": image_bytes}]
        result = await model.generate_content_async([prompt, image_parts[0]])
        answer = result.text.strip().upper()
        
        if "TRUE" in answer:
            print("✅ OK")
            return True
        else:
            print(f"🗑️ REJECT ({answer})")
            return False

    except Exception as e:
        print(f"⚠️ Error: {e}")
        return True # エラーの場合は安全のため残す

async def main():
    if not os.path.exists('collect.json'):
        print("collect.json not found.")
        return

    # バックアップを作成
    import shutil
    shutil.copy('collect.json', 'collect_backup.json')
    print("📦 Created backup: collect_backup.json")

    with open('collect.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"🔍 Total items before cleaning: {len(data)}")
    
    cleaned_data = []
    removed_count = 0

    for i, item in enumerate(data):
        # 画像URLがあるか確認
        if not item.get('images'):
            cleaned_data.append(item)
            continue

        image_url = item['images'][0]
        member_name = item['member_name']
        
        # AIチェック実行
        is_valid = await check_image_with_ai(image_url, member_name)
        
        if is_valid:
            cleaned_data.append(item)
        else:
            removed_count += 1
        
        # API制限（Rate Limit）対策：無料枠は1分間に15回までなので、4秒待つ
        time.sleep(4) 

    # 保存
    with open('collect.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print(f"✨ Cleaning Finished!")
    print(f"Original: {len(data)}")
    print(f"Removed : {removed_count}")
    print(f"Remaining: {len(cleaned_data)}")

if __name__ == "__main__":
    asyncio.run(main())
