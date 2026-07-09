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
  sla: null,
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

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
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

function money(value) {
  return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
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

const kpiDescriptions = {
  'Total leads': 'Novos leads recebidos no periodo selecionado.',
  'Atendimentos': 'Leads que chegaram em atendimento no CRM.',
  'Conversas na caixa': 'Conversas que entraram na caixa do CRM.',
  'Contatos no WhatsApp': 'Pessoas unicas que falaram pelo WhatsApp.',
  'Vendas': 'Oportunidades marcadas como venda no periodo.',
  'Taxa atendimento': 'Percentual de leads que viraram atendimento.',
  'Canais identificados': 'Leads com origem clara, como Google ou Instagram.',
  'Resposta media': 'Tempo medio ate a ultima resposta humana.',
};

function compareKpi(title, current, previous, unit = '', tone = 'blue', labels = {}) {
  const diff = Number(current || 0) - Number(previous || 0);
  const diffText = `${diff >= 0 ? '+' : ''}${diff}${unit ? ` ${unit}` : ''}`;
  const diffClass = diff >= 0 ? 'positive' : 'negative';
  const previousLabel = labels.previous || 'Periodo anterior';
  const currentLabel = labels.current || 'Periodo atual';
  const description = kpiDescriptions[title] || '';
  return `<article class="card compare-kpi ${tone}">
    <div class="compare-head">
      <span>${title}</span>
      <em class="${diffClass}">${diffText}</em>
    </div>
    ${description ? `<p class="kpi-description">${description}</p>` : ''}
    <div class="compare-main">
      <div><small>Anterior</small><span class="period-date">${previousLabel}</span><strong>${previous}</strong></div>
      <div class="arrow">&rarr;</div>
      <div><small>Atual</small><span class="period-date">${currentLabel}</span><strong>${current}</strong></div>
    </div>
  </article>`;
}

function singleKpi(title, value, subtitle = '', tone = 'blue') {
  const description = kpiDescriptions[title] || '';
  return `<article class="card compare-kpi single ${tone}">
    <div class="compare-head"><span>${title}</span></div>
    ${description ? `<p class="kpi-description">${description}</p>` : ''}
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
      ${singleKpi('Canais identificados', pct(leads ? (channel / leads) * 100 : 0), `${channel} leads`, 'blue')}
    </div>
    <br>
    ${renderHighlights()}
    ${renderDropRanking(currentRows)}
    ${renderExecutiveBoard(currentRows)}
  `;
}

function renderHighlights() {
  const highlights = state.current.highlights || {};
  return `<div class="highlight-grid">
    ${miniHighlight('Mais leads', highlights.most_leads, 'new_leads', 'blue')}
    ${miniHighlight('Mais conversas', highlights.most_inbox_conversations, 'inbox_conversations', 'blue')}
    ${miniHighlight('Maior alta', highlights.biggest_growth, 'lead_delta', 'green', ' leads')}
    ${miniHighlight('Maior queda', highlights.biggest_drop, 'lead_delta', 'red', ' leads')}
  </div>`;
}

function renderDropRanking(rows) {
  const drops = [...rows]
    .map((row) => ({
      ...row,
      lead_delta: Number(row.new_leads || 0) - Number(row.previous_new_leads || 0),
    }))
    .sort((a, b) => a.lead_delta - b.lead_delta)
    .slice(0, 5);
  if (!drops.length) return '';
  return `<article class="card drop-ranking">
    <header>
      <strong>Ranking de queda</strong>
      <span>Revistas que mais caíram em leads contra o período anterior.</span>
    </header>
    <div class="drop-ranking-list">
      ${drops.map((row) => `
        <div class="drop-ranking-row">
          <strong>${escapeHtml(row.account)}</strong>
          <span>${row.previous_new_leads || 0} → ${row.new_leads || 0}</span>
          <em class="${row.lead_delta < 0 ? 'negative' : 'positive'}">${signed(row.lead_delta)} leads</em>
        </div>
      `).join('')}
    </div>
  </article>`;
}

function ratio(value, total) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (Number(value || 0) / Number(total || 0)) * 100));
}

