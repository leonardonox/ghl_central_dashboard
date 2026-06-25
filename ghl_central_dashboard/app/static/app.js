const months = {
  Janeiro: 1,
  Fevereiro: 2,
  Marco: 3,
  Abril: 4,
  Maio: 5,
  Junho: 6,
  Julho: 7,
  Agosto: 8,
  Setembro: 9,
  Outubro: 10,
  Novembro: 11,
  Dezembro: 12,
};

const state = {
  accounts: [],
  selectedAccounts: new Set(),
  current: null,
  previous: null,
  weeks: [],
  selectedWeekIndex: 0,
  rankingMetric: 'new_leads',
};

const metricLabels = {
  new_leads: 'Leads',
  inbox_conversations: 'Conversas',
  whatsapp_contacts: 'WhatsApp',
  attendances: 'Atendimentos',
  sales: 'Vendas',
  attendance_rate: 'Taxa atendimento',
  sales_rate: 'Taxa venda',
  channel_identified_rate: 'Canais identificados',
  health_score: 'Saúde',
};

const $ = (id) => document.getElementById(id);

function iso(date) {
  return date.toISOString().slice(0, 10);
}

function today() {
  return new Date();
}

function parseLocalDate(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function monthRange(month) {
  const start = new Date(2026, month - 1, 1);
  const end = new Date(2026, month, 0);
  const now = today();
  if (start.getFullYear() === now.getFullYear() && start.getMonth() === now.getMonth()) {
    return [start, now < end ? now : end];
  }
  return [start, end];
}

function startOfWeekMonday(date) {
  const start = new Date(date);
  const day = start.getDay();
  const offset = day === 0 ? 6 : day - 1;
  start.setDate(start.getDate() - offset);
  return start;
}

function lastCompletedWeekRange() {
  const currentWeekStart = startOfWeekMonday(today());
  const end = new Date(currentWeekStart);
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - 6);
  return [start, end];
}

function weekNumber(date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil((((target - yearStart) / 86400000) + 1) / 7);
}

function buildYearWeeks(year = 2026) {
  const weeks = [];
  const firstWeekStart = startOfWeekMonday(new Date(year, 0, 4));
  const lastDay = new Date(year, 11, 31);
  const start = new Date(firstWeekStart);

  while (start <= lastDay) {
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    const label = `S${String(weekNumber(start)).padStart(2, '0')}`;
    weeks.push({ start: new Date(start), end, label, range: `${shortDate(start)} a ${shortDate(end)}` });
    start.setDate(start.getDate() + 7);
  }

  return weeks;
}

function quickRange() {
  const quick = $('quick').value;
  const now = today();
  if (quick === 'Hoje') return [now, now];
  if (quick === 'Semana') {
    const week = state.weeks[state.selectedWeekIndex] || buildYearWeeks()[0];
    return [week.start, week.end];
  }
  if (quick === 'Mes') return [new Date(now.getFullYear(), now.getMonth(), 1), now];
  if (quick === 'Mes especifico') return monthRange(months[$('month-b').value]);
  return [parseLocalDate($('start-date').value), parseLocalDate($('end-date').value)];
}

