/**
 * Format an ISO date string according to device/environment locale conventions.
 * Gracefully returns "Date unavailable" if the date is missing or invalid.
 */
export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return 'Date unavailable';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return 'Date unavailable';
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return 'Date unavailable';
  }
}
