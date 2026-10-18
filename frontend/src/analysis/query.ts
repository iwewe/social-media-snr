/** Susun query string dengan kunci terurut; nilai kosong/undefined dibuang (agar stabil dan dapat diuji). */
export function queryString(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const parts = Object.keys(params)
    .sort()
    .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== "")
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(String(params[k]))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}
