
"""Shared, original cover artwork for SVG previews and print PDFs."""
import math
import random
from reportlab.graphics.shapes import Drawing, Rect, Circle, Ellipse, Line, Group, Path
from reportlab.lib.colors import HexColor

COVER_STYLES = {
    'classic': ('Классический', '#f5ecdf', '#594438', '#a58b65'),
    'dark': ('Тёмный', '#222327', '#eed9a6', '#a99364'),
    'modern': ('Минималистичный', '#faf8f3', '#343331', '#9c9387'),
    'rose': ('Сад роз', '#371723', '#fae5d8', '#c29185'),
    'sage': ('Серебряные ветви', '#354944', '#f5ead8', '#b5b49c'),
    'wine': ('Бордовый бархат', '#541f2b', '#f8e5ce', '#b58c69'),
    'forest': ('Зелёный мрамор', '#233b33', '#f3e7c8', '#a8b887'),
    'amber': ('Золотой вечер', '#56412d', '#f9e9c7', '#c5a36c'),
}
TEMPLATE_CHOICES = [(key, value[0]) for key, value in COVER_STYLES.items()]

def cover_art(style='classic'):
    _, background, _, accent = COVER_STYLES.get(style, COVER_STYLES['classic'])
    d = Drawing(420, 595)
    d.add(Rect(0, 0, 420, 595, fillColor=HexColor(background), strokeColor=None))
    rng = random.Random(style)
    if style in ('forest', 'amber'):
        # Original layered mineral contours; all paths remain vector in the PDF.
        colors = ['#385144','#4c6550','#778368','#a5aa83'] if style == 'forest' else ['#6e5336','#8c6941','#ae8954','#c3a875']
        for i in range(23):
            path=Path(fillColor=HexColor(colors[i%4]),strokeColor=None,fillOpacity=.25)
            y=-60+i*31
            path.moveTo(-20,y)
            path.curveTo(80,y+90,180,y-65,270,y+30)
            path.curveTo(340,y+95,400,y-40,440,y+25)
            path.lineTo(440,y+80)
            path.curveTo(300,y+15,200,y+150,90,y+65)
            path.lineTo(-20,y+110);path.closePath()
            d.add(path)
    if style in ('rose','sage'):
        leaf_colors=['#53644d','#7c8260'] if style=='rose' else ['#8e9c83','#c2c0a1']
        for side in [0,1]:
            for j in range(8):
                x=18+rng.random()*42 if side==0 else 360+rng.random()*42
                y=35+j*74
                branch=Group()
                branch.add(Line(0,0,17,59,strokeColor=HexColor(leaf_colors[0]),strokeWidth=.8))
                for k in range(4):
                    leaf=Group(Ellipse(0,0,5,15,fillColor=HexColor(leaf_colors[k%2]),strokeColor=None))
                    leaf.rotate((-40 if k%2 else 45));leaf.translate(4+k*3,k*13+10)
                    branch.add(leaf)
                branch.rotate(-20 if side==0 else 20)
                placed=Group(branch);placed.translate(x,y);d.add(placed)
        if style=='rose':
            for x,y,r in [(37,60,26),(373,92,32),(54,491,25),(369,525,24),(330,41,17),(83,35,19)]:
                flower=Group()
                for ring in range(3):
                    for petal in range(7):
                        angle=petal*math.tau/7+ring*.4
                        radius=r*(1-ring*.25)
                        flower.add(Ellipse(math.cos(angle)*radius*.4,math.sin(angle)*radius*.4,radius*.58,radius*.38,fillColor=HexColor(['#8e4354','#af6573','#d39b9a'][ring]),strokeColor=HexColor('#743747'),strokeWidth=.3))
                flower.add(Circle(0,0,3,fillColor=HexColor('#e7c2ac'),strokeColor=None));flower.translate(x,y);d.add(flower)
    # The quiet central panel is shared by the web preview and printed cover.
    if style in ('rose','sage','forest','amber'):
        d.add(Rect(84,105,252,384,fillColor=HexColor(background),fillOpacity=.9,strokeColor=None))
    inset=19 if style!='modern' else 24
    d.add(Rect(inset,inset,420-2*inset,595-2*inset,fillColor=None,strokeColor=HexColor(accent),strokeWidth=.75))
    if style!='modern':
        d.add(Rect(inset+5,inset+5,420-2*(inset+5),595-2*(inset+5),fillColor=None,strokeColor=HexColor(accent),strokeWidth=.3))
        for x in [inset+6,420-inset-6]:
            for y in [inset+6,595-inset-6]:
                d.add(Circle(x,y,2,fillColor=HexColor(accent),strokeColor=None))
    d.add(Line(184,145,236,145,strokeColor=HexColor(accent),strokeWidth=.7))
    for angle in range(0,180,30):
        a=math.radians(angle)
        d.add(Line(210-12*math.cos(a),475-12*math.sin(a),210+12*math.cos(a),475+12*math.sin(a),strokeColor=HexColor(accent),strokeWidth=.8))
    return d
