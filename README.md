# Periodic Table Trainer

پروژه شامل سه نسخهٔ فعال است: وب (`web_index.html`)، ویندوز (`windows_app.py` و `windows_index.html`) و اندروید با Capacitor (`mobile_index.html`). نسخهٔ وب عمداً آمار دائمی، مدال‌ها و ذخیره‌سازی مرورگر ندارد؛ نتیجهٔ هر بازی فقط تا پایان همان نشست نمایش داده می‌شود. نسخه‌های ویندوز و موبایل قابلیت‌های ذخیره‌سازی و پشتیبان‌گیری مخصوص خود را دارند.

## فایل‌های فعال

- `web_index.html` — نسخهٔ مستقل وب؛ بدون آمار و مدال‌های دائمی.
- `windows_app.py`, `windows_index.html`, `update_config.py` — برنامه و رابط ویندوز و تنظیمات به‌روزرسانی HTML.
- `mobile_index.html`, `www/index.html` — رابط Capacitor؛ در انتشار اندروید، `www/index.html` از `mobile_index.html` ساخته/همگام می‌شود.
- `capacitor.config.json`, `package.json`, `package-lock.json` — پیکربندی و وابستگی‌های Capacitor.
- `capacitor/native/PeriodicTrainerNativePlugin.java`, `capacitor/scripts/prepare_android.py` — پل بومی اندروید برای پشتیبان‌گیری، بررسی نسخه، نصب به‌روزرسانی و ساخت آیکون‌های لانچر.
- `capacitor/android_icon_background.png`, `capacitor/android_icon_foreground.png` — لایهٔ گرادیان تمام‌صفحه و نشان شفافِ آیکون اندروید.
- `.github/workflows/build.yml`, `installer/PeriodicTableTrainer.iss` — ساخت نصب‌کنندهٔ ویندوز (بدون امضای کد) و APK/AAB اندروید با Capacitor (بدون امضا)؛ نصب‌کننده در Program Files نصب می‌کند و میان‌بر دسکتاپ می‌سازد. Pillow برای تولید منابع آیکون APK در مرحلهٔ build نصب می‌شود.
- `version.json` — manifest نسخه و نشانی‌های به‌روزرسانی.
- `windows_logo.png` — لوگوی دایره‌ای گرادیانی با بیرون شفاف؛ `app.ico` نسخهٔ ۲۵۶×۲۵۶ آن برای EXE ویندوز است.
- `app_logo.png` — پیش‌نمایش لوگوی موبایل با همان نشان و گرادیانِ کشیده‌شده تا لبه‌های تصویر.
- `convert_fonts.py`, `font_sources/` — منابع و ابزار بازتولید فونت‌های تعبیه‌شده.

## قاعدهٔ همگام‌سازی نسخه‌ها

`index.html` **مبنای همهٔ نسخه‌ها** است: هر تغییر رفتاری یا ظاهری اول در `index.html` اعمال و بررسی می‌شود، سپس همان تغییر
عیناً به `web_index.html` (وب)، `windows_index.html` (ویندوز) و `mobile_index.html` (اندروید، و کپی آن `www/index.html`) منتقل
می‌شود. تفاوت این فایل‌ها فقط در پل‌های مخصوص هر پلتفرم است:

- `index.html` — رابط و منطق پایه؛ بدون پل بومی و بدون شمارهٔ نسخه در فایل.
- `web_index.html` — همان رابط پایه (بدون ذخیره‌سازی دائمی آمار/مدال).
- `windows_index.html` — افزودن `CURRENT_APP_VERSION` و پل `pywebview` برای پشتیبان‌گیری و به‌روزرسانی.
- `mobile_index.html` / `www/index.html` — افزودن `CURRENT_APP_VERSION`، پل `Capacitor` و چیدمان اختصاصی موبایل.

