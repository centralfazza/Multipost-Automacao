from .models import Automation, Company, AnalyticsLog, Contact
from .services.instagram_api import InstagramAPI
from sqlalchemy.orm import Session
from datetime import datetime

class AutomationEngine:
    def __init__(self, db: Session):
        self.db = db

    def process_instagram_comment(self, company_id: str, comment_data: dict):
        comment_id = comment_data.get('id')
        post_id = comment_data.get('media_id')
        commenter_id = comment_data.get('from', {}).get('id')
        commenter_username = comment_data.get('from', {}).get('username')
        text = comment_data.get('text', '')

        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company or not company.instagram_access_token: return

        automations = self.db.query(Automation).filter(
            Automation.company_id == company_id,
            Automation.is_active == True,
            Automation.platform == "instagram"
        ).all()

        for auto in automations:
            triggers = auto.triggers
            if triggers.get('type') != 'comment': continue
            
            keywords = triggers.get('keywords', [])
            matched = any(kw.lower() in text.lower() for kw in keywords) if keywords else True
            
            if triggers.get('post_id') and triggers.get('post_id') != post_id: matched = False

            if matched:
                self.execute_actions(auto, {
                    "comment_id": comment_id,
                    "media_id": post_id,
                    "username": commenter_username,
                    "user_id": commenter_id,
                    "platform": "instagram",
                    "company": company
                })
                log = AnalyticsLog(automation_id=auto.id, success=True, trigger_data=comment_data)
                self.db.add(log)
                self.db.commit()

    def execute_actions(self, automation: Automation, context: dict):
        actions = sorted(automation.actions, key=lambda x: x.get('order', 0))
        ig_api = InstagramAPI(context['company'].instagram_access_token)

        for action in actions:
            action_type = action.get('type')
            content = self.replace_variables(action.get('content', ''), context)

            if action_type == 'reply_comment':
                ig_api.reply_to_comment(context['comment_id'], content)
            elif action_type == 'send_dm':
                ig_api.send_dm(context['user_id'], content)
            elif action_type == 'add_tag':
                self.add_tag(context['company'].id, context['platform'], context['user_id'], context['username'], action.get('tag'))

    def replace_variables(self, text, context):
        return text.replace("{username}", context.get('username', '')).replace("{time}", datetime.now().strftime("%H:%M"))

    def add_tag(self, company_id, platform, external_id, username, tag):
        contact = self.db.query(Contact).filter(Contact.company_id == company_id, Contact.platform == platform, Contact.external_id == external_id).first()
        if not contact:
            contact = Contact(company_id=company_id, platform=platform, external_id=external_id, username=username, tags=[tag])
            self.db.add(contact)
        else:
            tags = list(contact.tags) if contact.tags else []
            if tag not in tags:
                tags.append(tag)
                contact.tags = tags
        self.db.commit()
