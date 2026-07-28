import { View } from "react-native";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <View
      className={`bg-surface rounded-md p-3 border border-border shadow-sm ${className}`}
      style={{ elevation: 1 }}
    >
      {children}
    </View>
  );
}
