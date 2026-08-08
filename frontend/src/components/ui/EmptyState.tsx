import React from "react";
import { View, Text } from "react-native";
import { Button } from "./Button";

export type EmptyStateVariant = "page" | "list" | "card" | "compact" | "default";

export interface EmptyStateAction {
  label: string;
  onPress: () => void;
  icon?: React.ReactNode;
}

export interface EmptyStateProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  variant?: EmptyStateVariant;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  subtitle,
  icon,
  variant = "default",
  primaryAction,
  secondaryAction,
  action,
  className = "",
}: EmptyStateProps) {
  const isCompact = variant === "compact" || variant === "card";
  const isList = variant === "list";
  const isPage = variant === "page" || variant === "default";

  if (isCompact) {
    return (
      <View className={`items-center justify-center py-4 px-3 gap-1.5 bg-surface border border-border/60 rounded-md w-full ${className}`}>
        {icon}
        <Text className="text-xs font-sans-semibold text-text-primary text-center">{title}</Text>
        {subtitle && <Text className="text-[11px] font-sans text-text-muted text-center leading-4">{subtitle}</Text>}
        {(primaryAction || secondaryAction || action) && (
          <View className="flex-row items-center gap-2 mt-2">
            {primaryAction && (
              <Button
                label={primaryAction.label}
                variant="secondary"
                size="sm"
                icon={primaryAction.icon}
                onPress={primaryAction.onPress}
              />
            )}
            {secondaryAction && (
              <Button
                label={secondaryAction.label}
                variant="ghost"
                size="sm"
                onPress={secondaryAction.onPress}
              />
            )}
            {action}
          </View>
        )}
      </View>
    );
  }

  if (isList) {
    return (
      <View className={`items-center justify-center py-8 px-4 gap-2 bg-surface/50 border border-dashed border-border rounded-lg ${className}`}>
        {icon}
        <Text className="text-sm font-sans-semibold text-text-primary text-center">{title}</Text>
        {subtitle && <Text className="text-xs font-sans text-text-muted text-center max-w-sm leading-5">{subtitle}</Text>}
        {(primaryAction || secondaryAction || action) && (
          <View className="flex-row items-center gap-2.5 mt-2">
            {primaryAction && (
              <Button
                label={primaryAction.label}
                variant="primary"
                size="sm"
                icon={primaryAction.icon}
                onPress={primaryAction.onPress}
              />
            )}
            {secondaryAction && (
              <Button
                label={secondaryAction.label}
                variant="secondary"
                size="sm"
                onPress={secondaryAction.onPress}
              />
            )}
            {action}
          </View>
        )}
      </View>
    );
  }

  return (
    <View className={`flex-1 items-center justify-center px-6 py-12 gap-2 ${className}`}>
      {icon}
      <Text className="text-base font-sans-bold text-text-primary text-center">{title}</Text>
      {subtitle && <Text className="text-xs font-sans text-text-muted text-center max-w-md leading-5">{subtitle}</Text>}
      {(primaryAction || secondaryAction || action) && (
        <View className="flex-row items-center gap-3 mt-3">
          {primaryAction && (
            <Button
              label={primaryAction.label}
              variant="primary"
              size="sm"
              icon={primaryAction.icon}
              onPress={primaryAction.onPress}
            />
          )}
          {secondaryAction && (
            <Button
              label={secondaryAction.label}
              variant="secondary"
              size="sm"
              onPress={secondaryAction.onPress}
            />
          )}
          {action}
        </View>
      )}
    </View>
  );
}
