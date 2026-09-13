from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BookDedication, BookCover, BookPageQuestion, BookPageAnswer, Book, CustomUser, Review, AISettings
from django.utils.html import format_html

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    pass

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'text')

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['title', 'author', 'user__username']
    list_per_page = 25
    readonly_fields = ['print_files', 'approved_at', 'revision']

    def save_model(self, request, obj, form, change):
        if obj.status in ['printing', 'printed', 'shipped'] and not obj.approved_at:
            from django.contrib import messages
            messages.warning(request, 'Сначала клиент должен подтвердить макет. Книга оставлена на проверке.')
            obj.status = 'completed'
        super().save_model(request, obj, form, change)

    @admin.display(description='Файлы для типографии')
    def print_files(self, obj):
        from django.urls import reverse
        if not obj or not obj.pk:
            return 'Сначала сохраните книгу.'
        return format_html('<a class="btn btn-info" href="{}">Скачать комплект для печати</a>', reverse('admin:config_book_print', args=[obj.pk]))

    def get_urls(self):
        from django.urls import path
        return [path('<int:object_id>/print/', self.admin_site.admin_view(self.print_package), name='config_book_print')] + super().get_urls()

    def print_package(self, request, object_id):
        from django.core.exceptions import PermissionDenied
        from django.http import FileResponse, Http404
        from .book_pdf import generate_print_package
        book = self.get_object(request, object_id)
        if book is None:
            raise Http404
        if not self.has_view_permission(request, book):
            raise PermissionDenied
        return FileResponse(generate_print_package(book), as_attachment=True, filename=f'book-{book.pk}-print.zip', content_type='application/zip')


@admin.register(BookDedication)
class BookDedicationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(BookCover)
class BookCoverAdmin(admin.ModelAdmin):
    list_display = ('title', 'author_book', 'template', 'cover_preview')
    readonly_fields = ('cover_preview',)

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="max-height: 200px; max-width: 200px;" />', obj.cover_image.url)
        return "(No preview)"

    cover_preview.short_description = "Preview"


@admin.register(BookPageQuestion)
class BookPageQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_quiz', 'dedication')
    search_fields = ('quiz',)
    list_filter = ('dedication',)

    def short_quiz(self, obj):
        return obj.quiz[:50]

    short_quiz.short_description = "Вопрос"


@admin.register(BookPageAnswer)
class BookPageAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'quiz', 'short_answer')
    search_fields = ('answer', 'quiz', 'book__title', 'user__username')
    list_filter = ('user',)

    def short_answer(self, obj):
        return obj.answer[:50]

    short_answer.short_description = "Ответ"


@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = ('gemini_api_key', 'ai_question_count', 'is_ai_enabled')

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
