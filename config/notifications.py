import requests
from django.conf import settings
from django.utils import timezone
from .models import CustomUser, BookStatusEvent

def connect_customer(chat_id, text, chat_type):
    if chat_type != 'private' or not text.startswith('/start link_'): return False
    token=text.removeprefix('/start link_').strip()
    return bool(CustomUser.objects.filter(telegram_link_token=token,telegram_link_expires__gt=timezone.now()).exclude(telegram_link_token='').update(
        telegram_chat_id=str(chat_id),telegram_link_token='',telegram_link_expires=None))

def deliver_status_events():
    token=getattr(settings,'TELEGRAM_BOT_TOKEN','')
    if not token: return
    events=BookStatusEvent.objects.filter(telegram_sent=False).exclude(book__user__telegram_chat_id='').select_related('book__user')[:20]
    for event in events:
        try:
            response=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={
                'chat_id':event.book.user.telegram_chat_id,
                'text':f'Книга «{event.book.title}»: {event.get_status_display()}.'},timeout=10)
            response.raise_for_status()
            if not response.json().get('ok'): raise ValueError('Telegram rejected message')
            event.telegram_sent=True;event.delivery_error=''
        except (requests.RequestException, ValueError):
            event.delivery_error='Не доставлено. Повторите после проверки подключения.'
        event.save(update_fields=['telegram_sent','delivery_error'])
