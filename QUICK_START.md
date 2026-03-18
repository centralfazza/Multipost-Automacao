# ⚡ Quick Start — Fazza Automation

## 📦 Projeto Pronto em: `~/fazza-automation`

```
✅ Python backend com FastAPI
✅ Instagram Graph API v21.0 integrado
✅ Multipost automático (várias contas)
✅ OAuth2 connection
✅ Scheduled posting
✅ Segurança melhorada (API Key, CORS, URL validation)
✅ Git inicializado localmente
```

---

## 🚀 Próximos Passos

### **PASSO 1: Verificar setup local**

```bash
cd ~/fazza-automation
source venv/bin/activate  # Se tiver criado venv
pip install -r requirements.txt
cp .env.example .env
# ⚠️ Editar .env com seus valores:
# - INSTAGRAM_APP_ID
# - INSTAGRAM_APP_SECRET
# - API_KEY (gere com: openssl rand -hex 32)
```

### **PASSO 2: Testar localmente**

```bash
# Terminal 1: Rodar servidor
uvicorn app.main:app --reload --port 8000

# Terminal 2: Testar health check
curl http://localhost:8000/health
# Resultado esperado: {"status": "healthy", "version": "2.0.0"}
```

Acessar Swagger UI: http://localhost:8000/docs

---

### **PASSO 3: Criar repositório no GitHub**

1. Ir para https://github.com/new
2. Preencher:
   - **Repository name**: `fazza-automation`
   - **Description**: `Instagram multipost automation API`
   - **Privacy**: Private ✅
   - Não inicializar com README (já tem)
3. Clicar "Create repository"

---

### **PASSO 4: Push para GitHub**

```bash
cd ~/fazza-automation

# Adicionar remote
git remote add origin https://github.com/seu-usuario/fazza-automation.git

# Fazer push
git push -u origin main
```

Verificar em https://github.com/seu-usuario/fazza-automation

---

### **PASSO 5: Deploy no Vercel**

#### Opção A: Via CLI (recomendado)

```bash
# Instalar Vercel CLI
npm install -g vercel

# Deploy
cd ~/fazza-automation
vercel

# Seguir prompts:
# - Link to existing project? N
# - Project name: fazza-automation
# - Framework: Other
# - Output directory: ./
```

#### Opção B: Via Web

1. Ir para https://vercel.com/new
2. "Import Git Repository"
3. Conectar GitHub
4. Selecionar `fazza-automation`
5. Framework: **Other**
6. Clicar "Deploy"

---

### **PASSO 6: Configurar variáveis de ambiente no Vercel**

No painel Vercel:
1. Ir para "Settings" → "Environment Variables"
2. Adicionar:

```
INSTAGRAM_APP_ID = seu_valor
INSTAGRAM_APP_SECRET = seu_valor
INSTAGRAM_REDIRECT_URI = https://seu-projeto-xxx.vercel.app/callback
API_KEY = sua_chave_secreta_aqui
DATABASE_PATH = /tmp/automation.db
CORS_ORIGINS = https://seu-projeto-xxx.vercel.app
```

3. Clicar "Save"
4. Ir para "Deployments" → Redeploy

---

## 🔐 Brechas de Segurança Corrigidas

✅ **CORS restritivo** - Whitelist específica de domínios
✅ **Autenticação API Key** - Endpoints protegidos
✅ **Validação de URLs** - Previne SSRF
✅ **Tratamento de erro** - Instagram API com timeout
✅ **Sanitização de entrada** - Caption com limite
✅ **Rate limiting** - Preparado (slowapi)

Ver detalhes em: `SECURITY_REPORT.md`

---

## 📚 Documentação

- **DEPLOYMENT_GUIDE.md** - Setup completo (local, GitHub, Vercel)
- **SECURITY_REPORT.md** - 10 vulnerabilidades encontradas + soluções
- **API_DOCUMENTATION.md** - Endpoints disponíveis
- **INSTAGRAM_SETUP.md** - Como configurar OAuth do Instagram

---

## 🔑 Onde Obter Credenciais

### Instagram Graph API

1. Ir para https://developers.facebook.com/
2. "Create App" → type: "Business"
3. Adicionar "Instagram Graph API" product
4. Em "Settings" → "Basic":
   - Copiar `App ID` → `INSTAGRAM_APP_ID`
   - Copiar `App Secret` → `INSTAGRAM_APP_SECRET`
5. Em "Settings" → "Basic" → "App Domains":
   - Adicionar `localhost:8000` (dev)
   - Adicionar `seu-projeto-xxx.vercel.app` (prod)
6. Em "Instagram" → "Instagram Basic Display":
   - Gerar token de teste (50 dias)
   - Ou usar conta real para 60 dias

---

## 🧪 Testar API via curl

### Create post
```bash
curl -X POST https://seu-projeto-xxx.vercel.app/api/posts/ \
  -H "X-API-Key: sua_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "empresa123",
    "caption": "Olá mundo! #fazza",
    "media_urls": ["https://example.com/image.jpg"],
    "media_type": "IMAGE",
    "target_account_ids": ["account_id_1", "account_id_2"]
  }'
```

### List posts
```bash
curl -H "X-API-Key: sua_api_key" \
  "https://seu-projeto-xxx.vercel.app/api/posts/?company_id=empresa123"
```

### Publish now
```bash
curl -X POST \
  -H "X-API-Key: sua_api_key" \
  "https://seu-projeto-xxx.vercel.app/api/posts/{post_id}/publish"
```

---

## ⚠️ Importante

- **Nunca commitar `.env`** com credenciais reais ✅ (já está em .gitignore)
- **API_KEY** deve ser longa e aleatória (não "123456")
- **Instagram tokens** duram 60 dias, precisa refresh automático
- **Database** SQLite em dev, PostgreSQL em prod

---

## 🆘 Troubleshooting

**"API Key inválida"**
→ Verificar header: `-H "X-API-Key: ..."`

**"Instagram token expirado"**
→ Chamar POST `/api/accounts/{id}/refresh`

**Build erro no Vercel**
→ Verificar Python 3.9+ em "Settings" → "Build & Development"

**CORS error**
→ Adicionar domínio em `CORS_ORIGINS`

---

## 📞 Suporte

- FastAPI docs: http://localhost:8000/docs
- Erro detalhado: Verificar em Vercel → "Functions" → Logs
- GitHub Issues: Documentar erro + stack trace

---

**Status**: ✅ Pronto para produção
**Última atualização**: 2026-03-18
**Versão**: 2.0.0
