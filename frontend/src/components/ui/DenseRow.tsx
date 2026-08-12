import React from "react";
import { Pressable, View, Text } from "react-native";
import { ChevronRight } from "lucide-react-native";
import { COLORS } from "@/constants/colors";

export interface DenseRowProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  subtitleLines?: number;
  trailing?: React.ReactNode;
  onPress?: () => void;
  accessibilityLabel?: string;
  className?: string;
  testID?: string;
}

export function DenseRow({
  title,
  subtitle,
  subtitleLines,
  trailing,
  onPress,
  accessibilityLabel,
  className = "",
  testID,
}: DenseRowProps) {
  const content = (
    <>
      <View className="flex-1 gap-0.5 pr-2">
        {typeof title === "string" ? (
          <Text numberOfLines={1} className="text-sm font-sans-medium text-text-primary">
            {title}
          </Text>
        ) : (
          title
        )}
        {subtitle ? (
          typeof subtitle === "string" ? (
            <Text
              numberOfLines={subtitleLines ?? (subtitleLines === 0 ? undefined : 2)}
              className="text-xs font-sans text-text-muted leading-4"
            >
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
    </>
  );

  const containerClasses = `flex-row items-center justify-between px-3 py-2 bg-surface rounded-md border border-border min-h-[44px] min-w-[280px] ${className}`;

  if (onPress) {
    return (
      <Pressable
        testID={testID}
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel || (typeof title === "string" ? title : "Row action")}
        hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        className={`${containerClasses} active:bg-background`}
      >
        {content}
      </Pressable>
    );
  }

  return (
    <View testID={testID} className={containerClasses}>
      {content}
    </View>
  );
}
