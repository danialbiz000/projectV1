"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { formatPrice, type MapPoint } from "@/lib/api";
import { emptyFC, pointsToFC, ringToFC } from "@/lib/geojson";

// No vector-tile provider key is configured for the demo: raster OSM tiles
// are used at low volume for demonstration only (see docs/INTEGRATIONS.md —
// a licensed tile provider is required before any production-scale traffic).
const OSM_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
  // Public MapLibre demo glyph server, used only to render cluster-count
  // labels (no vector-tile provider is configured for the demo — see
  // docs/INTEGRATIONS.md).
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
};

export type LayerMode = "markers" | "heatmap";

interface Props {
  center: { lat: number; lon: number };
  points: MapPoint[];
  layerMode: LayerMode;
  drawing: boolean;
  polygon: number[][];
  radiusRing: number[][] | null;
  onMapClick: (lat: number, lon: number) => void;
}

export function PropertyMap({
  center,
  points,
  layerMode,
  drawing,
  polygon,
  radiusRing,
  onMapClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onMapClickRef = useRef(onMapClick);
  onMapClickRef.current = onMapClick;
  // Tracks "our sources/layers exist and can be mutated", set once by the
  // "load" event. Deliberately NOT map.isStyleLoaded(): that also reflects
  // whether the background raster tiles have finished streaming, so it can
  // stay false indefinitely if the tile provider is unreachable — which must
  // not block updating our own GeoJSON data/layers.
  const readyRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [center.lon, center.lat],
      zoom: 12,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource("listings", {
        type: "geojson",
        data: emptyFC() as GeoJSON.FeatureCollection,
        cluster: true,
        clusterMaxZoom: 15,
        clusterRadius: 45,
      });
      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "listings",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": ["step", ["get", "point_count"], "#7cb9ff", 10, "#2a7de1", 30, "#174f9c"],
          "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 30, 28],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: "listings",
        filter: ["has", "point_count"],
        layout: { "text-field": "{point_count_abbreviated}", "text-size": 12 },
        paint: { "text-color": "#ffffff" },
      });
      map.addLayer({
        id: "unclustered",
        type: "circle",
        source: "listings",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "price_per_sqm"], 0],
            1500,
            "#22a06b",
            3500,
            "#f2b705",
            6500,
            "#e2664c",
          ],
          "circle-radius": 7,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: "heatmap",
        type: "heatmap",
        source: "listings",
        filter: ["!", ["has", "point_count"]],
        layout: { visibility: "none" },
        paint: {
          "heatmap-weight": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "price_per_sqm"], 0],
            0,
            0,
            8000,
            1,
          ],
          "heatmap-intensity": 1,
          "heatmap-radius": 28,
          "heatmap-opacity": 0.8,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(33,102,172,0)",
            0.2,
            "rgb(103,169,207)",
            0.4,
            "rgb(209,229,240)",
            0.6,
            "rgb(253,219,199)",
            0.8,
            "rgb(239,138,98)",
            1,
            "rgb(178,24,43)",
          ],
        },
      });

      map.addSource("polygon", { type: "geojson", data: emptyFC() as GeoJSON.FeatureCollection });
      map.addLayer({
        id: "polygon-fill",
        type: "fill",
        source: "polygon",
        paint: { "fill-color": "#2a7de1", "fill-opacity": 0.15 },
      });
      map.addLayer({
        id: "polygon-line",
        type: "line",
        source: "polygon",
        paint: { "line-color": "#2a7de1", "line-width": 2, "line-dasharray": [2, 1] },
      });

      map.addSource("radius", { type: "geojson", data: emptyFC() as GeoJSON.FeatureCollection });
      map.addLayer({
        id: "radius-fill",
        type: "fill",
        source: "radius",
        paint: { "fill-color": "#f2b705", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "radius-line",
        type: "line",
        source: "radius",
        paint: { "line-color": "#c98f00", "line-width": 2 },
      });

      map.on("mouseenter", "clusters", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "clusters", () => (map.getCanvas().style.cursor = ""));
      map.on("mouseenter", "unclustered", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "unclustered", () => (map.getCanvas().style.cursor = ""));

      map.on("click", "clusters", async (e) => {
        const features = map.queryRenderedFeatures(e.point, { layers: ["clusters"] });
        const clusterId = features[0]?.properties?.cluster_id;
        const source = map.getSource("listings") as maplibregl.GeoJSONSource;
        if (clusterId === undefined) return;
        const zoom = await source.getClusterExpansionZoom(clusterId);
        const geometry = features[0].geometry as GeoJSON.Point;
        map.easeTo({ center: geometry.coordinates as [number, number], zoom });
      });

      map.on("click", "unclustered", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const p = feature.properties as MapPoint;
        const coords = (feature.geometry as GeoJSON.Point).coordinates.slice() as [
          number,
          number,
        ];
        new maplibregl.Popup({ closeButton: true, maxWidth: "220px" })
          .setLngLat(coords)
          .setHTML(
            `<a href="/listings/${p.id}" style="color:#2a7de1;font-weight:600;text-decoration:none">` +
              `${formatPrice(Number(p.price), String(p.currency))}</a>` +
              `<div style="font-size:12px;color:#475569;margin-top:2px">${p.size_sqm} m² · ${p.rooms} locali · ${
                p.price_per_sqm ? `${Math.round(Number(p.price_per_sqm)).toLocaleString("it-IT")} €/m²` : ""
              }</div>`,
          )
          .addTo(map);
      });

      map.on("click", (e) => {
        const hit = map.queryRenderedFeatures(e.point, { layers: ["clusters", "unclustered"] });
        if (hit.length === 0) onMapClickRef.current(e.lngLat.lat, e.lngLat.lng);
      });

      readyRef.current = true;
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- init once; center updates via flyTo below
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      const src = map.getSource("listings") as maplibregl.GeoJSONSource | undefined;
      src?.setData(pointsToFC(points) as GeoJSON.FeatureCollection);
    };
    if (readyRef.current) update();
    else map.once("load", update);
  }, [points]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const showMarkers = layerMode === "markers" ? "visible" : "none";
    const showHeat = layerMode === "heatmap" ? "visible" : "none";
    for (const id of ["clusters", "cluster-count", "unclustered"]) {
      map.setLayoutProperty(id, "visibility", showMarkers);
    }
    map.setLayoutProperty("heatmap", "visibility", showHeat);
  }, [layerMode, points]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      const src = map.getSource("polygon") as maplibregl.GeoJSONSource | undefined;
      src?.setData(ringToFC(polygon) as GeoJSON.FeatureCollection);
    };
    if (readyRef.current) update();
    else map.once("load", update);
  }, [polygon]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      const src = map.getSource("radius") as maplibregl.GeoJSONSource | undefined;
      src?.setData((radiusRing ? ringToFC(radiusRing) : emptyFC()) as GeoJSON.FeatureCollection);
    };
    if (readyRef.current) update();
    else map.once("load", update);
  }, [radiusRing]);

  useEffect(() => {
    mapRef.current?.flyTo({ center: [center.lon, center.lat], zoom: 12 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center.lat, center.lon]);

  useEffect(() => {
    if (containerRef.current) containerRef.current.style.cursor = drawing ? "crosshair" : "";
  }, [drawing]);

  return (
    <div
      ref={containerRef}
      data-testid="property-map"
      role="application"
      aria-label="Mappa interattiva degli immobili"
      className="h-[520px] w-full overflow-hidden rounded-xl"
    />
  );
}
