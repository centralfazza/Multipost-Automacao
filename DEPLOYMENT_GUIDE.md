# 🚀 Guia de Deployment — Fazza Automation

## 📋 Pré-requisitos

- Python 3.9+
- Git
- Conta GitHub
- Conta Vercel
- Credenciais Instagram Graph API (v21.0)

---

## 🏠 Setup Local

### 1. Clonar e instalar dependências

```bash
cd ~/fazza-automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Editar .env com suas credenciais
nano .env
```

**Variáveis obrigatórias**:
- `INSTAGRAM_APP_ID` - De https://developers.facebook.com/
- `INSTAGRAM_APP_SECRET` - De https://developers.facebook.com/
- `API_KEY` - Chave secreta para autenticação (gere com `openssl rand -hex 32`)

### 3. Inicializar banco de dados

```bash
python3 -c "from app.main import app; from app.database import Base, engine; Base.metadata.create_all(engine)"
```

### 4. Rodar localmente

```bash
uvicorn app.main:app --reload --port 8000
```

Acessar em `http://localhost:8000/docs` para Swagger UI.

---

## 🔑 Configurar Instagram OAuth

1. Ir para https://developers.facebook.com/
2. Criar novo App (type: Business)
3. Configurar Instagram Graph API
4. Adicionar Instagram Business Account
5. Gerar Access Token (longa duração: 60 dias)
6. Configurar `INSTAGRAM_REDIRECT_URI` em `.env`

---

## 🐙 Push para GitHub

### 1. Inicializar repositório Git

```bash
cd ~/fazza-automation
git init
git add .
git commit -m "Initial commit: Fazza Automation backend"
```

### 2. Criar repositório no GitHub

- Ir para https://github.com/new
- Nome: `fazza-automation`
- Descrição: "Instagram multipost automation API"
- Privado ✅
- Criar repositório

### 3. Push para GitHub

```bash
git remote add origin https://github.com/seu-usuario/fazza-automation.git
git branch -M main
git push -u origin main
```

---

## 🌐 Deploy no Vercel

### 1. Conectar GitHub ao Vercel

- Ir para https://vercel.com/new
- "Import Git Repository"
- Selecionar `fazza-automation`
- Framework: **Other**

### 2. Configurar variáveis de ambiente

No painel Vercel, em "Settings" → "Environment Variables", adicionar:

```
INSTAGRAM_APP_ID=seu_valor
INSTAGRAM_APP_SECRET=seu_valor
INSTAGRAM_REDIRECT_URI=https://seu-projeto.vercel.app/callback
API_KEY=sua_chave_secreta
DATABASE_PATH=/tmp/automation.db
CORS_ORIGINS=https://seu-projeto.vercel.app,https://seu-frontend.vercel.app
```

### 3. Deploy

```bash
git push origin main
```

Vercel fará deploy automaticamente. URL: `https://seu-projeto.vercel.app`

---

## ✅ Testar API

### Health check
```bash
curl https://seu-projeto.vercel.app/health
```

### Criar post (com API Key)
```bash
curl -X POST https://seu-projeto.vercel.app/api/posts/ \
  -H "X-API-Key: sua_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "empresa123",
    "caption": "Olá mundo!",
    "media_urls": ["https://example.com/image.jpg"],
    "media_type": "IMAGE",
    "target_account_ids": ["account123"]
  }'
```

---

## 🔐 Segurança em Produção

### Checklist antes de publicar

- [ ] Todos os secrets em variáveis de ambiente (não em código)
- [ ] Database migrado para PostgreSQL
- [ ] API Key alterada (gerada com `openssl rand -hex 32`)
- [ ] CORS_ORIGINS configurado com domínios específicos
- [ ] HTTPS enforced em todas as rotas
- [ ] Rate limiting ativo
- [ ] Logging estruturado habilitado
- [ ] Certificado SSL/TLS válido

### Monitoramento

- Habilitar Vercel Analytics
- Configurar alertas de erro
- Monitorar logs em `/var/log/`

---

## 📊 Estrutura de Pasta

```
fazza-automation/
├── app/
│   ├── main.py           # FastAPI app
│   ├── database.py       # SQLAlchemy config
│   ├── models.py         # Modelos de BD
│   ├── security.py       # Autenticação
│   ├── validators.py     # Validações de entrada
│   ├── routes/           # API endpoints
│   │   ├── multipost.py
│   │   ├── accounts.py
│   │   └── ...
│   └── services/         # Lógica de negócio
│       ├── instagram_publisher.py
│       ├── instagram_api.py
│       └── ...
├── api/
│   └── index.py          # Entry point Vercel
├── requirements.txt      # Dependências Python
├── vercel.json          # Config Vercel
├── .env.example         # Template de variáveis
├── .gitignore           # Arquivos ignorados
└── README.md            # Documentação
```

---

## 🐛 Troubleshooting

### "API Key inválida"
- Verificar header `X-API-Key`
- Comparar com valor em `.env`

### "Instagram token expirado"
- Chamar endpoint `/api/accounts/{id}/refresh`
- Tokens duram 60 dias

### "Database locked"
- SQLite não suporta concorrência
- Migrar para PostgreSQL

### Build failed na Vercel
- Verificar `python` version (3.9+)
- Verificar `requirements.txt` sintaxe
- Logs disponíveis em Vercel → Deployments

---

## 📚 Referências

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-graph-api)
- [Vercel Python](https://vercel.com/docs/functions/serverless-functions/python)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

**Última atualização**: 2026-03-18
**Versão API**: 2.0.0
