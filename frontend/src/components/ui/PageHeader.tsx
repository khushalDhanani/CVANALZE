import React from 'react';
import { View, Text, useWindowDimensions } from 'react-native';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  leading?: React.ReactNode;
  metadata?: React.ReactNode;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  testID?: string;
}

export function PageHeader({
  title,
  subtitle,
  leading,
  metadata,
  badge,
  actions,
  className = '',
  testID,
}: PageHeaderProps) {
  const { width } = useWindowDimensions();
  const isCompact = width < 640;

  return (
    <View
      testID={testID}
      className={`px-3 py-2.5 bg-surface border-b border-border ${
        isCompact ? 'gap-2' : 'flex-row justify-between items-center gap-3'
      } ${className}`}
    >
      <View className="flex-row items-center flex-1 min-w-[200px] gap-2">
        {leading}
        <View className="flex-1 gap-0.5">
          <View className="flex-row items-center gap-2 flex-wrap">
            <Text className="text-lg sm:text-xl font-sans-bold text-text-primary">
              {title}
            </Text>
            {badge}
          </View>
          {subtitle ? (
            <Text className="text-[11px] font-sans text-text-muted leading-4" numberOfLines={2}>
              {subtitle}
            </Text>
          ) : null}
          {metadata}
        </View>
      </View>

      {actions ? (
        <View className={`flex-row items-center gap-2 flex-wrap ${isCompact ? 'self-stretch justify-end' : ''}`}>
          {actions}
        </View>
      ) : null}
    </View>
  );
}
