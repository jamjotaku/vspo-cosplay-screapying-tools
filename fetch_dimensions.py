import json
import os
import requests
from PIL import Image
from io import BytesIO

def fetch_dimensions():
    file_path = 'collect.json'
    if not os.path.exists(file_path): return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("📸 画像サイズの解析を開始します...")
    count = 0
    # 1回の実行で処理する上限（GitHub Actionsの制限時間を考慮）
    limit = 100 

    for item in data:
        if count >= limit: break
        
        # 画像URLがあり、まだサイズが記録されていないもの
        if item.get('images') and not item.get('width'):
            img_url = item['images'][0]
            try:
                # タイムアウトを短めに設定して効率化
                response = requests.get(img_url, timeout=5)
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                
                item['width'] = width
                item['height'] = height
                
                # アスペクト比の判定
                ratio = width / height
                if ratio < 0.85:
                    item['aspect_type'] = 'Portrait (縦長)'
                elif ratio > 1.15:
                    item['aspect_type'] = 'Landscape (横長)'
                else:
                    item['aspect_type'] = 'Square (正方形)'
                
                count += 1
                print(f"  [{count}] Processed: {item['aspect_type']} ({width}x{height})")

            except Exception as e:
                print(f"  ❌ Skip {img_url}: {e}")
                continue

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✨ 完了！ 新たに {count} 件のサイズを特定しました。")

if __name__ == "__main__":
    fetch_dimensions()