import React from 'react';
import { View, Text } from 'react-native';
import { AlertOctagon, AlertTriangle, Info, AlertCircle, ShieldAlert } from 'lucide-react-native';
import { HiringRisk } from '@/types/api';
import { COLORS } from '@/constants/colors';

export interface HiringRisksCardProps {
  risks: HiringRisk[];
}

export function HiringRisksCard({ risks }: HiringRisksCardProps) {
  if (!risks || risks.length === 0) return null;

  return (
    <View className="gap-2 mt-3">
      <View className="flex-row items-center gap-1.5 mb-1">
        <ShieldAlert size={16} color={COLORS.danger} />
        <Text className="text-sm font-sans-bold text-text-primary">
          Hiring Risks & Concerns
        </Text>
      </View>
      
      {risks.map((risk, idx) => {
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
          default:
            tone = 'bg-surface border-border';
            break;
        }

        return (
          <View key={idx} className={`border rounded-md p-3 gap-1.5 ${tone}`}>
            <View className="flex-row items-start justify-between">
              <View className="flex-row items-center gap-1.5 flex-1 pr-2">
                {icon}
                <Text className={`text-xs font-sans-bold uppercase tracking-wider ${titleColor}`}>
                  {risk.title || risk.risk_code}
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
          </View>
        );
      })}
    </View>
  );
}
