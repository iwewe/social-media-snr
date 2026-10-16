export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Terjadi kesalahan tak terduga.";
}
