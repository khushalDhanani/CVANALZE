import React, { useState, useEffect } from 'react';
import {
  Modal,
  View,
  Text,
  Pressable,
  ScrollView,
  useWindowDimensions,
} from 'react-native';
import { X, CheckCircle } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { matchService } from '@/services/matchService';
import { JobMatchScore } from '@/types/api';
import { Button } from './Button';
import { TextField } from './TextField';
import { Card } from './Card';
import { SegmentedControl } from './SegmentedControl';

export interface HrReviewModalProps {
  visible: boolean;
  scanId: string;
  job: JobMatchScore | null;
  onClose: () => void;
  onSubmitted?: () => void;
}

export function HrReviewModal({
  visible,
  scanId,
  job,
  onClose,
  onSubmitted,
}: HrReviewModalProps) {
  const { width } = useWindowDimensions();
  const isDesktop = width >= 640;

  const [correctedScore, setCorrectedScore] = useState<string>('');
  const [classification, setClassification] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('LOW');
  const [feedbackNotes, setFeedbackNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  // Sync state whenever visible modal opens or target job changes
  useEffect(() => {
    if (visible && job) {
      setError(null);
      setSuccess(false);
      setFeedbackNotes('');

      // Populate score only if real overall_score exists on backend record; otherwise require deliberate input
      if (job.overall_score != null && !isNaN(job.overall_score) && job.overall_score > 0) {
        setCorrectedScore(String(Math.round(job.overall_score)));
      } else {
        setCorrectedScore('');
      }

      const rawCls = String(job.classification || job.vacancy_match_status || '').toUpperCase();
      if (rawCls.includes('HIGH') || rawCls.includes('STRONG') || rawCls.includes('MATCHED')) {
        setClassification('HIGH');
      } else if (rawCls.includes('MED') || rawCls.includes('POTENTIAL')) {
        setClassification('MEDIUM');
      } else {
        setClassification('LOW');
      }
    }
  }, [visible, job?.job_id, job?.overall_score]);

  if (!job) return null;

  const handleSubmit = async () => {
    const numScore = parseFloat(correctedScore);
    if (isNaN(numScore) || numScore < 0 || numScore > 100) {
      setError('Please provide a valid score between 0 and 100');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await matchService.submitHrReview({
        scan_id: scanId,
        job_id: Number(job.job_id),
        corrected_score: numScore,
        corrected_classification: classification,
        feedback_notes: feedbackNotes || '',
      });
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
        if (onSubmitted) onSubmitted();
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Failed to submit HR review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View className={`flex-1 bg-black/60 ${isDesktop ? 'items-center justify-center p-4' : 'justify-end'}`}>
        <View
          className={`w-full bg-surface ${
            isDesktop ? 'max-w-lg rounded-lg shadow-xl' : 'rounded-t-lg'
          } p-5 gap-3.5`}
        >
          <View className="flex-row justify-between items-center pb-2.5 border-b border-border">
            <Text className="text-base font-sans-bold text-text-primary">
              HR Review & Correction
            </Text>
            <Pressable
              onPress={onClose}
              hitSlop={8}
              className="p-1 rounded active:bg-background"
              accessibilityRole="button"
              accessibilityLabel="Close modal"
            >
              <X size={18} color={COLORS.textMuted} />
            </Pressable>
          </View>

          <ScrollView className="max-h-[80vh]" contentContainerStyle={{ gap: 14 }}>
            <View className="bg-background p-2.5 rounded border border-border/70">
              <Text className="text-xs font-sans-medium text-text-muted">
                Target Role: <Text className="font-sans-bold text-primary">{job.job_title}</Text>
              </Text>
              {job.department_name && (
                <Text className="text-[11px] font-sans text-text-muted mt-0.5">
                  Dept: {job.department_name}
                </Text>
              )}
            </View>

            {error && (
              <Card className="bg-danger/10 border-danger/30 p-2.5">
                <Text className="text-xs font-sans-semibold text-danger">
                  {error}
                </Text>
              </Card>
            )}

            {success && (
              <Card className="bg-success/10 border-success/30 p-2.5 flex-row items-center gap-1.5">
                <CheckCircle size={14} color={COLORS.success} />
                <Text className="text-xs font-sans-semibold text-success">
                  HR Review saved successfully!
                </Text>
              </Card>
            )}

            <TextField
              label="Corrected Match Score (0 - 100)"
              value={correctedScore}
              onChangeText={setCorrectedScore}
              keyboardType="numeric"
              placeholder="e.g. 75"
              accessibilityLabel="Corrected match score input"
            />

            <View className="gap-1.5">
              <Text className="text-xs font-sans-medium text-text-primary">
                Classification Category:
              </Text>
              <SegmentedControl
                options={[
                  { value: 'HIGH', label: 'High Match' },
                  { value: 'MEDIUM', label: 'Medium Match' },
                  { value: 'LOW', label: 'Low Match' },
                ]}
                value={classification}
                onChange={(val) => setClassification(val as 'HIGH' | 'MEDIUM' | 'LOW')}
              />
            </View>

            <TextField
              label="Feedback & Correction Notes"
              value={feedbackNotes}
              onChangeText={setFeedbackNotes}
              multiline
              numberOfLines={3}
              placeholder="Provide reason for score adjustment or manual decision..."
              style={{ textAlignVertical: 'top', height: 75 }}
            />

            <View className="flex-row gap-2.5 pt-2">
              <View className="flex-1">
                <Button label="Cancel" variant="secondary" size="md" onPress={onClose} />
              </View>
              <View className="flex-1">
                <Button
                  label="Submit Review"
                  size="md"
                  loading={submitting}
                  disabled={submitting}
                  onPress={handleSubmit}
                />
              </View>
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
