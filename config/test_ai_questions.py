from django.test import TestCase
from unittest.mock import patch
from .models import Book, BookDedication, BookPageQuestion, BookPageAnswer, CustomUser, AISettings
from .studio import chapters

class QuestionGenerationTests(TestCase):
    def setUp(self):
        self.user=CustomUser.objects.create_user('author')
        self.person=BookDedication.objects.create(name='Мама',text='Любит горы и путешествия')
        self.book=Book.objects.create(user=self.user,title='История',author='Автор',dedication=self.person)
        self.ai=AISettings.objects.create(is_ai_enabled=True,gemini_api_key='test-key',ai_question_count=2)

    @patch('config.utils.generate_questions_ai',return_value=['Первый поход?', 'Любимые горы?'])
    def test_person_context_and_generate_once(self, generate):
        BookPageQuestion.objects.create(quiz='Общий вопрос')
        self.assertEqual([q.quiz for q in chapters(self.book)],['Первый поход?', 'Любимые горы?'])
        chapters(self.book)
        generate.assert_called_once_with('Мама','Любит горы и путешествия',count=2,api_key='test-key')

    @patch('config.utils.generate_questions_ai')
    def test_dedication_catalogue_wins(self, generate):
        BookPageQuestion.objects.create(dedication=self.person,quiz='Готовый вопрос')
        self.assertEqual(chapters(self.book)[0].quiz,'Готовый вопрос')
        generate.assert_not_called()

    @patch('config.utils.generate_questions_ai',return_value=[])
    def test_failure_fallback_preserves_answers(self, generate):
        page=BookPageAnswer.objects.create(user=self.user,book=self.book,quiz='Моя глава',answer='Мой текст')
        self.assertIn('Моя глава',[q.quiz for q in chapters(self.book)])
        page.refresh_from_db()
        self.assertEqual(page.answer,'Мой текст')

    @patch('config.utils.generate_questions_ai')
    def test_disabled_and_existing_chapters(self, generate):
        self.ai.is_ai_enabled=False;self.ai.save()
        chapters(self.book)
        self.ai.is_ai_enabled=True;self.ai.save()
        chapters(self.book)
        generate.assert_not_called()

    @patch('config.utils.generate_questions_ai',return_value=['',42,'Вопрос','Вопрос','x'*256])
    def test_invalid_items_filtered(self, generate):
        self.assertEqual([q.quiz for q in chapters(self.book)],['Вопрос'])
