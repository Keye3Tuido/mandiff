/* Context-first reading, with only the representations the author selected. */
const renderContextViews = (host, baseline, sources, version) => {
  const views = baseline.views || [];
  host.replaceChildren(); host.onclick = null; host.onkeydown = null;
  const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  const byId = new Map(sources.map(source => [source.id, source]));
  for (const view of views) {
    const zh = /[\u3400-\u9fff]/u.test(JSON.stringify(view));
    const t = (en, cn) => zh ? cn : en;
    const refs = row => row.context_refs.map(id => {
      const source = byId.get(id);
      const location = `${source.path}${source.start_line ? ':' + source.start_line : ''} · ${source.locator}`;
      return `<details><summary>${esc(location)} · ${esc(source.summary)}</summary><small>${esc(source.snapshot)} · ${esc(source.revision)}</small><pre><code>${esc(source.excerpt)}</code></pre></details>`;
    }).join('');
    const section = document.createElement('section'); section.className = 'context-view';
    section.innerHTML = `<h4>${esc(view.title)}</h4><p class="small muted">${esc(view.reason)}</p>`;
    if (view.kind === 'sequence') {
      section.innerHTML += `<ol class="context-sequence">${view.rows.map(row => `<li><strong>${esc(row.from)} → ${esc(row.to)}</strong><p>${esc(row.label)}</p>${refs(row)}</li>`).join('')}</ol>`;
    } else {
      const columns = view.columns || (view.kind === 'state' ? [t('Before state', '原状态'), t('Event or condition', '事件或条件'), t('After state', '新状态')] : [t('Source', '来源'), t('Relationship or responsibility', '关系或职责'), t('Target', '目标')]);
      section.innerHTML += `<div class="table-wrap"><table><thead><tr>${[...columns, t('Evidence', '源码')].map(label => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${view.rows.map(row => `<tr><td>${esc(row.from)}</td><td>${esc(row.label)}</td><td>${esc(row.to)}</td><td>${refs(row)}</td></tr>`).join('')}</tbody></table></div>`;
    }
    host.append(section);
  }
  if (baseline.guide) {
    const details = document.createElement('details');
    const label = /[\u3400-\u9fff]/u.test(JSON.stringify(baseline)) ? '系统关系与运行过程' : 'System relationships and execution';
    details.innerHTML = `<summary>${label}</summary><div class="context-guide"></div>`;
    host.prepend(details);
    // Keep the core explanation visible; supplementary guides may opt into lazy rendering.
    let rendered = false;
    details.addEventListener('toggle', () => {
      if (details.open && !rendered) {
        renderContextGuide(details.querySelector('div'), baseline.guide, sources);
        rendered = true;
      }
    });
    if (baseline.guide.expanded !== false || version !== '1.6') { details.open = true; renderContextGuide(details.querySelector('div'), baseline.guide, sources); rendered = true; }
  } else if (!views.length && version !== '1.6') renderContextGuide(host, null, sources);
};
