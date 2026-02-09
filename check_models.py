import google.generativeai as genai
import os

# APIキーの設定
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# 環境変数になければ、ここに直接 "AIza..." を書き込んでテストしてください
if not GEMINI_API_KEY:
    print("⚠️ APIキーが見つかりません。直接コードに書き込むか環境変数を設定してください。")
else:
    genai.configure(api_key=GEMINI_API_KEY)

    print("--- Available Models ---")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
