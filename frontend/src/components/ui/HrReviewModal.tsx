import React, { useState } from 'react';
import {
  Modal,
  View,
  Text,
  Pressable
} from 'react-native';
import { X, CheckCircle } from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { matchService } from '@/services/matchService';
import { JobMatchScore } from '@/types/api';
import { Button } from './Button';
import { TextField } from './TextField';
import { Card } from './Card';

interface HrReviewModalProps {
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
  const [correctedScore, setCorrectedScore] = useState<string>(
    job?.overall_score ? String(Math.round(job.overall_score)) : '80'
  );
  const [classification, setClassification] = useState<'HIGH' | 'MEDIUM' | 'LOW'>(
    (job?.classification as any) || 'HIGH'
  );
  const [feedbackNotes, setFeedbackNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  if (!job) return null;

  const handleSubmit = async () => {
    const numScore = parseFloat(correctedScore);
    if (isNaN(numScore) || numScore < 0 || numScore > 100) {
      setError('Score must be a number between 0 and 100');
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
        feedback_notes: feedbackNotes || null,
      });
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
        if (onSubmitted) onSubmitted();
      }, 1200);
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
      <View className="flex-1 justify-end bg-black/60">
        <View className="w-full bg-surface rounded-t-lg p-5 gap-4">
          <View className="flex-row justify-between items-center pb-3 border-b border-border">
            <Text className="text-lg font-sans-bold text-text-primary">
              HR Review & Correction
            </Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <X size={20} color={COLORS.textFaint} />
            </Pressable>
          </View>

          <Text className="text-sm font-sans-medium text-text-primary">
            Job: <Text className="font-sans-bold text-primary">{job.job_title}</Text>
          </Text>

          {error && (
            <Card className="bg-danger/10 border-danger/30 p-3">
              <Text className="text-xs font-sans-semibold text-danger">
                {error}
              </Text>
            </Card>
          )}

          {success && (
            <Card className="bg-success/10 border-success/30 p-3 flex-row items-center gap-1.5">
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
            placeholder="e.g. 85"
          />

          <View className="gap-1.5">
            <Text className="text-xs font-sans-medium text-text-primary">
              Classification Category:
            </Text>
            <View className="flex-row gap-2">
              {(['HIGH', 'MEDIUM', 'LOW'] as const).map((cat) => (
                <Pressable
                  key={cat}
                  onPress={() => setClassification(cat)}
                  hitSlop={8}
                  className={`flex-1 py-2 rounded-md border items-center ${
                    classification === cat
                      ? 'bg-primary border-primary active:bg-primary-dark'
                      : 'bg-surface border-border active:bg-background'
                  }`}
                >
                  <Text
                    className={`text-xs font-sans-semibold ${
                      classification === cat
                        ? 'text-text-inverse'
                        : 'text-text-primary'
                    }`}
                  >
                    {cat}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <TextField
            label="Feedback & Correction Notes"
            value={feedbackNotes}
            onChangeText={setFeedbackNotes}
            multiline
            numberOfLines={3}
            placeholder="Explain changes..."
            style={{ textAlignVertical: 'top', height: 80 }}
          />

          <View className="flex-row gap-3 pt-2">
            <View className="flex-1">
              <Button label="Cancel" variant="secondary" size="md" onPress={onClose} />
            </View>
            <View className="flex-1">
              <Button label="Submit" size="md" loading={submitting} disabled={submitting} onPress={handleSubmit} />
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}
