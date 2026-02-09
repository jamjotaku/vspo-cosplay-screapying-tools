import json
import os
from datetime import datetime

def analyze_data():
    input_file = 'collect.json'
    output_file = 'analysis.json'

    if not os.path.exists(input_file):
        print("❌ データファイルがありません")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # 数値が入っているデータだけを抽出
    valid_data = [d for d in raw_data if d.get('like_count', 0) > 0]
    
    if not valid_data:
        print("⚠️ 数値データがまだありません")
        return

    # --- 1. メンバー別平均いいねランキング ---
    member_stats = {}
    for d in valid_data:
        name = d['member_name']
        likes = d['like_count']
        if name not in member_stats:
            member_stats[name] = {'total': 0, 'count': 0, 'max': 0}
        member_stats[name]['total'] += likes
        member_stats[name]['count'] += 1
        if likes > member_stats[name]['max']:
            member_stats[name]['max'] = likes

    member_ranking = []
    for name, stats in member_stats.items():
        if stats['count'] >= 3: # 投稿3件以上のみ
            avg = int(stats['total'] / stats['count'])
            member_ranking.append({
                'name': name,
                'avg': avg,
                'max': stats['max'],
                'count': stats['count']
            })
    member_ranking.sort(key=lambda x: x['avg'], reverse=True)

    # --- 2. エンゲージメント率ランキング (インプありのみ) ---
    with_imp = [d for d in valid_data if d.get('impression_count', 0) > 500]
    engagement_ranking = []
    for d in with_imp:
        rate = (d['like_count'] / d['impression_count']) * 100
        engagement_ranking.append({
            'member_name': d['member_name'],
            'url': d['url'],
            'rate': round(rate, 2),
            'likes': d['like_count'],
            'views': d['impression_count'],
            'thumb': d['images'][0] if d['images'] else ''
        })
    engagement_ranking.sort(key=lambda x: x['rate'], reverse=True)

    # --- 3. 総合いいねランキング ---
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:50]
    # 軽量化のため必要な情報だけに絞る
    simple_like_ranking = []
    for d in like_ranking:
        simple_like_ranking.append({
            'member_name': d['member_name'],
            'url': d['url'],
            'likes': d['like_count'],
            'thumb': d['images'][0] if d['images'] else ''
        })

    # --- 結果を出力 ---
    result = {
        'updated_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        'total_analyzed': len(valid_data),
        'total_records': len(raw_data),
        'member_ranking': member_ranking,
        'engagement_ranking': engagement_ranking[:30],
        'like_ranking': simple_like_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 分析完了: {len(valid_data)}件のデータを処理しました")

if __name__ == "__main__":
    analyze_data()