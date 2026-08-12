import React from 'react';
import { View, Text } from 'react-native';
import { AlertCircle, RefreshCw } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { Button } from './Button';

export interface ErrorBannerProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
  action?: React.ReactNode;
  className?: string;
  testID?: string;
}

export function ErrorBanner({ 
  title = 'An error occurred', 
  message,
  onRetry,
  retryLabel = 'Retry',
  action,
  className = '',
  testID,
}: ErrorBannerProps) {
  return (
    <View
      testID={testID}
      className={`bg-danger/10 border border-danger/30 rounded-md p-3 flex-row items-start gap-2.5 ${className}`}
    >
      <View className="mt-0.5">
        <AlertCircle size={16} color={COLORS.danger} />
      </View>
      <View className="flex-1 gap-1">
        <Text className="text-xs font-sans-bold text-danger">{title}</Text>
        {message ? (
          <Text className="text-[11px] font-sans text-danger leading-4 opacity-90">{message}</Text>
        ) : null}
        {(onRetry || action) && (
          <View className="flex-row items-center gap-2 mt-1.5">
            {onRetry && (
              <Button
                label={retryLabel}
                variant="ghost"
                size="sm"
                icon={<RefreshCw size={12} color={COLORS.danger} />}
                onPress={onRetry}
                className="self-start py-1 px-2 border border-danger/30 bg-danger/5"
              />
            )}
            {action}
          </View>
        )}
      </View>
    </View>
  );
}