پس از هر تغییر، چهار نسخه باید در این رفتارها یکسان باشند: تایمر (۳۰ ثانیه برای آرایش الکترونی، ۱۵ ثانیه برای بقیه)،
پیام خنثی در پایان بازی بدون پاسخ، نمایش نماد و نام در مود دسته‌بندی پیش از پاسخ و مشخصات کامل پس از آن، و خوانا بودن
کلیدهای توان در کیبورد آرایش الکترونی. یک بررسی سریع:

```bash
for f in index.html web_index.html windows_index.html mobile_index.html; do
  grep -c 'timerDuration=currentMode==="electron_config"?30:15' "$f"
  grep -c 'if(answered===0)root.innerHTML' "$f"
done
```

## چیدمان موبایل (افقی و تبلت)

`mobile_index.html` سه ناحیهٔ واکنش‌گرا دارد:

- `max-width:720px` — گوشی در حالت عمودی (چیدمان تک‌ستونی و کیبورد ۵ ستونه).
- `(orientation:landscape) and (max-height:600px)` — گوشی در حالت افقی: بازی دو ستونه می‌شود (کارت عنصر کنار کیبورد)،
  نوار بالایی غیرچسبان و فشرده می‌شود، کلیدها کوچک‌تر و کیبورد با ارتفاع محدود و اسکرول داخلی می‌شود تا همه‌چیز بدون
  اسکرول صفحه در دسترس باشد؛ برای ارتفاع کمتر از ۴۰۰px فشرده‌سازی بیشتری اعمال می‌شود.
- `(min-width:721px) and (max-width:1100px) and (min-height:601px)` — تبلت: کارت و پنل بزرگ‌تر، کلیدهای لمسی ≥۴۸px،
  کیبورد ۶–۸ ستونه و جدول تناوبی بلندتر.

قید `min-height:601px` عمدی است تا گوشی‌های افقی (ارتفاع کم) وارد قواعد تبلت نشوند و چیدمان فشرده خراب نشود.

## ساخت نسخهٔ ویندوز

Workflow ویندوز، برنامه را به‌شکل onedir می‌سازد و با Inno Setup یک نصب‌کننده تولید می‌کند. فایل `PeriodicTableTrainer-windows.zip` شامل `PeriodicTableTrainer-Setup-<version>.exe` و راهنمای نصب است. **در این پروژه امضای کد (Authenticode) انجام نمی‌شود**؛ نه گواهی PFX لازم است و نه هیچ secret‌ای برای امضا. در نتیجه Windows SmartScreen ممکن است در اجرای اول هشدار «ناشر ناشناس» نشان دهد؛ این طبیعی است و build را متوقف نمی‌کند. نصب‌کننده به‌طور پیش‌فرض برنامه را در `Program Files\PeriodicTableTrainer` نصب می‌کند، میان‌بر دسکتاپ می‌سازد و میان‌بر منوی Start را نیز اضافه می‌کند. برای نصب، کاربر باید پنجرهٔ مجوز Windows را تأیید کند.

آپدیتر ویندوز، رابط جدید را در AppData دانلود می‌کند و جابه‌جایی را به یک اسکریپت PowerShell می‌سپارد (فایل batch قبلی در پروسهٔ بدون کنسول نمی‌توانست `timeout` بزند و جابه‌جایی لغو می‌شد). نتیجهٔ هر تلاش در `%LOCALAPPDATA%\PeriodicTableTrainer\update.log` ثبت می‌شود؛ اگر پوستهٔ EXE قدیمی‌تر از نسخهٔ منتشرشده باشد، پنجرهٔ به‌روزرسانی هشدار می‌دهد و دکمهٔ دریافت نصب‌کنندهٔ جدید را نشان می‌دهد، چون به‌روزرسانی درون‌برنامه‌ای EXE را عوض نمی‌کند.

