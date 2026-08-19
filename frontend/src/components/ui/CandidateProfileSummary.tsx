import React from 'react';
import { View, Text } from 'react-native';
import { User, Mail, Phone, MapPin, Briefcase, Sparkles } from 'lucide-react-native';
import { Card } from './Card';
import { Badge } from './Badge';
import { COLORS } from '@/constants/colors';
import { EnrichedCandidateAnalysis } from '@/types/api';

interface CandidateProfileSummaryProps {
  analysis: EnrichedCandidateAnalysis;
}

export function CandidateProfileSummary({ analysis }: CandidateProfileSummaryProps) {
  const {
    full_name,
    candidate_name,
    normalized_resume,
    ai_career_summary,
    recommended_department,
    professional_domain,
    strengths,
  } = analysis;

  const resolvedName = full_name || candidate_name || 'Candidate';
  const contact = normalized_resume?.contact || {};
  const email = contact.email;
  const phone = contact.phone;
  const location = contact.location;

  return (
    <Card className="shadow-sm border-border/60">
      {/* Header Info */}
      <View className="flex-row items-center gap-2.5 pb-2 mb-2 border-b border-border/50">
        <View className="items-center justify-center w-9 h-9 rounded-full bg-primary/10">
          <User size={18} color={COLORS.primary} />
        </View>
        <View className="flex-1">
          <Text className="text-base font-sans-bold text-text-primary">
            {resolvedName}
          </Text>
          <View className="flex-row flex-wrap mt-1 gap-x-3 gap-y-1">
            {!!email && (
              <View className="flex-row items-center gap-1">
                <Mail size={12} color={COLORS.textMuted} />
                <Text className="font-sans text-xs text-text-muted">{email}</Text>
              </View>
            )}
            {!!phone && (
              <View className="flex-row items-center gap-1">
                <Phone size={12} color={COLORS.textMuted} />
                <Text className="font-sans text-xs text-text-muted">{phone}</Text>
              </View>
            )}
            {!!location && (
              <View className="flex-row items-center gap-1">
                <MapPin size={12} color={COLORS.textMuted} />
                <Text className="font-sans text-xs text-text-muted">{location}</Text>
              </View>
            )}
          </View>
        </View>
      </View>

      {/* Domain & Department */}
      {(!!professional_domain || !!recommended_department) && (
        <View className="flex-row flex-wrap gap-1.5 mb-2">
          {!!professional_domain && (
            <Badge
              label={`Domain: ${professional_domain}`}
              tone="info"
            />
          )}
          {!!recommended_department && (
            <Badge
              label={`Recommended Dept: ${recommended_department}`}
              tone="success"
            />
          )}
        </View>
      )}

      {/* Strengths */}
      {!!strengths && strengths.length > 0 && (
        <View className="mb-2">
          <Text className="text-xs font-sans-bold text-text-muted mb-1.5 uppercase tracking-wider">
            Key Strengths
          </Text>
          <View className="flex-row flex-wrap gap-1.5">
            {strengths.map((s, idx) => (
              <View
                key={idx}
                className="px-2 py-1 border rounded-md bg-surface-elevated border-border/60"
              >
                <Text className="font-sans text-xs text-text-primary">{s}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* AI Career Summary */}
      {!!ai_career_summary && (
        <View className="p-2.5 border rounded-md bg-primary/5 border-primary/20">
          <View className="flex-row items-center gap-1.5 mb-1.5">
            <Sparkles size={14} color={COLORS.primary} />
            <Text className="text-xs font-sans-bold text-primary">
              AI Career Summary
            </Text>
          </View>
          <Text className="font-sans text-xs leading-relaxed text-text-secondary">
            {ai_career_summary}
          </Text>
        </View>
      )}
    </Card>
  );
}
