import { Pressable, View, Text } from "react-native";
import { ChevronRight } from "lucide-react-native";

export function DenseRow({
  title,
  subtitle,
  trailing,
  onPress,
}: {
  title: string;
  subtitle?: string;
  trailing?: React.ReactNode;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      className="flex-row items-center justify-between px-3 py-2 bg-surface rounded-md border border-border active:bg-background"
    >
      <View className="flex-1 gap-0.5 pr-2">
        <Text numberOfLines={1} className="text-sm font-sans-medium text-text-primary">
          {title}
        </Text>
        {subtitle ? (
          <Text numberOfLines={1} className="text-xs font-sans text-text-muted">
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View className="flex-row items-center gap-1.5">
        {trailing}
        {onPress && <ChevronRight size={16} color="#9CA3AF" />}
      </View>
    </Pressable>
  );
}
