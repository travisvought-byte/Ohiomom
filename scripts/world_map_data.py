#!/usr/bin/env python3
"""Make data/ymt/world-map.json, the country outlines behind the map on world.html, from Natural Earth.

Natural Earth (https://www.naturalearthdata.com/) is in the public domain. This reads two of its files, version 5.1.2,
as published in its GitHub repository (nvkelso/natural-earth-vector, folder geojson/):

    ne_110m_admin_0_countries.geojson   the outlines (1:110 million, the coarsest scale)
    ne_50m_admin_0_countries.geojson    only for the label point of each country too small to be in the first file
                                        (Singapore, Barbados, Malta, Bahrain and the like), so it can still be a dot

Neither file is kept in the repository. Antarctica is left off. Natural Earth draws Crimea as part of Russia (it shows
who controls a place); this moves it back to Ukraine, as the United States and the United Nations General Assembly
(resolution 68/262) recognize it. Every other border is Natural Earth's own. The outlines are drawn in the Equal Earth projection,
1000 units wide, thinned (Douglas-Peucker) and rounded to whole units, so the file stays small.

    python3 scripts/world_map_data.py <ne_110m file> <ne_50m file>

The site never runs this when it builds; scripts/ymt_build.py only reads the JSON it writes. Run it again only to
change the outlines.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'ymt' / 'world-map.json'
WIDTH = 1000
TOLERANCE = 0.55  # map units; a unit is about 40 km at the equator
SOUTH, NORTH = -56.0, 84.0  # the map's edges: Cape Horn to the north of Greenland

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def equal_earth(lon, lat):
    t = math.asin(M * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = 2 * math.sqrt(3) * math.radians(lon) * math.cos(t) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = t * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
    return x, y


X0, _ = equal_earth(-180, 0)
_, Y_TOP = equal_earth(0, NORTH)
_, Y_BOTTOM = equal_earth(0, SOUTH)
SCALE = WIDTH / (2 * -X0)
HEIGHT = round((Y_TOP - Y_BOTTOM) * SCALE)


def project(lon, lat):
    x, y = equal_earth(lon, lat)
    return (x - X0) * SCALE, (Y_TOP - y) * SCALE


def thin(points, tol):
    """Douglas-Peucker on a closed ring, keeping its first point."""
    if len(points) < 4:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        far, at = 0.0, None
        for i in range(a + 1, b):
            px, py = points[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / length if length else math.hypot(px - ax, py - ay)
            if d > far:
                far, at = d, i
        if at is not None and far > tol:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(points, keep) if k]


def ring_path(ring):
    pts = thin([project(lon, max(SOUTH, min(NORTH, lat))) for lon, lat in ring], TOLERANCE)
    out = []
    for x, y in pts:
        p = (round(x), round(y))
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    if len(out) < 3:
        return '', 0.0
    area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(out, out[1:] + out[:1]))) / 2
    if area < 0.5:
        return '', 0.0
    d = f'M{out[0][0]} {out[0][1]}l'
    steps = []
    for (x1, y1), (x2, y2) in zip(out, out[1:]):
        steps.append(f'{x2 - x1} {y2 - y1}'.replace(' -', '-'))
    return d + ' '.join(steps).replace(' -', '-') + 'z', area


def code_of(props):
    code = props.get('ISO_A2_EH') or props.get('ISO_A2')
    return code if code and code != '-99' else None


def inside(point, ring):
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


CRIMEA = (34.1, 44.9)  # a point in the middle of the peninsula


def give_crimea_to_ukraine(features):
    by_code = {code_of(f['properties']): f for f in features}
    ru, ua = by_code['RU']['geometry'], by_code['UA']['geometry']
    moved = [poly for poly in ru['coordinates'] if inside(CRIMEA, poly[0])]
    if moved:
        ru['coordinates'] = [poly for poly in ru['coordinates'] if poly not in moved]
        if ua['type'] == 'Polygon':
            ua['type'], ua['coordinates'] = 'MultiPolygon', [ua['coordinates']]
        ua['coordinates'] += moved


def main(small_file, mid_file):
    countries = []
    have = set()
    features = json.loads(Path(small_file).read_text(encoding='utf-8'))['features']
    give_crimea_to_ukraine(features)
    for f in features:
        p = f['properties']
        code = code_of(p)
        if p.get('CONTINENT') == 'Antarctica' or code == 'AQ':
            continue
        geom = f['geometry']
        polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        parts, area = [], 0.0
        biggest = ('', 0.0)
        for poly in polys:
            for k, ring in enumerate(poly):
                d, a = ring_path(ring)
                if not d:
                    continue
                parts.append(d)
                area += a if k == 0 else -a
                if a > biggest[1]:
                    biggest = (d, a)
        if not parts:
            continue
        x, y = project(p['LABEL_X'], p['LABEL_Y'])
        entry = {'code': code, 'name': p['NAME'], 'd': ''.join(parts), 'area': round(area), 'label': [round(x), round(y)]}
        if not code:
            del entry['code']
        countries.append(entry)
        if code:
            have.add(code)
    points = []
    for f in json.loads(Path(mid_file).read_text(encoding='utf-8'))['features']:
        p = f['properties']
        code = code_of(p)
        if not code or code in have or code == 'AQ' or not (SOUTH <= p['LABEL_Y'] <= NORTH):
            continue
        x, y = project(p['LABEL_X'], p['LABEL_Y'])
        points.append({'code': code, 'name': p['NAME'], 'label': [round(x), round(y)]})
        have.add(code)
    countries.sort(key=lambda c: c['name'])
    points.sort(key=lambda c: c['name'])
    out = {
        'source': 'Natural Earth 5.1.2, Admin 0 countries at 1:110m (outlines) and 1:50m (points for small countries)',
        'license': 'Public domain (https://www.naturalearthdata.com/about/terms-of-use/)',
        'projection': 'Equal Earth, Antarctica left off',
        'width': WIDTH, 'height': HEIGHT,
        'countries': countries,
        'points': points,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'wrote {OUT.relative_to(ROOT)}: {len(countries)} outlines, {len(points)} points, {OUT.stat().st_size:,} bytes')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
