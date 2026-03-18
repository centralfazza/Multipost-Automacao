# 📝 Guia Completo de Testes da API

**Versão**: 3.0.0
**Data**: 2026-03-18

---

## 🚀 Quick Start

### 1. Iniciar o Backend Localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Copiar variáveis de ambiente
cp .env.example .env

# Editar .env com credenciais reais
# Importante: INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, API_KEY

# Iniciar servidor
uvicorn app.main:app --reload

# Acessar documentação automática
# http://localhost:8000/docs
```

---

## 🧪 Testes de CRUD de Posts

### Criar um Post (Draft)

```bash
curl -X POST "http://localhost:8000/api/posts/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "company_id": "empresa-001",
    "caption": "Meu primeiro post automático! 🚀",
    "media_urls": ["https://example.com/image.jpg"],
    "media_type": "IMAGE",
    "target_account_ids": ["account-001", "account-002"]
  }'
```

**Python**:
```python
import requests

headers = {
    "X-API-Key": "sua_api_key_aqui",
    "Content-Type": "application/json"
}

payload = {
    "company_id": "empresa-001",
    "caption": "Meu primeiro post automático! 🚀",
    "media_urls": ["https://example.com/image.jpg"],
    "media_type": "IMAGE",
    "target_account_ids": ["account-001"]
}

response = requests.post(
    "http://localhost:8000/api/posts/",
    json=payload,
    headers=headers
)

print(response.json())
# Output:
# {
#   "id": "uuid-do-post",
#   "status": "draft",
#   "company_id": "empresa-001",
#   "caption": "Meu primeiro post automático! 🚀",
#   ...
# }
```

---

### Listar Posts da Empresa

```bash
curl -X GET "http://localhost:8000/api/posts/?company_id=empresa-001&status=draft" \
  -H "X-API-Key: sua_api_key_aqui"
```

---

### Obter Detalhes de um Post

```bash
curl -X GET "http://localhost:8000/api/posts/{post_id}" \
  -H "X-API-Key: sua_api_key_aqui"
```

---

## 📅 Testes de Agendamento

### Agendar um Post

```bash
curl -X POST "http://localhost:8000/api/posts/{post_id}/schedule" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "scheduled_at": "2026-03-20T15:30:00"
  }'
```

**Python**:
```python
from datetime import datetime, timedelta

# Agendar para 1 hora a partir de agora
scheduled_time = datetime.utcnow() + timedelta(hours=1)

response = requests.post(
    f"http://localhost:8000/api/posts/{post_id}/schedule",
    json={"scheduled_at": scheduled_time.isoformat()},
    headers=headers
)
```

---

### Cancelar Agendamento

```bash
curl -X POST "http://localhost:8000/api/posts/{post_id}/cancel" \
  -H "X-API-Key: sua_api_key_aqui"
```

---

## 🔥 Testes de Publicação

### Publicar Imediatamente

```bash
curl -X POST "http://localhost:8000/api/posts/{post_id}/publish" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta (async background task):
# {
#   "status": "publishing",
#   "post_id": "uuid-do-post",
#   "message": "Publicação iniciada em background."
# }
```

---

## 📦 Testes de Batch Processing

### Criar Múltiplos Posts em Lote

```bash
curl -X POST "http://localhost:8000/api/posts/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "company_id": "empresa-001",
    "target_account_ids": ["account-001"],
    "posts": [
      {
        "caption": "Post 1 de uma campanha",
        "media_urls": ["https://example.com/img1.jpg"],
        "media_type": "IMAGE"
      },
      {
        "caption": "Post 2 com carousel",
        "media_urls": [
          "https://example.com/img2.jpg",
          "https://example.com/img3.jpg"
        ],
        "media_type": "CAROUSEL_ALBUM"
      },
      {
        "caption": "Post 3 com vídeo",
        "media_urls": ["https://example.com/video.mp4"],
        "media_type": "VIDEO"
      }
    ]
  }'

# Resposta:
# {
#   "total_requested": 3,
#   "created": 3,
#   "failed": 0,
#   "posts": [
#     {"index": 0, "post_id": "uuid1", "status": "draft"},
#     {"index": 1, "post_id": "uuid2", "status": "draft"},
#     {"index": 2, "post_id": "uuid3", "status": "draft"}
#   ],
#   "errors": []
# }
```

---

### Agendar Múltiplos Posts

```bash
curl -X POST "http://localhost:8000/api/posts/batch-schedule" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "post_ids": ["uuid1", "uuid2", "uuid3"],
    "scheduled_at": "2026-03-20T14:00:00"
  }'
```

---

### Publicar Múltiplos Posts em Lote

```bash
curl -X POST "http://localhost:8000/api/posts/batch-publish" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "post_ids": ["uuid1", "uuid2", "uuid3"]
  }'

