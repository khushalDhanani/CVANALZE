import React from 'react';
import { View, Text } from 'react-native';
import { Info, AlertTriangle, AlertCircle, CheckCircle2, Lightbulb } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';

export type CalloutTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral';

export interface CalloutProps {
  title?: string;
  message?: string;
  tone?: CalloutTone;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  testID?: string;
}

const TONE_CLASSES: Record<CalloutTone, { bg: string; border: string; text: string; iconColor: string }> = {
  info: {
    bg: 'bg-info/10',
    border: 'border-info/30',
    text: 'text-info',
    iconColor: COLORS.info,
  },
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
  neutral: {
    bg: 'bg-background',
    border: 'border-border',
    text: 'text-text-primary',
    iconColor: COLORS.textMuted,
  },
};

const DEFAULT_ICONS: Record<CalloutTone, (color: string) => React.ReactNode> = {
  info: (color) => <Info size={14} color={color} />,
  success: (color) => <CheckCircle2 size={14} color={color} />,
  warning: (color) => <AlertTriangle size={14} color={color} />,
  danger: (color) => <AlertCircle size={14} color={color} />,
  neutral: (color) => <Lightbulb size={14} color={color} />,
};

export function Callout({
  title,
  message,
  tone = 'info',
  icon,
  children,
  className = '',
  testID,
}: CalloutProps) {
  const styles = TONE_CLASSES[tone];
  const renderedIcon = icon !== undefined ? icon : DEFAULT_ICONS[tone](styles.iconColor);

  return (
    <View
      testID={testID}
      className={`rounded-md p-3 border ${styles.bg} ${styles.border} gap-1.5 ${className}`}
    >
      <View className="flex-row items-center gap-2">
        {renderedIcon}
        {title ? (
          <Text className={`text-xs font-sans-bold ${styles.text}`}>
            {title}
          </Text>
        ) : null}
      </View>
      {message ? (
        <Text className="text-xs font-sans text-text-primary leading-4">
          {message}
        </Text>
      ) : null}
      {children}
    </View>
  );
}
