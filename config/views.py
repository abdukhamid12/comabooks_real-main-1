from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book, BookPageAnswer, BookCover, BookPageQuestion, Review, AISettings
from .forms import BookForm, BookPageForm
from .utils import generate_book_pdf, send_telegram_notification, generate_questions_ai, enhance_answer_ai
from django.http import FileResponse, JsonResponse
import io
import os
from django.conf import settings

def home(request):
    reviews = Review.objects.all().order_by('-created_at')[:6]
    return render(request, "home.html", {"reviews": reviews})

@login_required
def dashboard(request):
    books = Book.objects.filter(user=request.user)
    return render(request, "books/dashboard.html", {"books": books})


@login_required
def create_book(request):
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()

            # Create Cover with selected template
            template_style = form.cleaned_data.get('template', 'classic')
            BookCover.objects.create(
                book=book,
                title=book.title,
                author_book=book.author,
                template=template_style
            )

            return redirect("edit_pages", book.id)
    else:
        form = BookForm()
    return render(request, "books/create_book.html", {"form": form})


@login_required
def edit_pages(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)

    # Get questions
    # 1. First check if book has its own custom questions (AI-generated for this user)
    questions = book.custom_questions.all()

    # 2. If no book-specific questions, check dedication questions (manually added by admin)
    if not questions.exists() and book.dedication:
        questions = book.dedication.questions.filter(book__isnull=True)

    # 3. If STILL no questions and AI is enabled, generate unique ones for this book
    if not questions.exists() and book.dedication:
        ai_settings = AISettings.objects.first()
        if ai_settings and ai_settings.is_ai_enabled and ai_settings.gemini_api_key:
            generated_questions = generate_questions_ai(
                book.dedication.name,
                book.dedication.text,
                count=ai_settings.ai_question_count,
                api_key=ai_settings.gemini_api_key
            )
            for q_text in generated_questions:
                BookPageQuestion.objects.create(
                    book=book, # Link to book for uniqueness
                    quiz=q_text
                )
            questions = book.custom_questions.all()

    # fallback to generic questions if nothing else works
    if not questions.exists():
        questions = BookPageQuestion.objects.filter(dedication__isnull=True, book__isnull=True)

    # Determine active question
    question_id = request.GET.get('q')
    if question_id:
        active_question = get_object_or_404(BookPageQuestion, id=question_id)
    else:
        active_question = questions.first()

    # Get existing answer if any
    try:
        current_answer = BookPageAnswer.objects.get(book=book, quiz=active_question.quiz)
    except (BookPageAnswer.DoesNotExist, AttributeError):
        current_answer = None

    if request.method == "POST":
        form = BookPageForm(request.POST, request.FILES, instance=current_answer)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.book = book
            answer.user = request.user
            answer.quiz = active_question.quiz
            answer.save()

            # Redirect to next question
            next_question = questions.filter(id__gt=active_question.id).first()
            if next_question:
                return redirect(f"{request.path}?q={next_question.id}")
            else:
                return redirect('dashboard') # Or finish page
    else:
        form = BookPageForm(instance=current_answer)

    # Get AI settings for UI toggles
    ai_settings = AISettings.objects.first()

    return render(request, "books/edit_pages.html", {
        "book": book,
        "questions": questions,
        "active_question": active_question,
        "form": form,
        "ai_settings": ai_settings,
    })


@login_required
def add_page(request, book_id):
    # Deprecated for new flow, but keeping for compatibility or direct access
    return redirect("edit_pages", book_id)


@login_required
def generate_pdf(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    buffer = generate_book_pdf(book)
    filename = f"{book.title}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


@login_required
def finish_book(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    if request.method == "POST":
        print(f"DEBUG: finish_book POST received for book {book.id}")
        book.status = 'completed'
        book.save()

        # Send Telegram Notification
        try:
            print(f"DEBUG: Generating PDF and sending notification for book {book.id}")
            pdf_buffer = generate_book_pdf(book)
            send_telegram_notification(book, pdf_buffer)
            print(f"DEBUG: Notification task finished for book {book.id}")
        except Exception as e:
            print(f"DEBUG: Error sending notification: {e}")
            # Don't block user flow if notification fails

    return redirect("dashboard")


@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    if request.method == "POST":
        book.delete()
    return redirect("dashboard")


@login_required
def enhance_answer_ajax(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        question = data.get('question')
        answer = data.get('answer')

        ai_settings = AISettings.objects.first()
        if not ai_settings or not ai_settings.is_ai_enabled or not ai_settings.gemini_api_key:
            return JsonResponse({'success': False, 'error': 'AI is disabled or not configured'})

        enhanced_text = enhance_answer_ai(question, answer, ai_settings.gemini_api_key)
        return JsonResponse({'success': True, 'enhanced_text': enhanced_text})

    return JsonResponse({'success': False, 'error': 'Invalid request'})
