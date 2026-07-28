import React from 'react';
import { Text, View } from 'react-native';
import { ComponentBreakdown } from '@/types/api';

interface ComponentScoreBarProps {
  scores: ComponentBreakdown;
}

const componentLabels: Record<keyof ComponentBreakdown, string> = {
  role: 'Role & Title Match',
  skills: 'Skills Coverage',
  experience: 'Experience Level',
  education: 'Education',
  domain: 'Industry Domain',
  technology: 'Tech Stack',
  certification: 'Certifications',
  responsibilities: 'Responsibilities',
};

export function ComponentScoreBar({ scores }: ComponentScoreBarProps) {
  return (
    <View className="gap-1.5 my-2">
      {Object.entries(scores || {}).map(([key, val]) => {
        const valNum = Math.min(100, Math.max(0, val || 0));
        const label = componentLabels[key as keyof ComponentBreakdown] || key;

        let barColor = 'bg-danger';
        if (valNum >= 70) barColor = 'bg-success';
        else if (valNum >= 40) barColor = 'bg-warning';

        return (
          <View key={key} className="gap-1">
            <View className="flex-row justify-between items-center">
              <Text className="text-xs font-sans-medium text-text-primary">
                {label}
              </Text>
              <Text className="text-xs font-sans-bold text-text-muted">
                {Math.round(valNum)}%
              </Text>
            </View>
            <View className="h-1.5 w-full bg-border rounded-full overflow-hidden">
              <View
                className={`h-full rounded-full ${barColor}`}
                style={{ width: `${valNum}%` }}
              />
            </View>
          </View>
        );
      })}
    </View>
  );
}
