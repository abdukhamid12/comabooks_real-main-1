
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from reportlab.graphics import renderSVG
from config.cover_designs import COVER_STYLES, cover_art


class Command(BaseCommand):
    help = "Regenerate SVG cover previews from the same artwork used in PDFs."

    def handle(self, *args, **options):
        folder = Path(settings.BASE_DIR) / 'static' / 'covers'
        folder.mkdir(parents=True, exist_ok=True)
        for style in COVER_STYLES:
            renderSVG.drawToFile(cover_art(style), str(folder / f'{style}.svg'))
        self.stdout.write(self.style.SUCCESS(f'Generated {len(COVER_STYLES)} cover previews.'))
