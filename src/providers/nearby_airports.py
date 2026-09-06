"""Geographic candidates, not a claim of flight or ground-transfer availability.

OurAirports public-domain snapshot contains scheduled-service airports worldwide.
Distance is great-circle distance from the selected arrival airport, not driving
distance to accommodation. Border crossings and transfers must be checked.
"""
import json
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path


@lru_cache(maxsize=1)
def airport_index():
    return json.loads(Path(__file__).with_name('airports_world.json').read_text(encoding='utf-8'))['airports']


def nearby_airports(destination, *, exclude=(), radius_km=300, limit=3):
    airports = airport_index()
    center = airports.get(destination)
    if center is None:
        return []
    lat, lon = map(radians, center[:2])
    candidates = []
    for code, point in airports.items():
        if code == destination or code in exclude:
            continue
        other_lat, other_lon = map(radians, point[:2])
        a = sin((other_lat-lat)/2)**2 + cos(lat)*cos(other_lat)*sin((other_lon-lon)/2)**2
        distance = 6371.0088 * 2 * asin(sqrt(min(1, max(0, a))))
        if distance <= radius_km:
            candidates.append({'code': code, 'distance_km': round(distance), 'cross_border': point[2] != center[2], '_distance': distance})
    candidates.sort(key=lambda item: (item['_distance'], item['code']))
    return [{k: v for k, v in item.items() if k != '_distance'} for item in candidates[:limit]]