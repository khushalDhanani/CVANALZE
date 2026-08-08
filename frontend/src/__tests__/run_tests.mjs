// Standalone test runner for Canonical Vacancy Match Status logic

function normalizeCanonicalMatchStatus(rawStatus) {
  if (!rawStatus) return 'NO_STRONG_MATCH';

  const s = String(rawStatus).trim().toUpperCase();

  if (s === 'MATCHED' || s === 'HIGH' || s === 'STRONG' || s === 'HIGHLY RECOMMENDED' || s === 'HIRE') {
    return 'MATCHED';
  }
  if (s === 'POTENTIAL_MATCH' || s === 'MEDIUM' || s === 'POTENTIAL FIT' || s === 'RECOMMENDED' || s === 'CONSIDER') {
    return 'POTENTIAL_MATCH';
  }
  if (s === 'NO_ACTIVE_VACANCIES') {
    return 'NO_ACTIVE_VACANCIES';
  }
  if (s === 'ANALYSIS_NOT_AVAILABLE' || s === 'ANALYSIS UNAVAILABLE' || s === 'N/A') {
    return 'ANALYSIS_NOT_AVAILABLE';
  }
  if (s === 'PROCESSING' || s === 'IN_PROGRESS' || s === 'ANALYZING') {
    return 'PROCESSING';
  }
  if (s === 'FAILED' || s === 'ERROR' || s === 'FAILURE' || s === 'REJECT') {
    return 'FAILED';
  }
  if (s === 'NO_STRONG_MATCH' || s === 'LOW' || s === 'NO_STRONG_VACANCY_MATCH' || s === 'NEEDS FURTHER REVIEW') {
    return 'NO_STRONG_MATCH';
  }

  return 'NO_STRONG_MATCH';
}

function getCanonicalMatchStatusMeta(rawStatus, score) {
  const status = normalizeCanonicalMatchStatus(rawStatus);

  switch (status) {
    case 'MATCHED':
      return {
        status,
        label: 'MATCHED',
        tone: 'success',
        description: 'Candidate strongly fits active vacancy requirements and hierarchy.',
        isProcessing: false,
        isError: false,
      };

    case 'POTENTIAL_MATCH':
      return {
        status,
        label: 'POTENTIAL MATCH',
        tone: 'warning',
        description: 'Candidate shows potential alignment with vacancy; manual review suggested.',
        isProcessing: false,
        isError: false,
      };

    case 'NO_STRONG_MATCH':
      return {
        status,
        label: 'NO STRONG MATCH',
        tone: 'neutral',
        description: 'Candidate analysis succeeded, active vacancies evaluated, but none passed fit criteria.',
        isProcessing: false,
        isError: false,
      };

    case 'NO_ACTIVE_VACANCIES':
      return {
        status,
        label: 'NO ACTIVE VACANCIES',
        tone: 'neutral',
        description: 'Analysis completed, but no active job openings are available in the system for evaluation.',
        isProcessing: false,
        isError: false,
      };

    case 'ANALYSIS_NOT_AVAILABLE':
      return {
        status,
        label: 'ANALYSIS UNAVAILABLE',
        tone: 'danger',
        description: 'Candidate record not found or analysis payload is missing.',
        isProcessing: false,
        isError: true,
      };

    case 'PROCESSING':
      return {
        status,
        label: 'PROCESSING',
        tone: 'info',
        description: 'Candidate analysis is currently running in the background.',
        isProcessing: true,
        isError: false,
      };

    case 'FAILED':
      return {
        status,
        label: 'ANALYSIS FAILED',
        tone: 'danger',
        description: 'Candidate processing encountered an error during evaluation.',
        isProcessing: false,
        isError: true,
      };
  }
}

const tests = [];
function test(name, fn) {
  tests.push({ name, fn });
}

function assertEquals(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg || 'Assertion Failed'}: Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function assertTrue(cond, msg) {
  if (!cond) throw new Error(msg || 'Assertion Failed');
}

// Tests
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

test('15. Frontend does NOT recalculate status from score thresholds', () => {
  const meta = getCanonicalMatchStatusMeta('NO_STRONG_MATCH', 95.0);
  assertEquals(meta.status, 'NO_STRONG_MATCH');
  assertEquals(meta.tone, 'neutral');
  assertEquals(meta.label, 'NO STRONG MATCH');

  const metaMatched = getCanonicalMatchStatusMeta('MATCHED', 40.0);
  assertEquals(metaMatched.status, 'MATCHED');
  assertEquals(metaMatched.tone, 'success');
  assertEquals(metaMatched.label, 'MATCHED');
});

console.log('\n=== RUNNING FRONTEND CANONICAL MATCH STATUS TESTS ===\n');
let passed = 0;
let failed = 0;

for (const t of tests) {
  try {
    t.fn();
    console.log(`  ✓ PASS: ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`  ✗ FAIL: ${t.name}`);
    console.error(`    ${err.message}`);
    failed++;
  }
}

console.log(`\nResults: ${passed} passed, ${failed} failed out of ${tests.length} tests\n`);
if (failed > 0) process.exit(1);
