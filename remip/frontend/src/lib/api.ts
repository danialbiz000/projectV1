/** Typed client for the REMIP backend API (v1). */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "remip_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.auth !== false) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// ---- API types (mirror backend schemas) ----

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  onboarding_completed: boolean;
}

export interface Area {
  id: string;
  country_code: string;
  level: string;
  name: string;
  slug: string;
  parent_id: string | null;
  centroid_lat: number;
  centroid_lon: number;
  population: number | null;
}

export interface ListingSummary {
  id: string;
  title: string;
  listing_type: string;
  status: string;
  current_price: number;
  currency: string;
  price_per_sqm: number | null;
  size_sqm: number;
  rooms: number;
  property_type: string;
  energy_class: string | null;
  area_id: string;
  area_name: string;
  lat: number;
  lon: number;
  published_at: string;
  days_on_market: number;
  photos_count: number;
  is_demo_data: boolean;
}

export interface ListingVersion {
  version_number: number;
  captured_at: string;
  price: number;
  status: string;
  diff: Record<string, { old: unknown; new: unknown }>;
}

export interface ListingDetail extends ListingSummary {
  description: string;
  address_text: string;
  bathrooms: number;
  floor: number | null;
  year_built: number | null;
  features: Record<string, boolean>;
  agency_name: string | null;
  source_code: string;
  source_name: string;
  dedup_confidence: number;
  first_seen_at: string;
  last_seen_at: string;
  price_history: { observed_at: string; price: number; currency: string }[];
  versions: ListingVersion[];
  comparables: {
    listing_id: string;
    title: string;
    price: number;
    currency: string;
    size_sqm: number;
    rooms: number;
    price_per_sqm: number;
    similarity: number;
  }[];
  estimate: {
    estimated_value: number;
    range_low: number;
    range_high: number;
    confidence: number;
    n_comparables: number;
    assumptions: string;
  } | null;
  deviation_from_area_pct: number | null;
}

export interface DataContext {
  sources: string[];
  period: string | null;
  observations: number | null;
  updated_at: string | null;
  quality: number | null;
  aggregation_level: string | null;
  methodology: string | null;
  limitations: string | null;
  is_demo_data: boolean;
}

export interface MarketSummary {
  area_id: string;
  area_name: string;
  area_level: string;
  available: boolean;
  period: string;
  avg_price: number;
  median_price: number;
  avg_price_sqm: number;
  median_price_sqm: number;
  active_listings: number;
  new_listings: number;
  removed_listings: number;
  avg_days_on_market: number;
  price_reduction_share: number;
  avg_discount_pct: number;
  rent_avg_sqm: number;
  gross_yield_pct: number;
  currency: string;
  changes_pct: Record<string, number | null>;
}

export interface MarketMetricPoint {
  period: string;
  avg_price: number;
  avg_price_sqm: number;
  median_price_sqm: number;
  active_listings: number;
  new_listings: number;
  removed_listings: number;
  avg_days_on_market: number;
  rent_avg_sqm: number;
  gross_yield_pct: number;
  sample_size: number;
  currency: string;
}

export interface ForecastItem {
  horizon_months: number;
  method: string;
  model_version: string;
  computed_at: string;
  scenarios: { negative: number; base: number; positive: number };
  confidence: number;
  drivers: { name: string; direction: string; evidence: string; detail: string }[];
  limitations: string;
}

export interface WatchlistItemOut {
  id: string;
  kind: string;
  listing_id: string | null;
  area_id: string | null;
  note: string;
  initial_price: number | null;
  notify: boolean;
  created_at: string;
}

export interface WatchlistOut {
  id: string;
  name: string;
  created_at: string;
  items: WatchlistItemOut[];
}

export interface NotificationOut {
  id: string;
  type: string;
  title: string;
  body: string;
  payload: { listing_id?: string };
  is_read: boolean;
  created_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export function formatPrice(value: number, currency = "EUR"): string {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "n/d";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}
