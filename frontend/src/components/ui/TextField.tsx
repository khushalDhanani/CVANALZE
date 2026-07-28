import { View, Text, TextInput } from "react-native";

export function TextField({
  label,
  error,
  helperText,
  ...inputProps
}: { label: string; error?: string; helperText?: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View className="gap-1">
      <Text className="text-xs font-sans-medium text-text-primary">{label}</Text>
      <TextInput
        className={`rounded-md border px-3 py-2.5 text-sm font-sans text-text-primary bg-surface ${
          error ? "border-danger" : "border-border"
        }`}
        placeholderTextColor="#9CA3AF"
        {...inputProps}
      />
      {error ? (
        <Text className="text-[11px] font-sans text-danger">{error}</Text>
      ) : helperText ? (
        <Text className="text-[11px] font-sans text-text-muted">{helperText}</Text>
      ) : null}
    </View>
  );
}
