import json
import os
import re
from datetime import datetime

INPUT_FILE = 'collect.json'
OUTPUT_FILE = 'analysis.json'

LOCATION_KEYWORDS = {
    "Event": ["コミケ", "C9", "C10", "夏コミ", "冬コミ", "アコスタ", "acosta", "池ハロ", "となコス", "超会議", "ニコ超", "ラグコス", "ワンフェス", "ホココス", "ビビコス", "ストフェス", "a!"],
    "Studio": ["スタジオ", "studio", "撮", "撮影会", "宅コス", "家", "自撮り", "セルフィー", "笹塚"]
}

def analyze_data():
    if not os.path.exists(INPUT_FILE): return
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    valid_data = [d for d in data if d.get('like_count', 0) > 0]
    if not valid_data: return

    global_avg = int(sum(d['like_count'] for d in valid_data) / len(valid_data))

    hourly_stats = {h: {'likes': [], 'count': 0} for h in range(24)}
    aspect_stats = {'Portrait': [], 'Landscape': [], 'Square': [], 'Unknown': []}
    location_stats = {'Event': {'likes': [], 'count': 0}, 'Studio/Home': {'likes': [], 'count': 0}, 'Others': {'likes': [], 'count': 0}}
    char_stats = {}
    ranking_data = []

    for item in valid_data:
        likes = item['like_count']
        followers = item.get('follower_count', 0)
        text = item.get('text', "")
        
        # --- 1. 時間帯分析 (ISO形式の末尾 Z 対策) ---
        try:
            date_str = item.get('created_at', "")
            if date_str.endswith('Z'):
                date_str = date_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(date_str)
            hour = dt.hour
            hourly_stats[hour]['likes'].append(likes)
            hourly_stats[hour]['count'] += 1
        except: pass

        # --- 2. 構図分析 (キー名揺れ対策) ---
        dims = item.get('dimensions') or item.get('image_dimensions')
        label = 'Unknown'
        if dims and dims.get('height', 0) > 0:
            ratio = dims['width'] / dims['height']
            label = 'Square' if 0.9 <= ratio <= 1.1 else ('Portrait' if ratio < 0.9 else 'Landscape')
        aspect_stats[label].append(likes)

        # 3. ロケーション / 4. 分離 / 5. スコア (以前と同じ)
        loc_label = 'Others'
        if any(k in text for k in LOCATION_KEYWORDS['Event']): loc_label = 'Event'
        elif any(k in text for k in LOCATION_KEYWORDS['Studio']): loc_label = 'Studio/Home'
        location_stats[loc_label]['likes'].append(likes)
        location_stats[loc_label]['count'] += 1

        char_name = item.get('member') or item.get('query') or 'Unknown'
        cos_id = 'Unknown'
        match = re.search(r'(?:twitter|x)\.com/([^/]+)/status', item.get('url', ''))
        if match: cos_id = match.group(1)

        if char_name not in char_stats: char_stats[char_name] = {'likes': [], 'count': 0}
        char_stats[char_name]['likes'].append(likes)
        char_stats[char_name]['count'] += 1

        viral_score = round((likes / followers) * 100, 2) if followers > 0 else 0
        ranking_data.append({
            'character_name': char_name, 'cosplayer_name': cos_id, 'like_count': likes,
            'followers': followers, 'viral_score': viral_score, 'url': item.get('url', ''),
            'location': loc_label
        })

    # レポート集計 (0除算回避)
    hourly_report = [{'hour': h, 'avg_likes': int(sum(s['likes'])/len(s['likes'])) if s['likes'] else 0, 'count': s['count']} for h, s in hourly_stats.items()]
    aspect_report = [{'type': t, 'avg': int(sum(l)/len(l)) if l else 0, 'count': len(l)} for t, l in aspect_stats.items()]
    location_report = [{'location': n, 'avg': int(sum(s['likes'])/len(s['likes'])) if s['likes'] else 0, 'count': s['count']} for n, s in location_stats.items()]
    char_ranking = sorted([{'name': n, 'avg': int(sum(s['likes'])/len(s['likes'])), 'count': s['count']} for n, s in char_stats.items()], key=lambda x: x['avg'], reverse=True)
    viral_ranking = sorted(ranking_data, key=lambda x: x['viral_score'], reverse=True)[:50]

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
    print(f"✨ 分析完了！ {len(ranking_data)} 件を処理しました。")

if __name__ == "__main__":
    analyze_data()