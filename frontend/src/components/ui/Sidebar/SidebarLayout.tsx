import { View, Text, Pressable, useWindowDimensions } from 'react-native';
import { Slot, usePathname, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Home, Search, Briefcase, Layers, Settings, Users, X } from 'lucide-react-native';
import { useState } from 'react';
import { COLORS } from '@/constants/colors';

type SidebarNavItem = {
  name: string;
  route: any; // using any for route string to bypass strict typing
  icon: React.ElementType;
};

const NAV_ITEMS: SidebarNavItem[] = [
  { name: 'Home', route: '/', icon: Home },
  { name: 'Match', route: '/cv-match', icon: Search },
  { name: 'Candidates', route: '/candidates', icon: Users },
  { name: 'Jobs', route: '/vacancies', icon: Briefcase },
  { name: 'Batch', route: '/batch', icon: Layers },
  { name: 'Config', route: '/config', icon: Settings },
];


export function SidebarLayout() {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const router = useRouter();

  const isMobile = width < 768;
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);

  // Sync drawer state with screen size changes
  if (!isMobile && !drawerOpen) setDrawerOpen(true);

  const closeDrawer = () => {
    if (isMobile) setDrawerOpen(false);
  };

  const handleSelect = (route: any) => {
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
        />
      )}

      {/* Sidebar */}
      {(drawerOpen || !isMobile) && (
        <View
          className={`bg-surface border-r border-border z-50 ${isMobile ? 'absolute left-0 top-0 bottom-0 w-64' : 'w-64'}`}
          style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}
        >
          <View className="flex-row items-center justify-between px-4 py-3 border-b border-border">
            <Text className="text-base font-sans-semibold text-text-primary">AIRIS</Text>
            {isMobile && (
              <Pressable onPress={closeDrawer} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} accessibilityLabel="Close sidebar">
                <X size={20} color={COLORS.textMuted} />
              </Pressable>
            )}
          </View>

          <View className="flex-1 py-4 gap-2 px-3">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.route;
              const Icon = item.icon;

              return (
                <Pressable
                  key={item.route}
                  onPress={() => handleSelect(item.route)}
                  className={`flex-row items-center gap-3 px-3 py-2 rounded-md ${isActive ? 'bg-primary/10' : 'active:bg-background'
                    }`}
                  accessibilityRole="button"
                >
                  <Icon size={20} color={isActive ? COLORS.primary : COLORS.textMuted} />
                  <Text
                    className={`text-sm ${isActive
                        ? 'font-sans-semibold text-primary'
                        : 'font-sans text-text-muted'
                      }`}
                  >
                    {item.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      )}

      {/* Main Content Area */}
      <View className="flex-1 relative">
        <Slot />

        {/* Mobile menu toggle (if needed, this can be managed within headers inside Slot screens, but here is a simple toggle just in case) */}
        {isMobile && !drawerOpen && (
          <Pressable
            onPress={() => setDrawerOpen(true)}
            className="absolute bottom-6 right-6 bg-primary rounded-full p-3 shadow-lg z-50"
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
