# Periodic Table Trainer

یک اپلیکیشن دسکتاپ آفلاین با Python 3.11+ و Kivy برای تمرین نمادها، اعداد اتمی، نام عناصر و دسته‌بندی‌ها. داده‌ها داخل `elements_data.py` هستند و برنامه برای اجرا به اینترنت نیاز ندارد.

## اجرا در ویندوز

1. Python 3.11 یا جدیدتر را نصب کنید.
2. در ترمینال، از پوشه‌ی پروژه Kivy را نصب کنید:

   ```bash
   python -m pip install kivy
   ```

3. برنامه را اجرا کنید:

   ```bash
   python main.py
   ```

در ابتدای بازی، نوع سؤال‌های دلخواه را انتخاب کنید. سؤال‌های فعال در یک جریان تصادفی ترکیب می‌شوند؛ هر عنصر در هر بازی فقط یک‌بار سؤال اصلی خواهد بود. دسته‌بندی‌ها در بازی به‌شکل انتخاب چندگزینه‌ای پرسیده می‌شوند.

## فایل‌ها

- `main.py` — رابط کاربری Kivy، جریان بازی، امتیازدهی و نتایج
- `elements_data.py` — دیتاست آفلاین عناصر
- `README.md` — راهنمای اجرا

دیتاست legacy شامل عناصر ۱ تا ۵۴ به‌علاوه‌ی Po، Rn و Og است؛ یعنی ۵۷ عنصر یکتا. فایل‌های standalone فعلی در `index.html` و نسخه‌های مستقل وب، ویندوز و Android قرار دارند.

## ساخت نسخه‌های standalone

### ویندوز (EXE)

در PowerShell/Command Prompt ویندوز، از ریشهٔ پروژه اجرا کنید:

```powershell
python -m pip install --upgrade pip "pywebview[winforms]" pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "PeriodicTableTrainer" --icon=app.ico --add-data "windows_index.html;." --collect-all webview --hidden-import=clr windows_app.py
```

فایل خروجی `dist/PeriodicTableTrainer.exe` است. برای به‌روزرسانی خودکار، برنامه را در پوشه‌ای قرار دهید که کاربر اجازهٔ نوشتن در آن را دارد؛ پوشه‌های محافظت‌شده مثل `Program Files` ممکن است به دسترسی Administrator نیاز داشته باشند.

### Android (APK)