# Nota: Posts são publicados com 5s de delay entre cada um
# para respeitar rate limits do Instagram
```

---

## 📊 Testes de Analytics

### Ver Resumo Geral

```bash
curl -X GET "http://localhost:8000/api/analytics/posts/summary?company_id=empresa-001&days=30" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "company_id": "empresa-001",
#   "period_days": 30,
#   "posts": {
#     "total": 10,
#     "draft": 2,
#     "scheduled": 1,
#     "published": 6,
#     "failed": 1
#   },
#   "publishing": {
#     "total_attempts": 7,
#     "successful": 6,
#     "failed": 1,
#     "success_rate": 85.71
#   },
#   "accounts": {
#     "total": 2,
#     "active": 2,
#     "token_expiring_soon": 0
#   }
# }
```

---

### Posts por Status

```bash
curl -X GET "http://localhost:8000/api/analytics/posts/posts-by-status?company_id=empresa-001&days=30" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "company_id": "empresa-001",
#   "period_days": 30,
#   "total_posts": 10,
#   "by_status": {
#     "draft": 2,
#     "scheduled": 1,
#     "publishing": 0,
#     "done": 6,
#     "error": 1
#   },
#   "success_rate": 60.0
# }
```

---

### Posts por Conta

```bash
curl -X GET "http://localhost:8000/api/analytics/posts/posts-by-account?company_id=empresa-001&days=30" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "company_id": "empresa-001",
#   "period_days": 30,
#   "total_accounts": 2,
#   "accounts": [
#     {
#       "account_id": "account-001",
#       "username": "@minha_conta",
#       "total_posts": 5,
#       "successful": 4,
#       "failed": 1,
#       "success_rate": 80.0
#     },
#     {
#       "account_id": "account-002",
#       "username": "@conta_secundaria",
#       "total_posts": 2,
#       "successful": 2,
#       "failed": 0,
#       "success_rate": 100.0
#     }
#   ]
# }
```

---

### Erros Recentes

```bash
curl -X GET "http://localhost:8000/api/analytics/posts/errors?company_id=empresa-001&days=7&limit=10" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "company_id": "empresa-001",
#   "period_days": 7,
#   "total_errors": 2,
#   "errors": [
#     {
#       "result_id": "result-uuid1",
#       "post_id": "post-uuid1",
#       "account": "@minha_conta",
#       "error": "Instagram API error: Video format not supported",
#       "timestamp": "2026-03-18T10:30:00",
#       "post_caption": "Video test post..."
#     },
#     {
#       "result_id": "result-uuid2",
#       "post_id": "post-uuid2",
#       "account": "@conta_secundaria",
#       "error": "Rate limit exceeded. Retry after 300 seconds.",
#       "timestamp": "2026-03-18T09:15:00",
#       "post_caption": "Batch post 2..."
#     }
#   ]
# }
```

---

## 🔧 Testes de Contas Instagram

### Conectar Conta Instagram

```bash
# 1. Obter URL de OAuth
curl -X GET "http://localhost:8000/api/accounts/oauth-url" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "oauth_url": "https://api.instagram.com/oauth/authorize?client_id=...&redirect_uri=...&scope=..."
# }

# 2. Após usuário autorizar, trocar code por token
curl -X POST "http://localhost:8000/api/accounts/connect" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "code": "authorization_code_from_instagram",
    "company_id": "empresa-001"
  }'

# Resposta:
# {
#   "status": "connected",
#   "account": {
#     "id": "account-uuid",
#     "company_id": "empresa-001",
#     "username": "@minha_conta",
#     "instagram_user_id": "123456789",
#     "account_type": "BUSINESS",
#     "is_active": true,
#     "token_expires_at": "2026-05-17T10:30:00",
#     "created_at": "2026-03-18T10:30:00"
#   }
# }
```

---

### Listar Contas da Empresa

```bash
curl -X GET "http://localhost:8000/api/accounts/?company_id=empresa-001" \
  -H "X-API-Key: sua_api_key_aqui"
```

---

### Renovar Token

```bash
curl -X POST "http://localhost:8000/api/accounts/{account_id}/refresh" \
  -H "X-API-Key: sua_api_key_aqui"

# Resposta:
# {
#   "status": "refreshed",
#   "expires_at": "2026-05-17T10:30:00"
# }
```

---

## ⚠️ Testes de Rate Limiting

### Verificar Rate Limiting

```bash
# Fazer muitas requisições rapidamente
for i in {1..50}; do
  curl -X GET "http://localhost:8000/api/posts/?company_id=empresa-001" \
    -H "X-API-Key: sua_api_key_aqui"
done

# Após atingir o limite, você receberá:
# HTTP 429 Too Many Requests
# {
#   "error": "rate_limited",
#   "message": "Muitas requisições. Tente novamente mais tarde.",
#   "retry_after": "60"
# }
```

---

## 🐛 Testes de Error Handling

### Teste com URLs Inválidas

```bash
curl -X POST "http://localhost:8000/api/posts/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua_api_key_aqui" \
  -d '{
    "company_id": "empresa-001",
    "caption": "Test",
    "media_urls": ["not-a-valid-url"],
    "media_type": "IMAGE",
    "target_account_ids": []
  }'

# Resposta esperada:
# HTTP 400 Bad Request
# {
#   "detail": "URL validation error: Invalid URL format"
# }
```

---

### Teste sem API Key

```bash
curl -X GET "http://localhost:8000/api/posts/?company_id=empresa-001"

# Resposta esperada:
# HTTP 401 Unauthorized
# {
#   "detail": "API Key inválida ou ausente."
# }
```

---

## 📋 Checklist de Testes

- [ ] CRUD básico de posts funciona
- [ ] Agendamento de posts funciona
- [ ] Publicação imediata funciona
- [ ] Batch processing (create/schedule/publish) funciona
- [ ] Analytics endpoints retornam dados corretos
- [ ] Rate limiting bloqueia requisições em excesso
- [ ] Error handling funciona para URLs inválidas
- [ ] API Key validation funciona
- [ ] Retry logic com backoff funciona
- [ ] Logs são gerados corretamente

---

## 🚀 Próximas Etapas

1. **Integração com Instagram Real**: Configure `INSTAGRAM_APP_ID` e `INSTAGRAM_APP_SECRET` reais
2. **Deploy em Staging**: Teste em Vercel antes de produção
3. **Monitoramento**: Configure logs estruturados e alertas
4. **Load Testing**: Teste performance com tools como Apache JMeter

---

**Desenvolvido com ❤️ por Claude Haiku 4.5**
