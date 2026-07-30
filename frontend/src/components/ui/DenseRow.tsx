import { Pressable, View, Text } from "react-native";
import { ChevronRight } from "lucide-react-native";
import { COLORS } from '@/constants/colors';

export function DenseRow({
  title,
  subtitle,
  trailing,
  onPress,
  className = "",
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  trailing?: React.ReactNode;
  onPress?: () => void;
  className?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      className={`flex-row items-center justify-between px-3 py-2 bg-surface rounded-md border border-border active:bg-background ${className}`}
    >
      <View className="flex-1 gap-0.5 pr-2">
        {typeof title === 'string' ? (
          <Text numberOfLines={1} className="text-sm font-sans-medium text-text-primary">
            {title}
          </Text>
        ) : (
          title
        )}
        {subtitle ? (
          typeof subtitle === 'string' ? (
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">
              {subtitle}
            </Text>
          ) : (
            subtitle
          )
        ) : null}
      </View>
      <View className="flex-row items-center gap-1.5">
        {trailing}
        {onPress && <ChevronRight size={16} color={COLORS.textFaint} />}
      </View>
    </Pressable>
  );
}
