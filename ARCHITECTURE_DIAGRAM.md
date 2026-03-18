# 🏗️ Arquitetura de Multipost v3.0

---

## 📐 Diagrama Geral de Fluxo

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTE HTTP                             │
│                    (Web, Mobile, API)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI SERVER                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              RATE LIMITER (slowapi)                      │  │
│  │  - 1000 req/h (global)                                   │  │
│  │  - 100 req/h (publish)                                   │  │
│  │  - 20 req/h (batch)                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             │                                    │
│  ┌─────────────────────────┼─────────────────────────────┐     │
│  │                         ▼                             │     │
│  │  ┌─────────────────────────────────────────────────┐  │     │
│  │  │         CORS MIDDLEWARE + AUTH                 │  │     │
│  │  │  - Whitelist de domínios                       │  │     │
│  │  │  - API Key validation (X-API-Key)             │  │     │
│  │  └─────────────────────────────────────────────────┘  │     │
│  │                         │                             │     │
│  │  ┌──────────┬───────────┼───────────┬─────────────┐  │     │
│  │  │          │           │           │             │  │     │
│  │  ▼          ▼           ▼           ▼             ▼  │     │
│  │ ┌──┐    ┌──┐        ┌──────┐    ┌──────┐    ┌──────┐│     │
│  │ │  │    │  │        │      │    │      │    │      ││     │
│  │ │  │    │  │        │      │    │      │    │      ││     │
│  │ └──┘    └──┘        └──────┘    └──────┘    └──────┘│     │
│  │ CRUD   SCHEDULE     BATCH     ANALYTICS  ACCOUNTS   │     │
│  │ Posts   Posts      Processing   Monitoring  OAuth    │     │
│  │                                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│                         │                                      │
└─────────────────────────┼──────────────────────────────────────┘
                          │
                    ┌─────▼─────┐
                    │ DATABASE  │
                    │(SQLite)   │
                    │(PostgreSQL)
                    └───────────┘
```

---

## 🔄 Fluxo de Publicação

### Publicação Imediata

```
POST /api/posts/{id}/publish
         │
         ▼
    ┌─────────────┐
    │ Validações  │
    │  - Post OK? │
    │  - Auth OK? │
    │  - Accounts?│
    └──────┬──────┘
           │ ✅ OK
           ▼
    ┌──────────────────┐
    │ Mark as          │
    │ "publishing"     │
    └────────┬─────────┘
             │
             ▼
    ┌────────────────────────────────────────┐
    │ Background Task: _publish_background() │
    │                                        │
    │  for each target_account:              │
    │    publisher = PostPublisher(db)       │
    │    result = publisher.publish_post()   │
    │                                        │
    │    if failed:                          │
    │      retry with exponential backoff    │
    │      2s, 5s, 10s                       │
    │                                        │
    │    save result to database             │
    └────────────────┬───────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
    ✅ All Success        ❌ Any Failure
    Post.status          Post.status
    = "done"             = "error"
```

### Publicação Agendada

```
POST /api/posts/{id}/schedule
         │
         ▼
    Mark as "scheduled"
    Set scheduled_at
         │
         ▼
    ┌─────────────────────────────┐
    │ APScheduler Background Job  │
    │ (Runs every 60s)            │
    │                             │
    │ Check: scheduled_at <= now? │
    │                             │
    └──────────┬──────────────────┘
               │ Yes
               ▼
    → PublishToAllAccounts()
      (mesmo fluxo acima)
```

---

## 🔗 Batch Processing

```
POST /api/posts/batch
    {
      "posts": [
        {...}, {...}, {...}  ← até 100 posts
      ]
    }
         │
         ▼
    ┌─────────────────┐
    │  Validar cada   │
    │  post conforme  │
    │  rules:         │
    │  - URLs OK?     │
    │  - Type OK?     │
    │  - Caption OK?  │
    └────────┬────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
  ✅ Valid       ❌ Invalid
  Create POST    Skip + Report
  in batch       in errors[]
    │
    └────────────────┬─────────────────┐
                     ▼                 ▼
                 Commit to DB    Return Summary
                                {
                                  created: N,
                                  failed: M,
                                  errors: [...]
                                }
