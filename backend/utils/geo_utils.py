import math
from typing import List, Dict, Any, Tuple, Optional

# Constants for WGS-84 to GCJ-02 transformation (China GPS standard)
x_PI = 3.14159265358979324 * 3000.0 / 180.0
PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def out_of_china(lng: float, lat: float) -> bool:
    """Checks if coordinates are outside mainland China bounds."""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def wgs84_to_gcj02(lat: float, lng: float) -> Tuple[float, float]:
    """
    Converts WGS-84 (Garmin standard GPS) to GCJ-02 (Tencent Map / WeChat Mini Program).
    Returns (gcj_lat, gcj_lng).
    """
    if out_of_china(lng, lat):
        return round(lat, 6), round(lng, 6)

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return round(mglat, 6), round(mglng, 6)


def downsample_points(points: List[Dict[str, Any]], max_points: int = 250) -> List[Dict[str, Any]]:
    """
    Downsamples a GPS polyline to max_points while preserving start and end points.
    """
    if not points or len(points) <= max_points:
        return points

    step = (len(points) - 1) / (max_points - 1)
    sampled = []
    for i in range(max_points):
        idx = int(round(i * step))
        if idx >= len(points):
            idx = len(points) - 1
        sampled.append(points[idx])
    return sampled
