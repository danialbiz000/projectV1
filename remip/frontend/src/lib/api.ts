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
  email_verified: boolean;
  onboarding_completed: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface MessageResponse {
  detail: string;
  // Only set when the backend runs with demo_mode=true — see
  // schemas/auth.py::MessageResponse. Never populated in production.
  dev_token?: string | null;
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
  duplicate_listings: {
    listing_id: string;
    agency_name: string | null;
    price: number;
    currency: string;
    status: string;
    dedup_confidence: number;
  }[];
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

export interface MapPoint {
  id: string;
  lat: number;
  lon: number;
  price: number;
  currency: string;
  price_per_sqm: number | null;
  listing_type: string;
  property_type: string;
  size_sqm: number;
  rooms: number;
}

export interface MapSearchRequest {
  area_id?: string;
  listing_type?: string;
  status?: string;
  property_type?: string;
  min_price?: number;
  max_price?: number;
  bbox?: { min_lon: number; min_lat: number; max_lon: number; max_lat: number };
  radius?: { lat: number; lon: number; radius_km: number };
  polygon?: number[][];
  limit?: number;
}

export interface MapSearchResponse {
  items: MapPoint[];
  total_matched: number;
  truncated: boolean;
  data_context: DataContext;
}

export interface NotificationDigest {
  unread_total: number;
  by_type: { type: string; label: string; count: number }[];
  by_listing: { listing_id: string; count: number; latest_title: string }[];
  generated_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface EstimateOut {
  estimated_value: number;
  range_low: number;
  range_high: number;
  confidence: number;
  n_comparables: number;
  assumptions: string;
}

export interface ValuationOut {
  id: string;
  listing_id: string;
  computed_at: string;
  estimated_value: number;
  range_low: number;
  range_high: number;
  currency: string;
  method: string;
  n_comparables: number;
  confidence: number;
  assumptions: string;
}

export interface TrendPoint {
  period: string;
  avg_price_sqm: number;
}

export interface MarketScore {
  score: number;
  label: string;
  observed_trend: string;
  evidence_strength: string;
  positive_drivers: ExplanationDriver[];
  negative_drivers: ExplanationDriver[];
  methodology: string;
  limitations: string;
}

export interface ListingCompareRow extends ListingSummary {
  deviation_from_area_pct: number | null;
  estimate: EstimateOut | null;
  market_score: MarketScore | null;
  price_trend: TrendPoint[];
}

export interface AreaCompareRow {
  area_id: string;
  area_name: string | null;
  area_level: string | null;
  available: boolean;
  listing_type: string | null;
  period: string | null;
  avg_price: number | null;
  median_price: number | null;
  avg_price_sqm: number | null;
  median_price_sqm: number | null;
  active_listings: number | null;
  new_listings: number | null;
  removed_listings: number | null;
  avg_days_on_market: number | null;
  price_reduction_share: number | null;
  avg_discount_pct: number | null;
  rent_avg_sqm: number | null;
  gross_yield_pct: number | null;
  currency: string | null;
  changes_pct: Record<string, number | null> | null;
  market_score: MarketScore | null;
  price_trend: TrendPoint[];
}

export interface NotificationPreferenceOut {
  frequency: string;
  muted_types: string[];
  updated_at: string | null;
}

export interface ExplanationDriver {
  name: string;
  direction: "positive" | "negative" | "neutral";
  strength: string;
  evidence: string;
  source: string;
}

export interface NationalContext {
  indicator: string;
  period: string;
  value: number;
  unit: string;
  source: string;
  is_demo_data: boolean;
  note: string;
}

export interface ExplanationResult {
  available: boolean;
  reason?: string;
  period_months?: number;
  observed_trend?: "in crescita" | "in calo" | "stabile";
  price_change_pct?: number | null;
  positive_drivers?: ExplanationDriver[];
  negative_drivers?: ExplanationDriver[];
  neutral_indicators?: ExplanationDriver[];
  evidence_strength?: string;
  sources?: string[];
  national_context?: NationalContext | null;
  market_score?: MarketScore | null;
  uncertain_elements?: string[];
  alternative_explanations?: string;
}

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  onboarding_completed: boolean;
  created_at: string;
}

export interface DataSource {
  code: string;
  name: string;
  kind: string;
  enabled: boolean;
  tos_compliant: boolean;
  is_demo: boolean;
  quality_score: number | null;
  last_ingested_at: string | null;
  notes: string | null;
}

export interface IngestionJob {
  id: string;
  provider_code: string;
  status: string;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  records_fetched: number | null;
  records_created: number | null;
  records_updated: number | null;
  error_message: string | null;
}

export interface AdminStats {
  users: number;
  areas: number;
  listings: number;
  listing_versions: number;
  notifications: number;
  listings_by_status: Record<string, number>;
}

export interface OAuthProvidersResponse {
  providers: string[];
}

export interface OAuthAuthorizeResponse {
  authorize_url: string;
  state: string;
}

export interface DataExport {
  exported_at: string;
  profile: Record<string, unknown>;
  watchlists: unknown[];
  notifications: unknown[];
  notification_preference: Record<string, unknown> | null;
  oauth_accounts: unknown[];
  audit_log: unknown[];
}

export interface FloorplanRoom {
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  area_sqm: number;
}

export interface Floorplan {
  width: number;
  height: number;
  rooms: FloorplanRoom[];
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