function previousRange(start, end) {
  const days = Math.round((end - start) / 86400000) + 1;
  const prevEnd = new Date(start);
  prevEnd.setDate(prevEnd.getDate() - 1);
  const prevStart = new Date(prevEnd);
  prevStart.setDate(prevStart.getDate() - days + 1);
  return [prevStart, prevEnd];
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function showStatus(message) {
  const status = $('status');
  status.textContent = message;
  status.classList.remove('hidden');
}

function hideStatus() {
  $('status').classList.add('hidden');
}

function fillMonthSelects() {
  state.weeks = buildYearWeeks();
  const [lastStart, lastEnd] = lastCompletedWeekRange();
  state.selectedWeekIndex = Math.max(0, state.weeks.findIndex((week) => iso(week.start) === iso(lastStart) && iso(week.end) === iso(lastEnd)));
  renderWeekSelector();
  for (const id of ['month-a', 'month-b']) {
    const select = $(id);
    select.innerHTML = Object.keys(months).map((name) => `<option>${name}</option>`).join('');
  }
  $('month-a').value = 'Maio';
  $('month-b').value = 'Junho';
  const [start, end] = quickRange();
  $('start-date').value = iso(start);
  $('end-date').value = iso(end);
  updateFilterVisibility();
}

function setSegmentValue(selectId, buttonContainerId, value) {
  $(selectId).value = value;
  document.querySelectorAll(`#${buttonContainerId} button`).forEach((button) => {
    button.classList.toggle('active', button.dataset.value === value);
  });
  updateFilterVisibility();
  loadDashboard();
}

function updateFilterVisibility() {
  const mode = $('mode').value;
  const quick = $('quick').value;
  document.querySelector('.months-card').style.display = mode === 'Comparar meses' || quick === 'Mes especifico' ? '' : 'none';
  document.querySelector('.date-card').style.display = mode === 'Periodo unico' && quick === 'Personalizado' ? '' : 'none';
  $('quick-card').style.display = mode === 'Periodo unico' ? '' : 'none';
  $('week-selector').style.display = mode === 'Periodo unico' && quick === 'Semana' ? '' : 'none';
}

function renderWeekSelector() {
  const container = $('week-selector');
  const select = $('week-select');
  if (!container) return;
  select.innerHTML = state.weeks.map((week, index) => (
    `<option value="${index}">${week.label} - ${week.range}</option>`
  )).join('');
  select.value = String(state.selectedWeekIndex);
  select.addEventListener('change', () => {
    state.selectedWeekIndex = Number(select.value);
    loadDashboard();
  });
}

function filterRows(rows) {
  const selected = selectedNames();
  if (!selected.length) return rows;
  return rows.filter((row) => selected.includes(row.account));
}

function sum(rows, key) {
  return rows.reduce((total, row) => total + Number(row[key] || 0), 0);
}

function pct(value) {
  return `${Number(value || 0).toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return 'Sem sincronizacao';
  return new Date(value).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function shortDate(date) {
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function rangeLabel(range) {
  const [start, end] = range;
  if (iso(start) === iso(end)) return shortDate(start);
  return `${shortDate(start)} a ${shortDate(end)}`;
}

function change(current, previous) {
  if (!previous) return current ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

function kpi(title, value, subtitle = '', tone = 'blue') {
  return `<article class="card kpi ${tone}"><span>${title}</span><strong>${value}</strong><small>${subtitle}</small></article>`;
}

function compareKpi(title, current, previous, unit = '', tone = 'blue', labels = {}) {
  const diff = Number(current || 0) - Number(previous || 0);
  const diffText = `${diff >= 0 ? '+' : ''}${diff}${unit ? ` ${unit}` : ''}`;
  const diffClass = diff >= 0 ? 'positive' : 'negative';
  const previousLabel = labels.previous || 'Periodo anterior';
  const currentLabel = labels.current || 'Periodo atual';
  return `<article class="card compare-kpi ${tone}">
    <div class="compare-head">
      <span>${title}</span>
      <em class="${diffClass}">${diffText}</em>
    </div>
    <div class="compare-main">
      <div><small>Anterior</small><span class="period-date">${previousLabel}</span><strong>${previous}</strong></div>
      <div class="arrow">&rarr;</div>
      <div><small>Atual</small><span class="period-date">${currentLabel}</span><strong>${current}</strong></div>
    </div>
  </article>`;
}

function singleKpi(title, value, subtitle = '', tone = 'blue') {
  return `<article class="card compare-kpi single ${tone}">
    <div class="compare-head"><span>${title}</span></div>
    <strong>${value}</strong>
    <small>${subtitle}</small>
  </article>`;
}

function section(title) {
  return `<div class="section-title">${title}</div>`;
}

function bars(rows, key, color = 'green') {
  const max = Math.max(...rows.map((row) => Number(row[key] || 0)), 1);
  return `<div class="bars">${rows.map((row) => {
    const value = Number(row[key] || 0);
    const width = Math.max((value / max) * 100, value ? 2 : 0);
    const label = key.includes('rate') ? pct(value) : value;
    return `<div class="bar-row"><strong>${row.account}</strong><div class="bar-track"><div class="bar-fill ${color}" style="width:${width}%"></div></div><span>${label}</span></div>`;
  }).join('')}</div>`;
}

function metricButtons() {
  return `<div class="metric-switch">${Object.entries(metricLabels).map(([key, label]) => (
    `<button type="button" class="${state.rankingMetric === key ? 'active' : ''}" data-metric="${key}">${label}</button>`
  )).join('')}</div>`;
}

function bindMetricButtons(currentRows) {
  document.querySelectorAll('[data-metric]').forEach((button) => {
    button.addEventListener('click', () => {
      state.rankingMetric = button.dataset.metric;
      renderMagazine(currentRows);
    });
  });
}

function cardValue(row, key) {
  if (!row) return '-';
  const value = row[key] ?? 0;
  if (key.includes('rate')) return pct(value);
  if (key === 'health_score') return `${value}/100`;
  return value;
}

function miniHighlight(title, row, key, tone = 'blue', extra = '') {
  return `<article class="card mini-highlight ${tone}">
    <span>${title}</span>
    <strong>${row?.account || '-'}</strong>
    <small>${cardValue(row, key)}${extra}</small>
  </article>`;
}

function svgLine(rows, key = 'leads') {
  if (!rows.length) return '<p>Sem dados.</p>';
  const grouped = new Map();
  for (const row of rows) {
    if (!grouped.has(row.account)) grouped.set(row.account, []);
    grouped.get(row.account).push(row);
  }
  const dates = [...new Set(rows.map((row) => row.date))].sort();
  const max = Math.max(...rows.map((row) => Number(row[key] || 0)), 1);
  const width = 900;
  const height = 300;
  const pad = 36;
  const colors = ['#2f6b22', '#e8792e', '#256da8', '#7c3aed', '#b42318'];
  const x = (date) => pad + (dates.indexOf(date) / Math.max(dates.length - 1, 1)) * (width - pad * 2);
  const y = (value) => height - pad - (value / max) * (height - pad * 2);
  const lines = [...grouped.entries()].map(([account, items], index) => {
    const byDate = new Map(items.map((item) => [item.date, Number(item[key] || 0)]));
    const points = dates.map((date) => `${x(date)},${y(byDate.get(date) || 0)}`).join(' ');
    const color = colors[index % colors.length];
    return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="3"/><text x="${pad}" y="${18 + index * 18}" fill="${color}" font-size="13">${account}</text>`;
  }).join('');
  return `<svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img">
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#cbd5e1"/>
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#cbd5e1"/>
    ${lines}
  </svg>`;
}

