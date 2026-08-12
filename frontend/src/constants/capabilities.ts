import {
  UploadCloud,
  FileCheck,
  FileCode,
  UserCheck,
  Sparkles,
  Target,
  Award,
  CheckCircle2,
} from 'lucide-react-native';

export interface PipelineCapabilityStage {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
}

export const PIPELINE_CAPABILITIES = {
  stages: [
    {
      id: 'upload',
      label: 'Upload CV',
      description: 'Transferring document to processing server',
      icon: UploadCloud,
    },
    {
      id: 'validation',
      label: 'Validation',
      description: 'Verifying file integrity & format compatibility',
      icon: FileCheck,
    },
    {
      id: 'parsing',
      label: 'Document Parsing',
      description: 'Extracting structured layout & OCR text elements',
      icon: FileCode,
    },
    {
      id: 'extraction',
      label: 'Profile Extraction',
      description: 'Structuring candidate profile, skills & work history',
      icon: UserCheck,
    },
    {
      id: 'ai_analysis',
      label: 'AI Reasoning',
      description: 'Semantic analysis & deep skill inference',
      icon: Sparkles,
    },
    {
      id: 'matching',
      label: 'Job Matching',
      description: 'Cross-evaluating candidate against active vacancies',
      icon: Target,
    },
    {
      id: 'ranking',
      label: 'Score Ranking',
      description: 'Calculating component weights & penalty thresholds',
      icon: Award,
    },
    {
      id: 'complete',
      label: 'Analysis Ready',
      description: 'Match scores & candidate evaluation generated',
      icon: CheckCircle2,
    },
  ] as PipelineCapabilityStage[],

  batchLimits: [5, 10, 20, 30] as const,
  defaultBatchLimit: 10,
  maxSupportedPdfPages: 25,
  ocrEngine: 'RapidOCR',
  documentParser: 'Docling',
  primaryLlm: 'Ollama local LLM',
  primaryVectorDb: 'PostgreSQL pgvector',
};
