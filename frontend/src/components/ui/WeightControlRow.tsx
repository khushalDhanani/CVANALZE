import React from 'react';
import { View } from 'react-native';
import { TextField } from './TextField';
import { DenseRow } from './DenseRow';

interface WeightControlRowProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
}

export function WeightControlRow({ label, value, onChange }: WeightControlRowProps) {
  return (
    <DenseRow
      title={label.charAt(0).toUpperCase() + label.slice(1)}
      trailing={
        <View className="w-20">
          <TextField
            label=""
            value={value}
            onChangeText={onChange}
            keyboardType="numeric"
            style={{ textAlign: 'right', paddingVertical: 4 }}
            accessibilityLabel={`${label} weight input`}
          />
        </View>
      }
    />
  );
}
