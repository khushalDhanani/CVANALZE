import { View, Text, Pressable, ScrollView, useWindowDimensions } from 'react-native';
import { Slot, usePathname, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Home, Search, Briefcase, Layers, Settings, Users, X, BarChart3, Database, GitBranch, BookOpen } from 'lucide-react-native';
import { useState, useEffect } from 'react';
import { COLORS } from '@/constants/colors';
import { BRAND } from '@/constants/brand';

import { NAV_ITEMS } from '@/constants/navigation';

export function SidebarLayout() {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const router = useRouter();

  const isMobile = width < 768;
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);

  // Sync drawer state cleanly with screen size changes without render-time side effects
  useEffect(() => {
    if (isMobile) {
      setDrawerOpen(false);
    } else {
      setDrawerOpen(true);
    }
  }, [isMobile]);

  const closeDrawer = () => {
    if (isMobile) setDrawerOpen(false);
  };

  const handleSelect = (route: any, isActive: boolean) => {
    if (isActive) {
      closeDrawer();
      return;
    }
    router.push(route);
    closeDrawer();
  };

  return (
    <View className="flex-1 flex-row bg-background">
      {/* Mobile Backdrop */}
      {isMobile && drawerOpen && (
        <Pressable
          className="absolute inset-0 bg-black/50 z-40"
          onPress={closeDrawer}
          accessibilityLabel="Close navigation drawer backdrop"
        />
      )}

      {/* Sidebar */}
      {(drawerOpen || !isMobile) && (
        <View
          className={`bg-surface border-r border-border z-50 ${isMobile ? 'absolute left-0 top-0 bottom-0 w-64' : 'w-64'}`}
          style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}
        >
          {/* Fixed Header */}
          <View className="flex-row items-center justify-between px-4 py-3.5 border-b border-border">
            <Text className="text-base font-sans-bold text-text-primary tracking-wide">{BRAND.name}</Text>
            {isMobile && (
              <Pressable
                onPress={closeDrawer}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                className="p-1"
                accessibilityRole="button"
                accessibilityLabel="Close navigation menu"
              >
                <X size={20} color={COLORS.textMuted} />
              </Pressable>
            )}
          </View>

          {/* Scrollable Nav Container for short phones / landscape */}
          <ScrollView
            className="flex-1 px-3 py-3"
            contentContainerStyle={{ gap: 6 }}
            showsVerticalScrollIndicator={false}
          >
            {NAV_ITEMS.map((item) => {
              const isActive = item.route === '/' 
                ? (pathname === '/' || pathname === '') 
                : (pathname === item.route || pathname.startsWith(`${item.route}/`));
              const Icon = item.icon;

              return (
                <Pressable
                  key={item.route}
                  onPress={() => handleSelect(item.route, isActive)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  accessibilityRole="button"
                  accessibilityState={{ selected: isActive }}
                  accessibilityLabel={item.name}
                  className={`flex-row items-center gap-3 px-3 py-2.5 min-h-[44px] rounded-md ${
                    isActive ? 'bg-primary/10' : 'active:bg-background'
                  }`}
                >
                  <Icon size={20} color={isActive ? COLORS.primary : COLORS.textMuted} />
                  <Text
                    className={`text-sm ${
                      isActive
                        ? 'font-sans-semibold text-primary'
                        : 'font-sans text-text-muted'
                    }`}
                  >
                    {item.name}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>
      )}

      {/* Main Content Area */}
      <View className="flex-1 relative">
        <Slot />

        {/* Mobile menu floating toggle button */}
        {isMobile && !drawerOpen && (
          <Pressable
            onPress={() => setDrawerOpen(true)}
            className="absolute bottom-6 right-6 bg-primary rounded-full p-3.5 shadow-lg z-50 min-h-[48px] min-w-[48px] items-center justify-center"
            style={{ elevation: 5 }}
            accessibilityRole="button"
            accessibilityLabel="Open navigation menu"
          >
            <Layers size={24} color={COLORS.textInverse} />
          </Pressable>
        )}
      </View>
    </View>
  );
}
