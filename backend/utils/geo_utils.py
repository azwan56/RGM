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
    Automatically boosts budget up to 600 points on tight multi-lap stadium/park circuits
    so 15-25km track sessions keep >=12-15 points per 400m lap instead of turning into polygons.
    """
    if not points or len(points) <= max_points:
        return points

    eff_max = max_points
    try:
        lats = [float(p["latitude"]) for p in points if p.get("latitude") is not None]
        lngs = [float(p["longitude"]) for p in points if p.get("longitude") is not None]
        if len(lats) >= 20 and len(lats) == len(lngs):
            mid_lat = (min(lats) + max(lats)) * 0.5
            h_m = (max(lats) - min(lats)) * 111320.0
            w_m = (max(lngs) - min(lngs)) * 111320.0 * math.cos(math.radians(mid_lat))
            if max(h_m, w_m) < 350.0:
                eff_max = min(len(points), max(max_points, 600))
    except Exception:
        pass

    if len(points) <= eff_max:
        return points

    step = (len(points) - 1) / (eff_max - 1)
    sampled = []
    for i in range(eff_max):
        idx = int(round(i * step))
        if idx >= len(points):
            idx = len(points) - 1
        sampled.append(points[idx])
    return sampled


def _wrap_angle_pi(rad: float) -> float:
    while rad <= -math.pi:
        rad += 2.0 * math.pi
    while rad > math.pi:
        rad -= 2.0 * math.pi
    return rad


def smooth_sparse_stadium_track(
    points: List[Dict[str, Any]],
    max_output_points: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Reconstructs smooth 400m stadium oval arcs ONLY when a legacy multi-lap stadium workout
    (e.g. 15-25km = 38-62 laps stored in 250 points, ~4-8 pts/lap) has large angular jumps
    that would otherwise draw diagonal star chords across the infield.
    Leaves road/park/trail runs and already-dense stadium tracks (>=13 pts/lap) untouched.
    """
    if not points or len(points) < 20:
        return points

    try:
        lats = [float(p["latitude"]) for p in points]
        lngs = [float(p["longitude"]) for p in points]
    except Exception:
        return points

    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    mid_lat = 0.5 * (min_lat + max_lat)
    mid_lng = 0.5 * (min_lng + max_lng)
    m_per_lat = 111320.0
    m_per_lng = 111320.0 * math.cos(math.radians(mid_lat))
    if m_per_lng < 1e-3:
        return points

    h_m = (max_lat - min_lat) * m_per_lat
    w_m = (max_lng - min_lng) * m_per_lng
    short_m, long_m = min(w_m, h_m), max(w_m, h_m)

    # Only match 200m-400m athletics stadium dimensions
    if not (45.0 <= short_m <= 165.0 and 85.0 <= long_m <= 265.0):
        return points

    xs = [(lng - mid_lng) * m_per_lng for lng in lngs]
    ys = [(lat - mid_lat) * m_per_lat for lat in lats]
    rs = [math.hypot(x, y) for x, y in zip(xs, ys)]
    sorted_rs = sorted(rs)
    med_r = sorted_rs[len(sorted_rs) // 2]
    # Hollow center check: ensure runner never cut across the infield
    if sorted_rs[0] < 18.0 or sorted_rs[0] < 0.33 * med_r:
        return points

    thetas = [math.atan2(y, x) for x, y in zip(xs, ys)]
    dthetas = [_wrap_angle_pi(thetas[i + 1] - thetas[i]) for i in range(len(thetas) - 1)]
    pos_frac = sum(1 for d in dthetas if d > 0.02) / float(len(dthetas))
    neg_frac = sum(1 for d in dthetas if d < -0.02) / float(len(dthetas))
    if max(pos_frac, neg_frac) < 0.82:
        return points
    loop_dir = 1.0 if pos_frac >= neg_frac else -1.0

    abs_steps = sorted(abs(d) for d in dthetas)
    med_step = abs_steps[len(abs_steps) // 2]
    # Already >= ~13 points per lap (e.g. Shen Lu 4.4km has ~23 pts/lap = 15.7 deg): keep exact points
    if med_step <= math.radians(28.0):
        return points

    # Build 72-sector (5 deg) empirical stadium contour r(theta) from the runner's own points
    num_bins = 72
    two_pi = 2.0 * math.pi
    bins: List[List[float]] = [[] for _ in range(num_bins)]
    for th, r in zip(thetas, rs):
        b_idx = int(((th + math.pi) / two_pi) * num_bins) % num_bins
        bins[b_idx].append(r)

    bin_r: List[Optional[float]] = [
        (sorted(vals)[len(vals) // 2] if vals else None) for vals in bins
    ]
    known = [i for i, v in enumerate(bin_r) if v is not None]
    if len(known) < 18:
        return points

    filled = list(bin_r)
    for i in range(num_bins):
        if filled[i] is None:
            prev_i = max((k for k in known if k < i), default=known[-1])
            next_i = min((k for k in known if k > i), default=known[0])
            span = (next_i - prev_i) % num_bins
            dist = (i - prev_i) % num_bins
            t = (dist / float(span)) if span > 0 else 0.0
            filled[i] = (1.0 - t) * float(bin_r[prev_i]) + t * float(bin_r[next_i])  # type: ignore[arg-type]

    smooth_r = [
        0.25 * float(filled[(i - 1) % num_bins])
        + 0.50 * float(filled[i])
        + 0.25 * float(filled[(i + 1) % num_bins])
        for i in range(num_bins)
    ]

    def contour_r(theta: float) -> float:
        pos = ((theta + math.pi) / two_pi) * num_bins
        i0 = int(math.floor(pos)) % num_bins
        i1 = (i0 + 1) % num_bins
        f = pos - math.floor(pos)
        return (1.0 - f) * smooth_r[i0] + f * smooth_r[i1]

    def interp_arc(th0: float, r0: float, th1: float, r1: float) -> List[Dict[str, float]]:
        d_raw = _wrap_angle_pi(th1 - th0)
        # Advance in the runner's loop direction if chord jumped >= ~150 deg
        if d_raw * loop_dir < 0 and abs(d_raw) > math.radians(35.0):
            d_raw += loop_dir * two_pi
        if abs(d_raw) <= math.radians(16.0) or d_raw * loop_dir < 0:
            return []
        n_sub = min(24, max(1, int(abs(d_raw) / math.radians(12.0))))
        c0 = max(10.0, contour_r(th0))
        c1 = max(10.0, contour_r(th1))
        s0 = r0 / c0
        s1 = r1 / c1
        arc_pts = []
        for k in range(1, n_sub + 1):
            frac = k / float(n_sub + 1)
            th = th0 + frac * d_raw
            rk = ((1.0 - frac) * s0 + frac * s1) * contour_r(th)
            arc_pts.append({
                "latitude": round(mid_lat + (rk * math.sin(th)) / m_per_lat, 6),
                "longitude": round(mid_lng + (rk * math.cos(th)) / m_per_lng, 6),
            })
        return arc_pts

    dense: List[Dict[str, Any]] = []
    for i in range(len(points) - 1):
        dense.append({
            "latitude": round(lats[i], 6),
            "longitude": round(lngs[i], 6),
        })
        dense.extend(interp_arc(thetas[i], rs[i], thetas[i + 1], rs[i + 1]))
    dense.append({
        "latitude": round(lats[-1], 6),
        "longitude": round(lngs[-1], 6),
    })

    if max_output_points and len(dense) > max_output_points and max_output_points >= 80:
        # Keep contiguous smooth opening laps + smooth bridge along stadium lane to exact finish point
        keep_head = max_output_points - 26
        trimmed = dense[:keep_head]
        last_pt = trimmed[-1]
        lx = (last_pt["longitude"] - mid_lng) * m_per_lng
        ly = (last_pt["latitude"] - mid_lat) * m_per_lat
        l_th = math.atan2(ly, lx)
        l_r = math.hypot(lx, ly)
        # Ensure angular delta bridges smoothly in loop direction to exact finish point
        d_end = _wrap_angle_pi(thetas[-1] - l_th)
        if d_end * loop_dir <= 0:
            d_end += loop_dir * two_pi
        n_bridge = max(2, int(abs(d_end) / math.radians(12.0)))
        s_start = l_r / max(10.0, contour_r(l_th))
        s_end = rs[-1] / max(10.0, contour_r(thetas[-1]))
        for k in range(1, n_bridge + 1):
            frac = k / float(n_bridge + 1)
            th = l_th + frac * d_end
            rk = ((1.0 - frac) * s_start + frac * s_end) * contour_r(th)
            trimmed.append({
                "latitude": round(mid_lat + (rk * math.sin(th)) / m_per_lat, 6),
                "longitude": round(mid_lng + (rk * math.cos(th)) / m_per_lng, 6),
            })
        trimmed.append({
            "latitude": round(lats[-1], 6),
            "longitude": round(lngs[-1], 6),
        })
        return trimmed

    return dense
