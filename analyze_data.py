import json
import os
from datetime import datetime, timedelta, timezone

# --- 1. 時間解析用の魔法 (Snowflake ID) ---
def get_tweet_time(tweet_id):
    try:
        # X(Twitter)の紀元: 2010-11-04 01:42:54.657 UTC
        tw_epoch = 1288834974657
        timestamp_ms = (int(tweet_id) >> 22) + tw_epoch
        # UTC -> JST (+9時間)
        dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
        dt_jst = dt_utc.astimezone(timezone(timedelta(hours=9)))
        return dt_jst
    except:
        return None

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

    # --- 2. データ結合と解析 ---
    valid_data = []
    hourly_stats = {h: {'likes': 0, 'count': 0} for h in range(24)} # 時間別集計用
    
    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue
        
        # ユーザーIDとTweet IDの特定
        url_parts = d['url'].split('x.com/')
        username = "unknown"
        tweet_id = None
        
        if len(url_parts) > 1:
            parts = url_parts[1].split('/')
            username = parts[0]
            try:
                status_idx = parts.index('status')
                tweet_id = parts[status_idx + 1].split('?')[0]
            except: pass
            
        followers = authors_data.get(username, 0)

        # Viral Score (フォロワー100人以上で計算)
        viral_score = 0
        if followers > 100:
            viral_score = round(likes / followers, 3)

        # 投稿時間の復元
        hour = -1
        if tweet_id:
            dt = get_tweet_time(tweet_id)
            if dt:
                hour = dt.hour
                hourly_stats[hour]['likes'] += likes
                hourly_stats[hour]['count'] += 1

        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        d_copy['posted_hour'] = hour
        valid_data.append(d_copy)

    # --- 3. 各種ランキング生成 ---
    
    # A. 時間帯別レポート
    hourly_report = []
    for h in range(24):
        s = hourly_stats[h]
        avg = int(s['likes'] / s['count']) if s['count'] > 0 else 0
        hourly_report.append({'hour': h, 'avg_likes': avg, 'count': s['count']})

    # B. エンゲージメント率 (インプ100以上)
    with_imp = [d for d in valid_data if d.get('impression_count', 0) > 100]
    engagement_ranking = []
    for d in with_imp:
        rate = (d['like_count'] / d['impression_count']) * 100
        d_copy = d.copy()
        d_copy['rate'] = round(rate, 2)
        engagement_ranking.append(d_copy)
    engagement_ranking.sort(key=lambda x: x['rate'], reverse=True)

    # C. Viral Score & いいね数
    viral_ranking = sorted(valid_data, key=lambda x: x['viral_score'], reverse=True)[:50]
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:50]

    # D. メンバー別平均
    member_stats = {}
    for d in valid_data:
        name = d['member_name']
        if name not in member_stats: member_stats[name] = {'total_likes': 0, 'count': 0}
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
        'hourly_report': hourly_report,
        'engagement_ranking': engagement_ranking[:30],
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 全分析完了！ {len(valid_data)}件処理 (時間解析・エンゲージメント・Viral Score含む)")

if __name__ == "__main__":
    analyze_data()