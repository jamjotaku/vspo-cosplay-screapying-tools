import json
import pandas as pd
import os

def run_analysis():
    # データの読み込み
    if not os.path.exists('collect.json'):
        print("データがありません")
        return

    with open('collect.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data: return

    df = pd.DataFrame(data)

    # --- 集計処理 ---

    # 1. メンバー別投稿数 (Top 20)
    member_counts = df['member_name'].value_counts().head(20).to_dict()

    # 2. 情報源の割合 (X vs Instagram)
    source_counts = df['source'].value_counts().to_dict()

    # 3. 日別トレンド (直近30日など)
    df['date'] = pd.to_datetime(df['collected_at']).dt.strftime('%Y-%m-%d')
    date_counts = df.groupby('date').size().to_dict()

    # 4. 総合サマリー
    summary = {
        "total_posts": len(df),
        "total_members": df['member_name'].nunique(),
        "last_updated": df['collected_at'].max()
    }

    # --- 結果を JSON で保存 ---
    analysis_result = {
        "member_ranking": member_counts,
        "source_ratio": source_counts,
        "timeline": date_counts,
        "summary": summary
    }

    with open('analysis.json', 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
    
    print("✅ 分析完了！ analysis.json を生成しました。")

if __name__ == "__main__":
    run_analysis()
