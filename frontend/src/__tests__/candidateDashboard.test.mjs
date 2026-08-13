import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(root, 'app/candidates/[id].tsx'), 'utf8');

assert.match(source, /title="CV Intelligence Dashboard"/, 'The candidate page must lead with the compact intelligence dashboard.');

for (const tab of ['Overview', 'Skills', 'Experience', 'Education', 'Matches', 'Risks', 'CV']) {
  assert.match(source, new RegExp(`\\['[^']+', '${tab}'\\]`), `The ${tab} tab must remain available.`);
}

for (const summaryField of ['Overall Match', 'Recommendation', 'Experience', 'Skills Match', 'Domain', 'Top Strength', 'Main Concern']) {
  assert.match(source, new RegExp(`>${summaryField}<`), `The five-second summary must include ${summaryField}.`);
}

for (const disclosure of ['View All Skills', 'View Full Timeline', 'View All Matches', 'View Full Reasoning', 'View Full CV']) {
  assert.match(source, new RegExp(disclosure), `Progressive disclosure must include ${disclosure}.`);
}

assert.match(source, /lg:flex-row/, 'Desktop sections must use responsive multi-column layouts.');
assert.match(source, /technicalDetailsExpanded/, 'Technical details must remain collapsed by default.');

for (const technicalField of ['RRF Score', 'Calibration Version', 'Taxonomy Path', 'Stage 0 Compatible', 'Stage 1 Compatible']) {
  assert.match(source, new RegExp(technicalField), `${technicalField} must remain available in technical details.`);
}

assert.doesNotMatch(source, /type TabType = [^;]*processing/, 'Processing must not occupy a primary recruiter tab.');

console.log('Candidate dashboard contracts passed.');
