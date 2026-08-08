import React from 'react';
import { Badge } from './Badge';
import { getCanonicalMatchStatusMeta } from './VacancyMatchStatusBadge';

interface ScoreBadgeProps {
  score: number; // 0 to 100
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  size?: 'sm' | 'md' | 'lg';
  showScore?: boolean;
}

export function ScoreBadge({
  score,
  classification,
  size = 'md',
  showScore = true,
}: ScoreBadgeProps) {
  const meta = getCanonicalMatchStatusMeta(classification, score);
  const roundedScore = Math.round(score * 10) / 10;

  const label = showScore
    ? `${roundedScore}% • ${meta.label}`
    : meta.label;

  return <Badge label={label} tone={meta.tone} />;
}

