from src.db import db
from src.models import Conversation, Message, User


def test_conversation_messages_relationship(app):
    with app.app_context():
        user = User(email='conversation@example.com', password_hash='hashed')
        db.session.add(user)
        db.session.commit()

        conversation = Conversation(user_id=user.id, telegram_chat_id='chat-123', state='new', context='{}')
        db.session.add(conversation)
        db.session.commit()

        first_message = Message(conversation_id=conversation.id, sender='user', text='Hello')
        second_message = Message(conversation_id=conversation.id, sender='bot', text='Hi there')
        db.session.add_all([first_message, second_message])
        db.session.commit()

        stored = db.session.get(Conversation, conversation.id)
        assert stored is not None
        assert len(stored.messages) == 2
        assert stored.messages[0].text == 'Hello'
        assert stored.messages[1].text == 'Hi there'
