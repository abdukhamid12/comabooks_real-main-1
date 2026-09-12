
"""Book layouts: reader PDF and separate, sequential production files.

No printer imposition or automatic spine estimate is performed.
"""
import io
import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, Flowable, KeepInFrame, Image as FlowImage
from .cover_designs import COVER_STYLES, cover_art


@dataclass(frozen=True)
class PrintSpec:
    width_mm: float = 148
    height_mm: float = 210
    inner_mm: float = 22
    outer_mm: float = 16
    top_mm: float = 18
    bottom_mm: float = 20
    bleed_mm: float = 3
    spine_mm: float | None = None

    def __post_init__(self):
        numbers=[self.width_mm,self.height_mm,self.inner_mm,self.outer_mm,self.top_mm,self.bottom_mm,self.bleed_mm]
        if not all(math.isfinite(n) for n in numbers):
            raise ValueError('Print dimensions must be finite.')
        if not 100 <= self.width_mm <= 300 or not 150 <= self.height_mm <= 420:
            raise ValueError('Unsupported trim size.')
        if min(self.inner_mm,self.outer_mm,self.top_mm,self.bottom_mm)<10 or not 0<=self.bleed_mm<=10:
            raise ValueError('Unsafe book margins or bleed.')
        if self.width_mm-self.inner_mm-self.outer_mm<65 or self.height_mm-self.top_mm-self.bottom_mm<95:
            raise ValueError('Text area is too small.')
        if self.spine_mm is not None and not 1<=self.spine_mm<=80:
            raise ValueError('Spine must be specified by the printer in millimetres.')

    @property
    def size(self):
        return self.width_mm*mm,self.height_mm*mm


def print_spec():
    return PrintSpec(**getattr(settings,'BOOK_PRINT',{}))


