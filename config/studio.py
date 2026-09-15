"""Owner-scoped book editing, exact PDF previews and print approval."""
import io
import json
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse, HttpResponse, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps
from .models import Book, BookPageQuestion, BookPageAnswer, AISettings
from .book_pdf import generate_book_pdf


def owner(request, book_id):
    return get_object_or_404(Book, pk=book_id, user=request.user)


def chapters(book):
    # Generate outside the database transaction; keep existing book chapters intact.
    titles = []
    if not book.custom_questions.exists():
        source = BookPageQuestion.objects.filter(book=None, dedication=book.dedication).order_by('position', 'pk') if book.dedication_id else BookPageQuestion.objects.none()
        titles = list(source.values_list('quiz', flat=True))
        if not titles and book.dedication_id and book.status == 'draft':
            ai = AISettings.objects.first()
            if ai and ai.is_ai_enabled and ai.gemini_api_key:
                from .utils import generate_questions_ai
                generated = generate_questions_ai(book.dedication.name, book.dedication.text,
                    count=max(1, min(ai.ai_question_count, 100)), api_key=ai.gemini_api_key)
                if isinstance(generated, list):
                    titles = list(dict.fromkeys(q.strip() for q in generated
                        if isinstance(q, str) and q.strip() and len(q.strip()) <= 255))[:max(1, min(ai.ai_question_count, 100))]
        if not titles:
            titles = list(BookPageQuestion.objects.filter(book=None, dedication=None).order_by('position','pk').values_list('quiz', flat=True))
        if not titles:
            titles = ['Как началась ваша история?', 'Ваш самый тёплый день', 'Что хочется сказать?']
    with transaction.atomic():
        Book.objects.select_for_update().get(pk=book.pk)
        # Another request may have created chapters while the AI was responding.
        if not book.custom_questions.exists():
            titles = list(dict.fromkeys(titles + list(book.pages.values_list('quiz', flat=True))))
            for i, title in enumerate(titles):
                BookPageQuestion.objects.create(book=book, quiz=title, position=i)
        result = list(book.custom_questions.order_by('position', 'pk'))
        for i, q in enumerate(result):
            if q.position != i:
                q.position=i
                q.save(update_fields=['position'])
            book.pages.filter(quiz=q.quiz).exclude(position=i).update(position=i)
    return result


@login_required
def editor(request, book_id):
    book = owner(request, book_id)
    questions = chapters(book)
    completed = set(book.pages.exclude(answer='').values_list('quiz', flat=True))
    return render(request, 'books/studio.html', {
        'book': book, 'studio_data': {
            'base': reverse('studio_state', args=[book.pk]),
            'revision': book.revision,
            'user': request.user.pk,
            'locked': book.status != 'draft',
            'chapters': [dict(id=q.pk, title=q.quiz, done=q.quiz in completed) for q in questions],
            'review': reverse('book_review', args=[book.pk]),
        }})


@login_required
def state(request, book_id):
    book = owner(request, book_id)
    q = get_object_or_404(book.custom_questions, pk=request.GET.get('q'))
    page = book.pages.filter(quiz=q.quiz).first()
    return JsonResponse({'revision': book.revision, 'answer': page.answer if page else '',
        'image': reverse('studio_photo', args=[book.pk, page.pk]) if page and page.image else '',
        'rotation': page.rotation if page else 0, 'image_fit': page.image_fit if page else 'contain',
        'focus_x': page.focus_x if page else .5, 'focus_y': page.focus_y if page else .5})