function table(rows) {
  if (!rows.length) return '<p>Sem dados.</p>';
  const columns = [
    ['account', 'Revista'],
    ['new_leads', 'Leads'],
    ['previous_new_leads', 'Anterior'],
    ['lead_change_percent', 'Var %'],
    ['attendances', 'Atend.'],
    ['inbox_conversations', 'Conversas'],
    ['whatsapp_contacts', 'WhatsApp'],
    ['sales', 'Vendas'],
    ['attendance_rate', 'Tx atend.'],
    ['sales_rate', 'Tx venda'],
    ['channel_identified_rate', 'Tx canal'],
    ['health_score', 'Saúde'],
    ['best_channel', 'Melhor canal'],
  ];
  return `<table><thead><tr>${columns.map(([, label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => (
    `<tr>${columns.map(([key]) => {
      const value = key.includes('rate') || key.includes('percent') ? pct(row[key]) : row[key];
      return `<td>${value ?? ''}</td>`;
    }).join('')}</tr>`
  )).join('')}</tbody></table>`;
}

function renderChips() {
  const container = $('account-chips');
  $('selected-count').textContent = `${state.selectedAccounts.size} de ${state.accounts.length} selecionadas`;
  container.innerHTML = state.accounts.map((account) => {
    const active = state.selectedAccounts.has(account.name);
    return `<button class="chip ${active ? '' : 'off'}" data-account="${account.name}">${account.name}</button>`;
  }).join('');
  container.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      const name = button.dataset.account;
      if (state.selectedAccounts.has(name)) state.selectedAccounts.delete(name);
      else state.selectedAccounts.add(name);
      renderChips();
      loadDashboard();
    });
  });
}

