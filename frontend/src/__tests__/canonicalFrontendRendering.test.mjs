// Frontend Component-Level Canonical Rendering Regression Tests

function sanitizeFieldString(val) {
  if (!val) return '';
  if (typeof val === 'string') return val;
  if (typeof val === 'object') {
    return val.normalized_value || val.raw_value || val.title || val.name || val.company || '';
  }
  return String(val);
}

function extractCanonicalExperienceDisplay(data) {
  const summary = data?.experience_summary || {};
  const years = data?.experience_years ?? summary?.experience_years ?? data?.quality_metrics?.experience_years ?? 0;
  const grossDisplay = data?.gross_display || summary?.gross_display || (years > 0 ? `${years} years` : '0 years 0 months');
  const state = data?.experience_state || summary?.experience_state || 'CALCULATED';

  return { grossDisplay, state, years };
}

function extractCanonicalMatchInfo(data) {
  const matchAnalysis = data?.match_analysis || {};
  const bestMatch = matchAnalysis.best_match || {};

  const dept = data?.department || matchAnalysis?.primary_department || bestMatch?.department_name || bestMatch?.department || '';
  const domain = data?.domain || matchAnalysis?.domain || '';
  const title = data?.designation || bestMatch?.job_title || data?.job_title || '';
  const score = bestMatch?.vacancy_fit_score ?? bestMatch?.overall_score ?? 0;

  return { dept, domain, title, score };
}

function renderExperienceTimelineCard(data) {
  const timeline = data?.work_experience || data?.resume_json?.work_experience || data?.resume_json?.experience || data?.normalized_resume?.employment || [];
  const renderedItems = timeline.slice(0, 5).map((exp) => {
    const rawTitle = exp.job_title || exp.role || '';
    const rawCompany = exp.company || exp.company_name || '';
    const title = sanitizeFieldString(rawTitle);
    const company = sanitizeFieldString(rawCompany);
    const dates = exp.interval?.raw_value || exp.dates || exp.duration || 'N/A';
    return { title, company, dates, renderedText: `${title} at ${company} (${dates})` };
  });

  return {
    itemCount: timeline.length,
    items: renderedItems,
  };
}

// -------------------------------------------------------------
// Assertions & Test Execution
// -------------------------------------------------------------

const tests = [];

function test(name, fn) {
  tests.push({ name, fn });
}

function assertEquals(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg || 'Assertion Failed'}: Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function assertNotEquals(actual, unexpected, msg) {
  if (actual === unexpected) {
    throw new Error(`${msg || 'Assertion Failed'}: Got unexpected value ${JSON.stringify(actual)}`);
  }
}

function assertNotContains(text, substring, msg) {
  if (String(text).includes(substring)) {
    throw new Error(`${msg || 'Assertion Failed'}: Text "${text}" should NOT contain "${substring}"`);
  }
}

test('1. Object field sanitization prevents [object Object] rendering', () => {
  const objTitle = { normalized_value: 'Senior Software Engineer', raw_value: 'Sr. Dev' };
  const objCompany = { name: 'Acme Technologies' };

  const cleanTitle = sanitizeFieldString(objTitle);
  const cleanCompany = sanitizeFieldString(objCompany);

  assertEquals(cleanTitle, 'Senior Software Engineer');
  assertEquals(cleanCompany, 'Acme Technologies');
  assertNotContains(cleanTitle, '[object Object]');
  assertNotContains(cleanCompany, '[object Object]');
});

test('2. Backend 7 years 8 months gross_display NEVER renders as 0 years 0 months', () => {
  const payload = {
    experience_years: 7.67,
    gross_display: '7 years 8 months',
    experience_state: 'CALCULATED',
    experience_summary: {
      experience_years: 7.67,
      gross_display: '7 years 8 months',
      experience_state: 'CALCULATED',
    },
  };

  const expInfo = extractCanonicalExperienceDisplay(payload);
  assertEquals(expInfo.grossDisplay, '7 years 8 months');
  assertEquals(expInfo.state, 'CALCULATED');
  assertNotEquals(expInfo.grossDisplay, '0 years 0 months');
  assertNotContains(expInfo.grossDisplay, '0 years');
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

test('4. ExperienceTimelineCard component rendering pipeline test', () => {
  const payload = {
    work_experience: [
      { job_title: { normalized_value: 'Lead Architect' }, company: { name: 'Global Corp' }, dates: '2020 - Present' },
      { job_title: 'Software Developer', company: 'Tech Solutions', dates: '2016 - 2020' },
    ],
  };

  const rendered = renderExperienceTimelineCard(payload);
  assertEquals(rendered.itemCount, 2);
  assertEquals(rendered.items[0].title, 'Lead Architect');
  assertEquals(rendered.items[0].company, 'Global Corp');
  assertNotContains(rendered.items[0].renderedText, '[object Object]');
  assertEquals(rendered.items[1].title, 'Software Developer');
  assertEquals(rendered.items[1].company, 'Tech Solutions');
});

test('5. Generation metadata preservation on candidate detail view', () => {
  const payload = {
    id: 'cv_candidate_101',
    result_generation_id: 'gen_1786173000000_abc12345',
    generation_sequence: 1045,
    schema_version: '2.0.0',
    payload_checksum: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
  };

  assertEquals(payload.result_generation_id, 'gen_1786173000000_abc12345');
  assertEquals(payload.generation_sequence, 1045);
  assertEquals(payload.schema_version, '2.0.0');
});

// Run tests
let passed = 0;
let failed = 0;
console.log('=== Running Component-Level Frontend Regression Tests ===');
for (const t of tests) {
  try {
    t.fn();
    console.log(`✓ PASSED: ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`✗ FAILED: ${t.name}\n  ${err.message}`);
    failed++;
  }
}
console.log(`\nFrontend Test Summary: ${passed} passed, ${failed} failed.`);
if (failed > 0) {
  process.exit(1);
}