def register_fonts():
    folder=Path(settings.BASE_DIR)/'static/fonts'
    for name,file in [('BookSerif','Lora-Regular.ttf'),('BookSerifBold','Lora-Semibold.ttf'),('BookSans','arial.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name,str(folder/file)))


def safe_text(value):
    # ReportLab paragraphs accept markup: escape all customer input first.
    return escape(str(value or '')).replace('\r\n','\n').replace('\r','\n').replace('\n','<br/>')


def fitted_text(canvas,text,x,y,width,height,font='BookSerif',size=26,color='#392b30'):
    if not text:
        return
    for point_size in range(size,5,-1):
        style=ParagraphStyle('fit',fontName=font,fontSize=point_size,leading=point_size*1.22,
                             alignment=TA_CENTER,textColor=HexColor(color),splitLongWords=True)
        paragraph=Paragraph(safe_text(text),style)
        _,actual=paragraph.wrap(width,height)
        if actual<=height:
            paragraph.drawOn(canvas,x,y+(height-actual)/2)
            return
    raise ValueError('Cover text cannot fit safely. Shorten the title or subtitle.')


def style_key(book):
    cover=getattr(book,'cover_data',None)
    key=getattr(cover,'template','classic')
    return key if key in COVER_STYLES else 'classic'


def paint_cover(canvas,book,spec,back=False):
    w,h=spec.size
    key=style_key(book)
    _,bg,ink,accent=COVER_STYLES[key]
    canvas.saveState()
    canvas.scale(w/420,h/595)
    renderPDF.draw(cover_art(key),canvas,0,0)
    canvas.restoreState()
    if back:
        fitted_text(canvas,'Каждая история заслуживает своей книги.',w*.22,h*.40,w*.56,h*.18,size=20,color=ink)
        fitted_text(canvas,'COMABOOKS',w*.25,h*.10,w*.5,h*.04,font='BookSans',size=8,color=ink)
        return
    fitted_text(canvas,'ЛИЧНАЯ ИСТОРИЯ',w*.24,h*.85,w*.52,h*.04,font='BookSans',size=7,color=ink)
    fitted_text(canvas,book.title,w*.22,h*.46,w*.56,h*.27,size=30,color=ink)
    fitted_text(canvas,book.subtitle,w*.23,h*.30,w*.54,h*.13,size=12,color=ink)
    fitted_text(canvas,book.author,w*.22,h*.14,w*.56,h*.085,size=11,color=ink)
    dedication=getattr(book,'dedication',None)
    fitted_text(canvas,dedication.name if dedication else '',w*.22,h*.075,w*.56,h*.055,font='BookSans',size=7,color=ink)


def cover_pdf(book,spec,back=False,bleed=True):
    register_fonts()
    w,h=spec.size;b=spec.bleed_mm*mm if bleed else 0
    result=io.BytesIO()
    c=Canvas(result,pagesize=(w+2*b,h+2*b),pageCompression=1)
    c.setTitle(str(book.title));c.setAuthor(str(book.author))
    c.setFillColor(HexColor(COVER_STYLES[style_key(book)][1]))
    c.rect(0,0,w+2*b,h+2*b,fill=1,stroke=0)
    c.translate(b,b);paint_cover(c,book,spec,back);c.showPage();c.save()
    reader=PdfReader(result);writer=PdfWriter()
    from pypdf.generic import RectangleObject
    page=reader.pages[0]
    page.trimbox=RectangleObject([b,b,w+b,h+b])
    page.bleedbox=RectangleObject([0,0,w+2*b,h+2*b])
    writer.add_page(page)
    dest=io.BytesIO();writer.write(dest);dest.seek(0);return dest


def image_flowable(field,width,height,warnings,label):
    try:
        with field.open('rb') as source:
            with Image.open(source) as original:
                image=ImageOps.exif_transpose(original).convert('RGBA')
                white=Image.new('RGBA',image.size,'white');white.alpha_composite(image)
                image=white.convert('RGB')
                scale=min(width/image.width,height/image.height)
                draw_w,draw_h=image.width*scale,image.height*scale
                dpi=min(image.width/(draw_w/72),image.height/(draw_h/72))
                if dpi<200:
                    warnings.append(f'{label}: разрешение фотографии около {dpi:.0f} dpi; рекомендуется 300 dpi.')
                data=io.BytesIO();image.save(data,format='JPEG',quality=95);data.seek(0)
                picture=FlowImage(data,width=draw_w,height=draw_h)
                picture.hAlign='CENTER'
                return picture
    except (OSError,ValueError) as exc:
        warnings.append(f'{label}: фотография недоступна ({type(exc).__name__}); проверьте исходный файл.')
        return None


def interior_pdf(book,spec,warnings=None):
    register_fonts()
    if warnings is None:warnings=[]
    w,h=spec.size
    inner,outer,top,bottom=[v*mm for v in (spec.inner_mm,spec.outer_mm,spec.top_mm,spec.bottom_mm)]
    content_w=w-inner-outer;content_h=h-top-bottom
    result=io.BytesIO()
    doc=BaseDocTemplate(result,pagesize=(w,h),leftMargin=inner,rightMargin=outer,topMargin=top,bottomMargin=bottom,
                        title=str(book.title),author=str(book.author),pageCompression=1)
    def furniture(c,d):
        d.handle_nextPageTemplate('Even' if d.page % 2 else 'Odd')
        if d.page<=2:return
        c.saveState()
        left=inner if d.page%2 else outer
        c.setStrokeColor(HexColor('#d5c7b6'));c.setLineWidth(.4)
        c.line(left,h-12*mm,left+content_w,h-12*mm)
        c.setFont('BookSans',6.5);c.setFillColor(HexColor('#756958'))
        header=str(book.title)
        while pdfmetrics.stringWidth(header,'BookSans',6.5)>content_w and header:
            header=header[:-2]+'…' if not header.endswith('…') else header[:-2]+'…'
        c.drawString(left,h-10*mm,header)
        c.setFont('BookSerif',9)
        x=w-outer if d.page%2 else outer
        if d.page%2:c.drawRightString(x,10*mm,str(d.page))
        else:c.drawString(x,10*mm,str(d.page))
        c.restoreState()
    odd=Frame(inner,bottom,content_w,content_h,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    even=Frame(outer,bottom,content_w,content_h,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='Odd',frames=[odd],onPage=furniture),
                          PageTemplate(id='Even',frames=[even],onPage=furniture)])
    body=ParagraphStyle('body',fontName='BookSerif',fontSize=11,leading=17,textColor=HexColor('#332c28'),
                        spaceAfter=10,alignment=TA_LEFT,allowWidows=0,allowOrphans=0,splitLongWords=True)
    question=ParagraphStyle('question',parent=body,fontName='BookSerifBold',fontSize=19,leading=25,spaceAfter=20,keepWithNext=True)
    label=ParagraphStyle('label',fontName='BookSans',fontSize=7,leading=11,textColor=HexColor('#877052'),spaceAfter=15,keepWithNext=True)
    class MemoryPage(Flowable):
        """One indivisible page; preserve photo proportions and all answer text."""
        def __init__(self, blocks, photo):
            super().__init__()
            self.width = content_w
            self.height = content_h - 1
            self.blocks = blocks
            self.photo = photo

        def draw(self):
            gap = 12 if self.photo else 0
            # Reserve a useful photo area before shrinking exceptionally long text.
            reserved = min(self.height * .24, self.photo.drawHeight) if self.photo else 0
            text = KeepInFrame(self.width, self.height - reserved - gap,
                               self.blocks, mode='shrink', hAlign='LEFT', vAlign='TOP')
            _, text_h = text.wrapOn(self.canv, self.width, self.height - reserved - gap)
            text.drawOn(self.canv, 0, self.height - text_h)
            if self.photo:
                available = max(1, self.height - text_h - gap)
                scale = min(1, available / self.photo.drawHeight)
                photo_w = self.photo.drawWidth * scale
                photo_h = self.photo.drawHeight * scale
                self.photo.drawWidth = photo_w
                self.photo.drawHeight = photo_h
                self.photo.drawOn(self.canv, (self.width-photo_w)/2,
                                  self.height-text_h-gap-photo_h)
    class FrontMatter(Flowable):
        def __init__(self, dedication=False):
            super().__init__()
            self.width=content_w
            self.height=content_h-1
            self.dedication=dedication

        def draw(self):
            c=self.canv; width=self.width; height=self.height
            if self.dedication:
                recipient=getattr(book,'dedication',None)
                fitted_text(c,'ПОСВЯЩАЕТСЯ',0,height*.69,width,20,font='BookSans',size=7,color='#877052')
                fitted_text(c,recipient.name if recipient else 'Тем, кто делает жизнь теплее',0,height*.42,width,height*.22,size=18)
                fitted_text(c,'Эти страницы хранят то, что хочется помнить.',0,height*.29,width,height*.08,size=10)
            else:
                fitted_text(c,'ЛИЧНАЯ ИСТОРИЯ',0,height*.85,width,20,font='BookSans',size=7,color='#877052')
                fitted_text(c,book.title,0,height*.43,width,height*.36,size=26)
                fitted_text(c,book.subtitle,0,height*.22,width,height*.16,size=12)
                fitted_text(c,book.author,0,height*.05,width,height*.12,size=12)

    story=[FrontMatter(),PageBreak(),FrontMatter(dedication=True),PageBreak()]
    pages=list(book.pages.all().order_by('pk'))
    if not pages:
        story.extend([Paragraph('История начинается здесь',question),Paragraph('В этой книге пока нет сохранённых ответов.',body)])
    for index,page in enumerate(pages,1):
        if index>1:story.append(PageBreak())
        blocks = [Paragraph(f'ВОСПОМИНАНИЕ {index:02d}',label),
                  Paragraph(safe_text(page.quiz),question)]
        if page.answer:
            for paragraph in str(page.answer).replace('\r\n','\n').split('\n\n'):
                if paragraph.strip():blocks.append(Paragraph(safe_text(paragraph),body))
        photo = None
        if page.image:
            photo=image_flowable(page.image,content_w,content_h*.48,warnings,f'Воспоминание {index}')
        story.append(MemoryPage(blocks, photo))
    doc.build(story)
    reader=PdfReader(result);writer=PdfWriter()
    for page in reader.pages:writer.add_page(page)
    if len(writer.pages)%2:writer.add_blank_page(width=w,height=h)
    writer.add_metadata({'/Title':str(book.title),'/Author':str(book.author),'/Subject':'Sequential book interior; duplex long-edge; no imposition'})
    dest=io.BytesIO();writer.write(dest);dest.seek(0);return dest


def generate_book_pdf(book):
    spec=print_spec()
    interior=interior_pdf(book,spec)
    writer=PdfWriter();w,h=spec.size
    writer.append(PdfReader(cover_pdf(book,spec,bleed=False)))
    writer.add_blank_page(width=w,height=h)
    writer.append(PdfReader(interior))
    writer.add_blank_page(width=w,height=h)
    writer.append(PdfReader(cover_pdf(book,spec,back=True,bleed=False)))
    writer.add_metadata({'/Title':str(book.title),'/Author':str(book.author)})
    result=io.BytesIO();writer.write(result);result.seek(0);return result


def spread_pdf(book,spec):
    """Flat soft-cover spread only; hardback cases require printer templates."""
    register_fonts()
    w,h=spec.size;b=spec.bleed_mm*mm;s=spec.spine_mm*mm
    result=io.BytesIO();c=Canvas(result,pagesize=(2*w+s+2*b,h+2*b))
    _,bg,ink,_=COVER_STYLES[style_key(book)]
    c.setFillColor(HexColor(bg));c.rect(0,0,2*w+s+2*b,h+2*b,fill=1,stroke=0)
    c.saveState();c.translate(b,b);paint_cover(c,book,spec,back=True);c.restoreState()
    c.saveState();c.translate(b+w+s,b);paint_cover(c,book,spec);c.restoreState()
    if spec.spine_mm>=8:
        c.saveState();c.translate(b+w+s/2,b+h/2);c.rotate(90)
        fitted_text(c,book.title,-h*.32,-s*.3,h*.64,s*.6,size=10,color=ink);c.restoreState()
    c.showPage();c.save()
    reader=PdfReader(result);writer=PdfWriter()
    from pypdf.generic import RectangleObject
    page=reader.pages[0];page.trimbox=RectangleObject([b,b,2*w+s+b,h+b]);writer.add_page(page)
    dest=io.BytesIO();writer.write(dest);dest.seek(0);return dest


def generate_print_package(book):
    spec=print_spec();warnings=[]
    interior=interior_pdf(book,spec,warnings)
    count=len(PdfReader(interior).pages)
    text=f"""COMABOOKS / КОМПЛЕКТ ДЛЯ ТИПОГРАФИИ
Книга: {book.title}
Автор: {book.author}
Формат после обрезки: {spec.width_mm} × {spec.height_mm} мм.
Внутренний блок: {count} страниц, включая титул, посвящение и технологические пустые страницы.
Поля: внутреннее {spec.inner_mm} мм, внешнее {spec.outer_mm} мм, верхнее {spec.top_mm} мм, нижнее {spec.bottom_mm} мм.
Вылеты обложек: {spec.bleed_mm} мм с каждой стороны. TrimBox задаёт линию обрезки.

01-interior.pdf: только внутренние страницы, по одной на лист PDF.
Печать в масштабе 100%, без «вписать в страницу», двусторонняя, переворот по длинной стороне.
Нечётные страницы справа, чётные слева. Поля зеркальные.
Пустые страницы намеренные; не удалять без проверки сторон разворота.
Спуск полос и раскладку тетрадей выполняет типография под своё оборудование.

02-cover-front.pdf / 03-cover-back.pdf: отдельные плоские обложки, без декоративных теней.
Обложки не включены во внутренний блок. Не печатать читательский PDF как внутренний блок.
"""
    if spec.spine_mm is None:
        text+="\nШирина корешка не задана. Перед сборкой запросите у типографии бумагу, толщину блока и тип переплёта. Полный разворот обложки не сформирован.\n"
    else:
        text+=f"\n04-cover-spread.pdf: задняя обложка слева, корешок {spec.spine_mm} мм по центру, лицевая справа. Это плоский макет мягкой обложки. Для твёрдого переплёта нужны шаблон типографии, расставы и загибы.\n"
    text+="\nШрифты встроены. Цвет RGB; это не сертифицированный PDF/X. Цветовой профиль, бумагу, переплёт и пробный отпечаток согласовать с типографией. Внутренние фотографии не выходят на обрез.\n"
    text+="\nПРОВЕРКА ФОТОГРАФИЙ\n"+ ('\n'.join(warnings) if warnings else 'Ошибок чтения и фотографий ниже 200 dpi не обнаружено.')
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('01-interior.pdf',interior.getvalue())
        archive.writestr('02-cover-front.pdf',cover_pdf(book,spec).getvalue())
        archive.writestr('03-cover-back.pdf',cover_pdf(book,spec,back=True).getvalue())
        if spec.spine_mm is not None:archive.writestr('04-cover-spread.pdf',spread_pdf(book,spec).getvalue())
        archive.writestr('READ-ME-print.txt',text.encode('utf-8-sig'))
        archive.writestr('print-spec.json',json.dumps({**spec.__dict__,'interior_pages':count,'warnings':warnings,'imposed':False,'color_space':'RGB'},ensure_ascii=False,indent=2))
    result.seek(0);return result

