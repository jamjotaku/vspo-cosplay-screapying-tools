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
    
    # ハッシュタグ分析用の箱
    tag_stats = {} 

    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue
        
        # ユーザー情報 & Viral Score
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

        # --- ハッシュタグ抽出 ---
        text = d.get('text', '')
        # ハッシュタグの正規表現 (#の後に続く文字)
        tags = re.findall(r'[#＃]([a-zA-Z0-9_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+)', text)
        
        for tag in tags:
            # "ぶいすぽ" "VSPO" などの当たり前すぎるタグは除外してもOKだが一旦全部集計
            if tag not in tag_stats:
                tag_stats[tag] = {'total_likes': 0, 'count': 0}
            tag_stats[tag]['total_likes'] += likes
            tag_stats[tag]['count'] += 1

        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        d_copy['posted_hour'] = hour
        valid_data.append(d_copy)

    # --- 集計結果の整形 ---
    
    # 1. ハッシュタグランキング (投稿数3件以上で平均いいねが高い順)
    tag_ranking = []
    for tag, s in tag_stats.items():
        if s['count'] >= 3: # ノイズ除去のため3回以上使われたタグに限定
            avg = int(s['total_likes'] / s['count'])
            tag_ranking.append({'tag': tag, 'avg_likes': avg, 'count': s['count']})
    tag_ranking.sort(key=lambda x: x['avg_likes'], reverse=True)

    # 2. 時間レポート
    hourly_report = []
    for h in range(24):
        s = hourly_stats[h]
        avg = int(s['likes'] / s['count']) if s['count'] > 0 else 0
        hourly_report.append({'hour': h, 'avg_likes': avg, 'count': s['count']})

    # 3. その他ランキング
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
        'tag_ranking': tag_ranking[:20], # Top 20タグ
        'hourly_report': hourly_report,
        'engagement_ranking': engagement_ranking[:30],
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 言語解析完了！ 有効なタグトレンドを抽出しました。")

if __name__ == "__main__":
    analyze_data()