import React from "react";
import { Pressable, Text, ActivityIndicator, View } from "react-native";
import { COLORS } from "@/constants/colors";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-primary active:bg-primary-dark",
  secondary: "bg-surface border border-border active:bg-background",
  ghost: "bg-transparent active:bg-background",
  destructive: "bg-danger active:opacity-90",
  outline: "bg-transparent border border-primary active:bg-primary/10",
};

const TEXT_CLASSES: Record<ButtonVariant, string> = {
  primary: "text-text-inverse",
  secondary: "text-text-primary",
  ghost: "text-primary",
  destructive: "text-text-inverse",
  outline: "text-primary",
};

const SPINNER_COLORS: Record<ButtonVariant, string> = {
  primary: COLORS.textInverse,
  secondary: COLORS.primary,
  ghost: COLORS.textMuted,
  destructive: COLORS.textInverse,
  outline: COLORS.primary,
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 min-h-[36px]",
  md: "px-3.5 py-2 min-h-[40px]",
  lg: "px-4 py-2.5 min-h-[44px]",
};

export interface ButtonProps {
  label?: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  accessibilityLabel?: string;
  testID?: string;
  className?: string;
}

export function Button({
  label,
  onPress,
  variant = "primary",
  size = "sm",
  loading = false,
  disabled = false,
  icon,
  accessibilityLabel,
  testID,
  className = "",
}: ButtonProps) {
  const isActionDisabled = disabled || loading;
  const effectiveA11yLabel = accessibilityLabel || label || (icon ? "Action button" : "Button");

  return (
    <Pressable
      onPress={onPress}
      disabled={isActionDisabled}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={effectiveA11yLabel}
      accessibilityState={{ disabled: isActionDisabled, busy: loading }}
      testID={testID}
      className={`rounded-md items-center justify-center flex-row gap-1.5 ${VARIANT_CLASSES[variant]} ${
        !label && icon ? "p-2 min-w-[36px] min-h-[36px]" : SIZE_CLASSES[size]
      } ${isActionDisabled ? "opacity-50" : ""} ${className}`}
    >
      {loading ? (
        <View className="flex-row items-center gap-1.5">
          <ActivityIndicator size="small" color={SPINNER_COLORS[variant]} />
          {!!label && (
            <Text className={`font-sans-semibold text-xs ${TEXT_CLASSES[variant]}`}>
              {label}
            </Text>
          )}
        </View>
      ) : (
        <>
          {icon}
          {!!label && (
            <Text className={`font-sans-semibold text-xs ${TEXT_CLASSES[variant]}`}>
              {label}
            </Text>
          )}
        </>
      )}
    </Pressable>
  );
}
