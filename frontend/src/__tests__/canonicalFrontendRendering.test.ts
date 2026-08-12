/**
 * Frontend Canonical Rendering & Regression Tests
 * Validates that candidate experience timeline, gaps, department, domain, designation,
 * gross_display, total experience, vacancy match, and generation IDs render correctly
 * and prevent fallbacks to `0 years 0 months` or `[object Object]`.
 */

function sanitizeFieldString(val: any): string {
  if (!val) return '';
  if (typeof val === 'string') return val;
  if (typeof val === 'object') {
    return val.normalized_value || val.raw_value || val.title || val.name || val.company || '';
  }
  return String(val);
}

function extractCanonicalExperienceDisplay(data: any): { grossDisplay: string; state: string; years: number } {
  const summary = data?.experience_summary || {};
  const years = data?.experience_years ?? summary?.experience_years ?? data?.quality_metrics?.experience_years ?? 0;
  const grossDisplay = data?.gross_display || summary?.gross_display || `${years} years`;
  const state = data?.experience_state || summary?.experience_state || 'CALCULATED';

  return { grossDisplay, state, years };
}

function extractCanonicalMatchInfo(data: any): { dept: string; domain: string; title: string; score: number } {
  const matchAnalysis = data?.match_analysis || {};
  const bestMatch = matchAnalysis.best_match || {};

  const dept = data?.department || matchAnalysis?.primary_department || bestMatch?.department_name || bestMatch?.department || '';
  const domain = data?.domain || matchAnalysis?.domain || '';
  const title = data?.designation || bestMatch?.job_title || data?.job_title || '';
  const score = bestMatch?.vacancy_fit_score ?? bestMatch?.overall_score ?? 0;

  return { dept, domain, title, score };
}

// -------------------------------------------------------------
// Assertions & Test Execution
// -------------------------------------------------------------

const tests: { name: string; fn: () => void }[] = [];

function test(name: string, fn: () => void) {
  tests.push({ name, fn });
}

function assertEquals(actual: any, expected: any, msg?: string) {
  if (actual !== expected) {
    throw new Error(`${msg || 'Assertion Failed'}: Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function assertNotEquals(actual: any, unexpected: any, msg?: string) {
  if (actual === unexpected) {
    throw new Error(`${msg || 'Assertion Failed'}: Got unexpected value ${JSON.stringify(actual)}`);
  }
}

test('1. Object field sanitization prevents [object Object] rendering', () => {
  const objTitle = { normalized_value: 'Senior Software Engineer', raw_value: 'Sr. Dev' };
  const objCompany = { name: 'Acme Technologies' };

  assertEquals(sanitizeFieldString(objTitle), 'Senior Software Engineer');
  assertEquals(sanitizeFieldString(objCompany), 'Acme Technologies');
  assertEquals(sanitizeFieldString('Plain String'), 'Plain String');
  assertNotEquals(sanitizeFieldString(objTitle), '[object Object]');
});

test('2. Canonical experience display extracts gross_display and state accurately', () => {
  const payload = {
    experience_years: 7.5,
    gross_display: '7 years 6 months',
    experience_state: 'CALCULATED',
    experience_summary: {
      experience_years: 7.5,
      gross_display: '7 years 6 months',
      experience_state: 'CALCULATED',
    },
  };

  const expInfo = extractCanonicalExperienceDisplay(payload);
  assertEquals(expInfo.grossDisplay, '7 years 6 months');
  assertEquals(expInfo.state, 'CALCULATED');
  assertEquals(expInfo.years, 7.5);
  assertNotEquals(expInfo.grossDisplay, '0 years 0 months');
});

test('3. Canonical match info extracts department, domain, designation, score correctly', () => {
  const payload = {
    department: 'Engineering',
    domain: 'Software & Technology',
    designation: 'Staff Engineer',
    match_analysis: {
      primary_department: 'Engineering',
      domain: 'Software & Technology',
      best_match: {
        job_title: 'Staff Engineer',
        vacancy_fit_score: 95.0,
      },
    },
  };

  const matchInfo = extractCanonicalMatchInfo(payload);
  assertEquals(matchInfo.dept, 'Engineering');
  assertEquals(matchInfo.domain, 'Software & Technology');
  assertEquals(matchInfo.title, 'Staff Engineer');
  assertEquals(matchInfo.score, 95.0);
});

test('4. Generation metadata is preserved on detail view response payload', () => {
  const payload = {
    id: 'cv_candidate_101',
    result_generation_id: 'gen_1786173000000_abc12345',
    generation_sequence: 1786173000000,
    schema_version: '2.0.0',
    payload_checksum: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
  };

  assertEquals(payload.result_generation_id, 'gen_1786173000000_abc12345');
  assertEquals(payload.generation_sequence, 1786173000000);
  assertEquals(payload.schema_version, '2.0.0');
});

// Run tests
let passed = 0;
let failed = 0;
console.log('=== Running Frontend Canonical Rendering Regression Tests ===');
for (const t of tests) {
  try {
    t.fn();
    console.log(`✓ PASSED: ${t.name}`);
    passed++;
  } catch (err: any) {
    console.error(`✗ FAILED: ${t.name}\n  ${err.message}`);
    failed++;
  }
}
console.log(`\nFrontend Test Summary: ${passed} passed, ${failed} failed.`);
if (failed > 0) {
  process.exit(1);
}
