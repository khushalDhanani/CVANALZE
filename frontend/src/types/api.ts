// API Type Definitions for CV Analyzer Backend Integration

export interface JobOpening {
  id: string;
  title: string;
  department: string;
  required_skills: string[];
  preferred_keywords: string[];
  min_experience_years?: number | null;
  max_experience_years?: number | null;
  min_ctc?: number | null;
  max_ctc?: number | null;
  preferred_gender?: string | null;
  company_name?: string | null;
  location_name?: string | null;
  
  job_description?: string | null;
  responsibilities?: string | null;
  education?: string | null;
  certifications?: string | null;

  vacancy_id?: number | null;
  job_profile_id?: number | null;
  business_group_id?: number | null;
  business_group_name?: string | null;
  company_id?: number | null;
  company_name_db?: string | null;
  location_id?: number | null;
  location_name_db?: string | null;
  main_department_id?: number | null;
  main_department_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  designation_id?: number | null;
  designation_name?: string | null;

  domain?: string | null;
  job_family?: string | null;
  status?: string | null;
  is_active?: boolean | null;
  vacancy_status?: string | null;
}

export interface BusinessGroupItem {
  id: number;
  name: string;
}

export interface CompanyItem {
  id: number;
  name: string;
  code?: string;
  business_group_id?: number;
}

export interface LocationItem {
  id: number;
  name: string;
  code?: string;
  company_id?: number;
}

export interface MainDepartmentItem {
  id: number;
  name: string;
}

export interface DepartmentItem {
  id: number;
  name: string;
  company_id?: number;
  main_department_id?: number;
}

export interface DesignationItem {
  id: number;
  name: string;
  company_id?: number;
  department_id?: number;
  main_department_id?: number;
}

export interface OrganizationSelection {
  business_group_id?: number | null;
  company_id?: number | null;
  location_id?: number | null;
  main_department_id?: number | null;
  department_id?: number | null;
  designation_id?: number | null;
}

export interface HierarchyValidationResult {
  is_valid: boolean;
  errors: string[];
  details: Record<string, any>;
}


export interface CVMatchRequest {
  cv_text: string;
}

export interface CVProcessingResponse {
  message: string;
  cv_key: string;
  status: 'processing' | 'completed' | 'COMPLETED' | 'failed' | 'FAILED' | string;
  progress?: number;
  stage?: string | null;
  is_complete?: boolean;
  failed_step?: string | null;
  error_details?: string | null;
  stage_durations_ms?: Record<string, number>;
}

export interface DualEvidence {
  cv_evidence: string;
  vacancy_evidence: string;
}

export interface MandatoryFailure {
  requirement: string;
  details: string;
  severity: 'HIGH' | 'CRITICAL' | string;
}

export interface MandatoryFailureDetails {
  requirement_id: string;
  description: string;
  reason: string;
  score_impact: number;
}

export interface RequirementEvaluation {
  requirement_id?: string;
  description?: string;
  requirement?: string;
  score?: number;
  tier?: 'MANDATORY' | 'PREFERRED' | 'OPTIONAL' | string;
  status?: 'SATISFIED' | 'PARTIALLY_SATISFIED' | 'FAILED' | string;
  matched?: boolean;
  evidence?: DualEvidence | string;
  failure_reason?: string | null;
}

export type CanonicalVacancyMatchStatus =
  | 'MATCHED'
  | 'POTENTIAL_MATCH'
  | 'NO_STRONG_MATCH'
  | 'NO_ACTIVE_VACANCIES'
  | 'ANALYSIS_NOT_AVAILABLE'
  | 'PROCESSING'
  | 'FAILED';

