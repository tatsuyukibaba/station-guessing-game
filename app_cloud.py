#!/usr/bin/env python3
"""
駅の場所当てゲーム - Streamlit Cloud版
"""

import streamlit as st
import json
import random
import math
import folium
from streamlit_folium import st_folium
import pandas as pd
import geopandas as gpd
from pathlib import Path
import base64
import io

# ページ設定
st.set_page_config(
    page_title="駅の場所当てゲーム",
    page_icon="🚉",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_tile_url(z, x, y):
    """Streamlit Cloud用のタイルURL取得"""
    # ローカルファイルからタイルを読み込む
    tile_path = f"tiles/kanto/{z}/{x}/{y}.png"
    if Path(tile_path).exists():
        return f"data:image/png;base64,{base64.b64encode(Path(tile_path).read_bytes()).decode()}"
    return None

def create_custom_tile_layer():
    """カスタムタイルレイヤーを作成"""
    # タイルレイヤーのJavaScriptコード
    js_code = """
    var customTileLayer = L.TileLayer.extend({
        getTileUrl: function(coords) {
            var z = coords.z;
            var x = coords.x;
            var y = coords.y;
            
            // タイルファイルの存在確認とbase64エンコード
            var tilePath = 'tiles/kanto/' + z + '/' + x + '/' + y + '.png';
            
            // ここでは実際のファイル読み込みはできないので、
            // 代わりに透明なタイルを返す
            return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
        }
    });
    
    return new customTileLayer();
    """
    
    return js_code

# セッション状態の初期化
if 'stations' not in st.session_state:
    st.session_state.stations = None
if 'current_station' not in st.session_state:
    st.session_state.current_station = None
if 'round' not in st.session_state:
    st.session_state.round = 1
if 'total_rounds' not in st.session_state:
    st.session_state.total_rounds = 5
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'game_started' not in st.session_state:
    st.session_state.game_started = False
if 'game_results' not in st.session_state:
    st.session_state.game_results = []
if 'clicked_location' not in st.session_state:
    st.session_state.clicked_location = None
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'show_summary' not in st.session_state:
    st.session_state.show_summary = False
if 'game_history' not in st.session_state:
    st.session_state.game_history = []
if 'difficulty_level' not in st.session_state:
    st.session_state.difficulty_level = 100

def load_stations():
    """駅データを読み込み"""
    try:
        with open('kanto_stations_integrated.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stations = []
        for feature in data['features']:
            props = feature['properties']
            geom = feature['geometry']
            
            # MultiPointの場合は最初の点を使用
            if geom['type'] == 'MultiPoint':
                coords = geom['coordinates'][0]
            else:
                coords = geom['coordinates']
            
            station = {
                'name': props['name'],
                'passengers': props['passengers'],
                'station_count': props['station_count'],
                'lat': coords[1],
                'lon': coords[0],
                'geometry': geom
            }
            stations.append(station)
        
        return stations
    except Exception as e:
        st.error(f"駅データの読み込みに失敗しました: {e}")
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算（ハヴァサイン公式）"""
    R = 6371  # 地球の半径（km）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def get_score(distance):
    """距離に基づくスコア計算"""
    return distance

def select_random_station(stations, difficulty_level=100):
    """ランダムに駅を選択（難易度に応じて上位N件から選択、TOP5は除外）"""
    # 乗降客数でソート
    sorted_stations = sorted(stations, key=lambda x: x['passengers'], reverse=True)
    
    # TOP5を除外
    available_stations = sorted_stations[5:]  # 6位以降の駅のみ
    
    if difficulty_level >= len(available_stations):
        return random.choice(available_stations)
    
    # 難易度に応じて上位N件を取得（TOP5は除外済み）
    top_stations = available_stations[:difficulty_level]
    return random.choice(top_stations)

def get_top5_stations(stations):
    """乗降客数上位5駅を取得"""
    sorted_stations = sorted(stations, key=lambda x: x['passengers'], reverse=True)
    return sorted_stations[:5]

def calculate_game_summary(game_results):
    """ゲーム結果からサマリ統計を計算"""
    if not game_results:
        return None
    
    distances = [result['distance'] for result in game_results]
    
    summary = {
        'total_rounds': len(game_results),
        'best_distance': min(distances),
        'worst_distance': max(distances),
        'average_distance': sum(distances) / len(distances),
        'total_distance': sum(distances),
        'perfect_guesses': len([d for d in distances if d < 0.5]),  # 0.5km以内
        'good_guesses': len([d for d in distances if 0.5 <= d < 2.0]),  # 0.5-2.0km
        'ok_guesses': len([d for d in distances if 2.0 <= d < 5.0]),  # 2.0-5.0km
        'poor_guesses': len([d for d in distances if d >= 5.0])  # 5.0km以上
    }
    
    return summary

def create_map(center_lat=35.6812, center_lon=139.7671, zoom=12, show_result=False, correct_station=None, guessed_location=None, current_click=None, stations=None, past_results=None):
    """地図を作成（Streamlit Cloud版）"""
    # 関東地方のXYZタイルを使用
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None,  # デフォルトのタイルを無効化
        min_zoom=6,  # 最小ズームレベル
        max_zoom=14,  # 最大ズームレベル
        zoom_control=True,  # ズームコントロールを有効化
        scroll_wheel_zoom=True,  # マウスホイールズームを有効化
        double_click_zoom=True,  # ダブルクリックズームを有効化
        box_zoom=True,  # ボックスズームを有効化
        keyboard=True,  # キーボードズームを有効化
        dragging=True  # ドラッグを有効化
    )
    
    # OpenStreetMapをベースレイヤーとして追加
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True,
        opacity=0.8
    ).add_to(m)
    
    # 過去のラウンドの正解を青いマーカーで表示
    if past_results:
        for i, result in enumerate(past_results):
            folium.Marker(
                [result['correct_lat'], result['correct_lon']],
                popup=f"ラウンド{result['round']} 正解: {result['station']['name']} ({result['distance']:.1f}km)",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(m)
    
    # 現在のクリック位置をリアルタイムで表示
    if current_click:
        folium.Marker(
            current_click,
            popup="選択した位置",
            icon=folium.Icon(color='purple', icon='map-marker')
        ).add_to(m)
    
    # TOP5の駅をマーク（参考用）
    if stations:
        top5_stations = get_top5_stations(stations)
        
        for i, station in enumerate(top5_stations):
            folium.Marker(
                [station['lat'], station['lon']],
                popup=f"#{i+1} {station['name']}",
                icon=folium.Icon(color='red', icon='star')
            ).add_to(m)
    
    # 答え合わせ時に正解と選択位置を表示
    if show_result and correct_station and guessed_location:
        # 正解の駅を緑色でマーク
        folium.Marker(
            [correct_station['lat'], correct_station['lon']],
            popup=f"正解: {correct_station['name']}",
            icon=folium.Icon(color='green', icon='check-circle')
        ).add_to(m)
        
        # 選択した位置を赤色でマーク
        guessed_lat, guessed_lon = guessed_location
        folium.Marker(
            [guessed_lat, guessed_lon],
            popup="あなたの選択",
            icon=folium.Icon(color='red', icon='times-circle')
        ).add_to(m)
        
        # 正解と選択位置を線で結ぶ
        folium.PolyLine(
            locations=[
                [correct_station['lat'], correct_station['lon']],
                [guessed_lat, guessed_lon]
            ],
            color='blue',
            weight=3,
            opacity=0.7,
            popup=f"距離: {calculate_distance(correct_station['lat'], correct_station['lon'], guessed_lat, guessed_lon):.2f}km"
        ).add_to(m)
    
    return m

def main():
    st.title("🚉 駅の場所当てゲーム")
    st.markdown("---")
    
    # 駅データを読み込み
    if st.session_state.stations is None:
        st.session_state.stations = load_stations()
    
    if st.session_state.stations is None:
        st.stop()
    
    # サイドバー（ゲーム中のみ表示）
    if st.session_state.game_started or st.session_state.show_summary:
        with st.sidebar:
            st.header("📊 ゲーム情報")
            st.metric("現在のラウンド", f"{st.session_state.round} / {st.session_state.total_rounds}")
            
            if st.session_state.game_started:
                if st.button("🔄 新しいゲーム", type="secondary"):
                    st.session_state.game_started = False
                    st.session_state.current_station = None
                    st.session_state.round = 1
                    st.session_state.score = 0
                    st.session_state.game_results = []
                    st.session_state.clicked_location = None
                    st.session_state.show_result = False
                    st.session_state.current_result = None
                    st.rerun()
            
            # ゲーム履歴表示
            if st.session_state.game_history:
                st.markdown("---")
                st.header("📈 ゲーム履歴")
                
                # 最新の5ゲームを表示
                recent_games = st.session_state.game_history[-5:]
                
                for i, game in enumerate(reversed(recent_games)):
                    with st.expander(f"ゲーム {len(st.session_state.game_history) - i} - {game['date']}"):
                        st.metric("ラウンド数", f"{game['total_rounds']}ラウンド")
                        st.metric("難易度", f"上位{game['difficulty']}駅")
                        
                        # 各ラウンドの結果
                        st.write("**ラウンド別結果:**")
                        for j, result in enumerate(game['results']):
                            st.write(f"ラウンド{j+1}: {result['station']['name']} - {result['distance']:.1f}km")
                
                # 履歴クリアボタン
                if st.button("🗑️ 履歴をクリア", type="secondary"):
                    st.session_state.game_history = []
                    st.rerun()
    
    # メインコンテンツ
    if not st.session_state.game_started and not st.session_state.show_summary:
        # スタート画面
        st.header("🎮 ゲーム設定")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.total_rounds = st.slider("ラウンド数", 1, 10, 5)
        
        with col2:
            # 難易度選択
            difficulty_options = {
                "超簡単 (上位50駅)": 50,
                "簡単 (上位100駅)": 100,
                "普通 (上位200駅)": 200,
                "難しい (上位500駅)": 500,
                "超難しい (全駅)": len(st.session_state.stations)
            }
            
            selected_difficulty = st.selectbox(
                "駅の難易度を選択",
                options=list(difficulty_options.keys()),
                index=1  # デフォルトは「簡単」
            )
            st.session_state.difficulty_level = difficulty_options[selected_difficulty]
        
        # 選択された難易度の説明
        if st.session_state.difficulty_level < len(st.session_state.stations):
            sorted_stations = sorted(st.session_state.stations, key=lambda x: x['passengers'], reverse=True)
            min_passengers = sorted_stations[st.session_state.difficulty_level - 1]['passengers']
            st.info(f"乗降客数 {min_passengers:,.0f}人以上の駅から出題されます")
        else:
            st.info("すべての駅から出題されます")
        
        if st.button("🎯 ゲーム開始", type="primary", use_container_width=True):
            st.session_state.game_started = True
            st.session_state.current_station = select_random_station(st.session_state.stations, st.session_state.difficulty_level)
            st.session_state.round = 1
            st.session_state.score = 0
            st.session_state.game_results = []
            st.session_state.clicked_location = None
            st.session_state.show_result = False
            st.session_state.current_result = None
            st.rerun()
        
        st.markdown("---")
        st.header("🎯 ゲームルール")
        st.markdown("""
        ### 関東地方の駅の場所当てゲーム
        
        **🎮 ゲームの流れ:**
        1. お題の駅名が表示されます
        2. 地図をクリックして、その駅の場所を予想してください
        3. 正解の駅とあなたの選択位置の距離が表示されます
        4. 設定したラウンド数まで繰り返します
        
        **🏆 評価基準:**
        - **完璧**: 0.5km以内 🎯
        - **良好**: 0.5-2.0km 👍
        - **普通**: 2.0-5.0km 👌
        - **要改善**: 5.0km以上 😅
        
        **💡 ヒント:**
        - 赤い星マーカーは乗降客数TOP5の駅です（参考用）
        - 過去の正解は青いマーカーで表示されます
        - 難易度を上げると、より多くの駅から出題されます
        """)
    
    elif st.session_state.show_summary:
        # ゲーム終了サマリ表示
        st.markdown("---")
        st.header("🎊 ゲーム完了！")
        
        # サマリ統計を計算
        summary = calculate_game_summary(st.session_state.game_results)
        
        if summary:
            # メトリクス表示
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総ラウンド数", f"{summary['total_rounds']}ラウンド")
            with col2:
                st.metric("最短距離", f"{summary['best_distance']:.1f}km")
            with col3:
                st.metric("最長距離", f"{summary['worst_distance']:.1f}km")
            with col4:
                st.metric("平均距離", f"{summary['average_distance']:.1f}km")
            
            # 成績分布
            st.markdown("### 📊 成績分布")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🎯 完璧", f"{summary['perfect_guesses']}回", help="0.5km以内")
            with col2:
                st.metric("👍 良好", f"{summary['good_guesses']}回", help="0.5-2.0km")
            with col3:
                st.metric("👌 普通", f"{summary['ok_guesses']}回", help="2.0-5.0km")
            with col4:
                st.metric("😅 要改善", f"{summary['poor_guesses']}回", help="5.0km以上")
            
            # 詳細結果表
            st.markdown("### 📋 詳細結果")
            results_data = []
            for result in st.session_state.game_results:
                results_data.append({
                    'ラウンド': result['round'],
                    '駅名': result['station']['name'],
                    '乗降客数': f"{result['passengers']:,}人",
                    '距離': f"{result['distance']:.1f}km"
                })
            
            df = pd.DataFrame(results_data)
            st.dataframe(df, width='stretch')
            
            # 履歴に保存
            from datetime import datetime
            game_summary = {
                'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'total_rounds': summary['total_rounds'],
                'difficulty': st.session_state.difficulty_level,
                'results': st.session_state.game_results,
                'summary': summary
            }
            st.session_state.game_history.append(game_summary)
        
        # 新しいゲーム開始ボタン
        if st.button("🎮 新しいゲームを開始", type="primary", use_container_width=True):
            st.session_state.game_started = False
            st.session_state.current_station = None
            st.session_state.round = 1
            st.session_state.score = 0
            st.session_state.game_results = []
            st.session_state.clicked_location = None
            st.session_state.show_result = False
            st.session_state.current_result = None
            st.session_state.show_summary = False
            st.rerun()
    
    else:
        # ゲーム中
        if st.session_state.current_station:
            station = st.session_state.current_station
            
            # 現在の問題を表示
            st.header(f"🎯 ラウンド {st.session_state.round}")
            st.info(f"**お題の駅**: {station['name']}")
            
            # 地図を表示
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # 地図を作成
                if st.session_state.show_result and st.session_state.current_result:
                    # 答え合わせモード
                    current_click = None
                    if st.session_state.clicked_location:
                        current_click = st.session_state.clicked_location
                    
                    m = create_map(
                        show_result=True,
                        correct_station=st.session_state.current_result['station'],
                        guessed_location=(st.session_state.current_result['guessed_lat'], st.session_state.current_result['guessed_lon']),
                        current_click=current_click,
                        stations=st.session_state.stations,
                        past_results=st.session_state.game_results
                    )
                else:
                    # 通常モード
                    current_click = None
                    if st.session_state.clicked_location:
                        current_click = st.session_state.clicked_location
                    
                    m = create_map(
                        current_click=current_click,
                        stations=st.session_state.stations,
                        past_results=st.session_state.game_results
                    )
                
                # 地図を表示してクリック位置を取得
                map_data = st_folium(m, width=600, height=400, key=f"map_{st.session_state.round}")
                
                # クリック位置を取得（答え合わせモードでない場合のみ）
                if not st.session_state.show_result and map_data and 'last_clicked' in map_data and map_data['last_clicked']:
                    clicked_lat = map_data['last_clicked']['lat']
                    clicked_lon = map_data['last_clicked']['lng']
                    st.session_state.clicked_location = (clicked_lat, clicked_lon)
                    st.rerun()
            
            with col2:
                # 現在のラウンド結果表示
                if st.session_state.show_result and st.session_state.current_result:
                    result = st.session_state.current_result
                    
                    st.markdown("### 📊 ラウンド結果")
                    st.metric("距離", f"{result['distance']:.2f}km")
                    
                    # 評価表示
                    if result['distance'] < 0.5:
                        st.success("🎯 完璧！")
                    elif result['distance'] < 2.0:
                        st.success("👍 良好！")
                    elif result['distance'] < 5.0:
                        st.info("👌 普通")
                    else:
                        st.warning("😅 要改善")
                    
                    # 次のラウンドボタン
                    if st.session_state.round < st.session_state.total_rounds:
                        if st.button("➡️ 次のラウンド", type="primary", use_container_width=True):
                            st.session_state.round += 1
                            st.session_state.current_station = select_random_station(st.session_state.stations, st.session_state.difficulty_level)
                            st.session_state.clicked_location = None
                            st.session_state.show_result = False
                            st.session_state.current_result = None
                            st.rerun()
                    else:
                        if st.button("🏁 ゲーム終了", type="primary", use_container_width=True):
                            st.session_state.show_summary = True
                            st.rerun()
                else:
                    # 回答待ち
                    if st.session_state.clicked_location:
                        if st.button("🎯 この位置で回答", type="primary", use_container_width=True):
                            # 距離計算
                            distance = calculate_distance(
                                station['lat'], station['lon'],
                                st.session_state.clicked_location[0], st.session_state.clicked_location[1]
                            )
                            
                            # 結果を保存
                            result = {
                                'round': st.session_state.round,
                                'station': station,
                                'guessed_lat': st.session_state.clicked_location[0],
                                'guessed_lon': st.session_state.clicked_location[1],
                                'distance': distance,
                                'passengers': station['passengers']
                            }
                            st.session_state.game_results.append(result)
                            st.session_state.current_result = result
                            st.session_state.show_result = True
                            st.rerun()
                    else:
                        st.info("地図をクリックして駅の位置を予想してください")
        
        # ラウンド結果表
        if st.session_state.game_results:
            st.markdown("---")
            st.subheader("📊 ラウンド結果")
            
            # 結果テーブル用のデータを準備
            results_data = []
            for result in st.session_state.game_results:
                results_data.append({
                    'ラウンド': result['round'],
                    '駅名': result['station']['name'],
                    '乗降客数': f"{result['passengers']:,}人",
                    '距離': f"{result['distance']:.1f}km"
                })
            
            # 表を表示
            df = pd.DataFrame(results_data)
            st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()
