import React from 'react';
import { Badge } from './Badge';

interface ScoreBadgeProps {
  score: number; // 0 to 100
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  size?: 'sm' | 'md' | 'lg';
}

export function ScoreBadge({
  score,
  classification,
  size = 'md',
}: ScoreBadgeProps) {
  const roundedScore = Math.round(score * 10) / 10;

  let tone: 'success' | 'warning' | 'danger' = 'danger';
  let badgeLabel = classification || (score >= 70 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW');

  if (score >= 70 || classification === 'HIGH') {
    tone = 'success';
    badgeLabel = 'HIGH MATCH';
  } else if (score >= 40 || classification === 'MEDIUM') {
    tone = 'warning';
    badgeLabel = 'MEDIUM';
  } else {
    tone = 'danger';
    badgeLabel = 'LOW MATCH';
  }

  return <Badge label={`${roundedScore}% • ${badgeLabel}`} tone={tone} />;
}
