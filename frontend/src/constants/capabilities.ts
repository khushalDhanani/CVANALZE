import {
  Award,
  CheckCircle2,
  FileCheck,
  FileCode,
  Sparkles,
  Target,
  UploadCloud,
  UserCheck,
} from 'lucide-react-native';
import type { PipelineStageCapability } from '@/types/capabilities';

export interface PipelineCapabilityStage extends PipelineStageCapability {
  icon: React.ElementType;
}

const PIPELINE_STAGE_ICONS: Record<string, React.ElementType> = {
  upload: UploadCloud,
  validation: FileCheck,
  parsing: FileCode,
  extraction: UserCheck,
  ai_analysis: Sparkles,
  matching: Target,
  ranking: Award,
  complete: CheckCircle2,
};

export function buildPipelineStages(stages: PipelineStageCapability[]): PipelineCapabilityStage[] {
  return stages.map((stage) => ({
    ...stage,
    icon: PIPELINE_STAGE_ICONS[stage.id] ?? FileCheck,
  }));
}
