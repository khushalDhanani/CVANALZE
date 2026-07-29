import React from 'react';
import { View, Pressable, Text } from 'react-native';
import { COLORS } from '@/constants/colors';

export interface SegmentedControlOption<T> {
  value: T;
  label: string;
  icon?: (props: { size: number; color: string }) => React.ReactNode;
  accessibilityLabel?: string;
}

interface SegmentedControlProps<T> {
  options: SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}

export function SegmentedControl<T>({ options, value, onChange, disabled }: SegmentedControlProps<T>) {
  return (
    <View className="flex-row bg-surface border border-border p-1 rounded-md">
      {options.map((option) => {
        const isActive = value === option.value;
        return (
          <Pressable
            key={String(option.value)}
            onPress={() => !disabled && onChange(option.value)}
            disabled={disabled}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityRole="button"
            accessibilityLabel={option.accessibilityLabel || option.label}
            className={`flex-1 py-2 rounded-sm items-center flex-row justify-center gap-1.5 ${
              isActive 
                ? 'bg-primary active:bg-primary-dark' 
                : 'bg-transparent active:bg-background'
            } ${disabled ? 'opacity-50' : ''}`}
          >
            {option.icon && option.icon({ size: 14, color: isActive ? COLORS.textInverse : COLORS.textFaint })}
            <Text
              className={`text-xs font-sans-bold ${
                isActive ? 'text-text-inverse' : 'text-text-muted'
              }`}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
