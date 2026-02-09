import json
import os
import requests
from io import BytesIO
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel

# --- 設定 ---
# GitHub Actionsでも動く軽量モデルを使用
MODEL_ID = "openai/clip-vit-base-patch32"

print("🚀 Loading CLIP model... (This may take a minute on the first run)")
model = CLIPModel.from_pretrained(MODEL_ID)
processor = CLIPProcessor.from_pretrained(MODEL_ID)

def check_image_locally(image_url, member_name):
    """
    CLIPを使って画像とテキストの類似度を計算し、
    その画像が指定したメンバーのコスプレである確率が高いかを判定する。
    """
    try:
        # 1. 画像の取得
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(image_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return False
        
        image = Image.open(BytesIO(response.content)).convert("RGB")

        # メンバーごとの特徴を考慮したラベル設定（例）
        labels = [
         f"a photo of a girl with colored hair cosplaying {member_name} from vspo anime style", # 正解
         "cosplay of Demon Slayer Kimetsu no Yaiba or Genshin Impact", # 強力な除外ターゲット
         "a screenshot of a video game or anime character", # 除外
         "just a random person or text or goods" # 除外
        ]
        # 3. 推論
        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        
        # 確率を取得
        probs = outputs.logits_per_image.softmax(dim=1)
        top_prob = probs[0][top_index].item()
        
        # 0番目（正解）が選ばれ、かつ「自信（確率）」が 0.6(60%) 以上の時だけ合格
        # この数値を 0.7 や 0.8 に上げると、より厳選されます
        if top_index == 0 and top_prob > 0.6:
            print(f"✅ OK ({member_name}) - Prob: {top_prob:.2f}")
            return True
        else:
            print(f"🗑️ REJECT - Prob: {top_prob:.2f} (Index: {top_index})")
            return False

    except Exception as e:
        print(f"⚠️ Error checking {image_url}: {e}")
        return True # エラー時は安全のために残す

def main():
    data_file = 'collect.json'
    if not os.path.exists(data_file):
        print("collect.jsonが見つかりません。")
        return

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"🔍 分析開始: {len(data)}件のデータをチェックします。")
    
    cleaned_data = []
    removed_count = 0

    for i, item in enumerate(data):
        print(f"[{i+1}/{len(data)}]", end=" ")
        
        # 画像がないデータは残す
        if not item.get('images') or len(item['images']) == 0:
            cleaned_data.append(item)
            continue

        # 判定実行
        if check_image_locally(item['images'][0], item['member_name']):
            cleaned_data.append(item)
        else:
            removed_count += 1

    # 上書き保存
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"\n✨ 掃除完了！ {removed_count}件のノイズを削除しました。")
    print(f"残ったデータ: {len(cleaned_data)}件")

if __name__ == "__main__":
    main()
