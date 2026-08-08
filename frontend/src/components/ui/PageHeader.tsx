import React from 'react';
import { View, Text, useWindowDimensions } from 'react-native';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  testID?: string;
}

export function PageHeader({
  title,
  subtitle,
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
      className={`border-b border-border/80 pb-3 mb-4 ${
        isCompact ? 'gap-2.5' : 'flex-row justify-between items-center'
      } ${className}`}
    >
      <View className="flex-1 min-w-[200px] gap-0.5">
        <View className="flex-row items-center gap-2 flex-wrap">
          <Text className="text-xl sm:text-2xl font-sans-bold text-text-primary">
            {title}
          </Text>
          {badge}
        </View>
        {subtitle ? (
          <Text className="text-xs font-sans text-text-muted leading-4">
            {subtitle}
          </Text>
        ) : null}
      </View>

      {actions ? (
        <View className={`flex-row items-center gap-2 flex-wrap ${isCompact ? 'self-start mt-1' : ''}`}>
          {actions}
        </View>
      ) : null}
    </View>
  );
}