export interface VacancyFitScoreBreakdown {
  hierarchy_score: number;
  designation_role_score: number;
  skills_score: number;
  experience_score: number;
  semantic_similarity_score: number;
  overall_fit_score: number;
  hierarchy_mismatch_penalty: number;
  is_hierarchy_valid: boolean;
  match_status: string;
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
  department?: string | null;
  vacancy_id?: number | string | null;
  job_profile_id?: number | null;
  company_id?: number | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  overall_score: number;
  score?: number;
  vacancy_fit_score?: number | null;
  vacancy_match_status?: CanonicalVacancyMatchStatus | string | null;
  score_breakdown?: VacancyFitScoreBreakdown | null;
  role_score: number;
  skills_score: number;
  experience_score: number;
  education_score: number;
  domain_score: number;
  technology_score: number;
  certification_score: number;
  responsibilities_score: number;
  coverage: number;
  recommendation?: string | null;
  component_scores: ComponentBreakdown;
  mandatory_fails: MandatoryFailure[];
  mandatory_failures: MandatoryFailureDetails[];
  requirement_evaluations: RequirementEvaluation[];
  mandatory_requirements: RequirementEvaluation[];
  preferred_requirements: RequirementEvaluation[];
  optional_requirements: RequirementEvaluation[];
  matched_skills: string[];
  missing_skills: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  matched_criteria: string[];
  missing_criteria: string[];
  evidence: Record<string, DualEvidence>;
  confidence: number;
  hr_review_required: boolean;
  reason: string;
  ranking_reason: string;
  llm_reason?: string | null;
  inferred_skills?: string[];
  classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  retrieval_source?: 'keyword' | 'vector' | 'both' | string;
  vector_score?: number | null;
  career_transition_detected: boolean;
  career_transition_note?: string | null;
  domain_mismatch_capped: boolean;
  domain_mismatch_reason?: string | null;
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
  status?: string | null;
  progress?: number | null;
  stage?: string | null;
  is_complete?: boolean | null;
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
  rejection_policy_note: string;
  llm_model_used?: string;
  llm_skipped?: boolean;
  match_status?: CanonicalVacancyMatchStatus | string | null;
  hiring_recommendation?: CanonicalVacancyMatchStatus | string | null;
  normalized_resume?: any;
}

export interface OptimizedCandidateProfile {
  core_skills?: string[];
  inferred_skills?: string[];
  relevant_experience_years?: number | null;
  education_domains?: string[];
  certifications?: string[];
  current_role?: string | null;
  professional_domains?: string[];
  recommended_department?: string | null;
  professional_domain?: string | null;
  strengths?: string[];
  suitable_job_roles?: string[];
}

export interface OptimizedVacancyMatch {
  vacancy_id: number | string;
  semantic_reason?: string;
  inferred_skills?: string[];
  matched_skills?: string[];
  missing_critical?: string[];
  semantic_fit_score?: number;
  career_transition_detected?: boolean;
  career_transition_note?: string | null;
}

export interface FieldConfidenceTiers {
  name?: 'HIGH' | 'MEDIUM' | 'LOW' | string | null;
  location?: 'HIGH' | 'MEDIUM' | 'LOW' | string | null;
  job_title?: 'HIGH' | 'MEDIUM' | 'LOW' | string | null;
  company_name?: 'HIGH' | 'MEDIUM' | 'LOW' | string | null;
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
  location?: string | null;
  job_title?: string | null;
  company_name?: string | null;
  name_confidence?: number | null;
  name_confidence_tier?: string | null;
  location_confidence_tier?: string | null;
  job_title_confidence_tier?: string | null;
  company_name_confidence_tier?: string | null;
  field_confidence?: Record<string, number | null> | null;
  field_confidence_tiers?: FieldConfidenceTiers | null;
  name_extraction_source?: string | null;
  match_analysis?: CandidateMatchAnalysis | null;
  enriched_match_analysis?: EnrichedCandidateAnalysis | null;
  [key: string]: any;
}