```

---

## 📊 Analytics Pipeline

```
Database Events
    │
    ├─→ POST created         ──→ status="draft"
    ├─→ POST scheduled       ──→ status="scheduled"
    ├─→ Publication started  ──→ status="publishing"
    ├─→ Publication success  ──→ result.status="success"
    │                            + result.ig_media_id
    └─→ Publication failed   ──→ result.status="error"
                                 + result.error_message

Analytics Endpoints
    │
    ├─→ /summary
    │   SELECT COUNT(*) GROUP BY status
    │   SELECT success_rate
    │
    ├─→ /posts-by-status
    │   SELECT status, COUNT(*)
    │
    ├─→ /posts-by-account
    │   SELECT account, COUNT(*), success_rate
    │
    └─→ /errors
        SELECT * FROM results WHERE status="error"
        GROUP BY account, error_message
```

---

## 🔄 Retry Logic Detalhado

```
publish_post(media_urls, media_type, caption)
    │
    for attempt in range(3):
        │
        ▼
    ┌──────────────────┐
    │ Tentativa N      │
    │ Create container │
    │ + Publish        │
    └────────┬─────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
   ✅ Success      ❌ Error
   Return ID      │
                  ▼
            ┌──────────────────┐
            │ Is transient?    │
            │ (timeout,        │
            │  rate_limit,     │
            │  connection)     │
            └────────┬─────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
       ✅ YES                  ❌ NO
       Retry?              Permanent
       │                   Error
       ├─ attempt < 3?     │
       │  │                └→ Return Error
       │  ├─ Yes: Wait
       │  │  (2s, 5s, 10s)
       │  │  + Retry
       │  │
       │  └─ No: Return Error
       │
       └─→ Next Attempt
```

---

## 💾 Schema do Banco de Dados

```
┌──────────────────────┐
│   INSTAGRAM_ACCOUNT  │
├──────────────────────┤
│ id (PK)              │
│ company_id (FK)      │
│ username             │
│ instagram_user_id    │
│ access_token         │ ← Renovável a cada 60 dias
│ token_expires_at     │
│ account_type         │
│ is_active            │
│ created_at           │
│ updated_at           │
└──────┬───────────────┘
       │
       │ (1:N)
       │
┌──────┴─────────────────┐
│   MEDIA_POST           │
├────────────────────────┤
│ id (PK)                │
│ company_id (FK)        │
│ caption                │
│ media_urls (JSON)      │
│ media_type             │ ← IMAGE, VIDEO, CAROUSEL, REELS
│ target_account_ids     │ ← JSON array
│ scheduled_at           │
│ status                 │ ← draft, scheduled, publishing, done, error
│ created_at             │
│ updated_at             │
└───────┬────────────────┘
        │
        │ (1:N)
        │
    ┌───┴──────────────┐
    │   POST_RESULT    │
    ├──────────────────┤
    │ id (PK)          │
    │ post_id (FK)     │
    │ account_id (FK)  │
    │ ig_media_id      │ ← ID retornado pelo Instagram
    │ status           │ ← pending, success, error
    │ error_message    │
    │ published_at     │
    │ created_at       │
    └──────────────────┘
