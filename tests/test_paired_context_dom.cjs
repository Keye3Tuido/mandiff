// NODE_PATH=<jsdom node_modules> node this-file <paired review.html> <legacy review.html>
// Verify side isolation and the real walkthrough; this does not verify browser layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM, VirtualConsole } = require('jsdom');
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => errors.push(error.message));
const open = file => new JSDOM(fs.readFileSync(file, 'utf8'), {
  runScripts: 'dangerously', url: 'https://mandiff.invalid/', virtualConsole,
});
const dom = open(process.argv[2]);
const { window } = dom, document = window.document;
const q = selector => { const item = document.querySelector(selector); assert.ok(item, selector); return item; };
const click = selector => q(selector).dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
const stack = () => [...document.querySelectorAll('.cg-stack li')].map(item => item.textContent);
assert.deepEqual(errors, []);
const exactDiff = q('#diff').textContent;
assert.match(q('#baseline-title').textContent, /改动前/);
assert.equal(q('[data-context-side="baseline"]').getAttribute('aria-pressed'), 'true');
assert.equal(document.querySelectorAll('.cg-scenarios option').length, 2);
const originalScenarios = [...document.querySelectorAll('.cg-scenarios option')].map(item => item.textContent);
const originalColumns = [...document.querySelectorAll('.context-view th')].map(item => item.textContent);
assert.equal(document.querySelectorAll('.context-view').length, 2);
assert.match(q('#context-guide').textContent, /具体输入与结果示例/);
assert.equal(document.querySelectorAll('#scenario-comparison tbody tr').length, 2);
assert.match(q('#scenario-comparison').textContent, /grp30/);
assert.ok(q('#scenario-comparison').compareDocumentPosition(q('.diff-panel')) & window.Node.DOCUMENT_POSITION_FOLLOWING);

click('[data-context-side="post_change"]');
assert.match(q('#baseline-title').textContent, /改动后/);
assert.match(q('#baseline-architecture').textContent, /applyValues/);
assert.equal(document.querySelectorAll('.cg-scenarios option').length, 3);
assert.deepEqual([...document.querySelectorAll('.cg-scenarios option')].slice(0, 2).map(item => item.textContent), originalScenarios);
assert.deepEqual([...document.querySelectorAll('.context-view th')].map(item => item.textContent), originalColumns);
assert.match(q('#context-guide').textContent, /_levelsPerFile = 100/);
assert.doesNotMatch(q('#context-guide').textContent, /原来的读取规则及用途/);
assert.equal(document.querySelectorAll('#context-guide svg').length, 1);
assert.ok([...document.querySelectorAll('#baseline-contexts small')].every(item => !item.textContent.includes('base at')));
assert.match(q('#baseline-contexts').textContent, /9b480496ccb1ae910abffd142a5ad2840a873d8d/);
assert.doesNotMatch(q('#baseline-contexts').textContent, /d89ce28b8361abde3d8454bd4821be9c43486169/);
assert.equal(q('#diff').textContent, exactDiff);

// After-side scenario states a new prerequisite; source-derived stack grows and returns.
const scenarios = q('.cg-scenarios');
scenarios.value = '2';
scenarios.dispatchEvent(new window.Event('change', { bubbles: true }));
assert.match(q('.cg-scenario-summary').textContent, /真实外层调用者/);
click('[data-cg-next]'); click('[data-cg-next]'); click('[data-cg-next]');
assert.equal(stack().length, 4);
assert.match(stack()[3], /_writeInjectedValues/);
assert.match(q('.cg-frame-evidence').textContent, /9b480496ccb1ae910abffd142a5ad2840a873d8d/);
click('[data-cg-next]');
assert.equal(stack().length, 3);
assert.match(stack()[2], /_parse/);
click('[data-cg-next]'); click('[data-cg-next]');
assert.equal(stack().length, 1);

click('[data-context-side="baseline"]');
assert.equal(document.querySelectorAll('.cg-scenarios option').length, 2);
assert.equal(stack().length, 1);
assert.equal(document.querySelectorAll('#cg-arrow').length, 1);
assert.match(q('#baseline-contexts').textContent, /d89ce28b8361abde3d8454bd4821be9c43486169/);
assert.doesNotMatch(q('#baseline-contexts').textContent, /9b480496ccb1ae910abffd142a5ad2840a873d8d/);
assert.equal(q('#diff').textContent, exactDiff);
dom.window.close();

const legacy = open(process.argv[3]);
assert.equal(legacy.window.document.querySelector('[data-context-side="post_change"]').disabled, true);
assert.match(legacy.window.document.querySelector('#context-side-note').textContent, /未提供改动后/);
assert.equal(legacy.window.document.querySelector('#scenario-comparison').hidden, true);
assert.deepEqual(errors, []);
legacy.window.close();
process.stdout.write('Paired context DOM checks passed: before/after switching, independent source and stacks, same-input comparison, stable exact diff, and explicit legacy limits.\n');
