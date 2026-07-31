"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import {
  api,
  formatPrice,
  type Area,
  type ListingSummary,
  type Paginated,
} from "@/lib/api";
import { AreaPicker } from "@/components/AreaPicker";

const PAGE_SIZE = 12;

const propertyTypes = [
  { value: "", label: "Tutte le tipologie" },
  { value: "apartment", label: "Appartamento" },
  { value: "studio", label: "Monolocale" },
  { value: "penthouse", label: "Attico" },
  { value: "detached_house", label: "Casa indipendente" },
];

function ListingCard({ listing }: { listing: ListingSummary }) {
  return (
    <Link
      href={`/listings/${listing.id}`}
      className="card block transition hover:border-brand-500"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold">{listing.title}</h3>
        <span className="whitespace-nowrap text-sm font-semibold text-brand-600">
          {formatPrice(listing.current_price, listing.currency)}
          {listing.listing_type === "rent" && "/mese"}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {listing.area_name} · {listing.size_sqm} m² · {listing.rooms} locali
        {listing.energy_class && ` · classe ${listing.energy_class}`}
        {listing.price_per_sqm && ` · ${listing.price_per_sqm.toLocaleString("it-IT")} €/m²`}
      </p>
      <p className="mt-1 text-xs text-slate-500">
        {listing.days_on_market} giorni sul mercato · {listing.photos_count} foto
      </p>
    </Link>
  );
}

function ListingsSearch() {
  const searchParams = useSearchParams();
  const initialAreaId = searchParams.get("area_id");
  const [area, setArea] = useState<Area | null>(null);
  const [listingType, setListingType] = useState("sale");
  const [propertyType, setPropertyType] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [minRooms, setMinRooms] = useState("");
  const [sortBy, setSortBy] = useState("published_at");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<Paginated<ListingSummary> | null>(null);
  const [loading, setLoading] = useState(false);

  const areaId = area?.id ?? initialAreaId;
  const onAreaChange = useCallback((a: Area | null) => {
    setArea(a);
    setPage(0);
  }, []);

  useEffect(() => {
    if (!areaId) return;
    const params = new URLSearchParams({
      area_id: areaId,
      listing_type: listingType,
      sort_by: sortBy,
      sort_dir: sortBy === "price" ? "asc" : "desc",
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (propertyType) params.set("property_type", propertyType);
    if (maxPrice) params.set("max_price", maxPrice);
    if (minRooms) params.set("min_rooms", minRooms);
    setLoading(true);
    api<Paginated<ListingSummary>>(`/api/v1/listings?${params}`, { auth: false })
      .then(setResult)
      .finally(() => setLoading(false));
  }, [areaId, listingType, propertyType, maxPrice, minRooms, sortBy, page]);

  const totalPages = result ? Math.ceil(result.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Ricerca immobili</h1>
      <div className="card space-y-3">
        <AreaPicker onChange={onAreaChange} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div>
            <label className="label" htmlFor="listingType">
              Contratto
            </label>
            <select
              id="listingType"
              className="input"
              value={listingType}
              onChange={(e) => {
                setListingType(e.target.value);
                setPage(0);
              }}
            >
              <option value="sale">Vendita</option>
              <option value="rent">Affitto</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="propertyType">
              Tipologia
            </label>
            <select
              id="propertyType"
              className="input"
              value={propertyType}
              onChange={(e) => {
                setPropertyType(e.target.value);
                setPage(0);
              }}
            >
              {propertyTypes.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="maxPrice">
              Prezzo max (€)
            </label>
            <input
              id="maxPrice"
              type="number"
              min={0}
              className="input"
              value={maxPrice}
              onChange={(e) => {
                setMaxPrice(e.target.value);
                setPage(0);
              }}
              placeholder="es. 400000"
            />
          </div>
          <div>
            <label className="label" htmlFor="minRooms">
              Locali min
            </label>
            <input
              id="minRooms"
              type="number"
              min={0}
              className="input"
              value={minRooms}
              onChange={(e) => {
                setMinRooms(e.target.value);
                setPage(0);
              }}
              placeholder="es. 2"
            />
          </div>
          <div>
            <label className="label" htmlFor="sortBy">
              Ordina per
            </label>
            <select
              id="sortBy"
              className="input"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="published_at">Più recenti</option>
              <option value="price">Prezzo crescente</option>
              <option value="size_sqm">Superficie</option>
            </select>
          </div>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Caricamento…</p>}
      {result && (
        <>
          <p className="text-sm text-slate-500">{result.total} annunci trovati (dati demo)</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {result.items.map((listing) => (
              <ListingCard key={listing.id} listing={listing} />
            ))}
          </div>
          {totalPages > 1 && (
            <nav className="flex items-center justify-center gap-3" aria-label="Paginazione">
              <button
                type="button"
                className="btn-secondary"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Precedente
              </button>
              <span className="text-sm text-slate-500">
                Pagina {page + 1} di {totalPages}
              </span>
              <button
                type="button"
                className="btn-secondary"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Successiva →
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}

export default function ListingsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Caricamento…</p>}>
      <ListingsSearch />
    </Suspense>
  );
}
