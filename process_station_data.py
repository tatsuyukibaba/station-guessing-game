#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
from collections import defaultdict
from pathlib import Path

def is_in_kanto_range(lon, lat):
    """関東地方の範囲内かどうかを判定"""
    # 関東地方の範囲: 東京都心部に絞った範囲 - kanto_xyz_generator.pyと同じ
    KANTO_BBOX = (139.3389, 35.4948, 139.9349, 35.8284)  # (min_lon, min_lat, max_lon, max_lat)
    return KANTO_BBOX[0] <= lon <= KANTO_BBOX[2] and KANTO_BBOX[1] <= lat <= KANTO_BBOX[3]

def extract_coordinates(geometry):
    """ジオメトリから座標を抽出"""
    coords = []
    
    if geometry["type"] == "Point":
        coords.append(geometry["coordinates"])
    elif geometry["type"] == "MultiPoint":
        coords.extend(geometry["coordinates"])
    elif geometry["type"] == "LineString":
        coords.extend(geometry["coordinates"])
    elif geometry["type"] == "MultiLineString":
        for line in geometry["coordinates"]:
            coords.extend(line)
    elif geometry["type"] == "Polygon":
        for ring in geometry["coordinates"]:
            coords.extend(ring)
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            for ring in polygon:
                coords.extend(ring)
    
    return coords

def process_station_data(input_file, output_file):
    """駅データを処理して統合"""
    print("駅データを読み込み中...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 関東地方の範囲内の駅のみを抽出
    kanto_stations = []
    for feature in data["features"]:
        geometry = feature.get("geometry")
        if not geometry:
            continue
            
        # 座標を抽出
        coords = extract_coordinates(geometry)
        if not coords:
            continue
            
        # 関東地方の範囲内の座標があるかチェック
        in_kanto = False
        for coord in coords:
            if len(coord) >= 2:
                lon, lat = coord[0], coord[1]
                if is_in_kanto_range(lon, lat):
                    in_kanto = True
                    break
        
        if in_kanto:
            kanto_stations.append(feature)
    
    print(f"関東地方の駅データ: {len(kanto_stations)}件")
    
    # 駅名でグループ化して統合
    station_groups = defaultdict(list)
    
    for station in kanto_stations:
        station_name = station["properties"].get("S12_001", "")
        if station_name:
            station_groups[station_name].append(station)
    
    print(f"ユニークな駅名: {len(station_groups)}件")
    
    # 統合された駅データを作成
    integrated_stations = []
    
    for station_name, stations in station_groups.items():
        # 乗降客数を合計
        total_passengers = 0
        all_coords = []
        
        for station in stations:
            passengers = station["properties"].get("S12_057", 0)
            if passengers:
                total_passengers += passengers
            
            # 座標を収集
            coords = extract_coordinates(station["geometry"])
            for coord in coords:
                if len(coord) >= 2:
                    all_coords.append(coord)
        
        # 重複する座標を除去（同じ座標の場合は1つだけ残す）
        unique_coords = []
        for coord in all_coords:
            if coord not in unique_coords:
                unique_coords.append(coord)
        
        if unique_coords and total_passengers > 0:
            # ジオメトリタイプを決定
            if len(unique_coords) == 1:
                geometry_type = "Point"
                geometry_coords = unique_coords[0]
            else:
                geometry_type = "MultiPoint"
                geometry_coords = unique_coords
            
            integrated_station = {
                "type": "Feature",
                "properties": {
                    "station_name": station_name,
                    "total_passengers": total_passengers,
                    "station_count": len(stations),
                    "original_stations": len(stations)
                },
                "geometry": {
                    "type": geometry_type,
                    "coordinates": geometry_coords
                }
            }
            
            integrated_stations.append(integrated_station)
    
    # 乗降客数でソート（降順）
    integrated_stations.sort(key=lambda x: x["properties"]["total_passengers"], reverse=True)
    
    # GeoJSONファイルとして保存
    output_data = {
        "type": "FeatureCollection",
        "features": integrated_stations
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"統合された駅データ: {len(integrated_stations)}件")
    print(f"出力ファイル: {output_file}")
    
    # 統計情報を表示
    print("\n=== 統計情報 ===")
    print(f"総駅数: {len(integrated_stations)}")
    print(f"総乗降客数: {sum(s['properties']['total_passengers'] for s in integrated_stations):,}")
    
    # 上位10駅を表示
    print("\n=== 乗降客数上位10駅 ===")
    for i, station in enumerate(integrated_stations[:10], 1):
        props = station["properties"]
        print(f"{i:2d}. {props['station_name']}: {props['total_passengers']:,}人 ({props['station_count']}箇所)")

def main():
    input_file = "data/S12-24_NumberOfPassengers.geojson"
    output_file = "kanto_stations_integrated.json"
    
    if not Path(input_file).exists():
        print(f"エラー: {input_file} が見つかりません")
        return
    
    process_station_data(input_file, output_file)

if __name__ == "__main__":
    main()
