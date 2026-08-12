const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const read = path => fs.readFileSync(path, 'utf8');
const state = read('static/js/modules/state.js');
const api = read('static/js/modules/api.js');
const ui = read('static/js/modules/ui.js');
const settings = read('static/js/modules/settings.js');
const sync = read('static/js/modules/sync.js');

const errorHelpers = state.slice(0, state.indexOf('// HTML 转义工具'));
const context = { window: {}, AbortController, fetch: () => {} };
vm.createContext(context);
vm.runInContext(errorHelpers, context);

assert.match(
    context.window.formatApiErrorMessage('ServiceUnavailableError: 503 internal payload'),
    /暂时繁忙/
);
assert.doesNotMatch(
    context.window.formatApiErrorMessage('LLM Provider NOT provided model=secret-model'),
    /secret-model/
);
assert.match(api, /finally\s*{[\s\S]*showAnalysisLoading\(false\)/);
assert.match(api, /summaryTask\.isCurrent\(\)/);
assert.match(ui, /renderEnhancedSummary\(details\.summary[\s\S]*databaseSummary:/);
assert.match(settings, /\/book_extensions/);
assert.match(settings, /cfg\.book_extensions[\s\S]*saveConfigPayload\(cfg\)/);
assert.match(api, /function saveConfigPayload\(payload\)[\s\S]*\/config/);
assert.match(sync, /\/db\/sync\/analyze/);
assert.match(sync, /renderDatabaseHealth\(data\.health\)/);

console.log('Frontend contract checks passed');
