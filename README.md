# 駅の場所当てゲーム

## ゲーム概要
関東地方の駅の場所を当てるインタラクティブなWebアプリケーションです。お題として与えられた駅名を見て、地図上でその駅の位置を推測します。

## ゲームの流れ
1. **ゲーム設定**: ラウンド数と難易度を選択
2. **駅の出題**: ランダムに選ばれた駅名が表示されます
3. **位置推測**: 地図をクリックして駅の位置を予想します
4. **結果表示**: 正解の駅と選択位置の距離が表示されます
5. **次のラウンド**: 設定したラウンド数まで繰り返します

## 技術仕様
- **フレームワーク**: Streamlit
- **地図ライブラリ**: Folium
- **データ形式**: GeoJSON
- **環境管理**: uv
- **Python**: 3.11
- **地図タイル**: カスタムXYZタイル（関東地方の県境・路線図）

## セットアップ

### 1. 依存関係のインストール
```bash
uv sync
```

### 2. 地図タイルの生成
```bash
uv run python kanto_xyz_generator.py data/N03-20250101_prefecture.geojson data/N02-24_RailroadSection.geojson tiles/kanto --min-zoom 6 --max-zoom 14
```

### 3. 駅データの処理
```bash
uv run python process_station_data.py
```

### 4. アプリケーションの起動
```bash
uv run streamlit run app.py
```

## ファイル構成
- `app.py`: メインのStreamlitアプリケーション
- `kanto_xyz_generator.py`: 関東地方のXYZタイル生成スクリプト
- `process_station_data.py`: 駅データの処理・統合スクリプト
- `geojson_to_xyz.py`: GeoJSONからXYZタイルへの変換ライブラリ
- `data/`: 元のGeoJSONデータファイル
  - `N03-20250101_prefecture.geojson`: 都道府県境界データ
  - `N02-24_RailroadSection.geojson`: 鉄道路線データ
  - `S12-24_NumberOfPassengers.geojson`: 駅乗降客数データ
- `tiles/kanto/`: 生成された関東地方のXYZタイル
- `kanto_stations_integrated.json`: 処理済みの関東地方駅データ

## 機能

### 🎮 ゲーム機能
- **難易度選択**: 上位50駅〜全駅まで5段階の難易度
- **ラウンド設定**: 1〜10ラウンドまで選択可能
- **リアルタイム位置表示**: クリックした位置に即座にピンが表示
- **過去の正解表示**: 過去のラウンドの正解駅が青いマーカーで表示
- **TOP5駅表示**: 乗降客数上位5駅が赤い星マーカーで表示（参考用）

### 🗺️ 地図機能
- **カスタムタイル**: 関東地方の県境と路線図を表示
- **ズーム制限**: 6〜14レベルに制限
- **インタラクティブ**: クリック、ドラッグ、ズーム操作に対応

### 📊 結果表示
- **距離ベース評価**: 0.5km以内（完璧）〜5.0km以上（要改善）
- **ラウンド結果表**: 各ラウンドの結果を表形式で表示
- **ゲームサマリ**: 総合的な成績と統計を表示
- **ゲーム履歴**: 過去のゲーム結果を保存・表示

## 評価基準
- **🎯 完璧**: 0.5km以内
- **👍 良好**: 0.5-2.0km
- **👌 普通**: 2.0-5.0km
- **😅 要改善**: 5.0km以上

## データについて
- **対象範囲**: 東京都市圏（緯度35.4948-35.8284, 経度139.3389-139.9349）
- **駅データ**: 乗降客数データに基づく統合済み駅情報
- **TOP5除外**: 乗降客数上位5駅は参考表示のみ（出題対象外）

## 地図タイルについて
- **県境**: 関東地方の都道府県境界を表示
- **路線図**: 関東地方の鉄道路線を表示
- **ズームレベル**: 6〜14（詳細な表示が可能）
- **投影法**: Web Mercator（EPSG:3857）

## Streamlit Cloud デプロイ

### 1. GitHubリポジトリの準備
```bash
# リポジトリを初期化
git init
git add .
git commit -m "Initial commit"

# GitHubリポジトリを作成してプッシュ
git remote add origin https://github.com/tatsuyukibaba/station-guessing-game.git
git branch -M main
git push -u origin main
```

### 2. Streamlit Cloudでデプロイ
1. [Streamlit Cloud](https://share.streamlit.io/)にアクセス
2. GitHubアカウントでログイン
3. "New app"をクリック
4. リポジトリを選択: `tatsuyukibaba/station-guessing-game`
5. ブランチを選択: `main`
6. メインファイル: `app_cloud.py`
7. "Deploy!"をクリック

### 3. デプロイ後の確認
- アプリケーションが正常に起動することを確認
- 地図が表示されることを確認
- ゲーム機能が動作することを確認

## 開発・カスタマイズ
- 駅データの追加・修正: `process_station_data.py`を編集
- 地図範囲の変更: `kanto_xyz_generator.py`の`KANTO_BBOX`を修正
- 難易度設定の変更: `app.py`の`difficulty_options`を編集
- 評価基準の変更: `app.py`の`calculate_game_summary`関数を編集

## ファイル構成（デプロイ版）
- `app_cloud.py`: Streamlit Cloud用のメインアプリケーション
- `requirements.txt`: Python依存関係
- `.streamlit/config.toml`: Streamlit設定
- `kanto_stations_integrated.json`: 処理済みの駅データ
- `tiles/kanto/`: 地図タイル（オプション、OpenStreetMapを使用）