function renderSummary(currentRows, previousRows) {
  const leads = sum(currentRows, 'new_leads');
  const prevLeads = sum(previousRows, 'new_leads');
  const attends = sum(currentRows, 'attendances');
  const prevAttends = sum(previousRows, 'attendances');
  const inboxConversations = sum(currentRows, 'inbox_conversations');
  const prevInboxConversations = sum(previousRows, 'inbox_conversations');
  const whatsapp = sum(currentRows, 'whatsapp_contacts');
  const prevWhatsapp = sum(previousRows, 'whatsapp_contacts');
  const sales = sum(currentRows, 'sales');
  const prevSales = sum(previousRows, 'sales');
  const channel = sum(currentRows, 'new_leads_with_channel');
  const ranges = getRanges();
  const labels = {
    previous: rangeLabel(ranges.previous),
    current: rangeLabel(ranges.current),
  };

  $('resumo').innerHTML = `
    ${section('Resumo executivo')}
    <div class="kpi-grid">
      ${compareKpi('Total leads', leads, prevLeads, 'leads', 'blue', labels)}
      ${compareKpi('Atendimentos', attends, prevAttends, '', 'green', labels)}
      ${compareKpi('Conversas na caixa', inboxConversations, prevInboxConversations, 'conversas', 'blue', labels)}
      ${compareKpi('Contatos no WhatsApp', whatsapp, prevWhatsapp, 'pessoas', 'green', labels)}
      ${compareKpi('Vendas', sales, prevSales, '', 'orange', labels)}
      ${singleKpi('Taxa atendimento', pct(leads ? (attends / leads) * 100 : 0), 'atendimentos / leads', 'orange')}
      ${singleKpi('Canais identificados', pct(leads ? (channel / leads) * 100 : 0), `${channel} leads`, 'blue')}
      ${singleKpi('Saúde média', `${Math.round(sum(currentRows, 'health_score') / Math.max(currentRows.length, 1))}/100`, 'score operacional', 'green')}
    </div>
    <br>
    ${renderHighlights()}
    <br>
    <div class="executive-summary">
      <strong>Resumo para envio</strong>
      <p>${state.current.executive_summary}</p>
      <button id="copy-summary" class="secondary" type="button">Copiar resumo</button>
    </div>
    <br>
    <div class="diagnosis">${state.current.diagnosis}</div>
    <div class="grid-2" style="margin-top:14px">
      <article class="card chart-card"><h3>Evolução diária de leads</h3>${svgLine(filterRows(state.current.daily_by_account))}</article>
      <article class="card chart-card"><h3>Conversas por dia</h3>${svgLine(filterRows(state.current.daily_conversations_by_account), 'conversations')}</article>
      <article class="card chart-card"><h3>Ranking rápido</h3>${bars([...currentRows].sort((a, b) => b[state.rankingMetric] - a[state.rankingMetric]), state.rankingMetric, 'green')}</article>
    </div>
  `;
  $('copy-summary').addEventListener('click', async () => {
    await navigator.clipboard.writeText(state.current.executive_summary);
    showStatus('Resumo executivo copiado.');
  });
}

function renderHighlights() {
  const highlights = state.current.highlights || {};
  return `<div class="highlight-grid">
    ${miniHighlight('Mais leads', highlights.most_leads, 'new_leads', 'blue')}
    ${miniHighlight('Mais conversas', highlights.most_inbox_conversations, 'inbox_conversations', 'blue')}
    ${miniHighlight('Mais WhatsApp', highlights.most_whatsapp, 'whatsapp_contacts', 'green')}
    ${miniHighlight('Maior alta', highlights.biggest_growth, 'lead_delta', 'green', ' leads')}
    ${miniHighlight('Maior queda', highlights.biggest_drop, 'lead_delta', 'red', ' leads')}
    ${miniHighlight('Melhor atendimento', highlights.best_attendance_rate, 'attendance_rate', 'orange')}
    ${miniHighlight('Menos leads', highlights.least_leads, 'new_leads', 'red')}
  </div>`;
}

