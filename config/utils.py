import io
import os
import requests
from django.conf import settings
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    KeepTogether, Image as RLImage, PageTemplate, Frame, NextPageTemplate
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
import google.generativeai as genai
import json

def split_text_by_words(text, limit=250):
    words = text.split()
    chunks = []
    for i in range(0, len(words), limit):
        chunks.append(" ".join(words[i:i+limit]))
    return chunks

# Shared reader and production layout engine.
from .book_pdf import generate_book_pdf


def send_telegram_notification(book, pdf_buffer, target_chat_id=None):
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = target_chat_id or settings.TELEGRAM_ADMIN_CHAT_ID

    if not token or not chat_id or token == 'YOUR_BOT_TOKEN_HERE':
        print("Telegram settings not configured.")
        return

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    # Reset buffer pos just in case
    pdf_buffer.seek(0)

    files = {
        'document': (f'{book.title}.pdf', pdf_buffer, 'application/pdf')
    }

    caption = (
        f"📘 *Новая книга на проверку!*\n\n"
        f"**Название:** {book.title}\n"
        f"**Автор:** {book.author}\n"
        f"**Пользователь:** {book.user.username}\n"
        f"**Время отправки:** {timezone.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Статус:** {book.get_status_display()}"
    )

    data = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': 'Markdown'
    }

    try:
        # verify=False used to bypass local SSL issues on Windows dev environment
        response = requests.post(url, data=data, files=files, verify=False)
        response.raise_for_status()
        print("Telegram notification sent successfully.")
        # Mark as sent
        book.is_notification_sent = True
        book.save()
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")


def generate_questions_ai(dedication_name, dedication_text, count=5, api_key=None):
    if not api_key:
        print("AI generation skipped: No API key provided.")
        return []

    try:
        genai.configure(api_key=api_key)
        # Using gemini-flash-latest which exists in your models list
        model = genai.GenerativeModel('gemini-flash-latest')

        prompt = (
            f"Ты — дружелюбный помощник по созданию подарочных книг. Твоя задача — придумать простые и теплые вопросы для автора книги, "
            f"которые помогут ему вспомнить добрые истории про человека по имени **{dedication_name}**. "
            f"Вот что автор написал об этом человеке: \"{dedication_text}\".\n\n"
            f"Сгенерируй {count} простых и душевных вопросов.\n"
            f"ПРАВИЛА:\n"
            f"1. Вопросы должны быть короткими и понятными (например: 'Вспомни твой любимый момент с {dedication_name}', 'Какое качество в {dedication_name} тебя больше всего восхищает?').\n"
            f"2. Используй имя {dedication_name} в вопросах.\n"
            f"3. Вопросы должны быть про личные воспоминания, чувства и общие приключения.\n"
            f"4. НЕ используй заумных слов. Представь, что ты общаешься с другом.\n\n"
            f"Верни ответ ТОЛЬКО в формате JSON массива строк.\n"
            f"Пример: [\"Вопрос 1\", \"Вопрос 2\"]"
        )

        response = model.generate_content(prompt, request_options={"timeout": 25})
        text = response.text.strip()

        # Clean potential markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        questions = json.loads(text)
        return questions
    except Exception:
        # Do not log provider exceptions: they can include request credentials.
        return []


def enhance_answer_ai(question, answer, api_key=None):
    if not api_key or not answer:
        return answer

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')

        prompt = (
            f"Ты — помощник писателя. Тебе дали короткий ответ на вопрос для книги воспоминаний. "
            f"Твоя задача — сделать этот ответ более красивым, эмоциональным и развернутым, сохранив основной смысл и факты.\n\n"
            f"Вопрос: {question}\n"
            f"Короткий ответ: {answer}\n\n"
            f"Требования к тексту:\n"
            f"1. Сделай текст более литературным и плавным.\n"
            f"2. Если ответ слишком короткий, добавь немного атмосферы, подходящей по смыслу.\n"
            f"3. Пиши от первого лица (как автор ответа).\n"
            f"4. НЕ добавляй выдуманных фактов, которых нет в ответе, просто раскрась имеющиеся.\n\n"
            f"Верни ТОЛЬКО улучшенный текст (без пояснений и кавычек)."
        )

        response = model.generate_content(prompt)
        enhanced_text = response.text.strip()

        if len(enhanced_text) > 5: # basic sanity check
            return enhanced_text
        return answer
    except Exception as e:
        print(f"Error enhancing answer with AI: {e}")
        return answer
