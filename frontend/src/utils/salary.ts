import { JobOpening } from '@/types/api';

/**
 * Format a numeric rupee value into either LPA or comma-separated Indian currency.
 */
export function formatRupees(val?: number | null): string | null {
  if (!val || val <= 0) return null;
  if (val <= 100) {
    return `₹${val} LPA`;
  }
  return `₹${val.toLocaleString('en-IN')}`;
}

/**
 * Shared salary formatter for JobOpening items across directory and detail screens.
 */
export function formatSalary(item?: Partial<JobOpening> | null): string {
  if (!item) return 'Not Specified';
  const min = item.min_ctc;
  const max = item.max_ctc;

  const formattedMin = min ? formatRupees(min) : null;
  const formattedMax = max ? formatRupees(max) : null;

  if (formattedMin && formattedMax) {
    return `${formattedMin} - ${formattedMax}`;
  }
  if (formattedMin) return `From ${formattedMin}`;
  if (formattedMax) return `Up to ${formattedMax}`;
  return 'Not Specified';
}

/**
 * Shared experience range formatter for JobOpening items.
 */
export function formatExperience(item?: Partial<JobOpening> | null): string {
  if (!item) return 'Any Experience';
  const min = item.min_experience_years;
  const max = item.max_experience_years;

  if (min != null && max != null && (min > 0 || max > 0)) {
    if (min === max) return `${min} Yrs Exp`;
    return `${min} - ${max} Yrs Exp`;
  }
  if (min != null && min > 0) return `${min}+ Yrs Exp`;
  if (max != null && max > 0) return `Up to ${max} Yrs Exp`;
  return 'Any Experience';
}