export interface HRReviewRequest {
  scan_id: string;
  job_id: number | string;
  corrected_score?: number | null;
  corrected_classification?: 'HIGH' | 'MEDIUM' | 'LOW' | string | null;
  feedback_notes: string;
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
  location?: string | null;
  job_title?: string | null;
  company_name?: string | null;
  name_confidence_tier?: string | null;
  location_confidence_tier?: string | null;
  job_title_confidence_tier?: string | null;
  company_name_confidence_tier?: string | null;
  field_confidence?: Record<string, number | null> | null;
  field_confidence_tiers?: FieldConfidenceTiers | null;
  parsed_at?: string;
  page_count?: number;
  is_scanned?: boolean;
  ocr_applied?: boolean;
  primary_department?: string | null;
  similarity_score?: number | null;
  search_mode?: string;
  match_status?: CanonicalVacancyMatchStatus | string | null;
  best_match?: {
    job_title?: string;
    department?: string;
    score?: number;
    vacancy_fit_score?: number | null;
    vacancy_match_status?: CanonicalVacancyMatchStatus | string | null;
    match_status?: CanonicalVacancyMatchStatus | string | null;
    classification?: string;
    recommendation?: string;
    domain_mismatch_capped?: boolean;
    domain_mismatch_reason?: string | null;
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
  location?: string;
  skills?: string[];
  education?: string;
  status?: string;
  min_similarity?: number;
  limit?: number;
}

export interface CandidateSearchResponse {
  total_found: number;
  search_mode: string;
  query?: string;
  candidates: CandidateSummary[];
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
  best_vacancies?: any[];
  related_skills?: string[];
  missing_qualifications?: MissingQualification[];
  recommended_certifications?: string[];
  talent_pools?: string[];
  hiring_recommendation?: CanonicalVacancyMatchStatus | 'Highly Recommended' | 'Recommended' | 'Potential Fit' | 'Needs Further Review' | 'HIRE' | 'CONSIDER' | 'REJECT' | string;
  role_department_fit?: string;
  interview_focus_areas?: string[];
  risk_flags?: string[];
  experience_assessment?: string;
  technical_vs_functional_fit?: string;
  next_steps_for_interviewer?: string[];
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


// ===== Talent Knowledge Graph Types =====
export interface GraphNode {
  id: string;
  type: 'Candidate' | 'Skill' | 'Company' | 'Vacancy' | 'Department' | string;
  label: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: 'HAS_SKILL' | 'WORKED_AT' | 'MATCHES' | 'SEMANTICALLY_SIMILAR' | 'BELONGS_TO' | 'REQUIRES_SKILL' | string;
  properties: Record<string, any>;
}

export interface CandidateGraphResponse {
  candidate_id: string;
  full_name: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface VacancyGraphResponse {
  vacancy_id: string;
  title: string;
  department: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface SkillGraphResponse {
  skill: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics: {
    candidate_supply_count: number;
    vacancy_demand_count: number;
    semantic_cluster_count: number;
  };
}

export interface RecruitmentAnalyticsGraphResponse {
  graph_summary: {
    total_candidates: number;
    total_vacancies: number;
    total_skills_tracked: number;
    total_departments: number;
    total_graph_nodes: number;
    total_graph_edges: number;
  };
  top_candidate_skills: { skill: string; candidate_count: number; }[];
  department_distribution: { department: string; candidate_count: number; }[];
}

// ===== Domain Knowledge Types =====
export interface DomainEquivalentRequest {
  term: string;
  category: string;
  threshold?: number;
  limit?: number;
}

export interface DomainEquivalent {
  term: string;
  similarity_score: number;
}

export interface DomainEquivalentResponse {
  term: string;
  category: string;
  equivalents: DomainEquivalent[];
}

// ===== Vector DB Types =====
export interface VectorDbStatusResponse {
  pgvector_enabled: boolean;
  pg_database_connected: boolean;
  embedding_model: string;
  candidate_embeddings_count: number;
  vacancy_embeddings_count: number;
  semantic_retrieval_top_n: number;
}

export interface VectorDbSyncResponse {
  message: string;
  status: string;
}

// ===== Talent Pools Types =====
export interface TalentPoolCandidate {
  candidate_id: string;
  full_name: string;
  skills: string[];
  experience_years: number | null;
}

export interface TalentPool {
  pool_name: string;
  candidate_count: number;
  sample_candidates: TalentPoolCandidate[];
}

export interface TalentPoolsResponse {
  total_pools: number;
  talent_pools: TalentPool[];
}

// ===== Experience Gap Analysis Types =====
export type EmploymentEntityResolution =
  | 'PARENT_EMPLOYMENT'
  | 'INTERNAL_ROLE'
  | 'DEPUTATION'
  | 'PROMOTION_TRANSFER'
  | 'INDEPENDENT_CONCURRENT_ROLE'
  | 'DUPLICATE'
  | 'INVALID_HEADING';

export interface ChildAssignmentItem {
  assignment_id: string;
  title_or_subrole: string;
  assignment_type: 'DEPUTATION' | 'PROMOTION' | 'TRANSFER' | 'INTERNAL_ASSIGNMENT' | 'SUB_ROLE' | string;
  entity_resolution: EmploymentEntityResolution;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  details?: string[];
}

export interface CanonicalJobItem {
  job_id: string;
  parent_company: string;
  primary_title: string;
  employment_type: string;
  entity_resolution: EmploymentEntityResolution;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  duration_months: number;
  date_confidence?: 'EXACT' | 'MONTH_ONLY' | 'YEAR_ONLY' | 'UNKNOWN' | string;
  responsibilities?: string[];
  child_assignments?: ChildAssignmentItem[];
}

export interface ExperienceGapItem {
  gap_id: string;
  category?: 'EMPLOYMENT_GAP' | string;
  coverage_status:
    | 'UNEXPLAINED'
    | 'EDUCATION_COVERED'
    | 'FREELANCE_COVERED'
    | 'CONTRACT_COVERED'
    | 'CAREER_TRANSITION'
    | 'TIMELINE_UNCERTAINTY'
    | string;
  boundary_reliability?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  start_date?: string | null;
  end_date?: string | null;
  duration_days: number;
  duration_months: number;
  preceding_role?: string | null;
  following_role?: string | null;
  description: string;
  hr_review_indicator: boolean;
  hr_review_reason?: string | null;
}

export interface ExperienceTimelineNodeItem {
  record_id: string;
  company: string;
  job_title: string;
  employment_type: string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  duration_months: number;
  precision?: string;
  date_confidence?: 'EXACT' | 'MONTH_ONLY' | 'YEAR_ONLY' | 'UNKNOWN' | string;
  responsibilities?: string[];
}

export interface ConcurrentRoleClusterItem {
  cluster_id: string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  duration_months: number;
  roles_count: number;
  child_nodes: ExperienceTimelineNodeItem[];
}

export interface TimelineEventItem {
  event_id: string;
  event_type:
    | 'EMPLOYMENT_PERIOD'
    | 'CONCURRENT_CLUSTER'
    | 'EMPLOYMENT_GAP'
    | 'COVERED_GAP'
    | 'TIMELINE_UNCERTAINTY'
    | string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  duration_months: number;
  node?: ExperienceTimelineNodeItem | null;
  cluster?: ConcurrentRoleClusterItem | null;
  gap?: ExperienceGapItem | null;
}

export interface ExperienceTimelineSummaryItem {
  total_verified_years: number;
  gross_display: string;
  timeline_start_date?: string | null;
  timeline_end_date?: string | null;
  has_current_employment: boolean;
  concurrent_roles_count: number;
  total_employment_gaps_count: number;
  unexplained_gaps_count: number;
  significant_gaps_count: number;
  total_gap_duration_months: number;
  analysis_confidence: number;
  timeline_uncertainty_score: number;
  hr_review_required: boolean;
  hr_observations?: string[];
}

export interface ExperienceGapAnalysisData {
  summary?: ExperienceTimelineSummaryItem;
  detected_gaps?: ExperienceGapItem[];
  canonical_jobs?: CanonicalJobItem[];
  timeline_nodes?: ExperienceTimelineNodeItem[];
  undated_nodes?: ExperienceTimelineNodeItem[];
  timeline_events?: TimelineEventItem[];
  hr_review_indicators?: string[];
}


