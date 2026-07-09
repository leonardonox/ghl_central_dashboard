from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from app.core.config import get_settings

st.set_page_config(page_title='Dashboard Revistas', layout='wide')

API_DEFAULT = 'http://127.0.0.1:8000'
settings = get_settings()
YEAR = 2026
MONTHS = {
    'Janeiro': 1,
    'Fevereiro': 2,
    'Marco': 3,
    'Abril': 4,
    'Maio': 5,
    'Junho': 6,
    'Julho': 7,
    'Agosto': 8,
    'Setembro': 9,
    'Outubro': 10,
    'Novembro': 11,
    'Dezembro': 12,
}
CHANNELS = [
    '1. JA PUBLIQUEI',
    '2. RECEBI UM CONVITE',
    '3. POR MEIO DO GOOGLE',
    '4. POR INDICACAO',
    '5. INSTAGRAM/FACEBOOK',
    '6. LINKEDIN',
]


def get_json(url: str, path: str, params: dict | None = None):
    response = requests.get(f'{url.rstrip("/")}{path}', params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def require_login() -> None:
    if st.session_state.get('authenticated'):
        return

    st.markdown(
        """
        <style>
            .block-container { max-width: 520px; padding-top: 5rem; }
            .stApp { background: #f3f7fb; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title('Dashboard Revistas')
    st.caption('Acesso restrito')
    username = st.text_input('Usuario')
    password = st.text_input('Senha', type='password')
    if st.button('Entrar', use_container_width=True):
        if username == settings.dashboard_username and password == settings.dashboard_password:
            st.session_state['authenticated'] = True
            st.rerun()
        st.error('Usuario ou senha invalidos.')
    st.stop()


def month_range(month: int) -> tuple[date, date]:
    start = date(YEAR, month, 1)
    if month == 12:
        end = date(YEAR, 12, 31)
    else:
        end = date(YEAR, month + 1, 1) - timedelta(days=1)
    today = date.today()
    if start.year == today.year and start.month == today.month:
        end = min(end, today)
    return start, end


def quick_range(option: str, custom_period, month_name: str) -> tuple[date, date]:
    today = date.today()
    if option == 'Hoje':
        return today, today
    if option == 'Semana':
        return today - timedelta(days=6), today
    if option == 'Mes':
        return today.replace(day=1), today
    if option == 'Mes especifico':
        return month_range(MONTHS[month_name])
    if isinstance(custom_period, tuple) and len(custom_period) == 2:
        return custom_period
    return today - timedelta(days=6), today


def pct(value: float) -> str:
    return f'{value:.2f}%'


def signed_pct(value: float) -> str:
    signal = '+' if value > 0 else ''
    return f'{signal}{value:.2f}%'


def metric_card(title: str, value, subtitle: str = '', tone: str = 'blue') -> None:
    colors = {
        'blue': '#2f80c1',
        'green': '#2f6b22',
        'orange': '#e8792e',
        'red': '#b42318',
        'gray': '#51606f',
    }
    border = colors.get(tone, '#2f80c1')
    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{border}">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def filter_rows(rows: list[dict], selected_names: list[str]) -> list[dict]:
    if not selected_names:
        return rows
    return [row for row in rows if row['account'] in selected_names]


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {
            'new_leads': 0,
            'attendances': 0,
            'sales': 0,
            'new_leads_with_channel': 0,
            'hsm_leads': 0,
            'attendance_rate': 0.0,
            'sales_rate': 0.0,
            'channel_identified_rate': 0.0,
        }
    leads = sum(row['new_leads'] for row in rows)
    attendances = sum(row['attendances'] for row in rows)
    sales = sum(row['sales'] for row in rows)
    channels = sum(row['new_leads_with_channel'] for row in rows)
    hsm = sum(row['hsm_leads'] for row in rows)
    return {
        'new_leads': leads,
        'attendances': attendances,
        'sales': sales,
        'new_leads_with_channel': channels,
        'hsm_leads': hsm,
        'attendance_rate': round((attendances / leads) * 100, 2) if leads else 0.0,
        'sales_rate': round((sales / leads) * 100, 2) if leads else 0.0,
        'channel_identified_rate': round((channels / leads) * 100, 2) if leads else 0.0,
    }


def filter_daily(items: list[dict], selected_names: list[str]) -> pd.DataFrame:
    rows = [item for item in items if not selected_names or item['account'] in selected_names]
    df = pd.DataFrame(rows)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df


def filter_channels(items: list[dict], selected_names: list[str]) -> pd.DataFrame:
    rows = [item for item in items if not selected_names or item['account'] in selected_names]
    return pd.DataFrame(rows)


require_login()

st.markdown(
    """
    <style>
        .stApp {
            background: #f3f7fb;
        }
        .block-container {
            padding-top: 0;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            max-width: 100%;
        }
        .topbar {
            background: linear-gradient(135deg, #1f5f95, #2f80c1);
            color: white;
            padding: 1rem 1.4rem;
            margin: 0 -0.8rem 1rem;
            box-shadow: 0 2px 12px rgba(31, 95, 149, 0.25);
        }
        .topbar h1 {
            color: white;
            font-size: 1.35rem;
            margin: 0;
            font-weight: 800;
        }
        .topbar p {
            margin: 0.25rem 0 0;
            color: rgba(255,255,255,0.82);
            font-size: 0.86rem;
        }
        .filter-panel {
            background: #ffffff;
            border: 1px solid #d7e3ef;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.8rem;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        }
        .section-title {
            width: 100%;
            border-radius: 5px;
            background: #0f172a;
            color: white;
            font-size: 0.78rem;
            font-weight: 800;
            text-align: center;
            padding: 0.35rem 0.5rem;
            margin: 0.75rem 0 0.6rem;
        }
        .kpi-card {
            background: #ffffff;
            border: 1px solid #dfe7f0;
            border-left: 5px solid #2f80c1;
            border-radius: 10px;
            min-height: 118px;
            padding: 0.9rem 1rem;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
        }
        .kpi-title {
            color: #5b6675;
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .kpi-value {
            color: #253047;
            font-size: 1.75rem;
            font-weight: 800;
            line-height: 1.15;
            margin-top: 0.5rem;
            overflow-wrap: anywhere;
        }
        .kpi-subtitle {
            color: #8a96a6;
            font-size: 0.76rem;
            margin-top: 0.25rem;
        }
        .diagnosis {
            background: #ffffff;
            border: 1px solid #dfe7f0;
            border-left: 5px solid #2f6b22;
            border-radius: 10px;
            padding: 0.9rem 1rem;
            color: #253047;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stTabs"] button {
            font-weight: 700;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

API_URL = st.sidebar.text_input('API URL', value=API_DEFAULT)
st.sidebar.header('Atualizacao')
sync_days = st.sidebar.number_input('Dias para sincronizar', min_value=1, max_value=3650, value=3650, step=1)
if st.sidebar.button('Atualizar dados do GHL', use_container_width=True):
    with st.spinner('Sincronizando dados...'):
        response = requests.post(f'{API_URL.rstrip("/")}/sync/run', params={'days_back': sync_days}, timeout=300)
        response.raise_for_status()
    st.sidebar.success('Dados atualizados.')
    st.rerun()

st.sidebar.header('Historico')
if st.sidebar.button('Consolidar historico', use_container_width=True):
    with st.spinner('Consolidando snapshots diarios...'):
        today = date.today()
        response = requests.post(
            f'{API_URL.rstrip("/")}/dashboard/snapshots/build',
            params={'start_date': (today - timedelta(days=sync_days - 1)).isoformat(), 'end_date': today.isoformat()},
            timeout=120,
        )
        response.raise_for_status()
    st.sidebar.success('Historico consolidado.')
    st.rerun()

if st.sidebar.button('Sair', use_container_width=True):
    st.session_state.clear()
    st.rerun()

try:
    accounts = get_json(API_URL, '/accounts')
    if not accounts:
        st.warning('Nenhuma revista ativa cadastrada.')
        st.stop()

    account_names = [account['name'] for account in accounts]

    st.markdown(
        f"""
        <div class="topbar">
            <h1>Dashboard Comparativo de Revistas — {YEAR}</h1>
            <p>Leads, atendimentos, canais, vendas, metas e comparativos por periodo</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.2, 2.2])
    with f1:
        mode = st.selectbox('Tipo de analise', ['Periodo unico', 'Comparar meses'])
    with f2:
        quick = st.selectbox('Periodo rapido', ['Semana', 'Mes', 'Hoje', 'Mes especifico', 'Personalizado'])
    with f3:
        month_single = st.selectbox('Mes do periodo', list(MONTHS.keys()), index=5)
    with f4:
        custom_period = st.date_input(
            'Periodo personalizado',
            value=(date.today() - timedelta(days=6), date.today()),
            format='DD/MM/YYYY',
            disabled=quick != 'Personalizado',
        )

    m1, m2, m3, m4 = st.columns([1, 1, 1, 2.5])
    with m1:
        month_a = st.selectbox('Mes A', list(MONTHS.keys()), index=4)
    with m2:
        month_b = st.selectbox('Mes B', list(MONTHS.keys()), index=5)
    with m3:
        metric_focus = st.selectbox('Metrica', ['new_leads', 'attendances', 'sales', 'attendance_rate'], format_func={
            'new_leads': 'Leads',
            'attendances': 'Atendimentos',
            'sales': 'Vendas',
            'attendance_rate': 'Taxa atendimento',
        }.get)
    with m4:
        selected_accounts = st.multiselect('Revistas', account_names, default=account_names)

    b1, b2, b3, b4 = st.columns([1, 1, 1, 3])
    with b1:
        if st.button('Todas', use_container_width=True):
            selected_accounts = account_names
    with b2:
        top_n = st.selectbox('Top', ['Todas', 'Top 3', 'Top 5', 'Top 10'])
    with b3:
        show_weekends = st.checkbox('Destacar FDS', value=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if mode == 'Comparar meses':
        start_a, end_a = month_range(MONTHS[month_a])
        start_b, end_b = month_range(MONTHS[month_b])
        current_label = month_b
        previous_label = month_a
    else:
        start_b, end_b = quick_range(quick, custom_period, month_single)
        days = (end_b - start_b).days + 1
        end_a = start_b - timedelta(days=1)
        start_a = end_a - timedelta(days=days - 1)
        current_label = f'{start_b.strftime("%d/%m")} - {end_b.strftime("%d/%m")}'
        previous_label = f'{start_a.strftime("%d/%m")} - {end_a.strftime("%d/%m")}'

    params_a = {'start_date': start_a.isoformat(), 'end_date': end_a.isoformat()}
    params_b = {'start_date': start_b.isoformat(), 'end_date': end_b.isoformat()}
    data_a = get_json(API_URL, '/dashboard/executive', params=params_a)
    data_b = get_json(API_URL, '/dashboard/executive', params=params_b)

    rows_a = filter_rows(data_a['rows'], selected_accounts)
    rows_b = filter_rows(data_b['rows'], selected_accounts)
    df_a = pd.DataFrame(rows_a)
    df_b = pd.DataFrame(rows_b)

    if top_n != 'Todas' and not df_b.empty:
        limit = int(top_n.split()[1])
        top_accounts = df_b.sort_values(metric_focus, ascending=False).head(limit)['account'].tolist()
        rows_a = filter_rows(rows_a, top_accounts)
        rows_b = filter_rows(rows_b, top_accounts)
        df_a = pd.DataFrame(rows_a)
        df_b = pd.DataFrame(rows_b)

    totals_a = aggregate(rows_a)
    totals_b = aggregate(rows_b)
    diff_leads = totals_b['new_leads'] - totals_a['new_leads']
    diff_att = totals_b['attendances'] - totals_a['attendances']
    diff_sales = totals_b['sales'] - totals_a['sales']

    tab_summary, tab_day, tab_revista, tab_channels, tab_single, tab_alerts = st.tabs([
        'Resumo',
        'Por dia',
        'Por revista',
        'Canais',
        'Individual',
        'Alertas',
    ])

    with tab_summary:
        section_title(f'RESUMO — {previous_label} VS {current_label}')
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            metric_card('Total leads', f"{totals_a['new_leads']} -> {totals_b['new_leads']}", f'{diff_leads:+} leads', 'blue')
        with c2:
            metric_card('Atendimentos', f"{totals_a['attendances']} -> {totals_b['attendances']}", f'{diff_att:+} atend.', 'green')
        with c3:
            metric_card('Vendas', f"{totals_a['sales']} -> {totals_b['sales']}", f'{diff_sales:+} vendas', 'green')
        with c4:
            metric_card('Taxa atendimento', f"{pct(totals_b['attendance_rate'])}", f"Antes: {pct(totals_a['attendance_rate'])}", 'orange')
        with c5:
            metric_card('Canais identificados', f"{pct(totals_b['channel_identified_rate'])}", f"{totals_b['new_leads_with_channel']} leads", 'blue')
        with c6:
            best_row = max(rows_b, key=lambda item: item[metric_focus]) if rows_b else {'account': '-', metric_focus: 0}
            metric_card('Melhor revista', best_row['account'], f"{metric_focus}: {best_row[metric_focus]}", 'green')

        st.markdown(f'<div class="diagnosis">{data_b["diagnosis"]}</div>', unsafe_allow_html=True)

        daily_a = filter_daily(data_a['daily_by_account'], selected_accounts)
        daily_b = filter_daily(data_b['daily_by_account'], selected_accounts)
        if not daily_a.empty:
            daily_a['periodo'] = previous_label
        if not daily_b.empty:
            daily_b['periodo'] = current_label
        daily_compare = pd.concat([daily_a, daily_b], ignore_index=True)
        daily_total = daily_compare.groupby(['date', 'periodo'], as_index=False)['leads'].sum() if not daily_compare.empty else pd.DataFrame()

        left, right = st.columns([1.15, 1])
        with left:
            st.markdown('**Evolucao diaria acumulada**')
            if daily_total.empty:
                st.info('Sem dados para o periodo.')
            else:
                daily_total = daily_total.sort_values(['periodo', 'date'])
                daily_total['acumulado'] = daily_total.groupby('periodo')['leads'].cumsum()
                fig = px.line(daily_total, x='date', y='acumulado', color='periodo', markers=True)
                fig.update_layout(height=360, plot_bgcolor='white', paper_bgcolor='white', margin={'l': 8, 'r': 8, 't': 10, 'b': 8})
                st.plotly_chart(fig, use_container_width=True)
        with right:
            st.markdown('**Composicao util vs FDS**')
            if daily_b.empty:
                st.info('Sem dados para o periodo.')
            else:
                daily_b['tipo_dia'] = daily_b['date'].dt.dayofweek.apply(lambda value: 'FDS' if value >= 5 else 'Dia util')
                donut_df = daily_b.groupby('tipo_dia', as_index=False)['leads'].sum()
                fig = px.pie(donut_df, names='tipo_dia', values='leads', hole=0.48, color_discrete_sequence=['#2f6b22', '#e8792e'])
                fig.update_layout(height=360, margin={'l': 8, 'r': 8, 't': 10, 'b': 8})
                st.plotly_chart(fig, use_container_width=True)

    with tab_day:
        section_title('ANALISE POR DIA')
        daily_b = filter_daily(data_b['daily_by_account'], selected_accounts)
        if daily_b.empty:
            st.info('Sem dados por dia.')
        else:
            if show_weekends:
                daily_b['tipo_dia'] = daily_b['date'].dt.dayofweek.apply(lambda value: 'FDS' if value >= 5 else 'Dia util')
                fig = px.bar(daily_b, x='date', y='leads', color='tipo_dia', facet_row='account', text='leads')
            else:
                fig = px.line(daily_b, x='date', y='leads', color='account', markers=True, text='leads')
            fig.update_layout(height=620, plot_bgcolor='white', paper_bgcolor='white', margin={'l': 8, 'r': 8, 't': 10, 'b': 8})
            st.plotly_chart(fig, use_container_width=True)

    with tab_revista:
        section_title('COMPARATIVO POR REVISTA')
        if df_b.empty:
            st.info('Sem revistas para exibir.')
        else:
            merged = df_b.merge(
                df_a[['account', metric_focus]].rename(columns={metric_focus: f'{metric_focus}_a'}),
                on='account',
                how='left',
            )
            chart_rows = []
            for _, row in merged.iterrows():
                chart_rows.append({'account': row['account'], 'periodo': previous_label, 'valor': row.get(f'{metric_focus}_a', 0)})
                chart_rows.append({'account': row['account'], 'periodo': current_label, 'valor': row[metric_focus]})
            chart_df = pd.DataFrame(chart_rows)
            fig = px.bar(chart_df, x='valor', y='account', color='periodo', barmode='group', orientation='h', text='valor', color_discrete_sequence=['#e8792e', '#2f6b22'])
            fig.update_layout(height=520, plot_bgcolor='white', paper_bgcolor='white', margin={'l': 8, 'r': 8, 't': 10, 'b': 8}, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

            export_df = df_b.rename(columns={
                'account': 'revista',
                'new_leads': 'leads',
                'attendances': 'atendimentos',
                'sales': 'vendas',
                'attendance_rate': 'taxa_atendimento',
                'sales_rate': 'taxa_venda',
                'channel_identified_rate': 'taxa_canal_identificado',
                'best_channel': 'melhor_canal',
            })
            st.dataframe(export_df, use_container_width=True, hide_index=True)
            st.download_button(
                'Baixar CSV',
                export_df.to_csv(index=False).encode('utf-8-sig'),
                file_name=f'dashboard_revistas_{start_b}_{end_b}.csv',
                mime='text/csv',
                use_container_width=True,
            )

    with tab_channels:
        section_title('CANAIS DE VENDA')
        channel_df = filter_channels(data_b['channel_comparison'], selected_accounts)
        if channel_df.empty:
            st.info('Sem canais identificados.')
        else:
            pivot = channel_df.pivot(index='account', columns='channel', values='leads').fillna(0)
            st.dataframe(pivot, use_container_width=True)
            fig = px.bar(channel_df, x='account', y='leads', color='channel', barmode='group', text='leads')
            fig.update_layout(height=440, plot_bgcolor='white', paper_bgcolor='white', margin={'l': 8, 'r': 8, 't': 10, 'b': 8})
            st.plotly_chart(fig, use_container_width=True)

    with tab_single:
        section_title('PAINEL INDIVIDUAL')
        selected_account = st.selectbox('Revista', selected_accounts or account_names)
        account_id = next(account['id'] for account in accounts if account['name'] == selected_account)
        detail = get_json(API_URL, '/dashboard/performance', params={**params_b, 'account_id': account_id})
        totals = detail['totals']
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            metric_card('Leads', totals['new_leads'])
        with d2:
            metric_card('Atendimentos/HSM', totals['hsm_leads'], tone='green')
        with d3:
            metric_card('Vendas', totals['sales'], tone='green')
        with d4:
            metric_card('Leads com canal', totals['new_leads_with_channel'])

        funnel = pd.DataFrame([
            {'etapa': key.replace('_', ' ').title(), 'quantidade': value}
            for key, value in detail.get('funnel_counts', {}).items()
        ])
        if not funnel.empty:
            fig = px.funnel(funnel, x='quantidade', y='etapa')
            fig.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white', margin={'l': 8, 'r': 8, 't': 10, 'b': 8})
            st.plotly_chart(fig, use_container_width=True)

    with tab_alerts:
        section_title('ALERTAS E DIAGNOSTICO')
        alerts = [alert for alert in data_b['alerts'] if not selected_accounts or alert['account'] in selected_accounts]
        st.markdown(f'<div class="diagnosis">{data_b["diagnosis"]}</div>', unsafe_allow_html=True)
        if alerts:
            st.dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
        else:
            st.success('Nenhum alerta encontrado para os filtros selecionados.')

except Exception as exc:
    st.error(f'Erro ao carregar dashboard: {exc}')
    st.info('Confira se a API esta rodando em http://127.0.0.1:8000')
