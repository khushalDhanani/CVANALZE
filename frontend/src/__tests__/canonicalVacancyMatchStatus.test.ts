/**
 * Frontend Canonical Vacancy Match Status Tests
 * Validates that all 7 canonical statuses, normalization, badge metadata,
 * and score breakdown formatting align strictly with backend single source of truth.
 */

import {
  normalizeCanonicalMatchStatus,
  getCanonicalMatchStatusMeta,
  resolveVacancyFitScore,
} from '../components/ui/VacancyMatchStatusBadge';
import { CanonicalVacancyMatchStatus } from '../types/api';

interface TestCase {
  name: string;
  fn: () => void;
}

const tests: TestCase[] = [];

function test(name: string, fn: () => void) {
  tests.push({ name, fn });
}

function assertEquals(actual: any, expected: any, msg?: string) {
  if (actual !== expected) {
    throw new Error(`${msg || 'Assertion Failed'}: Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function assertTrue(condition: boolean, msg?: string) {
  if (!condition) {
    throw new Error(msg || 'Assertion Failed: Expected condition to be true');
  }
}

// -------------------------------------------------------------
// 1. Canonical Status Normalization Tests
// -------------------------------------------------------------

test('1. MATCHED: normalizes canonical MATCHED and legacy HIGH/STRONG/HIRE aliases', () => {
  assertEquals(normalizeCanonicalMatchStatus('MATCHED'), 'MATCHED');
  assertEquals(normalizeCanonicalMatchStatus('HIGH'), 'MATCHED');
  assertEquals(normalizeCanonicalMatchStatus('STRONG'), 'MATCHED');
  assertEquals(normalizeCanonicalMatchStatus('HIGHLY RECOMMENDED'), 'MATCHED');
  assertEquals(normalizeCanonicalMatchStatus('HIRE'), 'MATCHED');
  assertEquals(normalizeCanonicalMatchStatus('matched'), 'MATCHED');
});

test('2. POTENTIAL_MATCH: normalizes canonical POTENTIAL_MATCH and legacy MEDIUM/CONSIDER aliases', () => {
  assertEquals(normalizeCanonicalMatchStatus('POTENTIAL_MATCH'), 'POTENTIAL_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('MEDIUM'), 'POTENTIAL_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('POTENTIAL FIT'), 'POTENTIAL_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('RECOMMENDED'), 'POTENTIAL_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('CONSIDER'), 'POTENTIAL_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('potential_match'), 'POTENTIAL_MATCH');
});

test('3. NO_STRONG_MATCH: normalizes canonical NO_STRONG_MATCH and legacy LOW/NO_STRONG_VACANCY_MATCH aliases', () => {
  assertEquals(normalizeCanonicalMatchStatus('NO_STRONG_MATCH'), 'NO_STRONG_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('LOW'), 'NO_STRONG_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('NO_STRONG_VACANCY_MATCH'), 'NO_STRONG_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('NEEDS FURTHER REVIEW'), 'NO_STRONG_MATCH');
  assertEquals(normalizeCanonicalMatchStatus('NO_SUITABLE_MATCH'), 'NO_STRONG_MATCH');
});

test('4. NO_ACTIVE_VACANCIES: normalizes NO_ACTIVE_VACANCIES cleanly', () => {
  assertEquals(normalizeCanonicalMatchStatus('NO_ACTIVE_VACANCIES'), 'NO_ACTIVE_VACANCIES');
  assertEquals(normalizeCanonicalMatchStatus('no_active_vacancies'), 'NO_ACTIVE_VACANCIES');
});

test('5. ANALYSIS_NOT_AVAILABLE: normalizes ANALYSIS_NOT_AVAILABLE and missing payload aliases', () => {
  assertEquals(normalizeCanonicalMatchStatus('ANALYSIS_NOT_AVAILABLE'), 'ANALYSIS_NOT_AVAILABLE');
  assertEquals(normalizeCanonicalMatchStatus('ANALYSIS UNAVAILABLE'), 'ANALYSIS_NOT_AVAILABLE');
  assertEquals(normalizeCanonicalMatchStatus('N/A'), 'ANALYSIS_NOT_AVAILABLE');
  assertEquals(normalizeCanonicalMatchStatus(null), 'NO_STRONG_MATCH');
  assertEquals(normalizeCanonicalMatchStatus(undefined), 'NO_STRONG_MATCH');
});

test('6. PROCESSING: normalizes in-flight background analysis states', () => {
  assertEquals(normalizeCanonicalMatchStatus('PROCESSING'), 'PROCESSING');
  assertEquals(normalizeCanonicalMatchStatus('IN_PROGRESS'), 'PROCESSING');
  assertEquals(normalizeCanonicalMatchStatus('ANALYZING'), 'PROCESSING');
});

test('7. FAILED: normalizes error/failure states', () => {
  assertEquals(normalizeCanonicalMatchStatus('FAILED'), 'FAILED');
  assertEquals(normalizeCanonicalMatchStatus('ERROR'), 'FAILED');
  assertEquals(normalizeCanonicalMatchStatus('FAILURE'), 'FAILED');
  assertEquals(normalizeCanonicalMatchStatus('REJECT'), 'FAILED');
});

// -------------------------------------------------------------
// 2. Canonical Status Metadata & Visual Tone Tests
// -------------------------------------------------------------

test('8. Metadata: MATCHED has success tone and non-error state', () => {
  const meta = getCanonicalMatchStatusMeta('MATCHED', 88.5);
  assertEquals(meta.status, 'MATCHED');
  assertEquals(meta.label, 'MATCHED');
  assertEquals(meta.tone, 'success');
  assertEquals(meta.isProcessing, false);
  assertEquals(meta.isError, false);
});

test('9. Metadata: POTENTIAL_MATCH has warning tone', () => {
  const meta = getCanonicalMatchStatusMeta('POTENTIAL_MATCH', 62.0);
  assertEquals(meta.status, 'POTENTIAL_MATCH');
  assertEquals(meta.label, 'POTENTIAL MATCH');
  assertEquals(meta.tone, 'warning');
  assertEquals(meta.isProcessing, false);
  assertEquals(meta.isError, false);
});

test('10. Metadata: NO_STRONG_MATCH has neutral tone', () => {
  const meta = getCanonicalMatchStatusMeta('NO_STRONG_MATCH', 35.0);
  assertEquals(meta.status, 'NO_STRONG_MATCH');
  assertEquals(meta.label, 'NO STRONG MATCH');
  assertEquals(meta.tone, 'neutral');
  assertEquals(meta.isProcessing, false);
  assertEquals(meta.isError, false);
});

test('11. Metadata: NO_ACTIVE_VACANCIES has neutral tone and clear description', () => {
  const meta = getCanonicalMatchStatusMeta('NO_ACTIVE_VACANCIES');
  assertEquals(meta.status, 'NO_ACTIVE_VACANCIES');
  assertEquals(meta.label, 'NO ACTIVE VACANCIES');
  assertEquals(meta.tone, 'neutral');
  assertTrue(meta.description.includes('no active job openings'));
});

test('12. Metadata: ANALYSIS_NOT_AVAILABLE has danger tone and isError flag', () => {
  const meta = getCanonicalMatchStatusMeta('ANALYSIS_NOT_AVAILABLE');
  assertEquals(meta.status, 'ANALYSIS_NOT_AVAILABLE');
  assertEquals(meta.label, 'ANALYSIS UNAVAILABLE');
  assertEquals(meta.tone, 'danger');
  assertEquals(meta.isError, true);
});

test('13. Metadata: PROCESSING has info tone and isProcessing flag', () => {
  const meta = getCanonicalMatchStatusMeta('PROCESSING');
  assertEquals(meta.status, 'PROCESSING');
  assertEquals(meta.label, 'PROCESSING');
  assertEquals(meta.tone, 'info');
  assertEquals(meta.isProcessing, true);
  assertEquals(meta.isError, false);
});

test('14. Metadata: FAILED has danger tone and isError flag', () => {
  const meta = getCanonicalMatchStatusMeta('FAILED');
  assertEquals(meta.status, 'FAILED');
  assertEquals(meta.label, 'ANALYSIS FAILED');
  assertEquals(meta.tone, 'danger');
  assertEquals(meta.isError, true);
});

// -------------------------------------------------------------
// 3. Score-Independence & Single Source of Truth Tests
// -------------------------------------------------------------

test('15. Frontend does NOT recalculate status from score thresholds', () => {
  // A candidate with 95% score but hard domain rejection has backend status NO_STRONG_MATCH:
  // Frontend MUST display NO_STRONG_MATCH, not invent 'HIGH MATCH' from the 95% number.
  const meta = getCanonicalMatchStatusMeta('NO_STRONG_MATCH', 95.0);
  assertEquals(meta.status, 'NO_STRONG_MATCH');
  assertEquals(meta.tone, 'neutral');
  assertEquals(meta.label, 'NO STRONG MATCH');

  // A candidate with 40% score classified as MATCHED by hierarchy evaluator:
  // Frontend MUST display MATCHED, not invent 'LOW MATCH'.
  const metaMatched = getCanonicalMatchStatusMeta('MATCHED', 40.0);
  assertEquals(metaMatched.status, 'MATCHED');
  assertEquals(metaMatched.tone, 'success');
  assertEquals(metaMatched.label, 'MATCHED');
});

test('16. resolveVacancyFitScore falls back to overall_score when vacancy_fit_score is explicitly zero', () => {
  const match = { vacancy_fit_score: 0.0, overall_score: 76.4, score: 76.4 };
  assertEquals(resolveVacancyFitScore(match), 76.4);
});

// -------------------------------------------------------------
// Test Runner
// -------------------------------------------------------------

export function runTests(): { passed: number; failed: number; total: number } {
  let passed = 0;
  let failed = 0;

  console.log('\n=== RUNNING FRONTEND CANONICAL MATCH STATUS TESTS ===\n');

  for (const t of tests) {
    try {
      t.fn();
      console.log(`  ✓ PASS: ${t.name}`);
      passed++;
    } catch (err: any) {
      console.error(`  ✗ FAIL: ${t.name}`);
      console.error(`    ${err.message}`);
      failed++;
    }
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed out of ${tests.length} tests\n`);
  return { passed, failed, total: tests.length };
}

// Default export runner
export default runTests;