```

---

## 📡 API Endpoints

### CRUD Posts
```
POST   /api/posts/                  Create post (draft)
GET    /api/posts/                  List posts (filtrado por company_id)
GET    /api/posts/{post_id}         Get post details
PUT    /api/posts/{post_id}         Update post
DELETE /api/posts/{post_id}         Delete post
```

### Ações
```
POST   /api/posts/{post_id}/publish        Publish now
POST   /api/posts/{post_id}/schedule       Schedule post
POST   /api/posts/{post_id}/cancel         Cancel schedule
GET    /api/posts/{post_id}/results        Get publish results
```

### Batch Processing ⭐ NOVO
```
POST   /api/posts/batch              Create 100+ posts
POST   /api/posts/batch-schedule     Schedule 100+ posts
POST   /api/posts/batch-publish      Publish 100+ posts
```

### Analytics ⭐ NOVO
```
GET    /api/analytics/posts/summary          Overall stats
GET    /api/analytics/posts/posts-by-status  Posts por status
GET    /api/analytics/posts/posts-by-account Posts por conta
GET    /api/analytics/posts/errors           Erros recentes
```

### Contas
```
GET    /api/accounts/oauth-url         Get OAuth URL
POST   /api/accounts/connect           Connect account (OAuth)
GET    /api/accounts/                  List accounts
GET    /api/accounts/{account_id}      Get account
PATCH  /api/accounts/{account_id}      Update account
POST   /api/accounts/{account_id}/refresh  Refresh token
DELETE /api/accounts/{account_id}      Delete account
```

---

## 🔐 Fluxo de Segurança

```
Request
   │
   ▼
┌────────────────────┐
│ CORS Check         │
│ Domain whitelist?  │
└────────┬───────────┘
         │ ✅ OK
         ▼
┌────────────────────┐
│ API Key Check      │
│ Header: X-API-Key  │
└────────┬───────────┘
         │ ✅ Valid
         ▼
┌────────────────────┐
│ Rate Limit Check   │
│ Requests/hour OK?  │
└────────┬───────────┘
         │ ✅ Within limit
         ▼
┌────────────────────┐
│ Input Validation   │
│ - URLs valid?      │
│ - Captions safe?   │
│ - SSRF check?      │
└────────┬───────────┘
         │ ✅ Valid
         ▼
    PROCESS REQUEST
```

---

## 🚀 Deployment Architecture

```
GitHub Repository
      │
      ▼
┌──────────────────┐
│  Vercel Hooks    │
│  - Pre-deploy    │
│  - Deploy        │
│  - Post-deploy   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐        ┌─────────────────┐
│  Build Stage     │───────▶│ requirements.txt│
│  - pip install   │        │ - All deps OK?  │
│  - Tests         │        └─────────────────┘
└────────┬─────────┘
         │
         ▼
┌──────────────────┐        ┌─────────────────┐
│  Run Stage       │───────▶│ Environment     │
│  - uvicorn       │        │ - API_KEY       │
│  - Port 3000     │        │ - INSTAGRAM_*   │
└────────┬─────────┘        └─────────────────┘
         │
         ▼
┌──────────────────┐        ┌─────────────────┐
│  HTTPS Endpoint  │───────▶│ Database        │
│  - your-app      │        │ - PostgreSQL    │
│  .vercel.app     │        │ - Backups daily │
└──────────────────┘        └─────────────────┘
```

---

## 📊 Data Flow Exemplo

```
1. Cliente cria batch de 50 posts
   POST /api/posts/batch

2. Cada post validado individualmente
   - URLs verificadas
   - Captions sanitizadas
   - Media type validado

3. Posts salvos como "draft"
   INSERT INTO media_posts (50 rows)

4. Cliente agenda todos para amanhã 14:00
   POST /api/posts/batch-schedule
   scheduled_at = 2026-03-19 14:00:00

5. Scheduler verifica a cada 60s
   APScheduler job: _process_scheduled_posts()

6. No tempo certo, dispara publicação
   for each post:
     for each target_account:
       PublishPost() com retry logic

7. Results salvos
   INSERT INTO post_results
   - ig_media_id (ou error_message)
   - status (success ou error)
   - published_at timestamp

8. Cliente consulta analytics
   GET /api/analytics/posts/summary

9. Dashboard mostra:
   - 50 posts publicados
   - 49 com sucesso
   - 1 com falha (detalhes do erro)
```

---

**Desenvolvido em**: 2026-03-18
**Versão**: 3.0.0
**Arquitetura**: Production-Ready
