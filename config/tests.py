
import io
import json
import tempfile
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from PIL import Image
from pypdf import PdfReader

from .book_pdf import PrintSpec, cover_pdf, generate_book_pdf, generate_print_package, interior_pdf
from .cover_designs import TEMPLATE_CHOICES
from .forms import BookForm
from .models import Book, BookCover, BookPageAnswer, CustomUser


class BookPrintTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='author')
        self.book = Book.objects.create(user=self.user, title='Наша история', author='Автор', subtitle='Тёплые воспоминания')
        self.cover = BookCover.objects.create(book=self.book, title=self.book.title, author_book=self.book.author)
        self.page = BookPageAnswer.objects.create(book=self.book, user=self.user, quiz='Как всё началось?', answer='Текст <b>не разметка</b> & воспоминания.')

    def test_all_cover_choices_and_trim_boxes(self):
        self.assertEqual(list(BookForm().fields['template'].choices), TEMPLATE_CHOICES)
        for key, _ in TEMPLATE_CHOICES:
            self.cover.template = key
            pdf = PdfReader(cover_pdf(self.book, PrintSpec()))
            self.assertEqual(len(pdf.pages), 1)
            self.assertAlmostEqual(float(pdf.pages[0].trimbox.width) / 72 * 25.4, 148, places=2)
            self.assertAlmostEqual(float(pdf.pages[0].trimbox.left) / 72 * 25.4, 3, places=2)

    def test_long_front_matter_stays_on_two_pages(self):
        self.book.title = 'Очень длинное название ' * 11
        self.book.author = 'Автор ' * 40
        self.book.subtitle = 'Подзаголовок ' * 20
        pdf = PdfReader(interior_pdf(self.book, PrintSpec()))
        self.assertIn('Очень длинное', pdf.pages[0].extract_text())
        self.assertIn('ПОСВЯЩАЕТСЯ', pdf.pages[1].extract_text())
        self.assertIn('Как всё началось?', pdf.pages[2].extract_text())
        self.assertEqual(len(pdf.pages) % 2, 0)
        self.assertIn('<b>не разметка</b> &', pdf.pages[2].extract_text())

    def test_mirrored_gutter_and_page_size(self):
        BookPageAnswer.objects.create(book=self.book, user=self.user, quiz='Второй вопрос', answer='Второй ответ.')
        pdf = PdfReader(interior_pdf(self.book, PrintSpec()))
        positions = []
        for page in pdf.pages[2:4]:
            found=[]
            def visitor(text,cm,tm,font,size):
                if 'ВОСПОМИНАНИЕ' in text:
                    found.append(cm[4]+tm[4])
            page.extract_text(visitor_text=visitor)
            positions.append(found[0])
        self.assertAlmostEqual(positions[0]/72*25.4,22,places=1)
        self.assertAlmostEqual(positions[1]/72*25.4,16,places=1)

    def test_photo_fit_and_low_resolution_report(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            image = Image.new('RGB', (80, 600), '#678577')
            data = io.BytesIO(); image.save(data, 'PNG')
            self.page.image.save('portrait.png', ContentFile(data.getvalue()))
            self.page.answer='слово ' * 250
            self.page.save()
            package=zipfile.ZipFile(generate_print_package(self.book))
            info=json.loads(package.read('print-spec.json'))
            self.assertTrue(info['warnings'])
            self.assertEqual(info['interior_pages']%2,0)
            self.assertNotIn('04-cover-spread.pdf',package.namelist())
            self.assertIn('01-interior.pdf',package.namelist())

    @override_settings(BOOK_PRINT={'spine_mm':12})
    def test_optional_spread_dimensions(self):
        package=zipfile.ZipFile(generate_print_package(self.book))
        spread=PdfReader(io.BytesIO(package.read('04-cover-spread.pdf')))
        self.assertAlmostEqual(float(spread.pages[0].trimbox.width)/72*25.4,308,places=2)

    def test_print_package_is_admin_only(self):
        admin_url = f'/admin/config/book/{self.book.pk}/print/'
        old_url = f'/book/{self.book.pk}/print/'
        self.assertEqual(self.client.get(old_url).status_code, 404)
        self.assertEqual(self.client.get(admin_url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(old_url).status_code, 404)
        self.assertEqual(self.client.get(admin_url).status_code, 302)
        self.assertNotContains(self.client.get('/dashboard/'), 'Комплект для типографии')
        reader = self.client.get(f'/book/{self.book.pk}/generate_pdf/')
        self.assertEqual(reader.status_code, 200)
        reader.close()
        outsider=CustomUser.objects.create_user(username='outsider',is_staff=True)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(admin_url).status_code, 403)
        administrator = CustomUser.objects.create_superuser(username='administrator')
        self.client.force_login(administrator)
        response = self.client.get(admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        response.close()
        self.assertContains(self.client.get(f'/admin/config/book/{self.book.pk}/change/'), 'Скачать комплект для печати')
        self.assertEqual(self.client.get(old_url).status_code, 404)

    def test_reader_contains_cover_and_full_answer(self):
        pdf=PdfReader(generate_book_pdf(self.book))
        self.assertIn('Наша история',pdf.pages[0].extract_text())
        self.assertTrue(any('не разметка' in p.extract_text() for p in pdf.pages))
        self.assertEqual(len(pdf.pages)%2,0)

    def test_invalid_print_dimensions_rejected(self):
        for options in [{'bleed_mm':-1},{'inner_mm':1},{'spine_mm':0},{'width_mm':float('nan')}]:
            with self.assertRaises(ValueError):
                PrintSpec(**options)
