import fs from 'node:fs';
import Module, { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(testDirectory, '../utils/runtimeConfig.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const output = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const runtimeModule = new Module(sourcePath);
runtimeModule.filename = sourcePath;
runtimeModule.paths = Module._nodeModulePaths(path.dirname(sourcePath));
runtimeModule._compile(output, sourcePath);

const { nextPollingAttempt, parsePositiveInteger, resolveApiBaseUrl } = runtimeModule.exports;

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

assert(nextPollingAttempt(0, 250) === 1, 'Polling starts with the next attempt.');
assert(nextPollingAttempt(249, 250) === 250, 'The configured final attempt is allowed.');
assert(nextPollingAttempt(250, 250) === null, 'Polling stops at the configured maximum.');
assert(parsePositiveInteger('1200', 10) === 1200, 'Positive integer overrides are accepted.');
assert(parsePositiveInteger('0', 10) === 10, 'Invalid integer overrides use the fallback.');
assert(resolveApiBaseUrl(undefined, 'android', true) === 'http://10.0.2.2:8000', 'Android development uses the emulator host.');
assert(resolveApiBaseUrl(undefined, 'web', true) === 'http://localhost:8000', 'Web development uses loopback.');
assert(resolveApiBaseUrl('https://api.example.com/', 'web', false) === 'https://api.example.com', 'Explicit production URLs are normalized.');

let productionFailure = false;
try {
  resolveApiBaseUrl(undefined, 'web', false);
} catch (error) {
  productionFailure = /EXPO_PUBLIC_API_URL/.test(String(error));
}
assert(productionFailure, 'Production must reject a missing API URL.');

console.log('Runtime configuration tests: passed');
