import React from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { COLORS } from '@/constants/colors';

export function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <View className="flex-1 items-center justify-center p-6 gap-3 min-h-[200px]">
      <ActivityIndicator size="large" color={COLORS.primary} />
      <Text className="text-sm font-sans-medium text-text-muted">{message}</Text>
    </View>
  );
}
