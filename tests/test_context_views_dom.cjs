// Optional development check: NODE_PATH=<jsdom node_modules> node this-file <review.html> <guide review.json>
// Checks interactions and evidence rendering; a DOM emulator does not verify layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM, VirtualConsole } = require('jsdom');
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => errors.push(error.message));
const dom = new JSDOM(fs.readFileSync(process.argv[2], 'utf8'), {
  runScripts: 'dangerously', url: 'https://mandiff.invalid/', virtualConsole,
});
const { window } = dom, document = window.document;
const host = document.querySelector('#context-guide');
const model = JSON.parse(document.querySelector('#mandiff-data').textContent);
const baseline = model.units[0].baseline;
const renderViews = window.eval('renderContextViews');
assert.deepEqual(errors, []);
assert.ok(host.querySelector('table'), 'the real report retains its parameter table');
assert.equal(host.querySelectorAll('svg').length, 1);
assert.equal(host.firstElementChild.tagName, 'DETAILS');
assert.equal(host.firstElementChild.open, true, 'core explanation is visible');
assert.deepEqual([...host.querySelectorAll('[data-guide-view]')].map(item => item.dataset.guideView), ['structure', 'flow']);
assert.equal(host.querySelectorAll('.cg-scenarios option').length, 2);
const sourceDetails = host.querySelector('td details');
assert.ok(sourceDetails);
assert.equal(sourceDetails.open, false);
sourceDetails.open = true;
assert.match(sourceDetails.querySelector('summary').textContent, /LSMetaConfig.cpp:\d+/);
assert.match(sourceDetails.querySelector('code').textContent, /LSMetaConfig::_parse/);
assert.ok([...document.querySelectorAll('#baseline-contexts details')].every(item => !item.open));
assert.equal(document.querySelectorAll('script[src], link[rel="stylesheet"]').length, 0);

const refs = [model.context_sources[0].id];
const sequence = {
  kind: 'sequence', title: '初始化', reason: '说明跨组件的先后顺序',
  rows: [
    { from: '调用方', label: '同步读取配置', to: '读取器', context_refs: refs },
    { from: '读取器', label: '返回值', to: '调用方', context_refs: refs },
  ],
};
renderViews(host, { views: [sequence] }, model.context_sources, '1.6');
assert.equal(host.querySelectorAll('ol > li').length, 2);
assert.match(host.querySelector('li').textContent, /调用方 → 读取器/);
assert.ok(host.querySelector('li code'));
const state = {
  kind: 'state', title: 'Lifecycle', reason: 'What event changes the state',
  rows: [{ from: 'empty', label: 'load succeeds', to: 'ready', context_refs: refs }],
};
renderViews(host, { views: [state] }, model.context_sources, '1.6');
assert.deepEqual([...host.querySelectorAll('th')].map(item => item.textContent),
  ['Before state', 'Event or condition', 'After state', 'Evidence']);
assert.deepEqual([...host.querySelectorAll('td')].slice(0, 3).map(item => item.textContent),
  ['empty', 'load succeeds', 'ready']);

const hostile = structuredClone(state), sources = structuredClone(model.context_sources);
hostile.title = '<img src=x onerror="window.injected=true">';
hostile.rows[0].from = '<script>window.injected=true</script>';
hostile.columns = ['<b>from</b>', 'rule', 'to'];
sources[0].excerpt = '</code><script>window.injected=true</script>';
renderViews(host, { views: [hostile] }, sources, '1.6');
assert.equal(host.querySelectorAll('script, img, b').length, 0);
assert.equal(window.injected, undefined);
assert.equal(host.querySelector('th').textContent, '<b>from</b>');
assert.match(host.querySelector('code').textContent, /<script>/);

renderViews(host, { architecture: 'A local rule needs only prose.' }, [], '1.6');
assert.equal(host.textContent, '');
renderViews(host, {}, [], '1.4');
assert.match(host.textContent, /older report/);

// Opt-in supplementary detail still renders lazily and only once.
if (process.argv[3]) {
  const detailed = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  detailed.units[0].baseline.guide.expanded = false;
  renderViews(host, detailed.units[0].baseline, detailed.context_sources, '1.6');
  const details = host.querySelector(':scope > details');
  assert.equal(details.open, false);
  assert.equal(host.querySelectorAll('svg').length, 0);
  details.open = true;
  details.dispatchEvent(new window.Event('toggle'));
  const svg = host.querySelector('svg');
  assert.ok(svg);
  details.open = false;
  details.dispatchEvent(new window.Event('toggle'));
  details.open = true;
  details.dispatchEvent(new window.Event('toggle'));
  assert.equal(host.querySelector('svg'), svg, 'reopening preserves the existing graph');
  // A walkthrough must work without silently creating an excluded flow diagram.
  detailed.units[0].baseline.guide.expanded = true;
  detailed.units[0].baseline.guide.views = ['structure'];
  renderViews(host, detailed.units[0].baseline, detailed.context_sources, '1.6');
  const next = host.querySelector('[data-cg-next]');
  next.dispatchEvent(new window.MouseEvent('click', {bubbles: true}));
  assert.equal(host.querySelector('[data-guide-view]').getAttribute('aria-pressed'), 'true');
  assert.equal(host.querySelectorAll('[data-cg-step]').length, 0);
  assert.equal(host.querySelector('.cg-counter').textContent, '2 / 3');
  assert.equal(host.querySelectorAll('.cg-stack li').length, 2);
  const scenarios = host.querySelector('.cg-scenarios');
  scenarios.value = '1';
  scenarios.dispatchEvent(new window.Event('change', {bubbles: true}));
  assert.equal(host.querySelectorAll('[data-guide-view]').length, 1);
  assert.equal(host.querySelector('.cg-counter').textContent, '1 / 10');
}
assert.deepEqual(errors, []);
dom.window.close();
process.stdout.write('Context view DOM checks passed: visible overview plus table/scenarios, selected diagrams, readable source, sequence, state, escaping, legacy reports, and supplementary lazy graph.\n');
