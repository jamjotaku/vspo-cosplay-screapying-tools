import json
import os
import re
from datetime import datetime, timedelta, timezone

# --- 1. Tweet IDから時間を復元する魔法 (Snowflake ID) ---
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

    if not os.path.exists(input_file):
        print(f"❌ {input_file} が見つかりません")
        return

    # データの読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    authors_data = {}
    if os.path.exists(authors_file):
        with open(authors_file, 'r', encoding='utf-8') as f:
            authors_data = json.load(f)

    # --- 集計用変数の初期化 ---
    valid_data = []
    
    # 時間帯 (0~23時)
    hourly_stats = {h: {'likes': 0, 'count': 0} for h in range(24)}
    
    # ハッシュタグ
    tag_stats = {} 
    
    # アスペクト比 (縦長/横長/正方形)
    aspect_stats = {
        'Portrait (縦長)': {'likes': 0, 'count': 0},
        'Landscape (横長)': {'likes': 0, 'count': 0},
        'Square (正方形)': {'likes': 0, 'count': 0},
        'Unknown': {'likes': 0, 'count': 0}
    }

    # 魔法のキーワード (分析したい単語リスト)
    target_keywords = [
        "速報", "宅コス", "初出し", "イベント", "コミケ", 
        "捏造", "私服", "動画", "自撮り", "オフショ", 
        "供養", "再掲", "そくほ", "スタジオ", "コラボ"
    ]
    keyword_stats = {k: {'total_likes': 0, 'count': 0} for k in target_keywords}

    # 全体平均算出用
    global_total_likes = 0
    global_count = 0

    # --- メインループ: 全データを解析 ---
    for d in raw_data:
        likes = d.get('like_count', 0)
        if likes == 0: continue # いいね0は除外（取得ミス等の可能性）
        
        global_total_likes += likes
        global_count += 1

        # A. ユーザー情報 & Viral Score
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

        # B. 時間解析
        hour = -1
        if tweet_id:
            dt = get_tweet_time(tweet_id)
            if dt:
                hour = dt.hour
                hourly_stats[hour]['likes'] += likes
                hourly_stats[hour]['count'] += 1

        # C. テキスト解析 (タグ & キーワード)
        text = d.get('text', '')
        
        # C-1. ハッシュタグ抽出
        tags = re.findall(r'[#＃]([a-zA-Z0-9_\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+)', text)
        for tag in tags:
            # 一般的すぎるタグは除外しても良いが、一旦すべて集計
            if tag not in tag_stats: tag_stats[tag] = {'total_likes': 0, 'count': 0}
            tag_stats[tag]['total_likes'] += likes
            tag_stats[tag]['count'] += 1

        # C-2. キーワード分析
        for kw in target_keywords:
            if kw in text:
                keyword_stats[kw]['total_likes'] += likes
                keyword_stats[kw]['count'] += 1

        # D. 画像アスペクト比分析 (width/heightがある場合)
        aspect_type = 'Unknown'
        if d.get('width') and d.get('height'):
            w, h = d['width'], d['height']
            ratio = w / h
            if ratio < 0.9: aspect_type = 'Portrait (縦長)'
            elif ratio > 1.1: aspect_type = 'Landscape (横長)'
            else: aspect_type = 'Square (正方形)'
            
            # データ自体にラベルを記録しておく
            d['aspect_type'] = aspect_type

        # 集計加算
        if aspect_type in aspect_stats:
            aspect_stats[aspect_type]['likes'] += likes
            aspect_stats[aspect_type]['count'] += 1

        # 有効データリストに追加
        d_copy = d.copy()
        d_copy['followers'] = followers
        d_copy['viral_score'] = viral_score
        d_copy['posted_hour'] = hour
        d_copy['aspect_type'] = aspect_type
        valid_data.append(d_copy)

    # --- 集計結果の整形とランキング作成 ---
    
    # 0. 全体平均 (基準値)
    global_avg = int(global_total_likes / global_count) if global_count > 0 else 0

    # 1. キーワードランキング (倍率付き)
    keyword_ranking = []
    for kw, s in keyword_stats.items():
        if s['count'] > 0:
            avg = int(s['total_likes'] / s['count'])
            multiplier = round(avg / global_avg, 2) if global_avg > 0 else 0
            keyword_ranking.append({
                'keyword': kw, 'avg_likes': avg, 'count': s['count'], 'multiplier': multiplier
            })
    keyword_ranking.sort(key=lambda x: x['avg_likes'], reverse=True)

    # 2. ハッシュタグランキング (3件以上)
    tag_ranking = []
    for tag, s in tag_stats.items():
        if s['count'] >= 3:
            avg = int(s['total_likes'] / s['count'])
            tag_ranking.append({'tag': tag, 'avg_likes': avg, 'count': s['count']})
    tag_ranking.sort(key=lambda x: x['avg_likes'], reverse=True)

    # 3. アスペクト比レポート
    aspect_report = []
    for atype, s in aspect_stats.items():
        if s['count'] > 0 and atype != 'Unknown':
            avg = int(s['likes'] / s['count'])
            aspect_report.append({'type': atype, 'avg': avg, 'count': s['count']})
    aspect_report.sort(key=lambda x: x['avg'], reverse=True)

    # 4. 時間帯レポート
    hourly_report = []
    for h in range(24):
        s = hourly_stats[h]
        avg = int(s['likes'] / s['count']) if s['count'] > 0 else 0
        hourly_report.append({'hour': h, 'avg_likes': avg, 'count': s['count']})

    # 5. エンゲージメント率ランキング (Impression 100以上)
    with_imp = [d for d in valid_data if d.get('impression_count', 0) > 100]
    engagement_ranking = []
    for d in with_imp:
        rate = (d['like_count'] / d['impression_count']) * 100
        d_copy = d.copy()
        d_copy['rate'] = round(rate, 2)
        engagement_ranking.append(d_copy)
    engagement_ranking.sort(key=lambda x: x['rate'], reverse=True)

    # 6. Viral Score ランキング
    viral_ranking = sorted(valid_data, key=lambda x: x['viral_score'], reverse=True)[:50]
    
    # 7. 単純いいねランキング
    like_ranking = sorted(valid_data, key=lambda x: x['like_count'], reverse=True)[:50]

    # 8. メンバー別ランキング
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

    # --- JSON保存 ---
    result = {
        'updated_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        'total_analyzed': len(valid_data),
        'total_records': len(raw_data),
        'global_avg': global_avg,
        'keyword_ranking': keyword_ranking,
        'tag_ranking': tag_ranking[:20],
        'aspect_report': aspect_report,     # 構図分析
        'hourly_report': hourly_report,     # 時間分析
        'engagement_ranking': engagement_ranking[:30],
        'viral_ranking': viral_ranking,
        'like_ranking': like_ranking,
        'member_ranking': member_ranking
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("-" * 30)
    print(f"✅ 分析コンプリート！")
    print(f"📊 データ数: {len(valid_data)}件")
    print(f"⏰ 時間解析: 完了")
    print(f"🗝️ キーワード: {len(keyword_ranking)}個の単語を分析")
    print(f"📸 構図分析: {len(aspect_report)}種類の比率を集計")
    print("-" * 30)

if __name__ == "__main__":
    analyze_data()