import React from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { Card } from "./Card";
import { COLORS } from "@/constants/colors";

export type StatCardTone = "neutral" | "success" | "warning" | "danger" | "info";

export interface StatCardProps {
  label: string;
  value: React.ReactNode;
  sublabel?: string;
  tone?: StatCardTone;
  loading?: boolean;
  className?: string;
  testID?: string;
}

const TONE_CONTAINERS: Record<StatCardTone, string> = {
  neutral: "",
  success: "bg-success/5 border-success/30",
  warning: "bg-warning/5 border-warning/30",
  danger: "bg-danger/5 border-danger/30",
  info: "bg-info/5 border-info/30",
};

const TONE_TEXT: Record<StatCardTone, string> = {
  neutral: "text-text-primary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

export function StatCard({
  label,
  value,
  sublabel,
  tone = "neutral",
  loading = false,
  className = "",
  testID,
}: StatCardProps) {
  return (
    <Card testID={testID} className={`flex-1 min-w-[140px] md:min-w-[180px] p-3.5 gap-1 ${TONE_CONTAINERS[tone]} ${className}`}>
      <Text className="text-xs font-sans-medium text-text-muted mb-0.5" numberOfLines={1}>
        {label}
      </Text>
      {loading ? (
        <View className="py-2 self-start">
          <ActivityIndicator size="small" color={COLORS.primary} />
        </View>
      ) : typeof value === "string" || typeof value === "number" ? (
        <Text
          numberOfLines={1}
          className={`text-xl sm:text-2xl font-sans-bold leading-7 ${TONE_TEXT[tone]}`}
        >
          {value}
        </Text>
      ) : (
        value
      )}
      {sublabel ? (
        <Text numberOfLines={1} className="text-[11px] font-sans text-text-faint mt-0.5">
          {sublabel}
        </Text>
      ) : null}
    </Card>
  );
}
