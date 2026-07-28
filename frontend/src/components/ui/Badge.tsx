import { View, Text } from "react-native";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-background text-text-muted",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
  info: "bg-info/10 text-info",
};

export function Badge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const [bgClass, textClass] = TONE_CLASSES[tone].split(" ").reduce(
    (acc, cls) => (cls.startsWith("text-") ? [acc[0], cls] : [cls, acc[1]]),
    ["", ""]
  );
  return (
    <View className={`self-start rounded-full px-2 py-0.5 ${bgClass}`}>
      <Text className={`text-[11px] font-sans-semibold ${textClass}`}>{label}</Text>
    </View>
  );
}
