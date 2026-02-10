import json
import os
import re
from datetime import datetime
from collections import Counter

# --- 設定 ---
INPUT_FILE = 'collect.json'
OUTPUT_FILE = 'analysis.json'

# ロケーション判定用キーワード
LOCATION_KEYWORDS = {
    "Event": [
        "コミケ", "C9", "C10", "夏コミ", "冬コミ", 
        "アコスタ", "acosta", "池ハロ", "となコス", 
        "超会議", "ニコ超", "ラグコス", "ワンフェス", 
        "ホココス", "ビビコス", "ストフェス", "a!"
    ],
    "Studio": [
        "スタジオ", "studio", "撮", "撮影会", 
        "宅コス", "家", "自撮り", "セルフィー", "笹塚"
    ]
}

def analyze_data():
    print("🚀 分析を開始します...")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ エラー: {INPUT_FILE} が見つかりません")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("❌ エラー: JSONファイルが破損しています")
            return

    # 有効データ（いいね数が取得できているもの）のみ抽出
    valid_data = [d for d in data if d.get('like_count', 0) > 0]
    total_posts = len(valid_data)
    
    if total_posts == 0:
        print("⚠️ 有効なデータ（いいね > 0）がありません。fetch_metrics.pyを実行してください。")
        return

    # 全体平均の算出
    total_likes = sum(d['like_count'] for d in valid_data)
    global_avg = int(total_likes / total_posts)

    # --- 集計用変数の初期化 ---
    # 0~23時の箱を用意
    hourly_stats = {h: {'likes': [], 'count': 0} for h in range(24)}
    
    # 構図ごとの箱
    aspect_stats = {
        'Portrait': [], 
        'Landscape': [], 
        'Square': [], 
        'Unknown': []
    }
    
    # ロケーションごとの箱
    location_stats = {
        'Event': {'likes': [], 'count': 0},
        'Studio/Home': {'likes': [], 'count': 0},
        'Others': {'likes': [], 'count': 0}
    }
    
    # キャラクター別集計用
    char_stats = {} 
    
    # ランキング用リスト
    ranking_data = []

    print(f"📊 {total_posts} 件のデータを解析中...")

    for item in valid_data:
        likes = item['like_count']
        followers = item.get('follower_count', 0)
        text = item.get('text', "")
        url = item.get('url', "")
        
        # 1. 時間帯分析
        try:
            dt = datetime.fromisoformat(item['created_at'])
            hour = dt.hour
            hourly_stats[hour]['likes'].append(likes)
            hourly_stats[hour]['count'] += 1
        except:
            pass # 日付形式エラーはスキップ

        # 2. 構図分析
        dims = item.get('dimensions')
        label = 'Unknown'
        if dims and dims.get('height', 0) > 0:
            w, h = dims['width'], dims['height']
            ratio = w / h
            if 0.9 <= ratio <= 1.1: label = 'Square'
            elif ratio < 0.9: label = 'Portrait'
            else: label = 'Landscape'
        aspect_stats[label].append(likes)

        # 3. ロケーション判定
        loc_label = 'Others'
        if any(k in text for k in LOCATION_KEYWORDS['Event']):
            loc_label = 'Event'
        elif any(k in text for k in LOCATION_KEYWORDS['Studio']):
            loc_label = 'Studio/Home'
        
        location_stats[loc_label]['likes'].append(likes)
        location_stats[loc_label]['count'] += 1

        # 4. キャラクター名とコスプレイヤーIDの分離
        # memberキー、またはqueryキーをキャラクター名として使用
        char_name = item.get('query') or item.get('member') or 'Unknown'
        
        # URLからコスプレイヤーIDを抽出
        cos_id = 'Unknown'
        match = re.search(r'(?:twitter|x)\.com/([^/]+)/status', url)
        if match:
            cos_id = match.group(1)

        # キャラクター別集計
        if char_name not in char_stats:
            char_stats[char_name] = {'likes': [], 'count': 0}
        char_stats[char_name]['likes'].append(likes)
        char_stats[char_name]['count'] += 1

        # 5. Viral Score (拡散効率) 計算
        # フォロワー0の場合は0点とする (エラー回避)
        viral_score = 0
        if followers > 0:
            viral_score = round((likes / followers) * 100, 2)
        
        ranking_data.append({
            'character_name': char_name,
            'cosplayer_name': cos_id,
            'like_count': likes,
            'followers': followers,
            'viral_score': viral_score,
            'url': url,
            'location': loc_label,
            'text': text[:50] + "..." if text else ""
        })

    # --- レポートデータの生成 (安全な計算処理) ---

    # A. 時間帯レポート
    hourly_report = []
    for h in range(24):
        data = hourly_stats[h]
        avg = int(sum(data['likes']) / len(data['likes'])) if data['likes'] else 0
        hourly_report.append({'hour': h, 'avg_likes': avg, 'count': data['count']})

    # B. 構図レポート
    aspect_report = []
    for type_name, likes_list in aspect_stats.items():
        avg = int(sum(likes_list) / len(likes_list)) if likes_list else 0
        aspect_report.append({'type': type_name, 'avg': avg, 'count': len(likes_list)})

    # C. ロケーションレポート
    location_report = []
    for loc_name, data in location_stats.items():
        avg = int(sum(data['likes']) / len(data['likes'])) if data['likes'] else 0
        # 全体平均との比較倍率
        multiplier = round(avg / global_avg, 2) if global_avg > 0 else 0
        location_report.append({
            'location': loc_name, 
            'avg': avg, 
            'count': data['count'],
            'multiplier': multiplier
        })

    # D. キャラクターランキング (平均いいね順)
    char_ranking = []
    for name, data in char_stats.items():
        avg = int(sum(data['likes']) / len(data['likes'])) if data['likes'] else 0
        char_ranking.append({'name': name, 'avg': avg, 'count': data['count']})
    # 並び替え
    char_ranking.sort(key=lambda x: x['avg'], reverse=True)

    # E. Viral Efficiency ランキング (スコア順)
    ranking_data.sort(key=lambda x: x['viral_score'], reverse=True)
    # Top 50のみ保存して容量削減
    viral_ranking = ranking_data[:50]

    # --- 出力データ作成 ---
    output = {
        'updated_at': datetime.now().strftime('%Y/%m/%d %H:%M'),
        'total_analyzed': len(ranking_data),
        'total_records': len(data),
        'global_avg': global_avg,
        'hourly_report': hourly_report,
        'aspect_report': aspect_report,
        'location_report': location_report,
        'member_ranking': char_ranking,
        'viral_ranking': viral_ranking
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 完了ログ
    print("-" * 30)
    print(f"✨ 分析完了！ (Avg: {global_avg} Likes)")
    if char_ranking:
        top_c = char_ranking[0]
        print(f"👑 Top Character: {top_c['name']} (Avg: {top_c['avg']})")
    if viral_ranking:
        top_v = viral_ranking[0]
        print(f"🚀 Top Viral Post: {top_v['viral_score']}% Efficiency (@{top_v['cosplayer_name']})")
    print("-" * 30)

if __name__ == "__main__":
    analyze_data()