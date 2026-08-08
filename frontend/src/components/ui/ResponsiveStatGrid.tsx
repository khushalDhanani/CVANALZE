import React from 'react';
import { View, useWindowDimensions } from 'react-native';

export interface ResponsiveStatGridProps {
  children: React.ReactNode;
  minCardWidth?: number;
  gap?: number;
  className?: string;
  testID?: string;
}

export function ResponsiveStatGrid({
  children,
  minCardWidth = 160,
  gap = 12,
  className = '',
  testID,
}: ResponsiveStatGridProps) {
  const { width } = useWindowDimensions();
  const isNarrow = width < 480;

  return (
    <View
      testID={testID}
      className={`flex-row flex-wrap items-stretch ${className}`}
      style={{ rowGap: gap, columnGap: gap }}
    >
      {React.Children.map(children, (child) => {
        if (!child) return null;
        return (
          <View
            style={{
              flexGrow: 1,
              flexShrink: 1,
              minWidth: isNarrow ? '100%' : minCardWidth,
            }}
          >
            {child}
          </View>
        );
      })}
    </View>
  );
}
