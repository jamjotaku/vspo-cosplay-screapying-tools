import json
import os
from collections import Counter
from datetime import datetime

def analyze_vspo_data():
    input_file = 'collect.json'
    output_file = 'analysis.json'

    if not os.path.exists(input_file):
        print(f"❌ {input_file} が見つかりません。")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"📊 {len(data)} 件のデータを分析中...")

    # 1. 基本サマリー
    total_posts = len(data)
    members = [item.get('member_name', 'Unknown') for item in data if item.get('member_name')]
    unique_members = len(set(members))
    
    # 2. メンバー別ランキング (Top 20)
    member_counts = Counter(members)
    member_ranking = dict(member_counts.most_common(20))

    # 3. プラットフォーム割合 (X vs Instagram)
    sources = [item.get('source', 'Unknown') for item in data]
    source_ratio = dict(Counter(sources))

    # 4. 時系列データ (日別の投稿数推移)
    # collected_at を日付(YYYY-MM-DD)に変換して集計
    dates = []
    for item in data:
        raw_date = item.get('collected_at', '')
        if raw_date:
            try:
                date_str = raw_date.split('T')[0]
                dates.append(date_str)
            except:
                continue
    
    # 直近30日分などのトレンドを把握
    timeline_counts = Counter(dates)
    # 日付順にソート（直近30件など）
    sorted_timeline = dict(sorted(timeline_counts.items(), reverse=True)[:30])
    # グラフ表示用に古い順に戻す
    display_timeline = dict(reversed(list(sorted_timeline.items())))

    # 5. 「いいね」数ランキング (Top 5)
    # 数値がない場合は0として処理
    sorted_by_likes = sorted(
        data, 
        key=lambda x: int(x.get('like_count', 0)), 
        reverse=True
    )
    
    top_liked_posts = []
    for item in sorted_by_likes[:5]:
        top_liked_posts.append({
            "member": item.get('member_name'),
            "likes": item.get('like_count', 0),
            "url": item.get('url'),
            "image": item.get('images', [""])[0]
        })

    # 集計結果のまとめ
    analysis_result = {
        "summary": {
            "total_posts": total_posts,
            "total_members": unique_members,
            "last_updated": datetime.now().isoformat()
        },
        "member_ranking": member_ranking,
        "source_ratio": source_ratio,
        "timeline": display_timeline,
        "top_liked_posts": top_liked_posts
    }

    # analysis.json として保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)

    print(f"✅ {output_file} を作成しました。")

if __name__ == "__main__":
    analyze_vspo_data()