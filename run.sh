#!/bin/bash

# 駅の場所当てゲーム起動スクリプト

echo "🚉 駅の場所当てゲームを起動しています..."

# データファイルの存在確認
if [ ! -f "tokyo_stations.json" ]; then
    echo "📊 駅データを準備中..."
    uv run python data_analyzer.py
fi

# Streamlitアプリケーションを起動
echo "🎮 アプリケーションを起動中..."
uv run streamlit run app.py
