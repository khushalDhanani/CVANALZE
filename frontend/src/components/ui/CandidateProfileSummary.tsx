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
    <Card className="border-border/60 shadow-sm mb-4">
      {/* Header Info */}
      <View className="flex-row items-center gap-3 pb-3 border-b border-border/50 mb-3">
        <View className="w-10 h-10 rounded-full bg-primary/10 items-center justify-center">
          <User size={20} color={COLORS.primary} />
        </View>
        <View className="flex-1">
          <Text className="text-base font-sans-bold text-text-primary">
            {resolvedName}
          </Text>
          <View className="flex-row flex-wrap gap-x-3 gap-y-1 mt-1">
            {!!email && (
              <View className="flex-row items-center gap-1">
                <Mail size={12} color={COLORS.textMuted} />
                <Text className="text-xs font-sans text-text-muted">{email}</Text>
              </View>
            )}
            {!!phone && (
              <View className="flex-row items-center gap-1">
                <Phone size={12} color={COLORS.textMuted} />
                <Text className="text-xs font-sans text-text-muted">{phone}</Text>
              </View>
            )}
            {!!location && (
              <View className="flex-row items-center gap-1">
                <MapPin size={12} color={COLORS.textMuted} />
                <Text className="text-xs font-sans text-text-muted">{location}</Text>
              </View>
            )}
          </View>
        </View>
      </View>

      {/* Domain & Department */}
      {(!!professional_domain || !!recommended_department) && (
        <View className="flex-row flex-wrap gap-2 mb-3">
          {!!professional_domain && (
            <Badge
              label={`Domain: ${professional_domain}`}
              tone="info"
              icon={<Briefcase size={10} color={COLORS.info} />}
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
        <View className="mb-3">
          <Text className="text-xs font-sans-bold text-text-muted mb-1.5 uppercase tracking-wider">
            Key Strengths
          </Text>
          <View className="flex-row flex-wrap gap-1.5">
            {strengths.map((s, idx) => (
              <View
                key={idx}
                className="bg-surface-elevated px-2 py-1 rounded-md border border-border/60"
              >
                <Text className="text-xs font-sans text-text-primary">{s}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* AI Career Summary */}
      {!!ai_career_summary && (
        <View className="bg-primary/5 border border-primary/20 rounded-md p-3">
          <View className="flex-row items-center gap-1.5 mb-1.5">
            <Sparkles size={14} color={COLORS.primary} />
            <Text className="text-xs font-sans-bold text-primary">
              AI Career Summary
            </Text>
          </View>
          <Text className="text-xs font-sans text-text-secondary leading-relaxed">
            {ai_career_summary}
          </Text>
        </View>
      )}
    </Card>
  );
}
