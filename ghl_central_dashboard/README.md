# Future GHL Central Dashboard

Dashboard central para consolidar leads, oportunidades, vendas e origem dos leads de múltiplas subcontas do GoHighLevel/LeadConnector.

## Rodar local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Gere a chave de criptografia:

```bash
python scripts/generate_fernet_key.py
```

Suba o banco com Docker:

```bash
docker compose up -d
```

Crie as tabelas:

```bash
python scripts/create_tables.py
```

Rode a API:

```bash
uvicorn app.main:app --reload
```

Rode o dashboard:

```bash
streamlit run dashboard/streamlit_app.py
```

## Fluxo MVP

1. Cadastrar subcontas em `/accounts`.
2. Rodar sincronização em `/sync/run`.
3. Ver métricas em `/dashboard/summary`.
4. Usar o Streamlit para comparar hoje x ontem ou datas personalizadas.

## Regras importantes

- Lead é contado por `ghl_created_at`, não por `synced_at`.
- Tokens são criptografados antes de salvar no banco.
- Duplicidade é bloqueada por `ghl_contact_id + account_id`.
