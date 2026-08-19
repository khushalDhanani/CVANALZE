import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

const card = read('components/ui/Card.tsx');
const pageHeader = read('components/ui/PageHeader.tsx');
const denseRow = read('components/ui/DenseRow.tsx');
const button = read('components/ui/Button.tsx');
const textField = read('components/ui/TextField.tsx');
const sidebar = read('components/ui/Sidebar/SidebarLayout.tsx');
const fieldGrid = read('components/ui/ResponsiveFieldGrid.tsx');
const candidateSummary = read('components/ui/CandidateProfileSummary.tsx');
const scoreBar = read('components/ui/ComponentScoreBar.tsx');

assert.match(card, /rounded-md p-3 border/, 'Cards must retain the shared 12px padding default.');
assert.match(pageHeader, /text-lg sm:text-xl/, 'Page titles must stay within the 18–20px compact scale.');
assert.doesNotMatch(pageHeader, /\bmb-4\b/, 'PageHeader must not own external section spacing.');
assert.match(denseRow, /min-h-\[44px\] sm:min-h-\[38px\]/, 'Rows must preserve mobile touch size and compact desktop height.');
assert.match(button, /min-h-\[44px\] sm:min-h-\[36px\]/, 'Small buttons must preserve mobile touch size and compact desktop height.');
assert.match(textField, /min-h-\[44px\] sm:min-h-\[40px\]/, 'Inputs must preserve mobile touch size and compact desktop height.');
assert.match(sidebar, /w-\[232px\]/, 'Desktop sidebar width must remain at the compact 232px target.');
assert.match(fieldGrid, /gap = Density\.component/, 'Responsive grids must use the shared dynamic density token.');
assert.doesNotMatch(fieldGrid, /isNarrow \? 'gap-2'/, 'Responsive grids must not combine class and inline gaps.');
assert.doesNotMatch(candidateSummary, /<Card className="mb-4/, 'Shared candidate cards must not own external margins.');
assert.doesNotMatch(scoreBar, /\bmy-2\b/, 'Shared score bars must not own external margins.');

console.log('Compact density contracts passed.');