Buildozer به Linux/WSL و Android SDK/NDK نیاز دارد. ساخت CI با Python 3.10، NDK 25b و معماری `arm64-v8a` انجام می‌شود. حداقل Android API روی 24 تنظیم شده، چون کد `remote_debugging` از `preadv`/`pwritev` استفاده می‌کند که در API 23 موجود نیست. در ریشهٔ پروژه:

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install "Cython==0.29.36" buildozer
cp mobile_app.py android_project/main.py
cp mobile_index.html android_project/mobile_index.html
cp update_config.py android_project/update_config.py
buildozer -v android debug
```

APK آزمایشی در پوشهٔ `bin/` ساخته می‌شود. این دستور آن را با کلید debug محلی امضا می‌کند؛ چنین APKای فقط برای آزمون مناسب است و با نسخهٔ release که با کلید CI امضا می‌شود، به‌روزرسانی درجا نخواهد داشت.

### ساخت Release امضاشده با GitHub Actions

Workflow در `.github/workflows/build.yml` ویندوز، فایل HTML جداگانهٔ ویندوز و Android را می‌سازد/آماده می‌کند و APK را با کلید ثابت release امضا می‌کند. پیش از اجرای آن، یک بار یک کلید خصوصی بسازید و آن را محرمانه نگه دارید:

```bash
keytool -genkeypair -v -keystore periodictrainer-release.jks -alias periodictrainer -keyalg RSA -keysize 2048 -validity 10000
base64 -w 0 periodictrainer-release.jks > periodictrainer-release.base64
```

مقدار base64 و رمزها را در GitHub repository secrets با نام‌های `ANDROID_KEYSTORE_BASE64`، `ANDROID_KEYSTORE_PASSWORD`، `ANDROID_KEY_ALIAS` و `ANDROID_KEY_PASSWORD` ثبت کنید. **فایل keystore و رمزها را commit نکنید و از کلید نسخه‌های قبلی پشتیبان امن بگیرید**؛ از دست‌دادن/تعویض کلید یا تغییر شناسهٔ بسته مانع نصب به‌روزرسانی روی نسخهٔ موجود می‌شود. شناسهٔ فعلی بسته `org.example.periodictrainer` است. Workflow با هر push یک APK، EXE و asset جداگانهٔ `windows_index.html` می‌سازد و Release ایجاد می‌کند.

## راه‌اندازی به‌روزرسانی خودکار

1. نشانی `VERSION_URL` اکنون به manifest همین مخزن تنظیم شده است: `https://raw.githubusercontent.com/AmirGFno/PeriodicTableTrainer/main/version.json`. اگر میزبانی دیگری انتخاب کردید، مقدار را در `update_config.py` تغییر دهید (در ویندوز می‌توان `PTT_VERSION_URL` را نیز تنظیم کرد). APK Android باید با تنظیم جدید دوباره build شود.
2. فایل `version.json` را روی همان میزبانی HTTPS منتشر کنید. قالب آن:

   ```json
   {
     "latest_version": "1.0.0",
     "notes": "یادداشت انتشار",
     "windows_url": "https://github.com/AmirGFno/PeriodicTableTrainer/releases/latest/download/PeriodicTableTrainer.exe",
     "windows_html_url": "https://raw.githubusercontent.com/AmirGFno/PeriodicTableTrainer/main/windows_index.html",
     "android_url": "https://github.com/AmirGFno/PeriodicTableTrainer/releases/latest/download/app-debug.apk"
   }
   ```

   Windows updater از `windows_html_url` استفاده می‌کند؛ `windows_url` صرفاً legacy است و در به‌روزرسانی Windows مصرف نمی‌شود. نشانی فعلی HTML از شاخهٔ `main` همین مخزن خوانده می‌شود؛ نشانی APK به آخرین asset انتشار GitHub اشاره می‌کند. برای دریافت APK، workflow باید با موفقیت تمام شده و Release در دسترس باشد؛ برای build خودکار Android نیز GitHub Secrets امضای release را تنظیم کنید.
3. برای انتشار نسخهٔ بعدی، نسخه را در `update_config.py`، `buildozer.spec` و ثابت `CURRENT_APP_VERSION` در `windows_index.html` و `mobile_index.html` افزایش دهید؛ سپس `latest_version` و یادداشت‌ها را در manifest به‌روز کنید. نسخهٔ نمایشی/نام‌گذاری‌شده را نیز در `buildozer.spec` افزایش دهید؛ Workflow کد عددی Android را به صورت افزایشی تعیین می‌کند.
4. Windows فقط رابط را از `windows_html_url` کنار برنامه با نام `new_index.html` دریافت می‌کند. `update.bat` پس از بستن برنامه، HTML قبلی را به `windows_index_old.html` می‌چرخاند، فایل جدید را جایگزین و EXE را دوباره اجرا می‌کند؛ خود EXE دانلود یا جایگزین نمی‌شود. فایل بیرونی `windows_index.html` در پوشهٔ EXE بر نسخهٔ داخلی اولویت دارد و در نبود آن، برنامه از نسخهٔ داخل EXE استفاده می‌کند. Android فایل APK را در فضای خصوصی برنامه دانلود و با `FileProvider` به نصب‌کنندهٔ سیستم تحویل می‌دهد؛ کاربر باید نصب را تأیید کند و در اولین نصب از این مسیر ممکن است اجازهٔ **Install from Unknown Sources** لازم باشد.

برای حفظ اطلاعات Android هنگام نصب روی نسخهٔ قبلی، `package ID` و کلید امضای release باید ثابت بمانند. فایل‌های رکورد جداگانه در فضای خصوصی برنامه نگهداری می‌شوند؛ نصب APK با امضای متفاوت، نصب درجا را مسدود می‌کند.

