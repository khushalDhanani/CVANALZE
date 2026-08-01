import React from 'react';
import { View, Text, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronRight, Home } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  showHome?: boolean;
}

export function Breadcrumbs({ items, showHome = true }: BreadcrumbsProps) {
  const router = useRouter();

  const allItems: BreadcrumbItem[] = showHome
    ? [{ label: 'Home', href: '/' }, ...items]
    : items;

  return (
    <View className="flex-row items-center flex-wrap gap-1 py-1.5 px-3 bg-surface/50 border-b border-border/50">
      {allItems.map((item, index) => {
        const isLast = index === allItems.length - 1;
        const isFirstHome = showHome && index === 0;

        return (
          <View key={`${item.label}-${index}`} className="flex-row items-center gap-1">
            {index > 0 && (
              <ChevronRight size={12} color={COLORS.textFaint} />
            )}
            {item.href && !isLast ? (
              <Pressable
                onPress={() => router.push(item.href as any)}
                className="flex-row items-center gap-1 py-0.5 px-1 rounded active:bg-background"
                accessibilityRole="button"
                accessibilityLabel={`Navigate to ${item.label}`}
              >
                {isFirstHome && <Home size={11} color={COLORS.textMuted} />}
                <Text className="text-[11px] font-sans-medium text-text-muted hover:text-primary">
                  {item.label}
                </Text>
              </Pressable>
            ) : (
              <View className="flex-row items-center gap-1 py-0.5 px-1">
                {isFirstHome && <Home size={11} color={COLORS.primary} />}
                <Text
                  className={`text-[11px] ${
                    isLast
                      ? 'font-sans-semibold text-text-primary'
                      : 'font-sans-medium text-text-muted'
                  }`}
                  numberOfLines={1}
                >
                  {item.label}
                </Text>
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
}
