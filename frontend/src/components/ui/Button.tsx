import { Pressable, Text, ActivityIndicator } from "react-native";

type Variant = "primary" | "secondary" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-primary active:bg-primary-dark",
  secondary: "bg-surface border border-border active:bg-background",
  ghost: "bg-transparent active:bg-background",
  destructive: "bg-danger active:opacity-90",
};

const TEXT_CLASSES: Record<Variant, string> = {
  primary: "text-text-inverse",
  secondary: "text-text-primary",
  ghost: "text-primary",
  destructive: "text-text-inverse",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-2",
  md: "px-3.5 py-2.5",
  lg: "px-4 py-3",
};

export function Button({
  label,
  onPress,
  variant = "primary",
  size = "sm",
  loading = false,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      accessibilityRole="button"
      accessibilityLabel={label}
      className={`rounded-md items-center justify-center flex-row gap-1.5 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${
        disabled ? "opacity-50" : ""
      }`}
    >
      {loading && <ActivityIndicator size="small" />}
      <Text className={`font-sans-semibold text-sm ${TEXT_CLASSES[variant]}`}>
        {label}
      </Text>
    </Pressable>
  );
}
