export function parsePositiveInteger(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function resolveApiBaseUrl(
  explicitUrl: string | undefined,
  platform: string,
  development: boolean,
): string {
  const normalized = explicitUrl?.trim().replace(/\/+$/, '');
  if (normalized) {
    let parsed: URL;
    try {
      parsed = new URL(normalized);
    } catch {
      throw new Error('EXPO_PUBLIC_API_URL must be an absolute HTTP or HTTPS URL.');
    }
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw new Error('EXPO_PUBLIC_API_URL must be an absolute HTTP or HTTPS URL.');
    }
    return normalized;
  }
  if (!development) {
    throw new Error('EXPO_PUBLIC_API_URL is required for production builds.');
  }
  return platform === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
}

export function nextPollingAttempt(attempt: number, maximum: number): number | null {
  return attempt >= maximum ? null : attempt + 1;
}
