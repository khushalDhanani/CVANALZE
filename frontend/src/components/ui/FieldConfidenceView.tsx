import React from 'react';
import { View, Text } from 'react-native';
import { Badge } from './Badge';

export interface FieldConfidenceViewProps {
  fieldName: 'name' | 'location' | 'job_title' | 'company_name' | string;
  value?: string | null;
  tier?: string | null;
  icon?: React.ReactNode;
  fallbackLabel?: string;
  className?: string;
  textClassName?: string;
  numberOfLines?: number;
}

export function FieldConfidenceView({
  fieldName,
  value,
  tier,
  icon,
  fallbackLabel,
  className = '',
  textClassName = '',
  numberOfLines = 1,
}: FieldConfidenceViewProps) {
  const isPresent = Boolean(
    value &&
    value.trim().length > 0 &&
    value.trim().toLowerCase() !== 'unknown candidate' &&
    value.trim().toLowerCase() !== 'unknown'
  );

  const formattedName = fieldName
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const displayText = isPresent ? value!.trim() : (fallbackLabel || `${formattedName} not detected`);

  const normalizedTier = (tier || '').toUpperCase();
  const isUnverified = isPresent && (normalizedTier === 'LOW' || normalizedTier === 'MEDIUM');

  return (
    <View className={`flex-row items-center gap-1.5 flex-wrap ${className}`}>
      {icon}
      {isPresent ? (
        <Text numberOfLines={numberOfLines} className={`text-sm font-sans-medium text-text-primary ${textClassName}`}>
          {displayText}
        </Text>
      ) : (
        <Text numberOfLines={numberOfLines} className={`text-sm font-sans-medium text-text-faint italic ${textClassName}`}>
          {displayText}
        </Text>
      )}
      {isUnverified && (
        <Badge label="Unverified" tone="warning" />
      )}
    </View>
  );
}