function signed(value) {
  const number = Number(value || 0);
  return `${number >= 0 ? '+' : ''}${number}`;
}

function compactDate(value) {
  const date = parseLocalDate(value);
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function dailyRowsFor(accountName) {
  const leads = filterRows(state.current.daily_by_account).filter((item) => item.account === accountName);
  const conversations = filterRows(state.current.daily_conversations_by_account).filter((item) => item.account === accountName);
  const conversationsByDate = new Map(conversations.map((item) => [item.date, Number(item.conversations || 0)]));
  return leads.map((item) => ({
    date: item.date,
    leads: Number(item.leads || 0),
    conversations: conversationsByDate.get(item.date) || 0,
  }));
}

function renderMiniBars(items, key) {
  if (!items.length) return '<div class="ops-empty">Sem dados diarios</div>';
  const max = Math.max(...items.map((item) => Number(item[key] || 0)), 1);
  return `<div class="ops-mini-bars">
    ${items.map((item) => {
      const value = Number(item[key] || 0);
      const height = Math.max(8, Math.round((value / max) * 58));
      return `<span style="--bar:${height}px" title="${compactDate(item.date)}: ${value}">
        <i>${value}</i>
        <em>${compactDate(item.date)}</em>
      </span>`;
    }).join('')}
  </div>`;
}

function renderGauge(label, percent, valueLabel) {
  const safePercent = Math.max(0, Math.min(100, Number(percent || 0)));
  return `<div class="ops-gauge" style="--pct:${safePercent}">
    <div class="ops-gauge-arc"></div>
    <strong>${valueLabel || pct(safePercent)}</strong>
    <span>${label}</span>
  </div>`;
}

function renderExecutiveBoard(rows) {
  const ordered = [...rows].sort((a, b) => Number(b.new_leads || 0) - Number(a.new_leads || 0));
  if (!ordered.length) return '<div class="empty-state"><strong>Nenhuma revista selecionada.</strong></div>';

  const maxLeads = Math.max(...ordered.map((row) => Number(row.new_leads || 0)), 1);
  return `<section class="ops-board">
    <header class="ops-board-title">
      <span>Resumo do periodo selecionado</span>
      <strong>Entrada de leads por revista</strong>
    </header>
    <div class="ops-help">
      <span><strong>Número grande:</strong> leads recebidos no período</span>
      <span><strong>Bolinha:</strong> diferença contra o período anterior</span>
      <span><strong>Medidores:</strong> atendimento e origem identificada</span>
      <span><strong>Rodapé:</strong> conversas, pessoas no WhatsApp e vendas</span>
    </div>
    <div class="ops-columns">
      ${ordered.map((row) => {
        const daily = dailyRowsFor(row.account);
        const leadShare = ratio(row.new_leads, maxLeads);
        const leadDelta = Number(row.new_leads || 0) - Number(row.previous_new_leads || 0);
        const tone = leadDelta >= 0 ? 'good' : 'bad';
        return `<article class="ops-column">
          <header class="ops-column-head">
            <strong>${escapeHtml(row.account)}</strong>
            <span>Origem principal: ${escapeHtml(row.best_channel || 'Sem canal')}</span>
          </header>
          <section class="ops-current">
            <div>
              <span>Leads recebidos</span>
              <strong>${row.new_leads || 0}</strong>
            </div>
            <em class="${tone}" title="Comparado com o periodo anterior">${signed(leadDelta)}</em>
          </section>
          <div class="ops-progress"><span style="width:${leadShare}%"></span></div>
          <section class="ops-gauge-row">
            ${renderGauge('Viraram atendimento', row.attendance_rate, pct(row.attendance_rate))}
            ${renderGauge('Com origem clara', row.channel_identified_rate, pct(row.channel_identified_rate))}
          </section>
          <section class="ops-history">
            <strong>Leads por dia</strong>
            ${renderMiniBars(daily, 'leads')}
          </section>
          <footer class="ops-foot">
            <span><strong>${row.inbox_conversations || 0}</strong> conversas abertas</span>
            <span><strong>${row.whatsapp_contacts || 0}</strong> pessoas no WhatsApp</span>
            <span><strong>${row.sales || 0}</strong> vendas feitas</span>
          </footer>
        </article>`;
      }).join('')}
    </div>
  </section>`;
}

function renderDailyOperations(rows) {
  const ordered = [...rows].sort((a, b) => Number(b.new_leads || 0) - Number(a.new_leads || 0));
  if (!ordered.length) return '<div class="empty-state"><strong>Nenhuma revista selecionada.</strong></div>';

  const allDaily = ordered.flatMap((row) => dailyRowsFor(row.account));
  const maxDaily = Math.max(...allDaily.map((item) => Math.max(item.leads, item.conversations)), 1);
  return `<section class="ops-day-board">
    <header class="ops-board-title">
      <span>Controle diario</span>
      <strong>Entrada de leads e conversas por dia</strong>
    </header>
    <div class="ops-day-grid">
      ${ordered.map((row) => {
        const daily = dailyRowsFor(row.account);
        return `<article class="ops-day-card">
          <header>
            <strong>${escapeHtml(row.account)}</strong>
            <span>${row.new_leads || 0} leads no periodo</span>
          </header>
          <div class="ops-day-table">
            ${daily.map((item) => {
              const leadHeat = (item.leads / maxDaily).toFixed(2);
              const conversationHeat = (item.conversations / maxDaily).toFixed(2);
              return `<div class="ops-day-row">
                <span>${compactDate(item.date)}</span>
                <strong style="--heat:${leadHeat}">${item.leads}</strong>
                <em style="--heat:${conversationHeat}">${item.conversations}</em>
              </div>`;
            }).join('') || '<div class="ops-empty">Sem dados diarios</div>'}
          </div>
          <footer><span>Leads</span><span>Conversas</span></footer>
        </article>`;
      }).join('')}
    </div>
  </section>`;
}

function renderDay() {
  $('dia').innerHTML = `${section('Por dia')}${renderDailyOperations(filterRows(state.current.rows))}`;
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
  const metrics = ['new_leads', 'inbox_conversations', 'whatsapp_contacts', 'attendances', 'sales', 'attendance_rate', 'sales_rate', 'channel_identified_rate', 'health_score'];
  const rows = [...currentRows].sort((a, b) => Number(b.new_leads || 0) - Number(a.new_leads || 0));

  $('comparar').innerHTML = `${section('Comparar revistas')}
    <div class="card compare-filter-card">
      <div class="compare-filter-head">
        <div>
          <strong>Revistas na comparação</strong>
          <span>${state.selectedAccounts.size} de ${state.accounts.length} selecionadas</span>
        </div>
        <button id="compare-select-all" class="secondary" type="button">Selecionar todas</button>
      </div>
      <div class="compare-chips">
        ${state.accounts.map((account) => {
          const active = state.selectedAccounts.has(account.name);
          return `<button type="button" class="compare-chip ${active ? '' : 'off'}" data-account="${account.name}">${account.name}</button>`;
        }).join('')}
      </div>
    </div>
    <br>
    <div class="lead-panel">
      ${rows.map((row) => `
        <article class="lead-card">
          <span>${row.account}</span>
          <strong>${row.new_leads || 0}</strong>
          <small>leads</small>
        </article>
      `).join('') || '<div class="empty-state"><strong>Nenhuma revista selecionada.</strong></div>'}
    </div>
    <br>
    <div class="card compare-table">
      <table>
        <thead><tr><th>Indicador</th>${rows.map((row) => `<th>${row.account}</th>`).join('')}<th>Vencedor</th></tr></thead>
        <tbody>
          ${metrics.map((key) => {
            const bestValue = Math.max(...rows.map((row) => Number(row[key] || 0)), 0);
            const winners = rows.filter((row) => Number(row[key] || 0) === bestValue).map((row) => row.account);
            const winner = !rows.length ? '-' : winners.length === rows.length ? 'Empate' : winners.join(', ');
            return `<tr><td>${metricLabels[key]}</td>${rows.map((row) => `<td>${cardValue(row, key)}</td>`).join('')}<td>${winner}</td></tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;

  $('compare-select-all').addEventListener('click', () => {
    state.selectedAccounts = new Set(state.accounts.map((account) => account.name));
    renderChips();
    renderCompare(filterRows(state.current.rows));
  });
  document.querySelectorAll('.compare-chip').forEach((button) => {
    button.addEventListener('click', () => {
      const name = button.dataset.account;
      if (state.selectedAccounts.has(name)) state.selectedAccounts.delete(name);
      else state.selectedAccounts.add(name);
      renderChips();
      renderCompare(filterRows(state.current.rows));
    });
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

function formatWait(minutes) {
  const value = Number(minutes || 0);
  const days = Math.floor(value / 1440);
  const remainder = value % 1440;
  const hours = Math.floor(remainder / 60);
  const mins = remainder % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours <= 0) return `${mins} min`;
  return `${hours}h ${String(mins).padStart(2, '0')}min`;
}

function formatSlaClock(item) {
  if (item.overdue) return `-${formatWait(item.overdue_minutes || 0)}`;
  if (item.minutes_to_overdue === null || item.minutes_to_overdue === undefined) return '-';
  return formatWait(item.minutes_to_overdue);
}

function slaStatusLabel(item) {
  if (item.overdue) return 'Vencido';
  if (Number(item.minutes_to_overdue || 0) <= 30) return 'Vence em breve';
  return 'Dentro do SLA';
}

function slaStatusClass(item) {
  if (item.overdue) return 'overdue';
  if (Number(item.minutes_to_overdue || 0) <= 30) return 'soon';
  return 'ok';
}

function actorClass(actor) {
  if (actor === 'IA/Automacao') return 'ai';
  if (actor === 'Atendente') return 'human';
  if (actor === 'Cliente') return 'client';
  return 'unknown';
}

function actorLabel(actor) {
  if (actor === 'IA/Automacao') return 'IA/automação';
  return actor || 'Indefinido';
}

function slaCriticalTable(items) {
  return `<table class="sla-table"><thead><tr>
    <th>Revista</th>
    <th>Contato</th>
    <th>Última interação</th>
    <th>Não lidas</th>
    <th>Telefone</th>
    <th>Ultima mensagem</th>
    <th>Timer GHL</th>
    <th>Tempo SLA</th>
    <th>Status</th>
    <th>Mensagem</th>
  </tr></thead><tbody>${items.map((item) => `
    <tr>
      <td>${escapeHtml(item.account)}</td>
      <td>${escapeHtml(item.contact_name)}</td>
      <td><span class="actor-pill ${actorClass(item.last_actor)}">${escapeHtml(actorLabel(item.last_actor))}</span></td>
      <td>${item.unread_count || 0}</td>
      <td>${escapeHtml(item.phone || '-')}</td>
      <td>${escapeHtml(formatDateTime(item.last_message_at))}</td>
      <td><span class="sla-clock ${slaStatusClass(item)}">${escapeHtml(formatSlaClock(item))}</span></td>
      <td>${escapeHtml(formatWait(item.wait_minutes))}</td>
      <td><span class="sla-pill ${slaStatusClass(item)}">${slaStatusLabel(item)}</span></td>
      <td class="sla-message">${escapeHtml(item.last_message_body || '-')}</td>
    </tr>
  `).join('')}</tbody></table>`;
}

function slaSummaryTable(rows) {
  return `<table class="sla-table"><thead><tr>
    <th>Revista</th>
    <th>Conversas</th>
    <th>Sem resposta</th>
    <th>Não lidas</th>
    <th>Com IA</th>
    <th>Atendente respondeu</th>
    <th>SLA vencido</th>
    <th>Vence em breve</th>
    <th>Dentro do SLA</th>
    <th>Resposta media</th>
    <th>Tempo medio</th>
    <th>Maior espera</th>
    <th>Taxa vencida</th>
  </tr></thead><tbody>${rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.account)}</td>
      <td>${row.conversations}</td>
      <td>${row.waiting_response}</td>
      <td>${row.unread || 0}</td>
      <td>${row.ai_handling || 0}</td>
      <td>${row.human_replied || 0}</td>
      <td>${row.overdue}</td>
      <td>${row.due_soon || 0}</td>
      <td>${row.sla_ok}</td>
      <td>${row.response_count ? escapeHtml(formatWait(Math.round(row.avg_response_minutes || 0))) : '-'}</td>
      <td>${escapeHtml(formatWait(Math.round(row.avg_wait_minutes || 0)))}</td>
      <td>${escapeHtml(formatWait(row.max_wait_minutes))}</td>
      <td>${escapeHtml(pct(row.overdue_rate || 0))}</td>
    </tr>
  `).join('')}</tbody></table>`;
}

function renderSla() {
  const data = state.sla;
  const container = $('sla');
  if (!data) {
    container.innerHTML = `${section('SLA de atendimento')}<div class="support-loading">Carregando SLA...</div>`;
    return;
  }

  const selected = new Set(selectedNames());
  const rows = (data.rows || []).filter((row) => selected.has(row.account));
  const critical = (data.critical_items || []).filter((item) => selected.has(item.account));
  const totals = rows.reduce((acc, row) => {
    acc.conversations += Number(row.conversations || 0);
    acc.waiting_response += Number(row.waiting_response || 0);
    acc.unread += Number(row.unread || 0);
    acc.ai_handling += Number(row.ai_handling || 0);
    acc.human_replied += Number(row.human_replied || 0);
    acc.due_soon += Number(row.due_soon || 0);
    acc.overdue += Number(row.overdue || 0);
    acc.sla_ok += Number(row.sla_ok || 0);
    acc.response_minutes += Number(row.avg_response_minutes || 0) * Number(row.response_count || 0);
    acc.response_count += Number(row.response_count || 0);
    return acc;
  }, { conversations: 0, waiting_response: 0, unread: 0, ai_handling: 0, human_replied: 0, due_soon: 0, overdue: 0, sla_ok: 0, response_minutes: 0, response_count: 0 });
  const overdueRate = totals.waiting_response ? (totals.overdue / totals.waiting_response) * 100 : 0;
  const avgResponse = totals.response_count ? Math.round(totals.response_minutes / totals.response_count) : 0;
  const avgWait = critical.length
    ? Math.round(critical.reduce((sumValue, item) => sumValue + Number(item.wait_minutes || 0), 0) / critical.length)
    : 0;
  const sortedRows = [...rows].sort((a, b) => Number(b.overdue || 0) - Number(a.overdue || 0));

  container.innerHTML = `${section('SLA de atendimento')}
    <div class="kpi-grid">
      ${singleKpi('Conversas no periodo', totals.conversations, 'entraram na caixa', 'blue')}
      ${singleKpi('SLA ativo', totals.waiting_response, 'timer vindo do GHL', totals.waiting_response ? 'orange' : 'green')}
      ${singleKpi('Com IA', totals.ai_handling, 'IA respondeu mas SLA segue', totals.ai_handling ? 'orange' : 'green')}
      ${singleKpi('Atendente respondeu', totals.human_replied, 'SLA resolvido por humano', 'green')}
      ${singleKpi('Não lidas', totals.unread, 'unreadCount do GHL', totals.unread ? 'orange' : 'green')}
      ${singleKpi('SLA vencido', totals.overdue, 'overdueAt já passou', totals.overdue ? 'red' : 'green')}
      ${singleKpi('Vence em breve', totals.due_soon, 'proximos 30 min', totals.due_soon ? 'orange' : 'green')}
      ${singleKpi('Resposta media', totals.response_count ? formatWait(avgResponse) : '-', 'ultima resposta humana', 'blue')}
      ${singleKpi('Tempo medio', formatWait(avgWait), 'desde slaStartAt', 'orange')}
      ${singleKpi('Taxa vencida', pct(overdueRate), 'vencidas / sem resposta', overdueRate ? 'red' : 'green')}
    </div>
    <br>
    <div class="grid-2">
      <article class="card chart-card">
        <h3>Revistas com mais SLA vencido</h3>
        ${bars(sortedRows, 'overdue', totals.overdue ? 'orange' : 'green')}
      </article>
      <article class="card chart-card">
        <h3>Conversas aguardando resposta</h3>
        ${bars([...rows].sort((a, b) => Number(b.waiting_response || 0) - Number(a.waiting_response || 0)), 'waiting_response', 'blue')}
      </article>
    </div>
    <br>
    <article class="card compare-table">
      <h3>Resumo por revista</h3>
      ${sortedRows.length ? slaSummaryTable(sortedRows) : '<p>Sem conversas para os filtros selecionados.</p>'}
    </article>
    <br>
    <article class="card compare-table">
      <h3>Fila critica</h3>
      ${critical.length ? slaCriticalTable(critical.slice(0, 40)) : '<p>Nenhuma conversa sem resposta no periodo.</p>'}
    </article>`;
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

async function renderEditorialSupport() {
  const container = $('suporte-editorial');
  container.innerHTML = `${section('Suporte editorial')}<div class="support-loading">Carregando suporte editorial...</div>`;

  try {
    const data = await api('/dashboard/editorial-support');
    const selected = new Set(selectedNames());
    const groups = (data.groups || []).filter((group) => selected.has(group.account));

    if (!groups.length) {
      container.innerHTML = `${section('Suporte editorial')}
        <div class="empty-state">
          <strong>Nenhuma oportunidade encontrada em Suporte editorial.</strong>
          <span>Conferi o CRM em tempo real e nenhuma revista selecionada tem pessoas nessa etapa agora.</span>
        </div>`;
      return;
    }

    container.innerHTML = `${section('Suporte editorial')}
      <div class="support-board">
        ${groups.map((group) => `
          <article class="support-column">
            <header>
              <div>
                <strong>${escapeHtml(group.account)}</strong>
                <span>Suporte editorial</span>
              </div>
              <em>${group.count}</em>
            </header>
            <div class="support-cards">
              ${group.error ? `<div class="support-card support-error">
                <div class="support-person">
                  <strong>Erro ao consultar esta revista</strong>
                </div>
                <div class="support-meta"><span>${escapeHtml(group.error)}</span></div>
              </div>` : ''}
              ${(group.items || []).map((item) => `
                <div class="support-card">
                  <div class="support-person">
                    <strong>${escapeHtml(item.name)}</strong>
                  </div>
                  <div class="support-line">
                    ${item.phone ? `<span>${escapeHtml(item.phone)}</span>` : ''}
                    ${!item.phone && item.email ? `<span>${escapeHtml(item.email)}</span>` : ''}
                    ${item.stage ? `<span>${escapeHtml(item.stage)}</span>` : ''}
                  </div>
                </div>
              `).join('')}
            </div>
          </article>
        `).join('')}
      </div>`;
  } catch (error) {
    container.innerHTML = `${section('Suporte editorial')}
      <div class="empty-state error-state">
        <strong>Erro ao carregar suporte editorial.</strong>
        <span>${escapeHtml(error.message)}</span>
      </div>`;
  }
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
  renderSla();
  renderAlerts();
  renderEditorialSupport();
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
    state.sla = await api(`/dashboard/sla?start_date=${iso(start)}&end_date=${iso(end)}&sla_hours=2`);
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

async function runSync(daysBack, label) {
  try {
    showStatus(`Sincronizando ${label} no GHL...`);
    const result = await api(`/sync/run?days_back=${daysBack}`, { method: 'POST' });
    if (result.errors?.length) {
      const errors = result.errors.map((item) => `${item.account || 'GHL'}: ${item.error}`).join(' | ');
      showStatus(`Sincronizacao concluida com erros. ${errors}`);
      return;
    }
    showStatus(
      `Sincronizado: ${result.accounts} revistas, `
      + `${result.leads_inserted_or_updated} leads, `
      + `${result.opportunities_inserted_or_updated} oportunidades, `
      + `${result.conversations_inserted_or_updated} conversas, `
      + `${result.snapshots_created_or_updated || 0} dias consolidados.`
    );
    await loadDashboard();
  } catch (error) {
    showStatus(`Erro ao sincronizar GHL: ${error.message}`);
  }
}

$('sync-btn').addEventListener('click', () => runSync(7, 'ultimos 7 dias'));
$('sync-full-btn').addEventListener('click', () => runSync(3650, 'historico completo'));

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
