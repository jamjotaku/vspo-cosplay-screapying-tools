import json
import os
from datetime import datetime

def analyze_data():
    input_file = 'collect.json'
    authors_file = 'authors.json'
    output_file = 'analysis.json'

    if not os.path.exists(input_file): return

    # データの読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    authors_data = {}
    if os.path.exists(authors_file):
        with open(authors_file, 'r', encoding='utf-8') as f:
            authors_data = json.load(f)

    # 数値計算
    valid_data = []
    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue
        
        # ユーザーID特定
        username = d['url'].split('x.com/')[1].split('/')[0]
        followers = authors_data.get(username, 0)

        # Viral Score の計算 (フォロワーが100人以上の場合のみ計算して精度を保つ)
        viral_score = 0
        if followers > 100:
            viral_score = round(likes / followers, 3)

        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        valid_data.append(d_copy)

    # --- ランキング作成 ---
    # 1. 真の実力ランキング (Viral Score)
    viral_ranking = sorted(valid_data, key=lambda x: x['viral_score'], reverse=True)[:30]
    
    # 2. 総合いいねランキング
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:30]

    # --- メンバー別集計 ---
    member_stats = {}
    for d in valid_data:
        name = d['member_name']
        if name not in member_stats:
            member_stats[name] = {'total_likes': 0, 'count': 0}
        member_stats[name]['total_likes'] += d['like_count']
        member_stats[name]['count'] += 1

    member_ranking = []
    for name, s in member_stats.items():
        if s['count'] >= 3:
            member_ranking.append({'name': name, 'avg': int(s['total_likes']/s['count'])})
    member_ranking.sort(key=lambda x: x['avg'], reverse=True)

    # 保存
    result = {
        'updated_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        'total_analyzed': len(valid_data),
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 分析完了！ {len(valid_data)}件を処理しました。")

if __name__ == "__main__":
    analyze_data()