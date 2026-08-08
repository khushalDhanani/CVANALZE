import React, { useState } from 'react';
import { View, Text, Pressable, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronRight, Home, MoreHorizontal } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  showHome?: boolean;
  maxVisibleItems?: number;
}

export function Breadcrumbs({ items, showHome = true, maxVisibleItems }: BreadcrumbsProps) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [expanded, setExpanded] = useState(false);

  const allItems: BreadcrumbItem[] = showHome
    ? [{ label: 'Home', href: '/' }, ...items]
    : items;

  // On small mobile screens (< 480px), collapse intermediate breadcrumb items unless expanded
  const effectiveMaxItems = maxVisibleItems ?? (width < 480 ? 2 : 4);
  const shouldCollapse = !expanded && allItems.length > effectiveMaxItems && allItems.length > 2;

  let displayItems = allItems;
  if (shouldCollapse) {
    displayItems = [
      allItems[0],
      { label: '...', href: undefined },
      allItems[allItems.length - 1],
    ];
  }

  return (
    <View className="flex-row items-center flex-wrap gap-1 py-1.5 px-3 bg-surface/50 border-b border-border/50">
      {displayItems.map((item, index) => {
        const isLast = index === displayItems.length - 1;
        const isEllipsis = item.label === '...';
        const isFirstHome = showHome && index === 0;

        if (isEllipsis) {
          return (
            <View key="ellipsis" className="flex-row items-center gap-1">
              <ChevronRight size={12} color={COLORS.textFaint} />
              <Pressable
                onPress={() => setExpanded(true)}
                className="p-1 min-h-[36px] min-w-[36px] items-center justify-center rounded active:bg-background"
                accessibilityRole="button"
                accessibilityLabel="Show all breadcrumb items"
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <MoreHorizontal size={14} color={COLORS.textMuted} />
              </Pressable>
            </View>
          );
        }

        return (
          <View key={`${item.label}-${index}`} className="flex-row items-center gap-1">
            {index > 0 && (
              <ChevronRight size={12} color={COLORS.textFaint} />
            )}
            {item.href && !isLast ? (
              <Pressable
                onPress={() => router.push(item.href as any)}
                className="flex-row items-center gap-1 py-1 px-1.5 min-h-[36px] rounded active:bg-background"
                accessibilityRole="button"
                accessibilityLabel={`Navigate to ${item.label}`}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                {isFirstHome && <Home size={12} color={COLORS.textMuted} />}
                <Text className="text-[11px] font-sans-medium text-text-muted hover:text-primary max-w-[160px]" numberOfLines={1}>
                  {item.label}
                </Text>
              </Pressable>
            ) : (
              <View className="flex-row items-center gap-1 py-1 px-1.5 min-h-[36px]">
                {isFirstHome && <Home size={12} color={COLORS.primary} />}
                <Text
                  className={`text-[11px] max-w-[200px] ${
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
