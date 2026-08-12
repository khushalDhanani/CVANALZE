import React, { useState } from "react";
import { View, Text, TextInput, TextInputProps } from "react-native";
import { COLORS } from "@/constants/colors";

export interface TextFieldProps extends TextInputProps {
  label?: string;
  error?: string;
  helperText?: string;
  containerClassName?: string;
}

export function TextField({
  label,
  error,
  helperText,
  containerClassName = "",
  placeholder,
  accessibilityLabel,
  onFocus,
  onBlur,
  className = "",
  ...inputProps
}: TextFieldProps) {
  const [isFocused, setIsFocused] = useState(false);
  const hasVisibleLabel = Boolean(label && label.trim().length > 0);
  const effectiveA11yLabel = accessibilityLabel || label || placeholder || "Text input";

  return (
    <View className={`gap-1 ${containerClassName}`}>
      {hasVisibleLabel && (
        <Text className="text-xs font-sans-medium text-text-primary">{label}</Text>
      )}
      <TextInput
        accessibilityLabel={effectiveA11yLabel}
        accessibilityHint={error ? `Input error: ${error}` : undefined}
        aria-invalid={Boolean(error)}
        placeholder={placeholder}
        placeholderTextColor={COLORS.textFaint}
        onFocus={(e) => {
          setIsFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setIsFocused(false);
          onBlur?.(e);
        }}
        className={`rounded-md border px-3 py-2 text-sm font-sans text-text-primary bg-surface min-h-[38px] ${
          error
            ? "border-danger ring-1 ring-danger/30"
            : isFocused
            ? "border-primary ring-1 ring-primary/30"
            : "border-border"
        } ${className}`}
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
