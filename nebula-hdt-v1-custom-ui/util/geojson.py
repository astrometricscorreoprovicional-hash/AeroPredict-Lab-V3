import json, os, time
from typing import List, Dict

def linestring(coords: List[List[float]], props: Dict=None) -> Dict:
    feat = {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props or {}}
    return feat

def polygon(coords: List[List[float]], props: Dict=None) -> Dict:
    feat = {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": props or {}}
    return feat

def feature_collection(features: List[Dict]) -> Dict:
    return {"type": "FeatureCollection", "features": features}

def save_geojson(fc: Dict, outdir: str = "exports", prefix: str = "export") -> str:
    os.makedirs(outdir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(outdir, f"{prefix}_{ts}.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    return path
