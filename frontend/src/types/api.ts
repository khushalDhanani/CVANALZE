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
  status: 'processing' | 'completed' | 'failed' | 'FAILED' | string;
  progress?: number;
  stage?: string | null;
  failed_step?: string | null;
  error_details?: string | null;
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
  score?: number;
  recommendation?: string | null;
  component_scores: ComponentBreakdown;
  mandatory_fails: MandatoryFailure[];
  requirement_evaluations: RequirementEvaluation[];
  ranking_reason: string;
  llm_reason?: string | null;
  inferred_skills?: string[];
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  retrieval_source?: 'keyword' | 'vector' | 'both' | string;
  vector_score?: number | null;
}


export interface CandidateMatchAnalysis {
  scan_id: string;
  parsed_at: string;
  full_name?: string | null;
  candidate_name?: string | null;
  best_match?: JobMatchScore | null;
  suitable_openings: JobMatchScore[];
  unsuitable_openings?: JobMatchScore[];
}

export interface EnrichedJobEvaluation extends JobMatchScore {
  llm_reason: string;
  inferred_skills: string[];
  semantic_score_boost: number;
  classification: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  retrieval_source?: 'keyword' | 'vector' | 'both' | string;
  vector_score?: number | null;
}

export interface EnrichedCandidateAnalysis {
  scan_id?: string;
  parsed_at?: string;
  full_name?: string | null;
  candidate_name?: string | null;
  primary_department?: string;
  recommended_department?: string;
  professional_domain?: string;
  strengths?: string[];
  suitable_job_roles?: string[];
  has_genuine_match?: boolean;
  active_vacancy_summary?: string;
  ai_career_summary?: string;
  best_match?: EnrichedJobEvaluation | null;
  suitable_openings: EnrichedJobEvaluation[];
  unsuitable_openings?: EnrichedJobEvaluation[];
  llm_model_used?: string;
  llm_skipped?: boolean;
}

export interface CVUploadResponse {
  scan_id: string;
  filename: string;
  parsed_at: string;
  markdown: string;
  full_name?: string | null;
  candidate_name?: string | null;
  email?: string | null;
  phone?: string | null;
  name_confidence?: number | null;
  name_extraction_source?: string | null;
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
  pg_database?: string;
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

export interface CandidateSummary {
  id: string;
  filename: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  parsed_at?: string;
  page_count?: number;
  is_scanned?: boolean;
  ocr_applied?: boolean;
  primary_department?: string | null;
  best_match?: {
    job_title?: string;
    department?: string;
    score?: number;
    classification?: string;
    recommendation?: string;
  };
}

export interface CacheAnalyticsResponse {
  global_metrics: {
    total_hits: number;
    total_misses: number;
    overall_hit_ratio: number;
    llm_calls_prevented: number;
    db_queries_prevented: number;
  };
  per_namespace: Record<
    string,
    {
      hits: number;
      misses: number;
      hit_ratio: number;
    }
  >;
  system_stats: {
    redis: {
      status: string;
      used_memory_human?: string;
      used_memory_bytes?: number;
      total_keys?: number;
    };
    memory_cache: {
      items_count: number;
      max_size: number;
    };
  };
}

export interface CandidateSearchOptions {
  query?: string;
  department?: string;
  min_experience?: number;
  max_experience?: number;
  limit?: number;
}

export interface CandidateSearchResponse {
  total_found: number;
  search_mode: string;
  query?: string;
  candidates: CandidateSummary[];
}

export interface CareerTransition {
  target_role: string;
  transferable_skills: string[];
  feasibility_score: number;
  growth_note: string;
}

export interface MissingQualification {
  requirement: string;
  impact: string;
  type: string;
  actionable_suggestion?: string;
}

export interface CandidateRecommendationsResponse {
  candidate_id: string;
  full_name?: string;
  primary_department?: string;
  strengths?: string[];
  overall_match_confidence?: number;
  actionable_suggestions?: string[];
  best_vacancies?: any[];
  related_skills?: string[];
  missing_qualifications?: MissingQualification[];
  recommended_certifications?: string[];
  career_transitions?: CareerTransition[];
  talent_pools?: string[];
}

export interface SkillGapInsight {
  skill: string;
  market_rarity: string;
  recommendation: string;
}

export interface VacancyRecommendationsResponse {
  vacancy_id: string;
  job_title?: string;
  department?: string;
  top_candidate_matches?: any[];
  similar_candidates?: any[];
  skill_gap_insights?: SkillGapInsight[];
  talent_pools?: string[];
}



