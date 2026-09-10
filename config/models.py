from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# 1. Пользователь
class CustomUser(AbstractUser):
    pass

# 2. Посвящение
class BookDedication(models.Model):
    name = models.CharField(max_length=255, verbose_name="Имя")
    text = models.TextField(verbose_name="Текст посвящения")

    def __str__(self):
        return self.name

# 3. Шаблон книги - REMOVED, using choices instead
# class BookTemplate(models.Model): ...

from .cover_designs import TEMPLATE_CHOICES

# ...

# 4. Вопрос (для каталога вопросов)
class BookPageQuestion(models.Model):
    dedication = models.ForeignKey(BookDedication, on_delete=models.CASCADE, related_name="questions", null=True, blank=True, verbose_name="Для кого (посвящение)")
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name="custom_questions", null=True, blank=True, verbose_name="Для книги")
    quiz = models.CharField(max_length=255, verbose_name="Вопрос")

    def __str__(self):
        return f"{self.quiz} ({self.dedication.name if self.dedication else 'Общий'})"

# 5. Главная книга
class Book(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('completed', 'Завершено (Ждет проверки)'),
        ('printed', 'Напечатано'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=255, verbose_name="Название книги")
    author = models.CharField(max_length=255, verbose_name="Автор")
    subtitle = models.CharField(max_length=255, blank=True, null=True, verbose_name="Подзаголовок")
    dedication = models.ForeignKey(BookDedication, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Посвящение")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    is_notification_sent = models.BooleanField(default=False, verbose_name="Уведомление отправлено")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.user.username})"

# 6. Ответ на вопрос (страница книги)
class BookPageAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="pages", null=True, blank=True)
    quiz = models.CharField(max_length=255, verbose_name="Вопрос")
    answer = models.TextField(verbose_name="Ответ")
    image = models.ImageField(upload_to="book_images/", blank=True, null=True, verbose_name="Фотография")

    def __str__(self):
        return f"{self.quiz[:20]} - {self.answer[:20]}"


# 7. Обложка
class BookCover(models.Model):
    title = models.CharField(max_length=255, verbose_name="Заголовок на обложке")
    author_book = models.CharField(max_length=255, verbose_name="Автор на обложке")
    template = models.CharField(max_length=50, choices=TEMPLATE_CHOICES, default='classic', verbose_name="Шаблон")
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="cover_data", null=True, blank=True)

# 8. Отзывы
class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Пользователь")
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Книга")
    text = models.TextField(verbose_name="Текст отзыва")
    rating = models.IntegerField(default=5, verbose_name="Оценка (1-5)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return f"Отзыв от {self.user.username} ({self.rating}/5)"


# 9. Настройки ИИ
class AISettings(models.Model):
    gemini_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gemini API Key")
    ai_question_count = models.IntegerField(default=5, verbose_name="Количество вопросов ИИ")
    is_ai_enabled = models.BooleanField(default=True, verbose_name="ИИ включен")

    class Meta:
        verbose_name = "Настройки ИИ"
        verbose_name_plural = "Настройки ИИ"

    def __str__(self):
        return "Настройки ИИ"

    def save(self, *args, **kwargs):
        if not self.pk and AISettings.objects.exists():
            return
        return super(AISettings, self).save(*args, **kwargs)
