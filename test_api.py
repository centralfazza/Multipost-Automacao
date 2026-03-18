import requests
import json

BASE_URL = "http://localhost:8000" # Ajuste se estiver rodando local ou na Vercel

def test_health():
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health Check: {response.json()}")

def test_create_company():
    payload = {"id": "company_test_1", "name": "Minha Empresa"}
    response = requests.post(f"{BASE_URL}/api/companies/", json=payload)
    print(f"Create Company: {response.status_code}")

def test_create_automation():
    payload = {
        "company_id": "company_test_1",
        "name": "Teste Comentário",
        "platform": "instagram",
        "triggers": {
            "type": "comment",
            "keywords": ["QUERO", "TOP"]
        },
        "actions": [
            { "order": 1, "type": "reply_comment", "content": "Enviado no direct!" },
            { "order": 2, "type": "send_dm", "content": "Olá! Aqui seu link." }
        ]
    }
    response = requests.post(f"{BASE_URL}/api/automations/", json=payload)
    print(f"Create Automation: {response.json()}")

if __name__ == "__main__":
    print("Iniciando testes (Certifique-se que o servidor está rodando)")
    # test_health()
    # test_create_company()
    # test_create_automation()
