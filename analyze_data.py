import json
import os
import re
from datetime import datetime, timedelta, timezone

# --- 1. 時間解析用の魔法 ---
def get_tweet_time(tweet_id):
    try:
        tw_epoch = 1288834974657
        timestamp_ms = (int(tweet_id) >> 22) + tw_epoch
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

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    authors_data = {}
    if os.path.exists(authors_file):
        with open(authors_file, 'r', encoding='utf-8') as f:
            authors_data = json.load(f)

    valid_data = []
    hourly_stats = {h: {'likes': 0, 'count': 0} for h in range(24)}
    tag_stats = {} 

    # --- 🎯 魔法のキーワード定義 ---
    # ここに分析したい単語を追加できます
    target_keywords = [
        "速報", "宅コス", "初出し", "イベント", "コミケ", 
        "捏造", "私服", "動画", "自撮り", "オフショ", 
        "供養", "再掲", "そくほ", "スタジオ"
    ]
    keyword_stats = {k: {'total_likes': 0, 'count': 0} for k in target_keywords}

    # 全体の平均いいね数（比較用）
    global_total_likes = 0
    global_count = 0

    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue
        
        global_total_likes += likes
        global_count += 1

        # ユーザー情報
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
        viral_score = 0
        if followers > 100:
            viral_score = round(likes / followers, 3)

        # 時間解析
        hour = -1
        if tweet_id:
            dt = get_tweet_time(tweet_id)
            if dt:
                hour = dt.hour
                hourly_stats[hour]['likes'] += likes
                hourly_stats[hour]['count'] += 1

        # --- テキスト解析 ---
        text = d.get('text', '')
        
        # A. ハッシュタグ抽出
        tags = re.findall(r'[#＃]([a-zA-Z0-9_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+)', text)
        for tag in tags:
            if tag not in tag_stats: tag_stats[tag] = {'total_likes': 0, 'count': 0}
            tag_stats[tag]['total_likes'] += likes
            tag_stats[tag]['count'] += 1

        # B. キーワード分析 (NEW!)
        for kw in target_keywords:
            if kw in text:
                keyword_stats[kw]['total_likes'] += likes
                keyword_stats[kw]['count'] += 1

        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        d_copy['posted_hour'] = hour
        valid_data.append(d_copy)

    # --- 集計結果の整形 ---
    
    # 0. 全体平均
    global_avg = int(global_total_likes / global_count) if global_count > 0 else 0

    # 1. キーワードランキング (NEW!)
    keyword_ranking = []
    for kw, s in keyword_stats.items():
        if s['count'] > 0:
            avg = int(s['total_likes'] / s['count'])
            # "倍率" (全体平均よりどれくらい高いか)
            multiplier = round(avg / global_avg, 2) if global_avg > 0 else 0
            keyword_ranking.append({
                'keyword': kw, 
                'avg_likes': avg, 
                'count': s['count'],
                'multiplier': multiplier
            })
    keyword_ranking.sort(key=lambda x: x['avg_likes'], reverse=True)

    # 2. ハッシュタグランキング
    tag_ranking = []
    for tag, s in tag_stats.items():
        if s['count'] >= 3:
            avg = int(s['total_likes'] / s['count'])
            tag_ranking.append({'tag': tag, 'avg_likes': avg, 'count': s['count']})
    tag_ranking.sort(key=lambda x: x['avg_likes'], reverse=True)

    # 3. 時間レポート
    hourly_report = []
    for h in range(24):
        s = hourly_stats[h]
        avg = int(s['likes'] / s['count']) if s['count'] > 0 else 0
        hourly_report.append({'hour': h, 'avg_likes': avg, 'count': s['count']})

    # 4. その他ランキング
    with_imp = [d for d in valid_data if d.get('impression_count', 0) > 100]
    engagement_ranking = []
    for d in with_imp:
        rate = (d['like_count'] / d['impression_count']) * 100
        d_copy = d.copy()
        d_copy['rate'] = round(rate, 2)
        engagement_ranking.append(d_copy)
    engagement_ranking.sort(key=lambda x: x['rate'], reverse=True)

    viral_ranking = sorted(valid_data, key=lambda x: x['viral_score'], reverse=True)[:50]
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:50]

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

    result = {
        'updated_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        'total_analyzed': len(valid_data),
        'total_records': len(raw_data),
        'global_avg': global_avg, # 全体平均を追加
        'keyword_ranking': keyword_ranking, # キーワード分析を追加
        'tag_ranking': tag_ranking[:20],
        'hourly_report': hourly_report,
        'engagement_ranking': engagement_ranking[:30],
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ キーワード分析完了！ 「速報」「宅コス」などの効果を測定しました。")

if __name__ == "__main__":
    analyze_data()