import json
import os

def prioritize_members():
    file_path = 'collect.json'
    if not os.path.exists(file_path): return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ここに優先したいメンバー名を入れる
    targets = ["花芽すみれ", "花芽なずな"]

    # 1. 優先メンバー (未取得)
    priority_todo = [d for d in data if d.get('member_name') in targets and d.get('like_count', 0) == 0]
    
    # 2. その他 (未取得)
    other_todo = [d for d in data if d.get('member_name') not in targets and d.get('like_count', 0) == 0]
    
    # 3. 完了済み
    done = [d for d in data if d.get('like_count', 0) > 0]

    # 並び替え: [優先] -> [その他] -> [完了]
    new_order = priority_todo + other_todo + done

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(new_order, f, ensure_ascii=False, indent=2)

    print(f"✨ 並び替え完了！ 次回は {len(priority_todo)} 件の推しデータを最優先で取得します。")

if __name__ == "__main__":
    prioritize_members()