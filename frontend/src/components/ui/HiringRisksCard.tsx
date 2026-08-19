import React from 'react';
import { View, Text } from 'react-native';
import { AlertOctagon, AlertTriangle, Info, AlertCircle, ShieldAlert } from 'lucide-react-native';
import { HiringRisk } from '@/types/api';
import { COLORS } from '@/constants/colors';
import { getHiringRiskPresentation } from '@/utils/hiringRisk';
import { Badge } from './Badge';

export interface HiringRisksCardProps {
  risks?: HiringRisk[] | null;
  showEmpty?: boolean;
}

export function HiringRisksCard({ risks = [], showEmpty = false }: HiringRisksCardProps) {
  if (!risks || risks.length === 0) {
    if (!showEmpty) return null;
    return (
      <View className="gap-1.5 p-2.5 border rounded-md bg-success/5 border-success/20">
        <View className="flex-row items-center gap-1.5">
          <ShieldAlert size={16} color={COLORS.success} />
          <Text className="text-sm font-sans-bold text-text-primary">Hiring Risks & Concerns</Text>
        </View>
        <Text className="text-xs font-sans text-success leading-5">
          No active deterministic hiring-risk policy was triggered for this vacancy match.
        </Text>
      </View>
    );
  }

  return (
    <View className="gap-2">
      <View className="flex-row items-center gap-1.5 mb-1">
        <ShieldAlert size={16} color={COLORS.danger} />
        <Text className="text-sm font-sans-bold text-text-primary">
          Hiring Risks & Concerns
        </Text>
      </View>
      
      {risks.map((risk, idx) => {
        const presentation = getHiringRiskPresentation(risk);
        const severity = risk.severity?.toUpperCase() || 'UNKNOWN';
        const severityTone = severity === 'CRITICAL'
          ? 'danger'
          : severity === 'HIGH' || severity === 'UNKNOWN'
            ? 'warning'
            : severity === 'MEDIUM'
              ? 'info'
              : 'neutral';
        let tone = 'bg-background border-border';
        let icon = <AlertCircle size={14} color={COLORS.textMuted} />;
        let textColor = 'text-text-primary';
        let titleColor = 'text-text-primary';
        
        switch (risk.severity?.toUpperCase()) {
          case 'CRITICAL':
            tone = 'bg-danger/10 border-danger/30';
            icon = <AlertOctagon size={14} color={COLORS.danger} />;
            textColor = 'text-danger';
            titleColor = 'text-danger';
            break;
          case 'HIGH':
            tone = 'bg-warning/10 border-warning/30';
            icon = <AlertTriangle size={14} color={COLORS.warning} />;
            textColor = 'text-warning';
            titleColor = 'text-warning';
            break;
          case 'MEDIUM':
            tone = 'bg-info/10 border-info/30';
            icon = <Info size={14} color={COLORS.info} />;
            textColor = 'text-info';
            titleColor = 'text-info';
            break;
          case 'UNKNOWN':
            tone = 'bg-warning/10 border-warning/30';
            icon = <AlertTriangle size={14} color={COLORS.warning} />;
            textColor = 'text-warning';
            titleColor = 'text-warning';
            break;
          case 'LOW':
            tone = 'bg-surface border-border';
            icon = <Info size={14} color={COLORS.textMuted} />;
            break;
          default:
            tone = 'bg-surface border-border';
            break;
        }

        return (
          <View key={`${presentation.key}-${idx}`} className={`border rounded-md p-2.5 gap-1.5 ${tone}`}>
            <View className="flex-row items-start justify-between">
              <View className="flex-row items-center gap-1.5 flex-1 pr-2">
                {icon}
                <Text className={`text-xs font-sans-bold uppercase tracking-wider ${titleColor}`}>
                  {presentation.title}
                </Text>
              </View>
              {risk.requires_manual_review && (
                <View className="bg-danger px-1.5 py-0.5 rounded">
                  <Text className="text-[10px] font-sans-bold text-white uppercase tracking-wider">
                    Review Required
                  </Text>
                </View>
              )}
            </View>
            <Text className={`text-xs font-sans leading-5 ${textColor}`}>
              {risk.explanation}
            </Text>
            <View className="flex-row flex-wrap gap-1.5">
              <Badge label={severity} tone={severityTone} />
              <Badge label={presentation.category} tone="neutral" />
              <Badge label={`Code: ${risk.risk_code}`} tone="neutral" />
              <Badge label={`Source: ${presentation.source}`} tone="neutral" />
            </View>
            {presentation.evidence.length > 0 ? (
              <View className="gap-1 pt-1 border-t border-border/60">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">Deterministic Evidence</Text>
                {presentation.evidence.map((evidence) => (
                  <Text key={evidence} className="text-[11px] font-sans text-text-primary leading-4">• {evidence}</Text>
                ))}
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}
