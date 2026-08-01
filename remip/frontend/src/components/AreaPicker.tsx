"use client";

import { useEffect, useId, useState } from "react";
import { api, type Area } from "@/lib/api";

interface Props {
  onChange: (area: Area | null) => void;
}

/** City + optional neighborhood selector; emits the most specific area chosen. */
export function AreaPicker({ onChange }: Props) {
  const cityFieldId = useId();
  const neighborhoodFieldId = useId();
  const [cities, setCities] = useState<Area[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<Area[]>([]);
  const [cityId, setCityId] = useState<string>("");
  const [neighborhoodId, setNeighborhoodId] = useState<string>("");

  useEffect(() => {
    api<Area[]>("/api/v1/geo/areas?level=city", { auth: false })
      .then((data) => {
        setCities(data);
        if (data.length > 0) setCityId((current) => current || data[0].id);
      })
      .catch(() => setCities([]));
  }, []);

  useEffect(() => {
    if (!cityId) return;
    setNeighborhoodId("");
    api<Area[]>(`/api/v1/geo/areas?level=neighborhood&parent_id=${cityId}`, { auth: false })
      .then(setNeighborhoods)
      .catch(() => setNeighborhoods([]));
  }, [cityId]);

  useEffect(() => {
    const selected =
      neighborhoods.find((n) => n.id === neighborhoodId) ??
      cities.find((c) => c.id === cityId) ??
      null;
    onChange(selected);
  }, [cityId, neighborhoodId, cities, neighborhoods, onChange]);

  return (
    <div className="flex flex-wrap gap-3">
      <div className="min-w-40 flex-1">
        <label className="label" htmlFor={cityFieldId}>
          Città
        </label>
        <select
          id={cityFieldId}
          className="input"
          value={cityId}
          onChange={(e) => setCityId(e.target.value)}
        >
          {cities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="min-w-40 flex-1">
        <label className="label" htmlFor={neighborhoodFieldId}>
          Quartiere (opzionale)
        </label>
        <select
          id={neighborhoodFieldId}
          className="input"
          value={neighborhoodId}
          onChange={(e) => setNeighborhoodId(e.target.value)}
        >
          <option value="">Tutta la città</option>
          {neighborhoods.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
