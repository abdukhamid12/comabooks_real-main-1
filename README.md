"# comabooks_real"


## Local setup (PowerShell)

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:DJANGO_SECRET_KEY = 'your-long-random-secret'
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py createsuperuser
.venv/Scripts/python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ and /admin/ for administration. Create your own administrator with `createsuperuser`; demo accounts and databases are not included.

`.env.example` documents available environment variables. Set them in your shell or hosting environment; the file is not loaded automatically. For deployment, set `DJANGO_DEBUG=false`, a unique `DJANGO_SECRET_KEY`, and your domain in `DJANGO_ALLOWED_HOSTS`. Telegram notifications require `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_CHAT_ID`.

See PRINTING.md for PDF production settings. Print packages are available only through the admin panel.
