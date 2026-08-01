"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Area, type MapPoint, type MapSearchRequest, type MapSearchResponse } from "@/lib/api";
import { AreaPicker } from "@/components/AreaPicker";
import { DataContextFooter } from "@/components/DataContextFooter";
import { PropertyMap, type LayerMode } from "@/components/PropertyMap";
import { circleRing } from "@/lib/geojson";

type SpatialMode = "area" | "polygon" | "radius";
type DrawTarget = "none" | "polygon" | "radius-center";

const DEFAULT_CENTER = { lat: 41.9028, lon: 12.4964 }; // Roma, until an area loads

export default function MapPage() {
  const [area, setArea] = useState<Area | null>(null);
  const [listingType, setListingType] = useState("sale");
  const [propertyType, setPropertyType] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [layerMode, setLayerMode] = useState<LayerMode>("markers");

  const [spatialMode, setSpatialMode] = useState<SpatialMode>("area");
  const [drawTarget, setDrawTarget] = useState<DrawTarget>("none");
  const [polygonPoints, setPolygonPoints] = useState<number[][]>([]);
  const [radiusCenter, setRadiusCenter] = useState<{ lat: number; lon: number } | null>(null);
  const [radiusKm, setRadiusKm] = useState(2);

  const [result, setResult] = useState<MapSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const onAreaChange = useCallback((a: Area | null) => setArea(a), []);

  const effectiveRadiusCenter = radiusCenter ?? (area ? { lat: area.centroid_lat, lon: area.centroid_lon } : null);

  const runSearch = useCallback(
    (overrides: Partial<MapSearchRequest> = {}) => {
      const body: MapSearchRequest = {
        listing_type: listingType,
        limit: 1500,
        ...(area ? { area_id: area.id } : {}),
        ...(propertyType ? { property_type: propertyType } : {}),
        ...(maxPrice ? { max_price: Number(maxPrice) } : {}),
        ...overrides,
      };
      setLoading(true);
      api<MapSearchResponse>("/api/v1/map/search", { method: "POST", body, auth: false })
        .then(setResult)
        .finally(() => setLoading(false));
    },
    [area, listingType, propertyType, maxPrice],
  );

  // default "area" view: refetch whenever the area/filters change
  useEffect(() => {
    if (!area || spatialMode !== "area") return;
    runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area, listingType, propertyType, maxPrice, spatialMode]);

  const startPolygonDraw = () => {
    setSpatialMode("polygon");
    setDrawTarget("polygon");
    setPolygonPoints([]);
  };

  const cancelDraw = () => {
    setDrawTarget("none");
    setPolygonPoints([]);
    setSpatialMode("area");
  };

  const finishPolygon = () => {
    if (polygonPoints.length < 3) return;
    setDrawTarget("none");
    runSearch({ area_id: undefined, polygon: polygonPoints });
  };

  const startRadiusMode = () => {
    setSpatialMode("radius");
    if (!radiusCenter && area) setRadiusCenter({ lat: area.centroid_lat, lon: area.centroid_lon });
  };

  const pickRadiusCenter = () => setDrawTarget("radius-center");

  const applyRadius = () => {
    if (!effectiveRadiusCenter) return;
    runSearch({
      area_id: undefined,
      radius: { lat: effectiveRadiusCenter.lat, lon: effectiveRadiusCenter.lon, radius_km: radiusKm },
    });
  };

  const resetToAreaView = () => {
    setSpatialMode("area");
    setDrawTarget("none");
    setPolygonPoints([]);
    setRadiusCenter(null);
  };

  const onMapClick = useCallback(
    (lat: number, lon: number) => {
      if (drawTarget === "polygon") {
        setPolygonPoints((pts) => [...pts, [lon, lat]]);
      } else if (drawTarget === "radius-center") {
        setRadiusCenter({ lat, lon });
        setDrawTarget("none");
      }
    },
    [drawTarget],
  );

  const points: MapPoint[] = result?.items ?? [];
  const center = area ? { lat: area.centroid_lat, lon: area.centroid_lon } : DEFAULT_CENTER;
  const radiusRing = spatialMode === "radius" && effectiveRadiusCenter ? circleRing(effectiveRadiusCenter.lat, effectiveRadiusCenter.lon, radiusKm) : null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Mappa</h1>

      <div className="card space-y-3">
        <AreaPicker onChange={onAreaChange} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className="label" htmlFor="mapListingType">
              Contratto
            </label>
            <select
              id="mapListingType"
              className="input"
              value={listingType}
              onChange={(e) => setListingType(e.target.value)}
            >
              <option value="sale">Vendita</option>
              <option value="rent">Affitto</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="mapPropertyType">
              Tipologia
            </label>
            <select
              id="mapPropertyType"
              className="input"
              value={propertyType}
              onChange={(e) => setPropertyType(e.target.value)}
            >
              <option value="">Tutte</option>
              <option value="apartment">Appartamento</option>
              <option value="studio">Monolocale</option>
              <option value="penthouse">Attico</option>
              <option value="detached_house">Casa indipendente</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="mapMaxPrice">
              Prezzo max (€)
            </label>
            <input
              id="mapMaxPrice"
              type="number"
              min={0}
              className="input"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="mapLayerMode">
              Visualizzazione
            </label>
            <select
              id="mapLayerMode"
              className="input"
              value={layerMode}
              onChange={(e) => setLayerMode(e.target.value as LayerMode)}
            >
              <option value="markers">Marker e cluster</option>
              <option value="heatmap">Heatmap prezzo/m²</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
          {spatialMode === "area" && (
            <>
              <button type="button" className="btn-secondary" onClick={startPolygonDraw}>
                ✏️ Disegna un&apos;area
              </button>
              <button type="button" className="btn-secondary" onClick={startRadiusMode}>
                ◎ Cerca per raggio
              </button>
            </>
          )}

          {spatialMode === "polygon" && (
            <>
              <span className="text-sm text-slate-500" data-testid="polygon-vertex-count">
                {drawTarget === "polygon"
                  ? `Clicca sulla mappa per aggiungere vertici (${polygonPoints.length})`
                  : `Area disegnata: ${polygonPoints.length} vertici`}
              </span>
              {drawTarget === "polygon" && polygonPoints.length >= 3 && (
                <button type="button" className="btn-primary" onClick={finishPolygon}>
                  Chiudi poligono e cerca
                </button>
              )}
              <button type="button" className="btn-secondary" onClick={cancelDraw}>
                Annulla
              </button>
            </>
          )}

          {spatialMode === "radius" && (
            <>
              <label className="label m-0" htmlFor="radiusKm">
                Raggio (km)
              </label>
              <input
                id="radiusKm"
                type="number"
                min={0.5}
                max={100}
                step={0.5}
                className="input w-24"
                value={radiusKm}
                onChange={(e) => setRadiusKm(Number(e.target.value))}
              />
              <button type="button" className="btn-secondary" onClick={pickRadiusCenter}>
                {drawTarget === "radius-center" ? "Clicca sulla mappa…" : "Sposta centro"}
              </button>
              <button type="button" className="btn-primary" onClick={applyRadius}>
                Applica raggio
              </button>
              <button type="button" className="btn-secondary" onClick={resetToAreaView}>
                Annulla
              </button>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <p className="mb-2 text-sm text-slate-500" aria-live="polite">
          {loading
            ? "Ricerca in corso…"
            : result
              ? `${result.total_matched} immobili trovati${result.truncated ? " (mostrati i primi " + points.length + ")" : ""} · ${
                  spatialMode === "polygon"
                    ? "area disegnata"
                    : spatialMode === "radius"
                      ? `raggio ${radiusKm} km`
                      : area
                        ? area.name
                        : "seleziona una zona"
                }`
              : "Seleziona una zona per iniziare"}
        </p>
        <PropertyMap
          center={center}
          points={points}
          layerMode={layerMode}
          drawing={drawTarget !== "none"}
          polygon={polygonPoints}
          radiusRing={radiusRing}
          onMapClick={onMapClick}
        />
        {result && <DataContextFooter context={result.data_context} />}
      </div>
    </div>
  );
}
