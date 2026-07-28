import { View, Text } from "react-native";

export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View className="flex-1 items-center justify-center px-6 py-12 gap-1.5">
      <Text className="text-base font-sans-semibold text-text-primary text-center">{title}</Text>
      {subtitle && <Text className="text-xs font-sans text-text-muted text-center">{subtitle}</Text>}
    </View>
  );
}
