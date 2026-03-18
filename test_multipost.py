"""
test_multipost.py
Testes de integração dos endpoints de multipost e accounts.
Usa httpx.AsyncClient com ASGITransport e pytest-asyncio.
Roda com: python3 -m pytest test_multipost.py -v
"""
import pytest
import pytest_asyncio
import httpx
from app.main import app
from app.database import Base, engine

# Configuração do pytest-asyncio para rodar em modo strict/auto
# @pytest.mark.asyncio em cada função ou pytestmark no topo
pytestmark = pytest.mark.asyncio

# ─────────────────────────────────────────────────
# FIXTURE — Cliente HTTPX assíncrono
# ─────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def client():
    # Cria as tabelas no banco de teste
    Base.metadata.create_all(bind=engine)
    
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
        
    Base.metadata.drop_all(bind=engine)

# ─────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

# ─────────────────────────────────────────────────
# POSTS — CRUD
# ─────────────────────────────────────────────────

async def test_create_post_image(client):
    r = await client.post("/api/posts/", json={
        "company_id": "empresa_teste",
        "caption": "Teste #multipost",
        "media_urls": ["https://picsum.photos/1080/1080"],
        "media_type": "IMAGE",
        "target_account_ids": [],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "draft"
    assert data["media_type"] == "IMAGE"

async def test_create_post_carousel(client):
    r = await client.post("/api/posts/", json={
        "company_id": "empresa_teste",
        "caption": "Carousel #3fotos",
        "media_urls": [
            "https://picsum.photos/1080/1080?r=1",
            "https://picsum.photos/1080/1080?r=2",
            "https://picsum.photos/1080/1080?r=3",
        ],
        "media_type": "CAROUSEL_ALBUM",
        "target_account_ids": [],
    })
    assert r.status_code == 201
    assert r.json()["media_type"] == "CAROUSEL_ALBUM"

async def test_carousel_requires_2_urls(client):
    r = await client.post("/api/posts/", json={
        "company_id": "x",
        "media_urls": ["https://picsum.photos/1080/1080"],
        "media_type": "CAROUSEL_ALBUM",
    })
    assert r.status_code == 400

async def test_invalid_media_type(client):
    r = await client.post("/api/posts/", json={
        "company_id": "x",
        "media_urls": ["https://picsum.photos/1080/1080"],
        "media_type": "STORY",
    })
    assert r.status_code == 400

async def test_list_posts(client):
    await client.post("/api/posts/", json={
        "company_id": "empresa_A",
        "media_urls": ["https://picsum.photos/1080"],
        "media_type": "IMAGE",
    })
    r = await client.get("/api/posts/", params={"company_id": "empresa_A"})
    assert r.status_code == 200
    assert len(r.json()) >= 1

async def test_get_post_detail(client):
    resp = await client.post("/api/posts/", json={
        "company_id": "x",
        "media_urls": ["https://picsum.photos/1080"],
        "media_type": "IMAGE",
    })
    post_id = resp.json()["id"]
    r = await client.get(f"/api/posts/{post_id}")
    assert r.status_code == 200
    assert "results" in r.json()

async def test_update_post(client):
    resp = await client.post("/api/posts/", json={
        "company_id": "x",
        "media_urls": ["https://picsum.photos/1080"],
        "media_type": "IMAGE",
    })
    post_id = resp.json()["id"]
    r = await client.put(f"/api/posts/{post_id}", json={"caption": "Legenda atualizada"})
    assert r.status_code == 200
    assert r.json()["caption"] == "Legenda atualizada"

async def test_delete_draft(client):
    resp = await client.post("/api/posts/", json={
        "company_id": "x",
        "media_urls": ["https://picsum.photos/1080"],
        "media_type": "IMAGE",
    })
    post_id = resp.json()["id"]
    r = await client.delete(f"/api/posts/{post_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    
    # Verifica que sumiu
    r2 = await client.get(f"/api/posts/{post_id}")
    assert r2.status_code == 404

# ─────────────────────────────────────────────────
# AGENDAMENTO
# ─────────────────────────────────────────────────

async def _criar_post(client, account_ids=None):
    resp = await client.post("/api/posts/", json={
        "company_id": "emp_sched",
        "media_urls": ["https://picsum.photos/1080"],
        "media_type": "IMAGE",
        "target_account_ids": account_ids or ["00000000-0000-0000-0000-000000000000"],
    })
    return resp.json()["id"]

async def test_schedule_post(client):
    post_id = await _criar_post(client)
    r = await client.post(f"/api/posts/{post_id}/schedule", json={
        "scheduled_at": "2099-12-31T23:59:00"
    })
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"

async def test_schedule_in_past_rejected(client):
    post_id = await _criar_post(client)
    r = await client.post(f"/api/posts/{post_id}/schedule", json={
        "scheduled_at": "2000-01-01T00:00:00"
    })
    assert r.status_code == 400

async def test_cancel_schedule(client):
    post_id = await _criar_post(client)
    await client.post(f"/api/posts/{post_id}/schedule", json={
        "scheduled_at": "2099-12-31T23:59:00"
    })
    r = await client.post(f"/api/posts/{post_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "draft"

# ─────────────────────────────────────────────────
# CONTAS
# ─────────────────────────────────────────────────

async def test_list_accounts_empty(client):
    r = await client.get("/api/accounts/", params={"company_id": "nova_empresa"})
    assert r.status_code == 200
    assert r.json() == []

async def test_get_oauth_url(client):
    r = await client.get("/api/accounts/oauth-url")
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        assert "instagram.com" in r.json()["url"]
