import { getHiringRiskPresentation } from '../utils/hiringRisk';
import { getHierarchyValidationState } from '../utils/hierarchyValidation';
import { HiringRisk } from '../types/api';
import { getProcessingProvenanceRows } from '../utils/processingProvenance';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

assertEquals(getHierarchyValidationState(true), 'VALID');
assertEquals(getHierarchyValidationState(false), 'INVALID');
assertEquals(getHierarchyValidationState(null), 'UNAVAILABLE');
assertEquals(getHierarchyValidationState(undefined), 'UNAVAILABLE');

const risk: HiringRisk = {
  risk_code: 'MISSING_MANDATORY_SKILL',
  category: 'Skills',
  severity: 'CRITICAL',
  title: '',
  explanation: 'A mandatory vacancy skill is missing.',
  evidence: ['Missing mandatory skills: SAP', 'Missing mandatory skills: SAP', '  '],
  source: 'RequirementEvaluator',
  requires_manual_review: true,
};

assertEquals(getHiringRiskPresentation(risk), {
  key: 'MISSING_MANDATORY_SKILL',
  title: 'MISSING_MANDATORY_SKILL',
  category: 'Skills',
  source: 'RequirementEvaluator',
  evidence: ['Missing mandatory skills: SAP'],
});

const legacyRows = getProcessingProvenanceRows({ scan_id: 'legacy', filename: 'legacy.pdf', parsed_at: '', markdown: '' });
assertEquals(legacyRows.length, 7);
assertEquals(legacyRows.find(({ key }) => key === 'hiring_risk_prompt_version')?.value, 'default-1.0.0 available after reprocess');
assertEquals(legacyRows.find(({ key }) => key === 'hiring_risk_prompt_identity')?.value, 'Default prompt identity recorded after reprocess');

const explicitlyMissingRows = getProcessingProvenanceRows({
  scan_id: 'missing',
  filename: 'missing.pdf',
  parsed_at: '',
  markdown: '',
  hiring_risk_prompt_version: 'missing',
  hiring_risk_prompt_identity: 'missing',
});
assertEquals(explicitlyMissingRows.find(({ key }) => key === 'hiring_risk_prompt_version')?.value, 'default-1.0.0 available after reprocess');

const currentRows = getProcessingProvenanceRows({
  scan_id: 'current',
  filename: 'current.pdf',
  parsed_at: '',
  markdown: '',
  matching_version: '2.1.0',
  llm_model_version: 'llama3.2:3b',
});
assertEquals(currentRows.find(({ key }) => key === 'matching_version')?.value, '2.1.0');
assertEquals(currentRows.find(({ key }) => key === 'llm_model_version')?.value, 'llama3.2:3b');
