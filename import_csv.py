import csv
import json
import os
from datetime import datetime

def import_csv_to_json():
    csv_file = 'vspo_data.csv'
    json_file = 'collect.json'
    
    if not os.path.exists(csv_file):
        print(f"❌ {csv_file} が見つかりません。")
        return

    # 既存データの読み込み
    current_data = []
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                current_data = json.load(f)
            except:
                current_data = []
    
    # 重複チェック用のURLセット
    existing_urls = {item['url'] for item in current_data}
    new_count = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        # UTF-8 with BOM や、カンマ区切りを考慮して読み込み
        reader = csv.reader(f)
        try:
            header = next(reader) # ヘッダー行をスキップ
        except StopIteration:
            return

        for row in reader:
            # A:メンバー, B:レイヤー名, C:画像, D:ツイートURL
            if len(row) < 4:
                continue
            
            m_name = row[0].strip() # ぶいすぽメンバー
            a_name = row[1].strip() # コスプレイヤー
            img_url = row[2].strip() # 画像(twimg)
            tweet_url = row[3].strip() # 元ツイート
            
            # URLが空、または既に登録済みの場合はスキップ
            if not tweet_url or tweet_url in existing_urls:
                continue

            # 共通フォーマットへ変換
            current_data.append({
                "member_name": m_name,
                "author_name": a_name,
                "images": [img_url] if img_url else [],
                "url": tweet_url,
                "source": "X",
                "content": f"Cosplayer: {a_name}", # 本文の代わりにレイヤー名を記載
                "like_count": 0,
                "impression_count": 0,
                "collected_at": datetime.now().isoformat()
            })
            existing_urls.add(tweet_url)
            new_count += 1

    # 日付順（新しい順）に並び替えて保存
    current_data.sort(key=lambda x: x.get('collected_at', ''), reverse=True)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

    print(f"✅ インポート完了！")
    print(f"新規追加: {new_count}件")
    print(f"現在の合計: {len(current_data)}件")

if __name__ == "__main__":
    import_csv_to_json()