function renderDay() {
  $('dia').innerHTML = `${section('Por dia')}`
    + `<div class="grid-2"><article class="card chart-card"><h3>Leads por dia</h3>${svgLine(filterRows(state.current.daily_by_account))}</article>`
    + `<article class="card chart-card"><h3>Conversas que entraram por dia</h3>${svgLine(filterRows(state.current.daily_conversations_by_account), 'conversations')}</article></div><br>`
    + `<article class="card chart-card"><h3>Heatmap por dia da semana</h3>${weekdayHeatmap(filterRows(state.current.weekday_heatmap))}</article>`;
}

function weekdayHeatmap(rows) {
  if (!rows.length) return '<p>Sem dados.</p>';
  const accounts = [...new Set(rows.map((row) => row.account))];
  const weekdays = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'];
  const max = Math.max(...rows.map((row) => Number(row.leads || 0)), 1);
  const byKey = new Map(rows.map((row) => [`${row.account}-${row.weekday}`, row.leads]));
  return `<div class="heatmap">
    <div></div>${weekdays.map((day) => `<strong>${day}</strong>`).join('')}
    ${accounts.map((account) => `
      <strong>${account}</strong>
      ${weekdays.map((day) => {
        const value = Number(byKey.get(`${account}-${day}`) || 0);
        const intensity = value / max;
        return `<span style="--heat:${intensity.toFixed(2)}">${value}</span>`;
      }).join('')}
    `).join('')}
  </div>`;
}

function renderMagazine(currentRows) {
  const metric = state.rankingMetric;
  const sorted = [...currentRows].sort((a, b) => Number(b[metric] || 0) - Number(a[metric] || 0));
  $('revista').innerHTML = `${section('Por revista')}`
    + `<div class="card chart-card"><h3>Ranking por ${metricLabels[metric]}</h3>${metricButtons()}${bars(sorted, metric, 'blue')}</div><br>`
    + table(currentRows)
    + `<br><div class="export-actions">
      <button id="download-summary">CSV resumo</button>
      <button id="download-daily">CSV por dia</button>
      <button id="download-conversations">CSV conversas por dia</button>
      <button id="download-channels">CSV canais</button>
      <button id="download-alerts">CSV alertas</button>
    </div>`;
  bindMetricButtons(currentRows);
  $('download-summary').addEventListener('click', () => downloadCsv(currentRows, 'resumo_revistas.csv'));
  $('download-daily').addEventListener('click', () => downloadCsv(filterRows(state.current.daily_by_account), 'por_dia_revistas.csv'));
  $('download-conversations')?.addEventListener('click', () => downloadCsv(filterRows(state.current.daily_conversations_by_account), 'conversas_por_dia_revistas.csv'));
  $('download-channels').addEventListener('click', () => downloadCsv(filterRows(state.current.channel_comparison), 'canais_revistas.csv'));
  $('download-alerts').addEventListener('click', () => downloadCsv(state.current.alerts, 'alertas_revistas.csv'));
}

