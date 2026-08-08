import React from 'react';
import { View, Text } from 'react-native';
import { Badge } from './Badge';
import { LlmHealthResponse, SystemHealthResponse } from '@/types/api';

export interface HealthStatusProps {
  label: string;
  status?: 'online' | 'offline' | 'disabled' | string | null;
  version?: string | null;
  loading?: boolean;
  className?: string;
}

export function HealthStatus({
  label,
  status,
  version,
  loading = false,
  className = '',
}: HealthStatusProps) {
  if (loading) {
    return <Badge label={`${label}: Checking...`} tone="neutral" className={className} />;
  }

  const s = (status || '').toLowerCase();

  if (s === 'online') {
    return (
      <Badge
        label={version ? `${label}: v${version}` : `${label}: Online`}
        tone="success"
        className={className}
      />
    );
  }

  if (s === 'disabled') {
    return <Badge label={`${label}: Disabled`} tone="info" className={className} />;
  }

  return <Badge label={`${label}: Offline`} tone="danger" className={className} />;
}
