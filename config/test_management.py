from django.test import TestCase
from django.urls import reverse
from .models import CustomUser, Book, AISettings
class ManagementTests(TestCase):
    def setUp(self):
        self.admin=CustomUser.objects.create_superuser('owner',password='secure-test-2026')
        self.customer=CustomUser.objects.create_user('reader')
        self.book=Book.objects.create(user=self.customer,title='Story',author='Author')
        self.client.force_login(self.admin)
    def test_sections_and_denial(self):
        for section in ['books','users','pages','questions','dedications','covers','reviews','ai','groups']:
            self.assertEqual(self.client.get(reverse('management_list',args=[section])).status_code,200)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('management_home')).status_code,403)
        self.assertEqual(self.client.get(reverse('management_file',args=[self.book.pk,'print'])).status_code,403)
    def test_create_client(self):
        r=self.client.post(reverse('management_add',args=['users']),{'username':'newreader','is_active':'on','new_password':'Maple!River2030','repeat_password':'Maple!River2030'})
        self.assertEqual(r.status_code,302, r.context["form"].errors if r.context else "")
        u=CustomUser.objects.get(username='newreader')
        self.assertTrue(u.check_password('Maple!River2030'))
        self.assertFalse(u.is_staff)
    def test_approval_and_revision(self):
        url=reverse('management_edit',args=['books',self.book.pk])
        self.client.post(url,{'title':'Story','author':'Author','status':'printing'})
        self.book.refresh_from_db()
        self.assertEqual(self.book.status,'draft')
        self.assertEqual(self.client.post(url,{'title':'Changed','author':'Author','status':'draft'}).status_code,302)
        self.book.refresh_from_db()
        self.assertEqual(self.book.revision,1)
    def test_key_not_exposed(self):
        obj=AISettings.objects.create(gemini_api_key='private-test-key')
        url=reverse('management_edit',args=['ai',obj.pk])
        self.assertNotContains(self.client.get(url),'private-test-key')
        self.assertEqual(self.client.post(url,{'gemini_api_key':'','ai_question_count':5,'is_ai_enabled':'on'}).status_code,302)
        obj.refresh_from_db()
        self.assertEqual(obj.gemini_api_key,'private-test-key')



    def test_history_restore_and_conflict(self):
        from .models import BookPageAnswer
        page=BookPageAnswer.objects.create(book=self.book,user=self.customer,quiz='Chapter',answer='First')
        first=page.versions.first()
        page.answer='Second'
        page.save()
        self.assertEqual(page.versions.count(),2)
        self.client.force_login(self.customer)
        url=reverse('restore_text',args=[self.book.pk,first.pk])
        self.assertEqual(self.client.post(url,{'revision':0}).status_code,302)
        page.refresh_from_db()
        self.assertEqual(page.answer,'First')
        self.assertEqual(page.versions.count(),3)
        self.assertEqual(self.client.post(url,{'revision':0}).status_code,409)
        stranger=CustomUser.objects.create_user('stranger')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse('book_history',args=[self.book.pk])).status_code,404)
