import React from "react";
import { View, ViewStyle } from "react-native";

export type CardVariant = "flat" | "raised";

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  variant?: CardVariant;
  elevated?: boolean;
  style?: ViewStyle;
  testID?: string;
}

export function Card({
  children,
  className = "",
  variant = "flat",
  elevated,
  style,
  testID,
}: CardProps) {
  const isShadowNone = className.includes("shadow-none");
  const isElevated = elevated !== undefined ? elevated : (variant === "raised" && !isShadowNone);

  return (
    <View
      testID={testID}
      className={`bg-surface rounded-md p-3 border border-border ${isElevated ? "shadow-sm" : ""} ${className}`}
      style={[{ elevation: isElevated ? 1 : 0 }, style]}
    >
      {children}
    </View>
  );
}
