#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, math, argparse
from pathlib import Path
from typing import Iterable, Tuple, List, Union

from PIL import Image, ImageDraw
import mercantile

TILE_SIZE = 256

# 関東地方の都道府県コード
KANTO_PREFECTURE_CODES = [8, 9, 10, 11, 12, 13, 14]  # 茨城、栃木、群馬、埼玉、千葉、東京、神奈川

def parse_args():
    p = argparse.ArgumentParser(
        description="関東地方の地図と路線図を重ねてXYZタイルを生成する"
    )
    p.add_argument("prefecture_geojson", help="都道府県GeoJSONファイルのパス")
    p.add_argument("railroad_geojson", help="路線GeoJSONファイルのパス")
    p.add_argument("outdir", help="XYZタイルの出力ディレクトリ")
    p.add_argument("--min-zoom", type=int, default=6)
    p.add_argument("--max-zoom", type=int, default=14)
    p.add_argument("--bg-color", default="transparent",
                   help="タイルの背景色 (例: '#00000000' または 'transparent')")
    p.add_argument("--prefecture-fill", default="#e6f3ff",
                   help="都道府県の塗りつぶし色")
    p.add_argument("--prefecture-line", default="#4a90e2",
                   help="都道府県の境界線色")
    p.add_argument("--prefecture-line-width", type=float, default=1.5)
    p.add_argument("--railroad-line", default="#ff6b6b",
                   help="路線の色")
    p.add_argument("--railroad-line-width", type=float, default=2.0)
    return p.parse_args()


# --- Web Mercator helpers (spherical mercator / slippy map) ---

def lonlat_to_global_pixel(lon: float, lat: float, z: int) -> Tuple[float, float]:
    """
    Convert lon/lat (EPSG:4326) to *global* pixel coordinates at zoom z for 256px tiles.
    """
    siny = math.sin(math.radians(lat))
    # Clamp latitude to the Web Mercator limits
    siny = min(max(siny, -0.9999), 0.9999)
    scale = 256 * (2 ** z)
    x = (lon + 180.0) / 360.0 * scale
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y

def to_tile_local_xy(lon: float, lat: float, z: int, x_tile: int, y_tile: int) -> Tuple[float, float]:
    gx, gy = lonlat_to_global_pixel(lon, lat, z)
    return gx - x_tile * TILE_SIZE, gy - y_tile * TILE_SIZE


# --- GeoJSON geometry iterators ---

def iter_geoms(feature) -> Iterable[Tuple[str, Union[List, Tuple]]]:
    """
    Yield (geom_type, coordinates) flattened over Multi* and GeometryCollection.
    """
    geom = feature.get("geometry") or feature  # feature or geom
    gtype = geom.get("type")
    coords = geom.get("coordinates")

    if gtype == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from iter_geoms(g)
    elif gtype.startswith("Multi"):
        base = gtype.replace("Multi", "")
        for part in coords:
            yield base, part
    else:
        yield gtype, coords


# --- Drawing primitives ---

def draw_line(draw: ImageDraw.ImageDraw, pts: List[Tuple[float, float]], color: str, width: float):
    if len(pts) >= 2:
        draw.line(pts, fill=color, width=int(max(1, round(width))), joint="curve")

def draw_polygon(draw: ImageDraw.ImageDraw, rings: List[List[Tuple[float, float]]],
                 fill_color: str = None, line_color: str = None, line_width: float = 1.0):
    # Simple fill without holes for now
    if fill_color and len(rings) > 0:
        draw.polygon(rings[0], fill=fill_color)

    # outline (exterior + holes)
    if line_color and len(rings) > 0:
        draw_line(draw, rings[0], line_color, line_width)
        for hole in rings[1:]:
            draw_line(draw, hole, line_color, line_width)


# --- Data filtering functions ---

def is_kanto_prefecture(feature):
    """関東地方の都道府県かどうかを判定（緯度経度範囲で判定）"""
    # 関東地方の範囲: [[34.8, 138.8], [36.4, 141.0]] - 少し緩く設定
    KANTO_BBOX = (139.3389, 35.4948, 139.9349, 35.8284)  # (min_lon, min_lat, max_lon, max_lat)
    
    geom = feature.get("geometry")
    if not geom:
        return False
    
    # 座標の範囲をチェック
    for gtype, coords in iter_geoms(feature):
        if gtype == "Polygon":
            for ring in coords:
                for lon, lat in ring:
                    if KANTO_BBOX[0] <= lon <= KANTO_BBOX[2] and KANTO_BBOX[1] <= lat <= KANTO_BBOX[3]:
                        return True
    return False

def is_kanto_railroad(feature):
    """関東地方の路線かどうかを判定（緯度経度範囲で判定）"""
    # 関東地方の範囲: [[34.8, 138.8], [36.4, 141.0]] - 少し緩く設定
    KANTO_BBOX = (139.3389, 35.4948, 139.9349, 35.8284)  # (min_lon, min_lat, max_lon, max_lat)
    
    geom = feature.get("geometry")
    if not geom:
        return False
    
    # 座標の範囲をチェック
    for gtype, coords in iter_geoms(feature):
        if gtype == "LineString":
            for lon, lat in coords:
                if KANTO_BBOX[0] <= lon <= KANTO_BBOX[2] and KANTO_BBOX[1] <= lat <= KANTO_BBOX[3]:
                    return True
    return False


# --- Main tiling ---

