import json
import os
import requests
from io import BytesIO
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel

# --- 設定 ---
MODEL_ID = "openai/clip-vit-base-patch32"
# 判定の厳しさ（0.6 ~ 0.8 推奨）
CONFIDENCE_THRESHOLD = 0.70 

print("🚀 Loading CLIP model...")
model = CLIPModel.from_pretrained(MODEL_ID)
processor = CLIPProcessor.from_pretrained(MODEL_ID)

def check_image_locally(image_url, member_name):
    try:
        # 1. 画像取得
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(image_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False
        
        image = Image.open(BytesIO(response.content)).convert("RGB")

        # 2. ラベル定義（ここが精度向上のカギ！）
        # 0番目: 正解（少し具体的に書く）
        # 1番目以降: 間違いの選択肢（よく混ざる作品名を名指しする）
        labels = [
            f"a high quality cosplay photo of {member_name} from VSPO VTuber group", # 正解
            "Demon Slayer Kimetsu no Yaiba cosplay", # 鬼滅
            "Genshin Impact or Honkai Star Rail character", # 原神・スタレ
            "generic anime girl figure or drawing", # フィギュア・絵
            "screenshot of text or game UI or twitter timeline" # スクショ
        ]

        # 3. AI推論
        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        
        # 確率計算
        probs = outputs.logits_per_image.softmax(dim=1)
        
        # ★ ここで変数を定義（前回のエラー箇所修正）
        top_index = probs.argmax().item()
        top_score = probs[0][top_index].item()

        # 4. 判定ロジック
        # 「0番目（正解）が選ばれた」 かつ 「確信度が閾値を超えている」 場合のみ合格
        if top_index == 0 and top_score > CONFIDENCE_THRESHOLD:
            print(f"✅ OK ({member_name}) - Score: {top_score:.2f}")
            return True
        else:
            # 何と間違えたか表示（デバッグ用）
            rejected_reason = labels[top_index] if top_index < len(labels) else "Unknown"
            print(f"🗑️ REJECT - Score: {top_score:.2f} (Matched: {rejected_reason})")
            return False

    except Exception as e:
        print(f"⚠️ Error checking {image_url}: {e}")
        return True # エラー時は安全のため残す

def main():
    data_file = 'collect.json'
    if not os.path.exists(data_file):
        print("collect.json not found.")
        return

    # バックアップ作成
    import shutil
    shutil.copy('collect.json', 'collect_backup.json')

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"🔍 Cleaning {len(data)} items with Strict Mode (Threshold: {CONFIDENCE_THRESHOLD})...")
    
    cleaned_data = []
    removed_count = 0

    for i, item in enumerate(data):
        if not item.get('images'):
            cleaned_data.append(item)
            continue
            
        # 進行状況表示
        if i % 10 == 0: print(f"Processing {i}/{len(data)}...")

        if check_image_locally(item['images'][0], item['member_name']):
            cleaned_data.append(item)
        else:
            removed_count += 1

    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"\n✨ Done! Removed {removed_count} items.")
    print(f"Original: {len(data)} -> Cleaned: {len(cleaned_data)}")

if __name__ == "__main__":
    main()
