from typing import Dict

def square_footprint(lat: float, lon: float, deg: float = 0.02) -> Dict:
    poly = [[lon-deg,lat-deg],[lon+deg,lat-deg],[lon+deg,lat+deg],[lon-deg,lat+deg],[lon-deg,lat-deg]]
    return {"type":"Polygon","coordinates":[poly]}
