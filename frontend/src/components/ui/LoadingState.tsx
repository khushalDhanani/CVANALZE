import React from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { COLORS } from '@/constants/colors';

export type LoadingStateVariant = 'page' | 'inline' | 'card';

export interface LoadingStateProps {
  message?: string;
  variant?: LoadingStateVariant;
  size?: 'small' | 'large';
  className?: string;
  testID?: string;
}

const VARIANT_CONTAINERS: Record<LoadingStateVariant, string> = {
  page: 'flex-1 items-center justify-center p-8 gap-3',
  inline: 'items-center justify-center py-4 px-3 gap-2',
  card: 'items-center justify-center py-8 px-4 gap-2 bg-surface/50 border border-border/50 rounded-md',
};

export function LoadingState({
  message = 'Loading...',
  variant = 'page',
  size = 'large',
  className = '',
  testID,
}: LoadingStateProps) {
  const isSmall = size === 'small' || variant === 'inline';

  return (
    <View testID={testID} className={`${VARIANT_CONTAINERS[variant]} ${className}`}>
      <ActivityIndicator size={isSmall ? 'small' : 'large'} color={COLORS.primary} />
      {!!message && (
        <Text className="text-xs font-sans-medium text-text-muted text-center">{message}</Text>
      )}
    </View>
  );
}
