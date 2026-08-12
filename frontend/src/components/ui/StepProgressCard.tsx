import React from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import {
  UploadCloud,
  FileCheck,
  FileCode,
  UserCheck,
  Sparkles,
  Target,
  Award,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  MinusCircle,
} from 'lucide-react-native';
import { COLORS } from '@/constants/colors';
import { PIPELINE_CAPABILITIES, PipelineCapabilityStage } from '@/constants/capabilities';
import { Button } from './Button';

export type ProcessingStep = PipelineCapabilityStage;
export type StepState = 'pending' | 'active' | 'completed' | 'skipped' | 'failed';

export const PIPELINE_STEPS: ProcessingStep[] = PIPELINE_CAPABILITIES.stages;

export interface StepProgressCardProps {
  currentStepIndex: number;
  stepStates: StepState[];
  elapsedSeconds: number;
  statusMessage?: string | null;
  error?: string | null;
  errorDetails?: string | null;
  failedStepName?: string | null;
  useLlmEnrichment?: boolean;
  onRetry?: () => void;
  isProcessing?: boolean;
  isComplete?: boolean;
  className?: string;
}

export function formatElapsedTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`);
  return `${pad(mins)}:${pad(secs)}`;
}

export function StepProgressCard({
  currentStepIndex,
  stepStates,
  elapsedSeconds,
  statusMessage,
  error,
  errorDetails,
  failedStepName,
  useLlmEnrichment = true,
  onRetry,
  isProcessing = false,
  isComplete = false,
  className = '',
}: StepProgressCardProps) {
  const totalSteps = PIPELINE_STEPS.length;
  const completedCount = stepStates.filter((s) => s === 'completed' || s === 'skipped').length;
  
  // Safe progress percentage: capped strictly below 100% until explicit confirmed completion
  let progressPercent = 0;
  if (isComplete) {
    progressPercent = 100;
  } else if (error) {
    progressPercent = Math.min(90, Math.round((completedCount / totalSteps) * 100));
  } else if (isProcessing) {
    progressPercent = Math.max(10, Math.min(95, Math.round((completedCount / totalSteps) * 100)));
  }

  return (
    <View className={`bg-surface border border-border rounded-lg p-4 shadow-sm ${className}`}>
      {/* Header Row: Title, Status Badge, Elapsed Time */}
      <View className="flex-row items-center justify-between mb-3 border-b border-border/60 pb-3">
        <View className="flex-row items-center gap-2">
          {isProcessing ? (
            <View className="w-2.5 h-2.5 rounded-full bg-primary" />
          ) : isComplete ? (
            <View className="w-2.5 h-2.5 rounded-full bg-success" />
          ) : error ? (
            <View className="w-2.5 h-2.5 rounded-full bg-danger" />
          ) : (
            <View className="w-2.5 h-2.5 rounded-full bg-text-faint" />
          )}
          <Text className="text-sm font-sans-bold text-text-primary">
            {isComplete
              ? 'Processing Complete'
              : error
              ? 'Processing Failed'
              : isProcessing
              ? 'Processing Candidate CV'
              : 'Pipeline Status'}
          </Text>
        </View>

        {/* Elapsed Timer Badge */}
        <View className="flex-row items-center gap-1.5 bg-background border border-border px-2.5 py-1 rounded-full">
          <Clock size={13} color={isProcessing ? COLORS.primary : COLORS.textMuted} />
          <Text className="text-xs font-sans-mono font-medium text-text-primary">
            {formatElapsedTime(elapsedSeconds)}
          </Text>
        </View>
      </View>

      {/* Progress Bar Container */}
      <View className="mb-4">
        <View className="flex-row justify-between items-center mb-1.5">
          <Text className="text-[11px] font-sans-medium text-text-muted">
            {isComplete
              ? '100% - All Stages Completed'
              : error
              ? `Halted at ${failedStepName || `Step ${currentStepIndex + 1}`}`
              : `Pipeline Progress: ${progressPercent}%`}
          </Text>
          <Text className="text-[11px] font-sans-bold text-primary">
            Step {Math.min(currentStepIndex + 1, totalSteps)} of {totalSteps}
          </Text>
        </View>
        <View className="h-2 w-full bg-border/50 rounded-full overflow-hidden">
          <View
            className={`h-full rounded-full ${
              error ? 'bg-danger' : isComplete ? 'bg-success' : 'bg-primary'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </View>
      </View>

      {/* Status Banner Message */}
      {!!statusMessage && !error && (
        <View className="bg-primary/10 border border-primary/20 rounded-md p-2.5 mb-3 flex-row items-center gap-2">
          {isProcessing && <ActivityIndicator size="small" color={COLORS.primary} />}
          <Text className="text-xs font-sans-medium text-primary flex-1">
            {statusMessage}
          </Text>
        </View>
      )}

      {/* Error Message with Retry Option */}
      {!!error && (
        <View className="bg-danger/10 border border-danger/30 rounded-md p-3 mb-3 gap-2">
          <View className="flex-row items-center gap-2">
            <AlertTriangle size={16} color={COLORS.danger} />
            <Text className="text-xs font-sans-bold text-danger flex-1">
              {error}
            </Text>
          </View>
          {!!errorDetails && (
            <View className="bg-background border border-danger/20 p-2 rounded mt-1">
              <Text className="text-[10px] font-sans-mono text-text-muted" numberOfLines={10}>
                {errorDetails}
              </Text>
            </View>
          )}
          {onRetry && (
            <View className="self-start mt-1">
              <Button
                label="Retry Upload"
                variant="destructive"
                size="sm"
                icon={<RefreshCw size={12} color={COLORS.textInverse} />}
                onPress={onRetry}
              />
            </View>
          )}
        </View>
      )}

      {/* Step Tracker List */}
      <View className="gap-2">
        {PIPELINE_STEPS.map((step, index) => {
          const state = stepStates[index] || 'pending';
          const isCurrent = index === currentStepIndex && isProcessing;
          const Icon = step.icon;

          return (
            <View
              key={step.id}
              className={`flex-row items-center gap-3 p-2.5 rounded-md border ${
                isCurrent
                  ? 'bg-primary/5 border-primary/40'
                  : state === 'completed'
                  ? 'bg-success/5 border-success/20'
                  : state === 'failed'
                  ? 'bg-danger/5 border-danger/30'
                  : state === 'skipped'
                  ? 'bg-surface border-border/40 opacity-60'
                  : 'bg-surface border-border/60'
              }`}
            >
              {/* Step Icon Container */}
              <View
                className={`w-7 h-7 rounded-full items-center justify-center ${
                  state === 'completed'
                    ? 'bg-success text-white'
                    : state === 'failed'
                    ? 'bg-danger text-white'
                    : state === 'skipped'
                    ? 'bg-border text-text-faint'
                    : isCurrent
                    ? 'bg-primary text-white'
                    : 'bg-border/60 text-text-faint'
                }`}
              >
                {isCurrent ? (
                  <ActivityIndicator size="small" color={COLORS.textInverse} />
                ) : state === 'completed' ? (
                  <CheckCircle2 size={15} color={COLORS.textInverse} />
                ) : state === 'skipped' ? (
                  <MinusCircle size={14} color={COLORS.textFaint} />
                ) : state === 'failed' ? (
                  <AlertTriangle size={14} color={COLORS.textInverse} />
                ) : (
                  <Icon size={14} color={COLORS.textMuted} />
                )}
              </View>

              {/* Step Label & Description */}
              <View className="flex-1">
                <View className="flex-row items-center justify-between">
                  <Text
                    className={`text-xs font-sans-bold ${
                      isCurrent
                        ? 'text-primary'
                        : state === 'completed'
                        ? 'text-text-primary'
                        : state === 'failed'
                        ? 'text-danger'
                        : state === 'skipped'
                        ? 'text-text-muted line-through'
                        : 'text-text-muted'
                    }`}
                  >
                    {step.label}
                  </Text>
                  {state === 'skipped' && (
                    <Text className="text-[10px] font-sans-medium text-text-faint bg-border/50 px-1.5 py-0.5 rounded">
                      Disabled
                    </Text>
                  )}
                  {state === 'completed' && (
                    <Text className="text-[10px] font-sans-medium text-success">
                      Done
                    </Text>
                  )}
                </View>
                <Text
                  className={`text-[11px] font-sans ${
                    isCurrent ? 'text-text-primary' : 'text-text-muted'
                  }`}
                  numberOfLines={1}
                >
                  {step.id === 'ai_analysis' && !useLlmEnrichment
                    ? 'Fast-track heuristic evaluation (LLM enrichment bypassed)'
                    : step.description}
                </Text>
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}
