export type MatchBandTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

export interface MatchBandInfo {
  classification: 'HIGH' | 'MEDIUM' | 'LOW';
  label: string;
  tone: MatchBandTone;
  minScore: number;
}

export function getMatchBand(score: number | null | undefined, config?: { highThreshold?: number; mediumThreshold?: number }): MatchBandInfo {
  const highThreshold = config?.highThreshold ?? 70;
  const mediumThreshold = config?.mediumThreshold ?? 40;
  const numScore = typeof score === 'number' && !isNaN(score) ? score : 0;

  if (numScore >= highThreshold) {
    return {
      classification: 'HIGH',
      label: 'Strong Fit',
      tone: 'success',
      minScore: highThreshold,
    };
  }

  if (numScore >= mediumThreshold) {
    return {
      classification: 'MEDIUM',
      label: 'Potential Fit',
      tone: 'warning',
      minScore: mediumThreshold,
    };
  }

  return {
    classification: 'LOW',
    label: 'Weak Fit',
    tone: 'danger',
    minScore: 0,
  };
}

export function normalizeClassification(cls?: string | null): 'HIGH' | 'MEDIUM' | 'LOW' {
  if (!cls) return 'LOW';
  const upper = cls.toUpperCase();
  if (upper.includes('HIGH') || upper.includes('STRONG') || upper.includes('MATCHED')) return 'HIGH';
  if (upper.includes('MED') || upper.includes('POTENTIAL') || upper.includes('MODERATE')) return 'MEDIUM';
  return 'LOW';
}