def main():
    a = parse_args()

    # 都道府県データを読み込み、関東地方のみを抽出
    print("都道府県データを読み込み中...")
    with open(a.prefecture_geojson, "r", encoding="utf-8") as f:
        prefecture_gj = json.load(f)
    
    kanto_prefectures = []
    if prefecture_gj.get("type") == "FeatureCollection":
        for feature in prefecture_gj["features"]:
            if is_kanto_prefecture(feature):
                kanto_prefectures.append(feature)
    print(f"関東地方の都道府県: {len(kanto_prefectures)}件")

    # 路線データを読み込み、関東地方のみを抽出
    print("路線データを読み込み中...")
    with open(a.railroad_geojson, "r", encoding="utf-8") as f:
        railroad_gj = json.load(f)
    
    kanto_railroads = []
    if railroad_gj.get("type") == "FeatureCollection":
        for feature in railroad_gj["features"]:
            if is_kanto_railroad(feature):
                kanto_railroads.append(feature)
    print(f"関東地方の路線: {len(kanto_railroads)}件")

    # 関東地方の全体のバウンディングボックスを計算
    def bbox_of_feature(feat) -> Tuple[float, float, float, float]:
        minx = miny = 1e9
        maxx = maxy = -1e9
        for gtype, coords in iter_geoms(feat):
            if gtype == "Point":
                x, y = coords
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
            elif gtype == "LineString":
                for x, y in coords:
                    minx = min(minx, x); maxx = max(maxx, x)
                    miny = min(miny, y); maxy = max(maxy, y)
            elif gtype == "Polygon":
                for ring in coords:
                    for x, y in ring:
                        minx = min(minx, x); maxx = max(maxx, x)
                        miny = min(miny, y); maxy = max(maxy, y)
        return minx, miny, maxx, maxy

    # 都道府県と路線のバウンディングボックスを統合
    all_bboxes = []
    for feat in kanto_prefectures + kanto_railroads:
        bbox = bbox_of_feature(feat)
        if bbox[0] != 1e9:  # 有効なバウンディングボックス
            all_bboxes.append(bbox)

    if not all_bboxes:
        print("関東地方のデータが見つかりませんでした")
        return

    minlon = min(b[0] for b in all_bboxes)
    minlat = min(b[1] for b in all_bboxes)
    maxlon = max(b[2] for b in all_bboxes)
    maxlat = max(b[3] for b in all_bboxes)

    print(f"関東地方の範囲: {minlon:.4f}, {minlat:.4f}, {maxlon:.4f}, {maxlat:.4f}")

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for z in range(a.min_zoom, a.max_zoom + 1):
        # 関東地方の範囲内のタイルのみを生成
        tiles = list(mercantile.tiles(minlon, minlat, maxlon, maxlat, [z]))
        print(f"[z={z}] タイル数: {len(tiles)}")
        
        for t in tiles:
            z_, x, y = t.z, t.x, t.y
            zdir = outdir / str(z_)
            xdir = zdir / str(x)
            xdir.mkdir(parents=True, exist_ok=True)
            png_path = xdir / f"{y}.png"

            # RGBAタイルを作成
            if a.bg_color.lower() == "transparent":
                img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
            else:
                img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), a.bg_color)
            draw = ImageDraw.Draw(img)

            # 1. 都道府県を描画（背景）- 関東地方の範囲内のみ
            KANTO_BBOX = (139.3389, 35.4948, 139.9349, 35.8284)  # (min_lon, min_lat, max_lon, max_lat)
            
            for feat in kanto_prefectures:
                if not feat.get("geometry"):
                    continue
                for gtype, coords in iter_geoms(feat):
                    if gtype == "Polygon":
                        # 関東地方の範囲内の座標のみを抽出
                        filtered_rings = []
                        for ring in coords:
                            filtered_ring = []
                            for lon, lat in ring:
                                if KANTO_BBOX[0] <= lon <= KANTO_BBOX[2] and KANTO_BBOX[1] <= lat <= KANTO_BBOX[3]:
                                    filtered_ring.append((lon, lat))
                            if len(filtered_ring) >= 3:  # ポリゴンとして有効な最小点数
                                filtered_rings.append(filtered_ring)
                        
                        if filtered_rings:
                            rings_px: List[List[Tuple[float, float]]] = []
                            for ring in filtered_rings:
                                ring_pts = [to_tile_local_xy(lon, lat, z_, x, y) for lon, lat in ring]
                                rings_px.append(ring_pts)
                            # タイル内に表示されるかチェック
                            exterior = rings_px[0]
                            if any((-32 <= px <= TILE_SIZE + 32 and -32 <= py <= TILE_SIZE + 32) for px, py in exterior):
                                draw_polygon(draw, rings_px, a.prefecture_fill, a.prefecture_line, a.prefecture_line_width)

            # 2. 路線を描画（前景）
            for feat in kanto_railroads:
                if not feat.get("geometry"):
                    continue
                for gtype, coords in iter_geoms(feat):
                    if gtype == "LineString":
                        pts = [to_tile_local_xy(lon, lat, z_, x, y) for lon, lat in coords]
                        # タイル内に表示されるかチェック
                        if any((-32 <= px <= TILE_SIZE + 32 and -32 <= py <= TILE_SIZE + 32) for px, py in pts):
                            draw_line(draw, pts, a.railroad_line, a.railroad_line_width)

            img.save(png_path, format="PNG", optimize=True)
    
    print("完了しました。")


if __name__ == "__main__":
    main()
