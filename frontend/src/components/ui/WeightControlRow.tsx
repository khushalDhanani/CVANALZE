import React from 'react';
import { View, Text } from 'react-native';
import { TextField } from './TextField';
import { Badge } from './Badge';

export interface WeightControlRowProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
  description?: string;
  error?: string;
  testID?: string;
}

export function WeightControlRow({
  label,
  value,
  onChange,
  description = 'Weight contribution ratio',
  error,
  testID,
}: WeightControlRowProps) {
  const numVal = parseFloat(value) || 0;
  const percentText = `${Math.round(numVal * 100)}%`;

  return (
    <View testID={testID} className="flex-row flex-wrap sm:flex-nowrap items-center justify-between py-2.5 border-b border-border/50 gap-2">
      <View className="flex-1 min-w-[160px] pr-2">
        <Text className="text-xs font-sans-semibold text-text-primary capitalize">{label}</Text>
        <Text className="text-[11px] font-sans text-text-muted">{description}</Text>
      </View>
      <View className="flex-row items-center gap-2 self-end sm:self-auto">
        <Badge label={percentText} tone="neutral" />
        <View className="w-24 sm:w-28">
          <TextField
            value={value}
            onChangeText={onChange}
            keyboardType="numeric"
            error={error}
            className="text-right py-1.5 min-h-[36px]"
            accessibilityLabel={`${label} weight ratio`}
          />
        </View>
      </View>
    </View>
  );
}
