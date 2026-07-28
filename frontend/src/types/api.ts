// API Type Definitions for CV Analyzer Backend Integration

export interface JobOpening {
  VacancyID: number;
  VacancyTitle: string;
  DepartmentID?: number | null;
  DepartmentName?: string | null;
  ExperienceYearReqMin?: number | null;
  ExperienceYearReqMax?: number | null;
  QualificationReq?: string | null;
  SalaryMin?: number | null;
  SalaryMax?: number | null;
  SkillsReq?: string | null;
  MandatorySkillsReq?: string | null;
  JobDescription?: string | null;
  KeyResponsibilities?: string | null;
  PreferredKeywords?: string | null;
  TargetDomainExperience?: string | null;
}

export interface CVMatchRequest {
  cv_text: string;
}

export interface CVProcessingResponse {
  message: string;
  cv_key: string;
  status: 'processing' | 'completed' | 'failed';
  progress?: number;
}

export interface MandatoryFailure {
  requirement: string;
  details: string;
  severity: 'HIGH' | 'CRITICAL' | string;
}

export interface RequirementEvaluation {
  requirement: string;
  score: number;
  matched: boolean;
  evidence: string;
}

export interface ComponentBreakdown {
  role: number;
  skills: number;
  experience: number;
  education: number;
  domain: number;
  technology: number;
  certification: number;
  responsibilities: number;
}

export interface JobMatchScore {
  job_id: number | string;
  job_title: string;
  department_name?: string | null;
  overall_score: number;
  component_scores: ComponentBreakdown;
  mandatory_fails: MandatoryFailure[];
  requirement_evaluations: RequirementEvaluation[];
  ranking_reason: string;
  llm_reason?: string | null;
  inferred_skills?: string[];
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
}

export interface CandidateMatchAnalysis {
  scan_id: string;
  parsed_at: string;
  best_match?: JobMatchScore | null;
  suitable_openings: JobMatchScore[];
  unsuitable_openings?: JobMatchScore[];
}

export interface EnrichedJobEvaluation extends JobMatchScore {
  llm_reason: string;
  inferred_skills: string[];
  semantic_score_boost: number;
  classification: 'HIGH' | 'MEDIUM' | 'LOW' | string;
}

export interface EnrichedCandidateAnalysis {
  scan_id: string;
  parsed_at: string;
  best_match?: EnrichedJobEvaluation | null;
  suitable_openings: EnrichedJobEvaluation[];
  unsuitable_openings: EnrichedJobEvaluation[];
  llm_model_used: string;
}

export interface CVUploadResponse {
  scan_id: string;
  filename: string;
  parsed_at: string;
  markdown: string;
  match_analysis?: CandidateMatchAnalysis | null;
  enriched_match_analysis?: EnrichedCandidateAnalysis | null;
  [key: string]: any;
}

export interface HRReviewRequest {
  scan_id: string;
  job_id: number;
  corrected_score: number;
  corrected_classification: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  feedback_notes?: string | null;
}

export interface TrainingExample {
  scan_id: string;
  job_id: number;
  cv_text: string;
  job_requirements: Record<string, any>;
  original_llm_analysis: {
    llm_reason: string;
    inferred_skills: string[];
  };
  original_score: number;
  original_classification: string;
  hr_corrected_score: number;
  hr_corrected_classification: string;
  hr_feedback?: string | null;
  timestamp: string;
}

export interface MatchComponentWeights {
  role: number;
  skills: number;
  experience: number;
  education: number;
  domain: number;
  technology: number;
  certification: number;
  responsibilities: number;
}

export interface MatchEngineConfigResponse {
  MATCH_HIGH_THRESHOLD: number;
  MATCH_MEDIUM_THRESHOLD: number;
  MANDATORY_FAILURE_PENALTY_PER_ITEM: number;
  MAX_SCORE_ON_MANDATORY_FAILURE: number;
  LLM_SEMANTIC_WEIGHT: number;
  MAX_LLM_BOOST: number;
  LLM_SKIP_MARGIN_THRESHOLD: number;
  LLM_SKIP_COVERAGE_THRESHOLD: number;
  MATCH_COMPONENT_WEIGHTS: MatchComponentWeights;
}

export interface MatchEngineConfigUpdate {
  MATCH_HIGH_THRESHOLD?: number;
  MATCH_MEDIUM_THRESHOLD?: number;
  MANDATORY_FAILURE_PENALTY_PER_ITEM?: number;
  MAX_SCORE_ON_MANDATORY_FAILURE?: number;
  LLM_SEMANTIC_WEIGHT?: number;
  MAX_LLM_BOOST?: number;
  LLM_SKIP_MARGIN_THRESHOLD?: number;
  LLM_SKIP_COVERAGE_THRESHOLD?: number;
  MATCH_COMPONENT_WEIGHTS?: Partial<MatchComponentWeights>;
}

export interface BatchCandidateResult {
  candidate_id: number;
  candidate_name: string;
  analysis: EnrichedCandidateAnalysis;
}

export interface BatchMatchResponse {
  message: string;
  matches: BatchCandidateResult[];
}

export interface BatchProgressMessage {
  status: string;
  processed?: number;
  total?: number;
  current_cv?: string;
  message?: string;
}

export interface SystemHealthResponse {
  status: string;
  version: string;
  database: string;
  ollama_llm: string;
}

export interface LlmHealthResponse {
  status: string;
  model_configured?: string;
  model_available?: boolean;
  available_models?: string[];
  message?: string;
  error?: string;
}