@login_required
@require_POST
def save(request, book_id):
    book = owner(request, book_id)
    q = get_object_or_404(book.custom_questions, pk=request.POST.get('q'))
    text = request.POST.get('answer', '')
    if len(text.split()) > 250:
        return JsonResponse({'error': 'На странице допускается 250 слов. Перенесите часть текста в новую главу.'}, status=400)
    try:
        revision = int(request.POST['revision'])
        rotation = int(request.POST.get('rotation', 0))
        fx, fy = float(request.POST.get('focus_x', .5)), float(request.POST.get('focus_y', .5))
        mode = request.POST.get('image_fit', 'contain')
        if rotation not in [0,90,180,270] or mode not in ['contain','cover'] or not (0<=fx<=1 and 0<=fy<=1):
            raise ValueError()
    except (ValueError, KeyError):
        return JsonResponse({'error':'Некорректные параметры страницы.'}, status=400)
    upload = request.FILES.get('image')
    warning = ''
    if upload:
        if upload.size > 15*1024*1024:
            return JsonResponse({'error':'Выберите фотографию до 15 МБ.'}, status=400)
        try:
            with Image.open(upload) as im:
                im.verify()
            upload.seek(0)
            with Image.open(upload) as im:
                if min(im.size)<600:
                    warning='Фотография небольшая: на бумаге может быть недостаточно чёткой.'
            upload.seek(0)
        except (OSError, ValueError, Image.DecompressionBombError):
            return JsonResponse({'error':'Не удалось прочитать изображение. Выберите JPEG или PNG.'}, status=400)
    with transaction.atomic():
        changed = Book.objects.filter(pk=book.pk, revision=revision, status='draft').update(revision=F('revision')+1, approved_at=None)
        if not changed:
            return JsonResponse({'error':'Книга изменена в другой вкладке или уже подтверждена. Скопируйте текст и обновите страницу.'}, status=409)
        page, _ = BookPageAnswer.objects.get_or_create(book=book, quiz=q.quiz, defaults={'user':request.user, 'answer':''})
        page.answer=text; page.position=q.position; page.rotation=rotation
        page.image_fit=mode; page.focus_x=fx; page.focus_y=fy
        if request.POST.get('remove_image')=='1': page.image=''
        if upload: page.image=upload
        page.save()
    return JsonResponse({'revision':revision+1, 'warning':warning, 'done':bool(text.strip())})


@login_required
@require_POST
def structure(request, book_id):
    book = owner(request, book_id)
    try:
        data=json.loads(request.body)
        revision=int(data['revision'])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error':'Некорректный запрос.'}, status=400)
    with transaction.atomic():
        if not Book.objects.filter(pk=book.pk, revision=revision, status='draft').update(revision=F('revision')+1, approved_at=None):
            return JsonResponse({'error':'Книга изменилась. Обновите страницу.'}, status=409)
        qs=list(book.custom_questions.order_by('position','pk'))
        title=str(data.get('title','')).strip()
        if data.get('action')=='add':
            if not title or len(title)>255 or any(q.quiz==title for q in qs):
                transaction.set_rollback(True)
                return JsonResponse({'error':'Введите уникальное название главы до 255 символов.'},status=400)
            BookPageQuestion.objects.create(book=book,quiz=title,position=len(qs))
        elif data.get('action')=='reorder':
            order=data.get('order',[])
            if sorted(order)!=sorted(q.pk for q in qs):
                transaction.set_rollback(True)
                return JsonResponse({'error':'Некорректный порядок глав.'},status=400)
            for i,pk in enumerate(order):
                q=next(q for q in qs if q.pk==pk)
                BookPageQuestion.objects.filter(pk=pk).update(position=i)
                book.pages.filter(quiz=q.quiz).update(position=i)
        else:
            transaction.set_rollback(True)
            return JsonResponse({'error':'Неизвестное действие.'},status=400)
    return JsonResponse({'revision':revision+1})


@login_required
def photo(request, book_id, page_id):
    book=owner(request,book_id)
    page=get_object_or_404(book.pages,pk=page_id)
    if not page.image: return HttpResponse(status=404)
    response=FileResponse(page.image.open('rb'))
    response['Cache-Control']='private, no-store'
    return response


@login_required
def preview(request, book_id):
    import pymupdf
    book=owner(request,book_id)
    key=f'book-preview:{book.pk}:{book.revision}'
    pdf=cache.get(key)
    if pdf is None:
        pdf=generate_book_pdf(book).getvalue(); cache.set(key,pdf,60)
    with pymupdf.open(stream=pdf,filetype='pdf') as document:
        try:
            if request.GET.get('q'):
                q=get_object_or_404(book.custom_questions,pk=request.GET['q'])
                pages=list(book.pages.order_by('position','pk').values_list('quiz',flat=True))
                if q.quiz not in pages: return JsonResponse({'error':'Сначала сохраните текст страницы.'},status=400)
                index=4+pages.index(q.quiz)
            else: index=int(request.GET.get('page',0))
            if not 0<=index<len(document): raise ValueError()
        except ValueError: return HttpResponse(status=404)
        if request.GET.get('info'):
            return JsonResponse({'pages':len(document)})
        pix=document[index].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5))
        response=HttpResponse(pix.tobytes('png'),content_type='image/png')
        response['Cache-Control']='private, no-store'
        return response


@login_required
def review(request, book_id):
    book=owner(request,book_id)
    questions=chapters(book)
    done=book.pages.exclude(answer='').count()
    return render(request,'books/review.html',{'book':book,'done':done,'total':len(questions),
        'events':book.status_events.all(), 'telegram_ready':bool(getattr(settings,'TELEGRAM_BOT_USERNAME',''))})


