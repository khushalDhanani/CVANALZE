import React from 'react';
import { Text, View } from 'react-native';
import { ComponentBreakdown } from '@/types/api';
import { getMatchBand } from '@/utils/scoreBand';

export interface ComponentScoreBarProps {
  scores?: ComponentBreakdown | null;
  className?: string;
}

const ORDERED_COMPONENTS: Array<{ key: keyof ComponentBreakdown; label: string }> = [
  { key: 'role', label: 'Role & Title Match' },
  { key: 'skills', label: 'Skills Coverage' },
  { key: 'experience', label: 'Experience Level' },
  { key: 'responsibilities', label: 'Responsibilities' },
  { key: 'domain', label: 'Industry Domain' },
  { key: 'technology', label: 'Tech Stack' },
  { key: 'education', label: 'Education' },
  { key: 'certification', label: 'Certifications' },
];

export function ComponentScoreBar({ scores, className = '' }: ComponentScoreBarProps) {
  if (!scores) return null;

  return (
    <View className={`gap-2 my-2 ${className}`}>
      {ORDERED_COMPONENTS.map(({ key, label }) => {
        const val = scores[key];
        if (val === undefined || val === null) return null;

        const valNum = Math.min(100, Math.max(0, val));
        const band = getMatchBand(valNum);

        const barColorClass =
          band.tone === 'success'
            ? 'bg-success'
            : band.tone === 'warning'
            ? 'bg-warning'
            : 'bg-danger';

        return (
          <View key={key} className="gap-1">
            <View className="flex-row justify-between items-center">
              <Text className="text-xs font-sans-medium text-text-primary">
                {label}
              </Text>
              <Text className="text-[11px] font-sans-bold text-text-muted">
                {Math.round(valNum)}%
              </Text>
            </View>
            <View className="h-1.5 w-full bg-border rounded-full overflow-hidden">
              <View
                className={`h-full rounded-full ${barColorClass}`}
                style={{ width: `${valNum}%` }}
              />
            </View>
          </View>
        );
      })}
    </View>
  );
}
