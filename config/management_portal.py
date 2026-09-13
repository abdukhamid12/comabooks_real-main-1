from functools import wraps
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from .models import Book, CustomUser, BookPageAnswer, BookPageQuestion, BookDedication, BookCover, Review, AISettings

SECTIONS = {
    'books': (Book, 'Книги и заказы', ['title','author','subtitle','dedication','status','tracking_url','due_date','internal_notes']),
    'users': (CustomUser, 'Клиенты и сотрудники', ['username','first_name','last_name','email','is_active']),
    'pages': (BookPageAnswer, 'Страницы книг', ['book','quiz','answer','image','position','rotation','image_fit','focus_x','focus_y']),
    'questions': (BookPageQuestion, 'Вопросы', ['book','dedication','quiz','position']),
    'dedications': (BookDedication, 'Посвящения', ['name','text']),
    'covers': (BookCover, 'Обложки', ['book','title','author_book','template','cover_image']),
    'reviews': (Review, 'Отзывы', ['user','book','text','rating']),
    'ai': (AISettings, 'Настройки ИИ', ['gemini_api_key','ai_question_count','is_ai_enabled']),
    'groups': (Group, 'Группы доступа', ['name','permissions']),
}

def staff(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped

def allowed(user, model, action):
    return user.has_perm(f'{model._meta.app_label}.{action}_{model._meta.model_name}')

def navigation(user):
    return [{'key': k, 'title': title} for k,(model,title,fields) in SECTIONS.items() if allowed(user,model,'view')]

def context(request, **kwargs):
    return {'sections': navigation(request.user), **kwargs}

@staff
def home(request):
    cards = [{**s, 'count': SECTIONS[s['key']][0].objects.count()} for s in navigation(request.user)]
    books = Book.objects.select_related('user').order_by('-created_at')[:6] if allowed(request.user,Book,'view') else []
    return render(request,'management/home.html',context(request,cards=cards,books=books))

def section_data(request, section, action='view'):
    if section not in SECTIONS: raise Http404
    model,title,fields=SECTIONS[section]
    if not allowed(request.user,model,action): raise PermissionDenied
    if model==Group and action!='view' and not request.user.is_superuser: raise PermissionDenied
    return model,title,fields

@staff
def listing(request, section):
    model,title,fields=section_data(request,section)
    qs=model.objects.order_by('-pk')
    query=request.GET.get('q','').strip()
    searchable={'books':['title','author','user__username'],'users':['username','first_name','last_name','email'],'pages':['quiz','answer','book__title'],'questions':['quiz'],'dedications':['name','text'],'covers':['title','author_book'],'reviews':['text','user__username'],'groups':['name']}.get(section,[])
    if query and searchable:
        condition=Q()
        for field in searchable: condition |= Q(**{field+'__icontains':query})
        qs=qs.filter(condition)
    status=request.GET.get('status','')
    if section=='books' and status in dict(Book.STATUS_CHOICES): qs=qs.filter(status=status)
    page=Paginator(qs,20).get_page(request.GET.get('page'))
    rows=[]
    for obj in page:
        label = 'Настройки ИИ' if section=='ai' else (obj.title if section=='covers' else str(obj))
        detail = obj.get_status_display() if section=='books' else ('Администратор' if obj.is_staff else 'Клиент') if section=='users' else ''
        rows.append({'object':obj,'label':label,'detail':detail})
    return render(request,'management/list.html',context(request,section=section,title=title,rows=rows,page=page,query=query,status=status,statuses=Book.STATUS_CHOICES if section=='books' else [],can_add=allowed(request.user,model,'add') and not(section=='ai' and model.objects.exists())))

def make_form(request, model, fields, obj):
    fields=list(fields)
    if model==Book and not obj: fields.insert(0,'user')
    if model==CustomUser and request.user.is_superuser:
        fields += ['is_staff','groups','user_permissions']
    if model==CustomUser and obj and obj.is_staff and not request.user.is_superuser: raise PermissionDenied
    Base=forms.modelform_factory(model,fields=fields)
    class EditorForm(Base):
        def clean(self):
            data=super().clean()
            if model==Book and data.get('status') in ['printing','printed','shipped'] and not (obj and obj.approved_at):
                self.add_error('status','Клиент должен подтвердить макет перед печатью.')
            if model==BookPageAnswer:
                if len(data.get('answer','').split())>250: self.add_error('answer','Не более 250 слов на странице.')
                for name in ['focus_x','focus_y']:
                    if data.get(name) is not None and not 0<=data[name]<=1: self.add_error(name,'Значение от 0 до 1.')
            if model==Review and data.get('rating') not in range(1,6): self.add_error('rating','Оценка от 1 до 5.')
            if model==AISettings and not 1<=data.get('ai_question_count',0)<=100: self.add_error('ai_question_count','От 1 до 100 вопросов.')
            if model==CustomUser:
                if obj and obj.pk==request.user.pk and (not data.get('is_active') or ('is_staff' in data and not data['is_staff'])):
                    self.add_error(None,'Нельзя отключить собственный доступ.')
                password=data.get('new_password')
                if password:
                    validate_password(password, obj or CustomUser(username=data.get('username','')))
                    if password!=data.get('repeat_password'): self.add_error('repeat_password','Пароли не совпадают.')
            return data
    form=EditorForm(request.POST or None,request.FILES or None,instance=obj)
    if model==Book: form.fields['due_date'].widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')
    if model==BookPageAnswer: form.fields['book'].required=True
    if obj and 'book' in form.fields: form.fields['book'].disabled=True
    if model==CustomUser:
        form.fields['new_password']=forms.CharField(label='Новый пароль',required=not bool(obj),widget=forms.PasswordInput,help_text='Оставьте пустым, чтобы сохранить пароль.' if obj else 'Пароль для входа клиента на сайте.')
        form.fields['repeat_password']=forms.CharField(label='Повторите пароль',required=not bool(obj),widget=forms.PasswordInput)
    if model==AISettings:
        form.fields['gemini_api_key'].widget=forms.PasswordInput(render_value=False)
        form.fields['gemini_api_key'].help_text='Оставьте пустым, чтобы сохранить подключённый ключ.'
    labels={'user':'Клиент','book':'Книга','position':'Порядок страницы','rotation':'Поворот фотографии','image_fit':'Размещение фотографии','focus_x':'Центр кадра по горизонтали (0–1)','focus_y':'Центр кадра по вертикали (0–1)','cover_image':'Изображение обложки','is_staff':'Доступ к панели управления','groups':'Группы доступа','user_permissions':'Разрешения','name':'Название','permissions':'Разрешения'}
    for name,field in form.fields.items():
        if name in labels: field.label=labels[name]
        field.widget.attrs['class']='portal-control'
    return form

@staff
def edit(request, section, pk=None):
    model,title,fields=section_data(request,section,'change' if pk else 'add')
    obj=get_object_or_404(model,pk=pk) if pk else None
    if section=='ai' and not pk and model.objects.exists(): return redirect('management_edit',section=section,pk=model.objects.first().pk)
    form=make_form(request,model,fields,obj)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            saved=form.save(commit=False)
            related_book = saved if model==Book else getattr(saved,'book',None)
            if related_book:
                locked=Book.objects.select_for_update().get(pk=related_book.pk) if related_book.pk else None
                content_change=model in [BookPageAnswer,BookCover,BookPageQuestion] or (model==Book and any(f in form.changed_data for f in ['title','author','subtitle','dedication']))
                if locked and content_change and locked.status!='draft':
                    form.add_error(None,'Макет подтверждён. Сначала верните книгу в черновик, чтобы изменить содержание.')
                elif locked:
                    saved.revision=locked.revision+1 if model==Book else getattr(saved,'revision',0)
                    if model!=Book: Book.objects.filter(pk=locked.pk).update(revision=F('revision')+1)
                    if model==Book and saved.status=='draft': saved.approved_at=None
            if not form.errors:
                if model==BookPageAnswer: saved.user=saved.book.user
                if model==CustomUser and form.cleaned_data.get('new_password'): saved.set_password(form.cleaned_data['new_password'])
                if model==AISettings and not form.cleaned_data.get('gemini_api_key') and pk:
                    saved.gemini_api_key=model.objects.get(pk=pk).gemini_api_key
                saved.save()
                form.save_m2m()
                messages.success(request,'Изменения сохранены.')
                return redirect('management_list',section=section)
    return render(request,'management/edit.html',context(request,section=section,title=title,form=form,object=obj,is_book=model==Book))

@staff
def book_file(request, pk, kind):
    section_data(request,'books')
    book=get_object_or_404(Book,pk=pk)
    from .book_pdf import generate_print_package, generate_book_pdf
    if kind=='print': return FileResponse(generate_print_package(book),as_attachment=True,filename=f'book-{pk}-print.zip',content_type='application/zip')
    if kind=='pdf': return FileResponse(generate_book_pdf(book),as_attachment=True,filename=f'book-{pk}.pdf',content_type='application/pdf')
    raise Http404
