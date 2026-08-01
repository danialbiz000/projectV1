/** Client-side "compare list" for listings — a small persisted selection
 * (max 4, mirrors the backend's ListingCompareRequest bound) that survives
 * navigation between /listings, a listing detail page and /compare. */

const KEY = "remip_compare_listings";
export const MAX_COMPARE = 4;

function read(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function write(ids: string[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(ids));
  window.dispatchEvent(new Event("remip-compare-change"));
}

export function getCompareIds(): string[] {
  return read();
}

export function isInCompare(id: string): boolean {
  return read().includes(id);
}

export function toggleCompare(id: string): string[] {
  const current = read();
  const next = current.includes(id)
    ? current.filter((x) => x !== id)
    : current.length < MAX_COMPARE
      ? [...current, id]
      : current;
  write(next);
  return next;
}

export function removeFromCompare(id: string): string[] {
  const next = read().filter((x) => x !== id);
  write(next);
  return next;
}

export function clearCompare() {
  write([]);
}
