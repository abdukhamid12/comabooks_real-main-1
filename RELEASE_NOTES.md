# Site management and book studio

- Staff login opens /manage/ using the existing Django model permissions.
- Studio supports autosave, exact PDF preview, photo positioning and chapter ordering.
- Text history is available from the book editor; versions accumulate after this update.
- Order cards include internal notes, due date, status and print downloads.

## Updating an installation

1. Back up the database and media together.
2. Install requirements: `pip install -r requirements.txt`.
3. Run `python manage.py migrate` (migrations 0010 and 0011).
4. Run `python manage.py collectstatic --noinput` where static collection is used.
5. Restart the application.

Set TELEGRAM_BOT_USERNAME, TELEGRAM_BOT_TOKEN and the existing bot settings in the process environment, then run `python manage.py run_bot` for notifications. AI correction requires a configured key. No demo database, books, passwords or uploaded media are included.

Validation: 22 Django tests covering PDF layout, studio access, version conflicts, history restoration and management forms.
