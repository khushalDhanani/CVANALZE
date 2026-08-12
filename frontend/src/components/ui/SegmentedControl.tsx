import React from 'react';
import { View, Pressable, Text, ScrollView } from 'react-native';
import { COLORS } from '@/constants/colors';

export interface SegmentedControlOption<T> {
  value: T;
  label: string;
  icon?: (props: { size: number; color: string }) => React.ReactNode;
  accessibilityLabel?: string;
  badge?: string | number;
}

export type SegmentedControlVariant = 'equal' | 'content' | 'scrollable';

export interface SegmentedControlProps<T> {
  options: SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
  variant?: SegmentedControlVariant;
  disabled?: boolean;
  className?: string;
}

export function SegmentedControl<T>({
  options,
  value,
  onChange,
  variant = 'equal',
  disabled,
  className = '',
}: SegmentedControlProps<T>) {
  const isScrollable = variant === 'scrollable';
  const isContent = variant === 'content';

  const renderOptions = () => (
    options.map((option) => {
      const isActive = value === option.value;
      const flexClass = isScrollable || isContent ? 'flex-shrink-0 px-3' : 'flex-1';

      return (
        <Pressable
          key={String(option.value)}
          onPress={() => !disabled && onChange(option.value)}
          disabled={disabled}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="tab"
          accessibilityState={{ selected: isActive, disabled: Boolean(disabled) }}
          accessibilityLabel={option.accessibilityLabel || option.label}
          className={`${flexClass} py-1.5 min-h-[36px] rounded items-center flex-row justify-center gap-1.5 ${
            isActive 
              ? 'bg-primary active:bg-primary-dark shadow-xs' 
              : 'bg-transparent active:bg-background'
          } ${disabled ? 'opacity-50' : ''}`}
        >
          {option.icon && option.icon({ size: 14, color: isActive ? COLORS.textInverse : COLORS.textFaint })}
          <Text
            numberOfLines={1}
            className={`text-xs font-sans-bold ${
              isActive ? 'text-text-inverse' : 'text-text-muted'
            }`}
          >
            {option.label}
          </Text>
          {option.badge !== undefined && (
            <View className={`px-1.5 py-0.2 rounded-full ${isActive ? 'bg-white/20' : 'bg-border'}`}>
              <Text className={`text-[10px] font-sans-bold ${isActive ? 'text-text-inverse' : 'text-text-muted'}`}>
                {option.badge}
              </Text>
            </View>
          )}
        </Pressable>
      );
    })
  );

  if (isScrollable) {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        className={`bg-surface border border-border p-1 rounded-md ${className}`}
        contentContainerStyle={{ gap: 4 }}
      >
        {renderOptions()}
      </ScrollView>
    );
  }

  return (
    <View className={`flex-row bg-surface border border-border p-1 rounded-md gap-1 ${className}`}>
      {renderOptions()}
    </View>
  );
}
