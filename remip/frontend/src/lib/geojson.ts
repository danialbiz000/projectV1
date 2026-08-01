/** Minimal local GeoJSON types — avoids pulling in @types/geojson directly. */
import type { MapPoint } from "@/lib/api";

export type PointFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: Record<string, unknown>;
};

export type PolygonFeature = {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: Record<string, unknown>;
};

export type FeatureCollection = {
  type: "FeatureCollection";
  features: (PointFeature | PolygonFeature)[];
};

export function emptyFC(): FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}

export function pointsToFC(points: MapPoint[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: points.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: { ...p },
    })),
  };
}

export function ringToFC(ring: number[][]): FeatureCollection {
  if (ring.length < 3) return emptyFC();
  const closed = ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
    ? ring
    : [...ring, ring[0]];
  return {
    type: "FeatureCollection",
    features: [
      { type: "Feature", geometry: { type: "Polygon", coordinates: [closed] }, properties: {} },
    ],
  };
}

/** Client-side mirror of the backend's circle_polygon (services/geo.py), for
 * rendering the radius-search overlay without an extra API round trip. */
export function circleRing(lat: number, lon: number, radiusKm: number, points = 48): number[][] {
  const EARTH_RADIUS_KM = 6371.0;
  const latRad = (lat * Math.PI) / 180;
  const coords: number[][] = [];
  for (let i = 0; i <= points; i++) {
    const angle = (2 * Math.PI * i) / points;
    const dLat = (radiusKm / EARTH_RADIUS_KM) * Math.cos(angle);
    const dLon = (radiusKm / EARTH_RADIUS_KM) * Math.sin(angle) / Math.max(Math.cos(latRad), 1e-6);
    coords.push([lon + (dLon * 180) / Math.PI, lat + (dLat * 180) / Math.PI]);
  }
  return coords;
}
