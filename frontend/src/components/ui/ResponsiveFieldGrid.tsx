import React from 'react';
import { View, useWindowDimensions } from 'react-native';

export interface ResponsiveFieldGridProps {
  children: React.ReactNode;
  minItemWidth?: number;
  gap?: number;
  className?: string;
  testID?: string;
}

export function ResponsiveFieldGrid({
  children,
  minItemWidth = 220,
  gap = 12,
  className = '',
  testID,
}: ResponsiveFieldGridProps) {
  const { width } = useWindowDimensions();
  const isNarrow = width < 480;

  return (
    <View
      testID={testID}
      className={`flex-row flex-wrap items-center ${isNarrow ? 'gap-2' : 'gap-3'} ${className}`}
      style={{ rowGap: gap, columnGap: gap }}
    >
      {React.Children.map(children, (child) => {
        if (!child) return null;
        return (
          <View
            style={{
              flexGrow: 1,
              flexShrink: 1,
              minWidth: isNarrow ? '100%' : minItemWidth,
            }}
          >
            {child}
          </View>
        );
      })}
    </View>
  );
}
