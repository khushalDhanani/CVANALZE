import React from 'react';
import {
  Modal,
  View,
  Text,
  Pressable,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  useWindowDimensions,
} from 'react-native';
import { X } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';

export interface ModalShellProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: number;
  testID?: string;
}

export function ModalShell({
  visible,
  onClose,
  title,
  subtitle,
  children,
  footer,
  maxWidth = 540,
  testID,
}: ModalShellProps) {
  const { width, height } = useWindowDimensions();
  const isDesktop = width >= 640;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      testID={testID}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        className="flex-1"
      >
        <View
          className={`flex-1 bg-black/60 ${
            isDesktop ? 'items-center justify-center p-4' : 'justify-end'
          }`}
        >
          <View
            className={`w-full bg-surface ${
              isDesktop ? 'rounded-lg shadow-xl' : 'rounded-t-lg'
            } p-5 gap-3`}
            style={isDesktop ? { maxWidth } : { maxHeight: height * 0.9 }}
          >
            {/* Header */}
            <View className="flex-row justify-between items-center pb-2.5 border-b border-border">
              <View className="flex-1 pr-2">
                <Text className="text-base font-sans-bold text-text-primary" numberOfLines={1}>
                  {title}
                </Text>
                {subtitle && (
                  <Text className="text-xs font-sans text-text-muted mt-0.5" numberOfLines={1}>
                    {subtitle}
                  </Text>
                )}
              </View>
              <Pressable
                onPress={onClose}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                className="p-1 rounded active:bg-background"
                accessibilityRole="button"
                accessibilityLabel="Close dialog"
              >
                <X size={18} color={COLORS.textMuted} />
              </Pressable>
            </View>

            {/* Scrollable Content Area */}
            <ScrollView
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={{ gap: 12, paddingBottom: 4 }}
            >
              {children}
            </ScrollView>

            {/* Footer Actions */}
            {footer && (
              <View className="pt-2 border-t border-border/60">
                {footer}
              </View>
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
