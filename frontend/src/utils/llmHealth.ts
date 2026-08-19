import { LlmHealthResponse } from '@/types/api';

export type LlmHealthTone = 'success' | 'warning' | 'danger' | 'info';

export interface LlmHealthPresentation {
  value: string;
  detail: string;
  tone: LlmHealthTone;
}

export function getLlmHealthPresentation(health: LlmHealthResponse | null): LlmHealthPresentation {
  if (health?.status === 'online') {
    return {
      value: 'ONLINE',
      detail: health.model_configured || 'Connected',
      tone: 'success',
    };
  }

  if (health?.status === 'disabled') {
    return {
      value: 'DISABLED',
      detail: health.message || 'LLM reasoning disabled',
      tone: 'info',
    };
  }

  if (health?.status === 'configuration_error') {
    const missingModels = health.missing_models?.filter(Boolean) || [];
    return {
      value: 'CONFIG ERROR',
      detail: missingModels.length > 0 ? `Missing: ${missingModels.join(', ')}` : health.error || 'Configured Ollama model is unavailable',
      tone: 'warning',
    };
  }

  return {
    value: 'OFFLINE',
    detail: health?.error || 'Ollama server unreachable',
    tone: 'danger',
  };
}

export function getAvailableOllamaModelsLabel(health: LlmHealthResponse | null): string {
  if (health?.status === 'disabled') {
    return 'Bypass (Fast-Track Rule Engine)';
  }
  if (health?.available_models?.length) {
    return health.available_models.join(', ');
  }
  if (health?.status === 'configuration_error') {
    return 'No installed models reported';
  }
  return health?.error || 'Ollama server unreachable';
}
