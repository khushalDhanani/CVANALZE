import type { CVUploadResponse } from '@/types/api';
import { cleanCandidateText } from '@/utils/candidateDetail';

export interface ProcessingProvenanceRow {
  key: keyof CVUploadResponse;
  label: string;
  value?: string;
  recorded: boolean;
}

const PROCESSING_VERSION_FIELDS: Array<{ key: keyof CVUploadResponse; label: string }> = [
  { key: 'matching_version', label: 'Matching Version' },
  { key: 'rule_config_version', label: 'Rule Configuration' },
  { key: 'hiring_risk_policy_version', label: 'Hiring Risk Policy' },
  { key: 'hiring_risk_prompt_version', label: 'Hiring Risk Prompt' },
  { key: 'hiring_risk_prompt_identity', label: 'Risk Prompt Identity' },
  { key: 'optimized_prompt_version', label: 'Optimized Prompt' },
  { key: 'llm_model_version', label: 'LLM Model' },
];

const HIRING_RISK_DEFAULT_VERSION = 'default-1.0.0';

const resolveProvenanceValue = (data: CVUploadResponse, key: keyof CVUploadResponse): string | undefined => {
  const recordedValue = cleanCandidateText(data[key]);
  if (recordedValue && recordedValue.toLowerCase() !== 'missing') return recordedValue;
  if (key === 'hiring_risk_prompt_version') return `${HIRING_RISK_DEFAULT_VERSION} available after reprocess`;
  if (key === 'hiring_risk_prompt_identity') return 'Default prompt identity recorded after reprocess';
  return recordedValue;
};

export const getProcessingProvenanceRows = (data: CVUploadResponse): ProcessingProvenanceRow[] => {
  return PROCESSING_VERSION_FIELDS.map(({ key, label }) => {
    const recordedValue = cleanCandidateText(data[key]);
    return {
      key,
      label,
      value: resolveProvenanceValue(data, key),
      recorded: Boolean(recordedValue && recordedValue.toLowerCase() !== 'missing'),
    };
  });
};
