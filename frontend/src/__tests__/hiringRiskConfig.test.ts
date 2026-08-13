import { applyMatchUpdate, toMatchEngineConfig } from '../services/configService';
import { UnifiedRuleConfig } from '../types/api';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

const activeConfig = {
  version: '2.0',
  description: 'Active configuration',
  last_updated: '2026-08-13T00:00:00Z',
  global_confidence_tiers: {},
  fields: {},
  scoring: {
    match: {
      scoring_parameters: {
        match_high_threshold: 70,
        match_medium_threshold: 40,
        mandatory_failure_penalty: 20,
        max_score_on_failure: 60,
        llm_semantic_weight: 0.15,
        max_llm_boost: 15,
        component_weights: {
          role: 0.15,
          skills: 0.25,
          experience: 0.15,
          education: 0.1,
          domain: 0.15,
          technology: 0.1,
          certification: 0.05,
          responsibilities: 0.05,
        },
      },
    },
    prefilter: {},
    taxonomy: {},
    resume_quality: {},
    domain_embedding: {},
  },
  workflow: {},
  hiring_risks: {
    policies: {
      DOMAIN_MISMATCH: {
        enabled: true,
        severity: 'HIGH',
        manual_review: false,
        category: 'Domain',
        title: null,
        source: 'CrossDomainGuard',
      },
    },
  },
} as UnifiedRuleConfig;

assertEquals(toMatchEngineConfig(activeConfig).HIRING_RISK_POLICIES, activeConfig.hiring_risks.policies);

const updatedPolicies = {
  ...activeConfig.hiring_risks.policies,
  DOMAIN_MISMATCH: {
    ...activeConfig.hiring_risks.policies.DOMAIN_MISMATCH,
    enabled: false,
    manual_review: true,
  },
};
const nextConfig = applyMatchUpdate(activeConfig, { HIRING_RISK_POLICIES: updatedPolicies }, 'ui-test');

assertEquals(nextConfig.version, 'ui-test');
assertEquals(nextConfig.hiring_risks.policies, updatedPolicies);
assertEquals(nextConfig.scoring, activeConfig.scoring);