function renderCompare(currentRows) {
  const [first = state.accounts[0]?.name, second = state.accounts[1]?.name || state.accounts[0]?.name] = selectedNames();
  const options = state.accounts.map((account) => `<option value="${account.name}">${account.name}</option>`).join('');
  const left = currentRows.find((row) => row.account === first) || currentRows[0];
  const right = currentRows.find((row) => row.account === second) || currentRows[1] || currentRows[0];
  const metrics = ['new_leads', 'inbox_conversations', 'whatsapp_contacts', 'attendances', 'sales', 'attendance_rate', 'sales_rate', 'channel_identified_rate', 'health_score'];

  $('comparar').innerHTML = `${section('Comparar duas revistas')}
    <div class="compare-selectors">
      <label><span>Revista A</span><select id="compare-a">${options}</select></label>
      <label><span>Revista B</span><select id="compare-b">${options}</select></label>
    </div>
    <br>
    <div class="card compare-table">
      <table>
        <thead><tr><th>Indicador</th><th>${left?.account || '-'}</th><th>${right?.account || '-'}</th><th>Vencedor</th></tr></thead>
        <tbody>
          ${metrics.map((key) => {
            const leftValue = Number(left?.[key] || 0);
            const rightValue = Number(right?.[key] || 0);
            const winner = leftValue === rightValue ? 'Empate' : leftValue > rightValue ? left.account : right.account;
            return `<tr><td>${metricLabels[key]}</td><td>${cardValue(left, key)}</td><td>${cardValue(right, key)}</td><td>${winner}</td></tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;

  $('compare-a').value = left?.account || '';
  $('compare-b').value = right?.account || '';
  $('compare-a').addEventListener('change', () => {
    state.selectedAccounts = new Set([$('compare-a').value, $('compare-b').value]);
    renderChips();
    renderCompare(filterRows(state.current.rows));
  });
  $('compare-b').addEventListener('change', () => {
    state.selectedAccounts = new Set([$('compare-a').value, $('compare-b').value]);
    renderChips();
    renderCompare(filterRows(state.current.rows));
  });
}

function renderChannels() {
  const rows = filterRows(state.current.channel_comparison);
  const totals = new Map();
  for (const row of rows) totals.set(row.channel, (totals.get(row.channel) || 0) + row.leads);
  const channelRows = [...totals.entries()].map(([account, new_leads]) => ({ account, new_leads }));
  $('canais').innerHTML = `${section('Canais')}`
    + `<div class="card chart-card">${bars(channelRows.sort((a, b) => b.new_leads - a.new_leads), 'new_leads', 'orange')}</div>`;
}

async function renderIndividual() {
  const selected = selectedNames()[0] || state.accounts[0]?.name;
  const account = state.accounts.find((item) => item.name === selected);
  if (!account) return;
  const [start, end] = getRanges().current;
  const detail = await api(`/dashboard/performance?start_date=${iso(start)}&end_date=${iso(end)}&account_id=${account.id}`);
  const funnel = Object.entries(detail.funnel_counts || {}).map(([account, new_leads]) => ({ account: account.replaceAll('_', ' '), new_leads }));
  $('individual').innerHTML = `
    ${section(`Individual — ${account.name}`)}
    <div class="kpi-grid">
      ${kpi('Leads', detail.totals.new_leads)}
      ${kpi('Conversas', detail.totals.inbox_conversations || 0, 'entraram na caixa', 'blue')}
      ${kpi('WhatsApp', detail.totals.whatsapp_contacts || 0, 'pessoas que falaram no periodo', 'green')}
      ${kpi('HSM enviado', detail.totals.hsm_leads, '', 'green')}
      ${kpi('Vendas', detail.totals.sales, '', 'green')}
      ${kpi('Leads com canal', detail.totals.new_leads_with_channel)}
    </div>
    <br>
    <article class="card chart-card"><h3>Funil</h3>${bars(funnel, 'new_leads', 'green')}</article>
  `;
}

function renderAlerts() {
  const alerts = state.current.alerts.filter((alert) => selectedNames().includes(alert.account));
  $('alertas').innerHTML = `${section('Alertas e diagnóstico')}
    <div class="diagnosis">${state.current.diagnosis}</div><br>
    <div class="diagnosis">
      <strong>Base de conferencia</strong><br>
      Leads: oportunidades criadas no GHL. WhatsApp: pessoas unicas com mensagem recebida no periodo. Atendimentos: tag de atendimento nas oportunidades.
    </div><br>`
    + (alerts.length ? `<div class="alert-list">${alerts.map((alert) => `<div class="alert"><strong>${alert.account}</strong><br>${alert.message}</div>`).join('')}</div>` : '<div class="diagnosis">Nenhum alerta encontrado.</div>');
}

