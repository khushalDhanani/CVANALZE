import React from 'react';
import { View, Text } from 'react-native';
import { Badge } from './Badge';
import { getCanonicalMatchStatusMeta } from './VacancyMatchStatusBadge';
import { getMatchBand } from '@/utils/scoreBand';

export type ScoreBadgeSize = 'sm' | 'md' | 'lg';

export interface ScoreBadgeProps {
  score: number; // 0 to 100
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  size?: ScoreBadgeSize;
  showScore?: boolean;
  className?: string;
}

const SIZE_CLASSES: Record<ScoreBadgeSize, { badge: string; text: string }> = {
  sm: { badge: 'px-1.5 py-0.2', text: 'text-[10px]' },
  md: { badge: 'px-2 py-0.5', text: 'text-[11px]' },
  lg: { badge: 'px-2.5 py-1', text: 'text-xs' },
};

export function ScoreBadge({
  score,
  classification,
  size = 'md',
  showScore = true,
  className = '',
}: ScoreBadgeProps) {
  // If explicit classification is provided, use canonical status meta; otherwise derive from score band
  const band = getMatchBand(score);
  const effectiveClassification = classification || band.classification;
  const meta = getCanonicalMatchStatusMeta(effectiveClassification, score);
  const roundedScore = Math.round(score * 10) / 10;

  const label = showScore
    ? `${roundedScore}% • ${meta.label}`
    : meta.label;

  return (
    <Badge
      label={label}
      tone={meta.tone}
      className={`${SIZE_CLASSES[size].badge} ${className}`}
    />
  );
}
