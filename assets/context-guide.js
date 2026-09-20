/* Offline diagrams and source-derived walkthroughs. No external renderer or requests. */
const renderContextGuide = (host, guide, sources) => {
  host.replaceChildren();
  const zh = /[\u3400-\u9fff]/u.test(JSON.stringify(guide || {}));
  const t = (en, cn) => zh ? cn : en;
  const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  if (!guide) {
    host.textContent = t('This older report has no source-backed diagram guide.', '此报告没有结构化关系图；不能由旧版文字自动推断调用关系。');
    return;
  }
  const nodes = new Map(guide.nodes.map(node => [node.id, node]));
  const execution = guide.execution;
  const steps = new Map((execution.steps || []).map(step => [step.id, step]));
  const contexts = new Map(sources.map(source => [source.id, source]));
  const selectedViews = guide.views || ['structure', 'calls', 'flow'];
  let view = selectedViews[0], scenarioIndex = 0, frameIndex = 0;
  let activeNode = guide.nodes[0]?.id, activeStep = null;
  const kindLabel = kind => ({contains: t('contains', '包含'), depends_on: t('depends on', '依赖'), calls: t('calls', '调用'), dispatches: t('schedules', '安排回调'), reads: t('reads', '读取'), writes: t('writes', '写入'), next: t('then', '继续'), branch: t('condition', '条件'), loop: t('repeat', '循环'), async: t('later', '异步继续')})[kind] || kind;
  const sourceHtml = refs => [...new Set(refs)].map(id => {
    const source = contexts.get(id);
    if (!source) return '';
    const location = `${source.path}${source.start_line ? `:${source.start_line}` : ''} · ${source.locator}`;
    const code = String(source.excerpt || '').split('\n').map((line, index) => `<span class="cg-source-line"><span class="cg-line-number">${source.start_line ? source.start_line + index : index + 1}</span>${esc(line)}</span>`).join('\n');
    const numbering = source.start_line ? t('Original line numbers', '原始行号') : t('Line numbers within this excerpt', '片段内行号，非原文件行号');
    return `<section class="cg-source"><strong>${esc(location)}</strong><p>${esc(source.summary)}</p><small>${esc(source.snapshot)} · ${esc(source.revision)} · ${numbering}</small><pre><code>${code}</code></pre></section>`;
  }).join('');
  const viewLabels = {structure: t('Architecture & dependencies', '架构与依赖'), calls: t('Calls', '调用关系'), flow: t('Execution flow', '运行流程')};
  host.innerHTML = `<div class="cg-toolbar" role="group" aria-label="${t('Diagram views', '关系图视图')}">
    ${selectedViews.map(name => `<button type="button" data-guide-view="${name}">${viewLabels[name]}</button>`).join('')}</div>
    <p class="cg-view-caption"></p><div class="cg-diagram" tabindex="0" aria-label="${t('Scrollable relationship diagram', '可滚动关系图')}"></div>
    <section class="cg-detail" aria-live="polite"><h4 class="cg-detail-title"></h4><p class="cg-detail-text"></p><details><summary>${t('View cited source', '查看所引用的源码')}</summary><div class="cg-evidence"></div></details></section>
    <details><summary>${t('All relationships and their meanings', '全部关系及其含义')}</summary><div class="cg-relations"></div></details>
    <section class="cg-walkthrough"></section>`;
  const el = selector => host.querySelector(selector);
  const highlight = () => {
    host.querySelectorAll('[data-cg-node]').forEach(item => item.classList.toggle('cg-active', item.dataset.cgNode === activeNode));
    host.querySelectorAll('[data-cg-step]').forEach(item => item.classList.toggle('cg-active', item.dataset.cgStep === activeStep));
  };
  const detail = (title, prose, refs) => {
    el('.cg-detail-title').textContent = title;
    el('.cg-detail-text').textContent = prose;
    el('.cg-evidence').innerHTML = sourceHtml(refs);
    highlight();
  };
  const showNode = id => {
    const node = nodes.get(id); if (!node) return;
    activeNode = id;
    detail(node.label, node.responsibility, node.context_refs);
  };
  // Breadth-first levels terminate for recursion, loops, and disconnected roots.
  const diagram = (items, edges, flow) => {
    const incoming = new Set(edges.map(edge => edge.to));
    const ranks = new Map();
    const visit = root => {
      const queue = [[root, 0]];
      for (let index = 0; index < queue.length; index++) {
        const [id, rank] = queue[index]; if (ranks.has(id)) continue;
        ranks.set(id, rank);
        edges.filter(edge => edge.from === id).forEach(edge => queue.push([edge.to, rank + 1]));
      }
    };
    items.filter(item => !incoming.has(item.id)).forEach(item => visit(item.id));
    items.forEach(item => { if (!ranks.has(item.id)) visit(item.id); });
    const levels = new Map();
    items.forEach(item => { const rank = ranks.get(item.id); if (!levels.has(rank)) levels.set(rank, []); levels.get(rank).push(item); });
    const cols = Math.max(1, ...[...levels.values()].map(level => level.length));
    const width = Math.max(680, cols * 244 + 72), height = levels.size * 150 + 38;
    const positions = new Map();
    levels.forEach((level, rank) => level.forEach((item, col) => positions.set(item.id, {x: (width - level.length * 244) / 2 + col * 244 + 12, y: rank * 150 + 20})));
    const wrap = value => {
      const chars = [...String(value)]; const lines = []; let line = '', length = 0;
      for (const char of chars) { const weight = /[^\x00-\xff]/.test(char) ? 2 : 1; if (length + weight > 25) { lines.push(line); line = ''; length = 0; } line += char; length += weight; }
      if (line) lines.push(line);
      return lines.slice(0, 3).map((value, i) => i === 2 && lines.length > 3 ? value.slice(0, -1) + '…' : value);
    };
    const paths = edges.map((edge, index) => {
      const a = positions.get(edge.from), b = positions.get(edge.to); if (!a || !b) return '';
      let path, lx, ly;
      if (b.y > a.y) {
        const x1 = a.x + 104, y1 = a.y + 84, x2 = b.x + 104, y2 = b.y;
        const middle = (y1 + y2) / 2;
        path = `M${x1},${y1} C${x1},${middle} ${x2},${middle} ${x2},${y2}`;
        lx = (x1 + x2) / 2; ly = middle - 4;
      } else {
        const side = width - 12 - (index % 4) * 12;
        path = `M${a.x + 208},${a.y + 60} C${side},${a.y + 60} ${side},${b.y + 24} ${b.x + 208},${b.y + 24}`;
        lx = side - 42; ly = (a.y + b.y) / 2 + 37;
      }
      const label = `${index + 1}. ${kindLabel(edge.kind)}`;
      return `<g class="cg-edge" role="button" tabindex="0" data-cg-edge="${index}" aria-label="${esc(edge.label)}"><title>${esc(edge.label)}</title><path d="${path}" marker-end="url(#cg-arrow)" ${['async', 'dispatches'].includes(edge.kind) ? 'stroke-dasharray="6 4"' : ''}/><text x="${lx}" y="${ly}" text-anchor="middle">${esc(label)}</text></g>`;
    }).join('');
    const boxes = items.map(item => {
      const pos = positions.get(item.id), label = item.label;
      const attr = flow ? `data-cg-step="${esc(item.id)}"` : `data-cg-node="${esc(item.id)}"`;
      const location = contexts.get(item.context_refs?.[0]);
      return `<g class="cg-node" role="button" tabindex="0" ${attr} aria-label="${esc(label)}"><title>${esc(label)}${location ? ' · ' + esc(location.path) : ''}</title><rect x="${pos.x}" y="${pos.y}" width="208" height="84" rx="9"/>${wrap(label).map((line, i) => `<text x="${pos.x + 12}" y="${pos.y + 23 + i * 19}">${esc(line)}</text>`).join('')}</g>`;
    }).join('');
    return `<svg viewBox="0 0 ${width} ${height}" style="width:${width}px" role="group" aria-label="${esc(t('Select a node or arrow to read its source', '选择节点或箭头查看含义和源码'))}"><defs><marker id="cg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z"/></marker></defs>${paths}${boxes}</svg>`;
  };
  let viewEdges = [];
  const draw = () => {
    host.querySelectorAll('[data-guide-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.guideView === view)));
    const flow = view === 'flow';
    if (flow && execution.status !== 'available') {
      el('.cg-diagram').textContent = execution.reason; el('.cg-relations').replaceChildren(); viewEdges = [];
      el('.cg-view-caption').textContent = t('Execution is not established.', '执行过程未提供。'); return;
    }
    viewEdges = flow ? execution.transitions : guide.relations.filter(edge => view === 'calls' ? ['calls', 'dispatches'].includes(edge.kind) : !['calls', 'dispatches'].includes(edge.kind));
    const used = new Set(viewEdges.flatMap(edge => [edge.from, edge.to]));
    const items = flow ? execution.steps.map(step => ({...step, label: step.action})) : guide.nodes.filter(node => used.has(node.id) || (view === 'structure' && used.size === 0));
    el('.cg-view-caption').textContent = t('Arrows point from source to target. Select any node or numbered relationship below for its meaning and frozen source. Dashed arrows schedule later work.', '箭头从发起方指向目标。选择节点或下方关系，可查看职责、含义和源码；虚线表示安排稍后执行的工作。');
    el('.cg-diagram').innerHTML = items.length ? diagram(items, viewEdges, flow) : `<p>${esc(t('No calls are established by this context.', '当前上下文未证明调用关系。'))}</p>`;
    const labels = new Map(items.map(item => [item.id, item.label]));
    el('.cg-relations').innerHTML = viewEdges.map((edge, index) => `<button type="button" data-cg-edge="${index}"><strong>${index + 1}. ${esc(labels.get(edge.from))} → ${esc(labels.get(edge.to))}</strong><span>${esc(edge.label)}</span></button>`).join('');
    highlight();
  };
  const drawExecution = () => {
    if (selectedViews.includes('flow')) view = 'flow';
    draw();
  };
  const showFrame = () => {
    const scenario = execution.scenarios[scenarioIndex], frame = scenario.walkthrough[frameIndex], step = steps.get(frame.step);
    activeStep = frame.step; activeNode = step.node;
    el('.cg-scenario-summary').textContent = scenario.summary;
    el('.cg-counter').textContent = `${frameIndex + 1} / ${scenario.walkthrough.length}`;
    el('[data-cg-prev]').disabled = frameIndex === 0;
    el('[data-cg-next]').disabled = frameIndex === scenario.walkthrough.length - 1;
    el('.cg-trace').innerHTML = scenario.walkthrough.map((item, index) => `<button type="button" data-cg-frame="${index}" aria-pressed="${index === frameIndex}">${index + 1}. ${esc(steps.get(item.step).action)}</button>`).join('');
    el('.cg-stack').innerHTML = frame.stack.map((id, index) => `<li><button type="button" data-cg-node="${esc(id)}">${index + 1}. ${esc(nodes.get(id).label)}</button></li>`).join('');
    el('.cg-frame-explanation').textContent = frame.explanation;
    el('.cg-frame-evidence').innerHTML = sourceHtml([...step.context_refs, ...frame.context_refs]);
    detail(step.action, frame.explanation, [...step.context_refs, ...frame.context_refs]);
  };
  if (execution.status === 'available') {
    el('.cg-walkthrough').innerHTML = `<h4>${t('Follow a scenario', '跟着一次操作看运行过程')}</h4><label>${t('Scenario', '场景')} <select class="cg-scenarios">${execution.scenarios.map((scenario, index) => `<option value="${index}">${esc(scenario.title)}</option>`).join('')}</select></label><p class="cg-scenario-summary"></p><p class="cg-stack-note">${t('Source-derived stack illustration, not a runtime capture. Frames run from outermost caller to current function. An asynchronous continuation starts a new stack.', '调用栈依据源码推导，未实际运行。下方按外层调用者到当前函数排列；异步回调会开始新的调用栈。')}</p><div class="cg-toolbar"><button type="button" data-cg-prev>${t('Previous step', '上一步')}</button><span class="cg-counter"></span><button type="button" data-cg-next>${t('Next step', '下一步')}</button></div><div class="cg-walk-grid"><div class="cg-trace"></div><div><strong>${t('Active stack', '当前调用栈')}</strong><ol class="cg-stack"></ol><p class="cg-frame-explanation"></p><details><summary>${t('Source for this step', '本步源码')}</summary><div class="cg-frame-evidence"></div></details></div></div>`;
    el('.cg-scenarios').addEventListener('change', event => { scenarioIndex = Number(event.target.value); frameIndex = 0; drawExecution(); showFrame(); });
  } else el('.cg-walkthrough').textContent = execution.reason;
  host.onclick = event => {
    const target = event.target.closest('button, [role="button"]'); if (!target) return;
    if (target.dataset.guideView) { view = target.dataset.guideView; draw(); return; }
    if (target.dataset.cgNode) { showNode(target.dataset.cgNode); return; }
    if (target.dataset.cgStep) {
      const id = target.dataset.cgStep;
      let index = execution.scenarios[scenarioIndex].walkthrough.findIndex(frame => frame.step === id);
      if (index < 0) {
        const matchingScenario = execution.scenarios.findIndex(scenario => scenario.walkthrough.some(frame => frame.step === id));
        if (matchingScenario >= 0) {
          scenarioIndex = matchingScenario;
          el('.cg-scenarios').value = String(scenarioIndex);
          index = execution.scenarios[scenarioIndex].walkthrough.findIndex(frame => frame.step === id);
        }
      }
      if (index >= 0) { frameIndex = index; showFrame(); }
      else {
        const step = steps.get(id); activeStep = id; activeNode = step.node;
        el('.cg-stack').replaceChildren();
        el('.cg-counter').textContent = t('Outside the selected walkthrough', '此步骤未包含在已提供的场景中');
        detail(step.action, nodes.get(step.node).responsibility, step.context_refs);
      }
      return;
    }
    if (target.dataset.cgEdge !== undefined) { const edge = viewEdges[Number(target.dataset.cgEdge)]; detail(edge.label, kindLabel(edge.kind), edge.context_refs); return; }
    if (target.hasAttribute('data-cg-prev')) frameIndex--;
    else if (target.hasAttribute('data-cg-next')) frameIndex++;
    else if (target.dataset.cgFrame !== undefined) frameIndex = Number(target.dataset.cgFrame);
    else return;
    drawExecution(); showFrame();
  };
  host.onkeydown = event => { if (event.target.matches('g[role="button"]') && ['Enter', ' '].includes(event.key)) { event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click', {bubbles: true})); } };
  draw();
  if (execution.status === 'available') showFrame(); else showNode(activeNode);
};
