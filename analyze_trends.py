import json
import os
from datetime import datetime

def analyze_trends():
    file_path = 'collect.json'
    
    if not os.path.exists(file_path):
        print("データファイルが見つかりません。")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 数値が入っているデータだけを抽出
    analyzable_data = [d for d in data if d.get('like_count', 0) > 0]

    if not analyzable_data:
        print("数値データ（いいね数）がまだ取得できていないようです。fetch_metrics.py を回しましょう！")
        return

    print(f"\n📊 分析対象: {len(analyzable_data)} 件 / 全 {len(data)} 件")
    print("="*60)

    # ---------------------------------------------------------
    # 1. 総合「神」投稿ランキング (Top 5)
    # ---------------------------------------------------------
    print("\n🏆 【総合】いいね数ランキング Top 5")
    sorted_by_likes = sorted(analyzable_data, key=lambda x: x['like_count'], reverse=True)
    for i, item in enumerate(sorted_by_likes[:5]):
        print(f"{i+1}. {item['member_name']} (♥️ {item['like_count']:,}) - {item.get('author_name', 'Unknown')}")
        print(f"   🔗 {item['url']}")

    # ---------------------------------------------------------
    # 2. メンバー別 平均戦闘力（平均いいね数）
    # ---------------------------------------------------------
    print("\n📈 【メンバー別】平均いいね数 (投稿5件以上のみ)")
    member_stats = {}
    for item in analyzable_data:
        m = item['member_name']
        if m not in member_stats: member_stats[m] = []
        member_stats[m].append(item['like_count'])
    
    # 平均を計算してソート
    avg_stats = []
    for m, likes in member_stats.items():
        if len(likes) >= 5: # データが少なすぎるメンバーは除外
            avg_stats.append((m, sum(likes)/len(likes), len(likes)))
    
    avg_stats.sort(key=lambda x: x[1], reverse=True)
    
    for rank, (name, avg, count) in enumerate(avg_stats):
        print(f"{rank+1}. {name}: 平均 {int(avg):,} いいね (母数: {count}件)")

    # ---------------------------------------------------------
    # 3. 隠れた名作？ エンゲージメント率ランキング (インプが取れている場合)
    # ---------------------------------------------------------
    # 「見られた回数は少ないのに、見た人は高確率でいいねした」＝ 写真の力が強い
    print("\n💎 【高効率】エンゲージメント率 Top 5 (Likes / Views)")
    with_impressions = [d for d in analyzable_data if d.get('impression_count', 0) > 1000] # インプ1000以上限定
    
    if with_impressions:
        sorted_by_eng = sorted(with_impressions, key=lambda x: (x['like_count'] / x['impression_count']), reverse=True)
        for i, item in enumerate(sorted_by_eng[:5]):
            rate = (item['like_count'] / item['impression_count']) * 100
            print(f"{i+1}. {rate:.2f}% - {item['member_name']} (♥️{item['like_count']} / 👀{item['impression_count']})")
            print(f"   🔗 {item['url']}")
    else:
        print("   (インプレッションデータが不足しているためスキップ)")

if __name__ == "__main__":
    analyze_trends()