async function renderConfig() {
  const accounts = await api('/accounts/all');
  $('configuracoes').innerHTML = `${section('Configurações das revistas')}
    <div class="card config-card deploy-card">
      <h3>Deploy do painel</h3>
      <p>Use quando quiser publicar a versao mais recente do GitHub no Render.</p>
      <div class="deploy-actions">
        <button id="redeploy-render" type="button">Redeploy Render</button>
        <span id="redeploy-hint" class="deploy-hint">Apos ficar Live no Render, atualize esta pagina.</span>
        <button id="refresh-page" class="secondary" type="button">Atualizar pagina</button>
      </div>
    </div>
    <br>
    <div class="card config-card">
      <h3>Adicionar revista</h3>
      <div class="config-form">
        <label><span>Revista</span><input id="new-account-name" placeholder="Nome da revista" autocomplete="off" /></label>
        <label><span>Location ID</span><input id="new-account-location" placeholder="ID ou URL da location" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" /></label>
        <label><span>Token PIT</span><input id="new-account-token" placeholder="Token da integração privada" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" /></label>
        <button id="create-account">Adicionar</button>
      </div>
    </div>
    <br>
    <div class="card config-card">
      <h3>Revistas cadastradas</h3>
      <div class="config-list">
        ${accounts.map((account) => `
          <div class="config-row" data-account-id="${account.id}">
            <label><span>Revista</span><input class="config-name" value="${account.name}" autocomplete="off" /></label>
            <label><span>Location</span><input class="config-location" placeholder="Salvo, preencha para trocar" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" /></label>
            <label><span>Token</span><input class="config-token" placeholder="Salvo, preencha para trocar" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" /></label>
            <label class="config-active"><input class="config-active-input" type="checkbox" ${account.active ? 'checked' : ''} /> Ativa</label>
            <div class="config-actions">
              <button class="save-account">Salvar</button>
              <button class="deactivate-account secondary">Desativar</button>
              <button class="delete-account danger" type="button">Excluir</button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;

  $('redeploy-render').addEventListener('click', async () => {
    try {
      $('redeploy-hint').textContent = 'Solicitando redeploy no Render...';
      await api('/deploy/render', { method: 'POST' });
      $('redeploy-hint').textContent = 'Redeploy solicitado. Quando o Render ficar Live, clique em Atualizar pagina.';
      $('refresh-page').disabled = false;
    } catch (error) {
      $('redeploy-hint').textContent = `Erro ao solicitar redeploy: ${error.message}`;
    }
  });

  $('refresh-page').addEventListener('click', () => {
    window.location.reload();
  });

  $('create-account').addEventListener('click', async () => {
    await api('/accounts', {
      method: 'POST',
      body: JSON.stringify({
        name: $('new-account-name').value,
        location_id: $('new-account-location').value,
        api_token: $('new-account-token').value,
      }),
    });
    await refreshAccounts();
  });

  document.querySelectorAll('.save-account').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('.config-row');
      const account = accounts.find((item) => String(item.id) === row.dataset.accountId);
      const locationId = row.querySelector('.config-location').value || account.location_id;
      const payload = {
        name: row.querySelector('.config-name').value,
        location_id: locationId,
        active: row.querySelector('.config-active-input').checked,
      };
      const token = row.querySelector('.config-token').value;
      if (token) payload.api_token = token;
      await api(`/accounts/${row.dataset.accountId}`, { method: 'PUT', body: JSON.stringify(payload) });
      await refreshAccounts();
    });
  });

  document.querySelectorAll('.deactivate-account').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('.config-row');
      await api(`/accounts/${row.dataset.accountId}`, { method: 'DELETE' });
      await refreshAccounts();
    });
  });

  document.querySelectorAll('.delete-account').forEach((button) => {
    button.addEventListener('click', async () => {
      const row = button.closest('.config-row');
      const name = row.querySelector('.config-name').value;
      if (!window.confirm(`Excluir definitivamente ${name}?`)) return;
      await api(`/accounts/${row.dataset.accountId}/permanent`, { method: 'DELETE' });
      await refreshAccounts();
    });
  });
}

