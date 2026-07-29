import { View, Text, ActivityIndicator } from "react-native";
import { Card } from "./Card";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

export function StatCard({
  label,
  value,
  sublabel,
  tone = "neutral",
  loading = false,
}: {
  label: string;
  value: React.ReactNode;
  sublabel?: string;
  tone?: Tone;
  loading?: boolean;
}) {
  const toneBg = {
    neutral: "",
    success: "bg-success/10 border-success/30",
    warning: "bg-warning/10 border-warning/30",
    danger: "bg-danger/10 border-danger/30",
    info: "bg-info/10 border-info/30",
  }[tone];

  const toneText = {
    neutral: "text-text-primary",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    info: "text-info",
  }[tone];

  return (
    <Card className={`flex-1 p-3 ${toneBg}`}>
      <Text className="text-xs font-sans-medium text-text-muted mb-1">
        {label}
      </Text>
      {loading ? (
        <ActivityIndicator size="small" className="mt-1 self-start" />
      ) : typeof value === "string" || typeof value === "number" ? (
        <Text
          numberOfLines={2}
          ellipsizeMode="tail"
          className={`text-2xl font-sans-bold ${toneText}`}
        >
          {value}
        </Text>
      ) : (
        value
      )}
      {sublabel ? (
        <Text className="text-[11px] text-text-faint mt-1 truncate">
          {sublabel}
        </Text>
      ) : null}
    </Card>
  );
}
