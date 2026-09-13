import io, json, tempfile
from unittest.mock import patch, Mock
from datetime import timedelta
from PIL import Image
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Book, BookCover, BookPageQuestion, BookPageAnswer, CustomUser, BookStatusEvent
from .notifications import connect_customer, deliver_status_events


class StudioTests(TestCase):
    def setUp(self):
        self.user=CustomUser.objects.create_user('writer',password='test-password')
        self.book=Book.objects.create(user=self.user,title='Книга',author='Автор')
        BookCover.objects.create(book=self.book,title='Книга',author_book='Автор')
        self.q=BookPageQuestion.objects.create(book=self.book,quiz='Первая глава')
        self.client.force_login(self.user)

    def save(self,**kwargs):
        return self.client.post(reverse('studio_save',args=[self.book.pk]),{'q':self.q.pk,'revision':0,'answer':'Мой рассказ','rotation':0,'image_fit':'contain',**kwargs})

    def test_autosave_and_conflict_preserve_text(self):
        self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.save(answer='Чужое изменение').status_code,409)
        self.assertEqual(self.book.pages.get().answer,'Мой рассказ')
        self.assertEqual(self.save(revision=1,answer='слово '*251).status_code,400)
        self.assertEqual(self.book.pages.get().answer,'Мой рассказ')

    def test_cross_owner_access_and_question_rejected(self):
        other=CustomUser.objects.create_user('other')
        b=Book.objects.create(user=other,title='Чужая',author='Другой')
        q=BookPageQuestion.objects.create(book=b,quiz='Чужая глава')
        self.assertEqual(self.save(q=q.pk).status_code,404)
        for name in ['edit_pages','book_review','book_preview','generate_pdf']:
            self.assertEqual(self.client.get(reverse(name,args=[b.pk])).status_code,404)

    def test_image_options_and_exact_preview(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image=Image.new('RGB',(300,900),'green');data=io.BytesIO();image.save(data,'PNG')
            response=self.save(image=SimpleUploadedFile('photo.png',data.getvalue(),'image/png'),rotation=90,image_fit='cover',focus_x=.2,focus_y=.8)
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.json()['warning'])
            page=self.book.pages.get();self.assertEqual(page.rotation,90)
            self.assertEqual(page.image_fit,'cover')
            url=reverse('book_preview',args=[self.book.pk])
            preview=self.client.get(url,{'q':self.q.pk})
            self.assertEqual(preview.status_code,200)
            self.assertEqual(preview['Content-Type'],'image/png')
            self.assertEqual(self.client.get(url,{'info':1}).json()['pages'],8)
            self.assertEqual(self.save(revision=1,remove_image='1').status_code,200)
            self.assertFalse(self.book.pages.get().image)

    def test_reorder_changes_pdf_page_order(self):
        q2=BookPageQuestion.objects.create(book=self.book,quiz='Вторая глава',position=1)
        self.save()
        self.save(q=q2.pk,revision=1,answer='Второй рассказ')
        url=reverse('studio_structure',args=[self.book.pk])
        r=self.client.post(url,json.dumps({'action':'reorder','revision':2,'order':[q2.pk,self.q.pk]}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(list(self.book.pages.order_by('position').values_list('quiz',flat=True)),['Вторая глава','Первая глава'])
        r=self.client.post(url,json.dumps({'action':'add','revision':3,'title':'Моя новая глава'}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertTrue(self.book.custom_questions.filter(quiz='Моя новая глава').exists())

    def test_approval_locks_and_reopen_invalidates(self):
        self.save()
        url=reverse('finish_book',args=[self.book.pk])
        self.assertEqual(self.client.post(url,{'revision':1}).status_code,400)
        self.assertEqual(self.client.post(url,{'confirm':'yes','revision':0}).status_code,409)
        self.assertEqual(self.client.post(url,{'confirm':'yes','revision':1}).status_code,302)
        self.book.refresh_from_db();self.assertIsNotNone(self.book.approved_at)
        self.assertEqual(self.save(revision=1).status_code,409)
        self.assertEqual(self.book.status_events.count(),1)
        self.client.post(reverse('book_reopen',args=[self.book.pk]))
        self.book.refresh_from_db();self.assertIsNone(self.book.approved_at)
        self.assertEqual(self.book.status,'draft')

    def test_staff_login_from_site(self):
        self.client.logout()
        admin=CustomUser.objects.create_user('manager',password='test-password',is_staff=True)
        r=self.client.post(reverse('login'),{'username':'manager','password':'test-password'})
        self.assertRedirects(r,reverse('management_home'),fetch_redirect_response=False)
        self.assertContains(self.client.get('/'),'Админка')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get('/'),'Админка')
        self.assertEqual(self.client.get('/admin/').status_code,302)

    def test_helpers_offer_suggestions_without_saving(self):
        url=reverse('studio_assistant',args=[self.book.pk])
        r=self.client.post(url,json.dumps({'q':self.q.pk,'mode':'start','text':''}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertFalse(self.book.pages.exists())
        self.assertIn('…',r.json()['text'])

    @override_settings(TELEGRAM_BOT_TOKEN='test-only-token')
    def test_telegram_opt_in_and_delivery(self):
        self.user.telegram_link_token='one-time';self.user.telegram_link_expires=timezone.now()+timedelta(minutes=5);self.user.save()
        self.assertFalse(connect_customer(12,'/start link_one-time','group'))
        self.assertTrue(connect_customer(12,'/start link_one-time','private'))
        self.assertFalse(connect_customer(99,'/start link_one-time','private'))
        event=BookStatusEvent.objects.create(book=self.book,status='printing')
        with patch('config.notifications.requests.post',return_value=Mock(json=lambda:{'ok':True})) as post:
            deliver_status_events();deliver_status_events();self.assertEqual(post.call_count,1)
        event.refresh_from_db();self.assertTrue(event.telegram_sent)
