import requests

class WhatsAppAPI:
    def __init__(self, token, phone_id): self.token, self.phone_id = token, phone_id
    def send_message(self, to, text):
        return requests.post(f"https://graph.facebook.com/v21.0/{self.phone_id}/messages", headers={"Authorization": f"Bearer {self.token}"}, json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}).json()
