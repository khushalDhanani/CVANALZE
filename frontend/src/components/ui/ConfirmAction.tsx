import React from 'react';
import { View, Text } from 'react-native';
import { AlertTriangle, AlertCircle } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { ModalShell } from './ModalShell';
import { Button } from './Button';

export interface ConfirmActionProps {
  visible: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  destructive?: boolean;
  details?: string[];
  testID?: string;
}

export function ConfirmAction({
  visible,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  loading = false,
  destructive = true,
  details,
  testID,
}: ConfirmActionProps) {
  return (
    <ModalShell
      visible={visible}
      onClose={onClose}
      title={title}
      maxWidth={460}
      testID={testID}
      footer={
        <View className="flex-row justify-end gap-2.5">
          <Button
            label={cancelLabel}
            variant="ghost"
            size="md"
            onPress={onClose}
            disabled={loading}
          />
          <Button
            label={confirmLabel}
            variant={destructive ? 'destructive' : 'primary'}
            size="md"
            loading={loading}
            onPress={onConfirm}
          />
        </View>
      }
    >
      <View className="gap-3">
        <View className="flex-row items-start gap-2.5">
          {destructive ? (
            <AlertCircle size={18} color={COLORS.danger} className="mt-0.5" />
          ) : (
            <AlertTriangle size={18} color={COLORS.warning} className="mt-0.5" />
          )}
          <Text className="text-xs font-sans text-text-primary leading-5 flex-1">
            {message}
          </Text>
        </View>

        {details && details.length > 0 && (
          <View className="gap-1.5 pl-3 border-l-2 border-border/80 bg-background/50 p-2.5 rounded">
            {details.map((d, i) => (
              <Text key={i} className="text-xs font-sans text-text-muted leading-4">
                • {d}
              </Text>
            ))}
          </View>
        )}
      </View>
    </ModalShell>
  );
}
