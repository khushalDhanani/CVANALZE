import React from 'react';
import { View, Text } from 'react-native';
import { AlertCircle } from 'lucide-react-native';

export function ErrorBanner({ 
  title = 'An error occurred', 
  message 
}: { 
  title?: string;
  message?: string;
}) {
  return (
    <View className="bg-danger/10 border border-danger/30 rounded-md p-3 mb-4 flex-row items-start gap-2">
      <View className="mt-0.5">
        <AlertCircle size={16} color="#DC2626" />
      </View>
      <View className="flex-1 gap-0.5">
        <Text className="text-sm font-sans-bold text-danger">{title}</Text>
        {message ? (
          <Text className="text-xs font-sans text-danger opacity-90">{message}</Text>
        ) : null}
      </View>
    </View>
  );
}
