import React from 'react';
import { View, Text } from 'react-native';
import { CheckCircle, AlertTriangle, AlertCircle, Info, RefreshCw } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { Button } from './Button';

export type StatusBannerTone = 'success' | 'warning' | 'danger' | 'info';

export interface StatusBannerProps {
  title?: string;
  message?: string;
  tone?: StatusBannerTone;
  onRetry?: () => void;
  action?: React.ReactNode;
  className?: string;
  testID?: string;
}

const TONE_CONFIGS: Record<StatusBannerTone, { bg: string; border: string; text: string; iconColor: string }> = {
  success: {
    bg: 'bg-success/10',
    border: 'border-success/30',
    text: 'text-success',
    iconColor: COLORS.success,
  },
  warning: {
    bg: 'bg-warning/10',
    border: 'border-warning/30',
    text: 'text-warning',
    iconColor: COLORS.warning,
  },
  danger: {
    bg: 'bg-danger/10',
    border: 'border-danger/30',
    text: 'text-danger',
    iconColor: COLORS.danger,
  },
  info: {
    bg: 'bg-info/10',
    border: 'border-info/30',
    text: 'text-info',
    iconColor: COLORS.info,
  },
};

export function StatusBanner({
  title,
  message,
  tone = 'info',
  onRetry,
  action,
  className = '',
  testID,
}: StatusBannerProps) {
  const config = TONE_CONFIGS[tone];

  const renderIcon = () => {
    switch (tone) {
      case 'success':
        return <CheckCircle size={16} color={config.iconColor} />;
      case 'warning':
        return <AlertTriangle size={16} color={config.iconColor} />;
      case 'danger':
        return <AlertCircle size={16} color={config.iconColor} />;
      default:
        return <Info size={16} color={config.iconColor} />;
    }
  };

  return (
    <View
      testID={testID}
      className={`rounded-md p-3 border flex-row items-start gap-2.5 ${config.bg} ${config.border} ${className}`}
    >
      <View className="mt-0.5">{renderIcon()}</View>
      <View className="flex-1 gap-1">
        {title ? (
          <Text className={`text-xs font-sans-bold ${config.text}`}>
            {title}
          </Text>
        ) : null}
        {message ? (
          <Text className={`text-[11px] font-sans ${config.text} opacity-90 leading-4`}>
            {message}
          </Text>
        ) : null}
        {(onRetry || action) && (
          <View className="flex-row items-center gap-2 mt-1.5">
            {onRetry && (
              <Button
                label="Retry"
                variant="ghost"
                size="sm"
                icon={<RefreshCw size={12} color={config.iconColor} />}
                onPress={onRetry}
                className="self-start py-1 px-2 border border-border bg-surface"
              />
            )}
            {action}
          </View>
        )}
      </View>
    </View>
  );
}
