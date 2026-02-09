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

    # 数値計算とデータ結合
    valid_data = []
    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue
        
        # ユーザーID特定
        url_parts = d['url'].split('x.com/')
        if len(url_parts) > 1:
            username = url_parts[1].split('/')[0]
        else:
            username = "unknown"
            
        followers = authors_data.get(username, 0)

        # Viral Score の計算 (フォロワーが100人以上の場合のみ計算)
        viral_score = 0
        if followers > 100:
            viral_score = round(likes / followers, 3)

        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        valid_data.append(d_copy)

    # --- 1. エンゲージメント率ランキング (復活！) ---
    # インプレッションがあるデータのみ抽出
    with_imp = [d for d in valid_data if d.get('impression_count', 0) > 100]
    engagement_ranking = []
    for d in with_imp:
        rate = (d['like_count'] / d['impression_count']) * 100
        d_copy = d.copy()
        d_copy['rate'] = round(rate, 2)
        engagement_ranking.append(d_copy)
    
    # 率が高い順にソートしてTop30
    engagement_ranking.sort(key=lambda x: x['rate'], reverse=True)
    engagement_ranking = engagement_ranking[:30]

    # --- 2. 真の実力ランキング (Viral Score) ---
    viral_ranking = sorted(valid_data, key=lambda x: x['viral_score'], reverse=True)[:30]
    
    # --- 3. 総合いいねランキング ---
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:30]

    # --- 4. メンバー別集計 ---
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
        'total_records': len(raw_data),
        'engagement_ranking': engagement_ranking, # ここを復活
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 分析完了！ {len(valid_data)}件を処理しました（エンゲージメント計算含む）。")

if __name__ == "__main__":
    analyze_data()