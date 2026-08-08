import React from 'react';
import { Pressable, View, ActivityIndicator } from 'react-native';
import { COLORS } from '@/constants/colors';

export type IconButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive' | 'outline';
export type IconButtonSize = 'sm' | 'md' | 'lg';

const VARIANT_CONTAINERS: Record<IconButtonVariant, string> = {
  primary: 'bg-primary active:bg-primary-dark',
  secondary: 'bg-surface border border-border active:bg-background',
  ghost: 'bg-transparent active:bg-background',
  destructive: 'bg-danger/10 border border-danger/30 active:bg-danger/20',
  outline: 'bg-transparent border border-primary active:bg-primary/10',
};

const SIZE_CONTAINERS: Record<IconButtonSize, { size: string; iconSize: number }> = {
  sm: { size: 'w-8 h-8 min-w-[32px] min-h-[32px]', iconSize: 14 },
  md: { size: 'w-10 h-10 min-w-[40px] min-h-[40px]', iconSize: 18 },
  lg: { size: 'w-12 h-12 min-w-[44px] min-h-[44px]', iconSize: 22 },
};

export interface IconButtonProps {
  icon: React.ReactNode | ((props: { size: number; color?: string }) => React.ReactNode);
  onPress: () => void;
  accessibilityLabel: string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  testID?: string;
}

export function IconButton({
  icon,
  onPress,
  accessibilityLabel,
  variant = 'ghost',
  size = 'md',
  disabled = false,
  loading = false,
  className = '',
  testID,
}: IconButtonProps) {
  const isActionDisabled = disabled || loading;
  const config = SIZE_CONTAINERS[size];

  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={isActionDisabled}
      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: isActionDisabled, busy: loading }}
      className={`rounded-md items-center justify-center ${VARIANT_CONTAINERS[variant]} ${config.size} ${
        isActionDisabled ? 'opacity-50' : ''
      } ${className}`}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={variant === 'primary' ? COLORS.textInverse : COLORS.primary}
        />
      ) : typeof icon === 'function' ? (
        icon({ size: config.iconSize })
      ) : (
        icon
      )}
    </Pressable>
  );
}
