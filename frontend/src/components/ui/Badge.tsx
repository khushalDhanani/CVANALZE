import React from "react";
import { View, Text } from "react-native";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";
export type BadgeColorScheme = "default" | "category" | "taxonomy" | "tag" | "purple" | "blue" | "teal" | "indigo";
export type Tone = BadgeTone; // backward compatibility

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-background text-text-muted border border-border/60",
  success: "bg-success/10 text-success border border-success/20",
  warning: "bg-warning/10 text-warning border border-warning/20",
  danger: "bg-danger/10 text-danger border border-danger/20",
  info: "bg-info/10 text-info border border-info/20",
};

const SCHEME_CLASSES: Record<BadgeColorScheme, string> = {
  default: "",
  category: "bg-primary/10 text-primary border border-primary/20",
  taxonomy: "bg-info/10 text-info border border-info/20",
  tag: "bg-surface border border-border text-text-primary",
  purple: "bg-category-purple/10 text-category-purple border border-category-purple/20",
  blue: "bg-category-blue/10 text-category-blue border border-category-blue/20",
  teal: "bg-category-teal/10 text-category-teal border border-category-teal/20",
  indigo: "bg-category-indigo/10 text-category-indigo border border-category-indigo/20",
};

export interface BadgeProps {
  label: string;
  tone?: BadgeTone;
  colorScheme?: BadgeColorScheme;
  icon?: React.ReactNode;
  className?: string;
}

export function Badge({
  label,
  tone = "neutral",
  colorScheme = "default",
  icon,
  className = "",
}: BadgeProps) {
  const activeStyle = colorScheme !== "default" ? SCHEME_CLASSES[colorScheme] : TONE_CLASSES[tone];
  const parts = activeStyle.split(" ");
  const textClasses = parts.filter(c => c.startsWith("text-")).join(" ");
  const containerClasses = parts.filter(c => !c.startsWith("text-")).join(" ");

  return (
    <View className={`flex-row items-center rounded-full px-2 py-0.5 gap-1 ${containerClasses} ${className}`}>
      {icon}
      <Text className={`text-[11px] font-sans-semibold ${textClasses}`}>{label}</Text>
    </View>
  );
}