به‌روزرسانی درون‌برنامه‌ای همچنان **فقط HTML** را دانلود می‌کند؛ HTML جدید در پوشهٔ قابل‌نوشتن کاربر در `%LOCALAPPDATA%\PeriodicTableTrainer` جایگزین می‌شود و EXE دست‌نخورده می‌ماند. بنابراین نصب در Program Files به دسترسی نوشتن در آن پوشه نیاز ندارد و داده‌ها/WebView profile در AppData حفظ می‌شوند. نسخه‌های قدیمی onefile که خطای Python DLL می‌دهند با updater ترمیم نمی‌شوند؛ باید یک‌بار ZIP را دریافت و نصب‌کنندهٔ جدید را اجرا کرد. نصب جدید فایل‌های برنامه را در پوشهٔ نصب قرار می‌دهد و داده‌های ذخیره‌شدهٔ کاربر را پاک نمی‌کند.

## ساخت Android با Capacitor

ساخت اندروید در GitHub Actions با Node.js 22، Capacitor 8، Java 21 و target/compile API 36 انجام می‌شود. **هیچ امضای کدی در CI انجام نمی‌شود** و هیچ secret‌ای برای ساخت لازم نیست. خروجی‌ها:

- `app-debug.apk` — برای نصب جانبی/تست؛ Gradle آن را با کلید debug خودکار امضا می‌کند تا روی دستگاه نصب‌شدنی باشد. چون این کلید روی هر runner تازه ساخته می‌شود، امضای هر build متفاوت است و نصب مستقیم روی نسخهٔ قبلی ممکن است به حذف برنامه نیاز داشته باشد.
- `PeriodicTableTrainer-<run_number>.aab` — App Bundle **بدون امضا**، فقط برای نگهداری. AAB بدون امضا در Play Console پذیرفته نمی‌شود؛ برای انتشار در Play باید خودتان با کلید upload امضا کنید. این workflow چیزی را در Play منتشر نمی‌کند.

```bash
npm ci
python3 -m pip install "Pillow>=10,<13"
cp mobile_index.html www/index.html
npx cap add android
python3 capacitor/scripts/prepare_android.py
npx cap sync android
cd android
./gradlew --no-daemon assembleDebug bundleRelease
```

پیکربندی فعلی با شناسهٔ `com.amirgfno.periodictrainer` است. APKهای قبلی Buildozer شناسهٔ متفاوتی داشتند و داده‌هایشان خودکار به نسخهٔ Capacitor منتقل نمی‌شود.

## به‌روزرسانی نسخه‌ها

برای انتشار بعدی، نسخهٔ `package.json` و فیلدهای متناظر در `version.json` را هماهنگ کنید. `windows_app.py` از نشانی `windows_html_url` استفاده می‌کند؛ `capacitor/native/PeriodicTrainerNativePlugin.java` manifest را برای بررسی و دریافت APK می‌خواند. `update_config.py` تنظیمات به‌روزرسانی Windows را نگه می‌دارد.

Workflow انتشار در `.github/workflows/build.yml` با push روی شاخهٔ `main` یا اجرای دستی (`workflow_dispatch`) اجرا می‌شود و ZIP نصب‌کنندهٔ ویندوز، HTML جایگزین ویندوز، APK اندروید و AAB بدون امضا را می‌سازد. job انتشار حتی اگر یکی از دو پلتفرم شکست بخورد اجرا می‌شود تا خروجی پلتفرم سالم از دست نرود. نام Release به‌شکل `v<version> (Build <n>)` و تگ آن `v<version>-build<n>` است.

نکته: mergeهایی که با توکن پیش‌فرض `GITHUB_TOKEN` انجام می‌شوند رویداد `push` تولید نمی‌کنند؛ برای انتشار پس از merge یک‌بار اجرای دستی لازم است:

```bash
gh workflow run build.yml --ref main
```

برای Google Play، برنامه باید همان شناسهٔ بسته و کلید upload مورد تأیید Play Console را داشته باشد؛ امضای upload خارج از این مخزن انجام می‌شود.