@login_required
@require_POST
def approve(request, book_id):
    book=owner(request,book_id)
    if request.POST.get('confirm')!='yes': return HttpResponse('Подтвердите проверку макета.',status=400)
    with transaction.atomic():
        book=Book.objects.select_for_update().get(pk=book.pk)
        if str(book.revision)!=request.POST.get('revision'): return HttpResponse('Макет изменился. Откройте предпросмотр заново.',status=409)
        if book.status=='draft':
            if not book.pages.exclude(answer='').exists(): return HttpResponse('Добавьте текст книги.',status=400)
            book.status='completed';book.approved_at=timezone.now();book.is_notification_sent=False;book.save()
    return redirect('book_review',book.pk)


@login_required
@require_POST
def reopen(request, book_id):
    book=owner(request,book_id)
    with transaction.atomic():
        book=Book.objects.select_for_update().get(pk=book.pk)
        if book.status not in ['draft','completed']: return HttpResponse('Книга уже в производстве. Свяжитесь с администратором.',status=409)
        book.status='draft';book.approved_at=None;book.revision+=1;book.save()
    return redirect('edit_pages',book.pk)


@login_required
@require_POST
def assistant(request, book_id):
    book=owner(request,book_id)
    try: data=json.loads(request.body)
    except ValueError: return JsonResponse({'error':'Некорректный запрос.'},status=400)
    q=get_object_or_404(book.custom_questions,pk=data.get('q'))
    mode=data.get('mode'); text=str(data.get('text',''))[:20000]
    if mode=='start':
        return JsonResponse({'text':f'Я хочу рассказать об этом моменте: {q.quiz.lower()}\n\nВсё началось с…\nБольше всего мне запомнилось…\nДля меня это важно, потому что…','kind':'template'})
    if mode=='question':
        return JsonResponse({'text':'Где это происходило? Какая небольшая деталь запомнилась? Что вы почувствовали и что хотите сказать сейчас?','kind':'question'})
    if mode!='correct': return JsonResponse({'error':'Неизвестное действие.'},status=400)
    ai=AISettings.objects.first()
    if not ai or not ai.is_ai_enabled or not ai.gemini_api_key:
        return JsonResponse({'error':'Исправление ошибок станет доступно после подключения ИИ администратором. Подсказки для начала уже работают.'},status=503)
    try:
        import google.generativeai as genai
        genai.configure(api_key=ai.gemini_api_key)
        result=genai.GenerativeModel('gemini-flash-latest').generate_content(
            'Исправь только орфографию и пунктуацию. Сохрани смысл, факты, стиль и язык. Не добавляй событий. Верни только исправленный текст. Текст автора:\n'+text,
            request_options={'timeout':25})
        return JsonResponse({'text':result.text,'kind':'correction'})
    except Exception:
        return JsonResponse({'error':'Помощник временно недоступен. Ваш текст сохранён без изменений.'},status=503)


@login_required
@require_POST
def telegram_link(request):
    name=getattr(settings,'TELEGRAM_BOT_USERNAME','').lstrip('@')
    if not name: return JsonResponse({'error':'Администратору нужно указать имя Telegram-бота.'},status=503)
    user=request.user
    user.telegram_link_token=secrets.token_urlsafe(24)
    user.telegram_link_expires=timezone.now()+timedelta(minutes=15)
    user.save(update_fields=['telegram_link_token','telegram_link_expires'])
    return JsonResponse({'url':f'https://t.me/{name}?start=link_{user.telegram_link_token}'})


@login_required
def history(request, book_id):
    book = owner(request, book_id)
    pages = book.pages.prefetch_related('versions').order_by('position','pk')
    return render(request, 'books/history.html', {'book':book,'pages':pages})

@login_required
@require_POST
def restore_text(request, book_id, version_id):
    from .models import PageVersion
    book = owner(request, book_id)
    version = get_object_or_404(PageVersion,pk=version_id,page__book=book)
    with transaction.atomic():
        try: revision=int(request.POST.get('revision',''))
        except ValueError: return HttpResponse('Некорректная версия книги.',status=400)
        if not Book.objects.filter(pk=book.pk,revision=revision,status='draft').update(revision=F('revision')+1):
            return HttpResponse('Книга изменилась или подтверждена. Обновите историю перед восстановлением.',status=409)
        page=BookPageAnswer.objects.get(pk=version.page_id)
        page.answer=version.text
        page.save(update_fields=['answer'])
    return redirect('book_history',book_id=book.pk)