async function refreshAccounts() {
  state.accounts = await api('/accounts');
  state.selectedAccounts = new Set(state.accounts.map((account) => account.name));
  renderChips();
  await loadDashboard();
  await renderConfig();
}

function render() {
  const currentRows = filterRows(state.current.rows);
  const previousRows = filterRows(state.previous.rows);
  renderSummary(currentRows, previousRows);
  renderDay();
  renderMagazine(currentRows);
  renderCompare(currentRows);
  renderChannels();
  renderIndividual();
  renderAlerts();
  renderConfig();
}

function getRanges() {
  if ($('mode').value === 'Comparar meses') {
    return {
      previous: monthRange(months[$('month-a').value]),
      current: monthRange(months[$('month-b').value]),
    };
  }
  const current = quickRange();
  return { current, previous: previousRange(current[0], current[1]) };
}

async function loadDashboard() {
  try {
    showStatus('Carregando dashboard...');
    const ranges = getRanges();
    const [prevStart, prevEnd] = ranges.previous;
    const [start, end] = ranges.current;
    $('period-label').textContent = `Período: ${iso(start)} a ${iso(end)} | Comparação: ${iso(prevStart)} a ${iso(prevEnd)}`;
    state.current = await api(`/dashboard/executive?start_date=${iso(start)}&end_date=${iso(end)}`);
    state.previous = await api(`/dashboard/executive?start_date=${iso(prevStart)}&end_date=${iso(prevEnd)}`);
    $('last-sync').textContent = `Atualizado: ${formatDateTime(state.current.last_sync_at)}`;
    render();
    hideStatus();
  } catch (error) {
    showStatus(`Erro ao carregar: ${error.message}`);
  }
}

function downloadCsv(rows, filename = 'comparativo_revistas.csv') {
  const columns = Object.keys(rows[0] || {});
  const csv = [columns.join(';')]
    .concat(rows.map((row) => columns.map((col) => String(row[col] ?? '').replaceAll(';', ',')).join(';')))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
}

function selectedNames() {
  return [...state.selectedAccounts];
}

async function initApp() {
  fillMonthSelects();
  state.accounts = await api('/accounts');
  state.selectedAccounts = new Set(state.accounts.map((account) => account.name));
  renderChips();
  await renderConfig();
  await loadDashboard();
}

document.querySelectorAll('#mode-segment button').forEach((button) => {
  button.addEventListener('click', () => setSegmentValue('mode', 'mode-segment', button.dataset.value));
});

document.querySelectorAll('#quick-buttons button').forEach((button) => {
  button.addEventListener('click', () => setSegmentValue('quick', 'quick-buttons', button.dataset.value));
});

$('clear-filters').addEventListener('click', () => {
  state.selectedAccounts = new Set(state.accounts.map((account) => account.name));
  renderChips();
  loadDashboard();
});

$('sync-btn').addEventListener('click', async () => {
  try {
    showStatus('Sincronizando dados do GHL...');
    const result = await api('/sync/run?days_back=365', { method: 'POST' });
    if (result.errors?.length) {
      const errors = result.errors.map((item) => `${item.account || 'GHL'}: ${item.error}`).join(' | ');
      showStatus(`Sincronizacao concluida com erros. ${errors}`);
      return;
    }
    showStatus(
      `Sincronizado: ${result.accounts} revistas, `
      + `${result.leads_inserted_or_updated} leads, `
      + `${result.opportunities_inserted_or_updated} oportunidades, `
      + `${result.conversations_inserted_or_updated} conversas.`
    );
    await loadDashboard();
  } catch (error) {
    showStatus(`Erro ao sincronizar GHL: ${error.message}`);
  }
});

$('pdf-btn').addEventListener('click', () => {
  window.print();
});

document.querySelectorAll('.tabs button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach((item) => item.classList.add('hidden'));
    button.classList.add('active');
    $(button.dataset.tab).classList.remove('hidden');
  });
});

['mode', 'quick', 'month-a', 'month-b', 'start-date', 'end-date'].forEach((id) => {
  $(id).addEventListener('change', () => {
    updateFilterVisibility();
    loadDashboard();
  });
});

initApp();
