# Periodic Table Trainer

پروژه شامل سه نسخهٔ فعال است: وب (`web_index.html`)، ویندوز (`windows_app.py` و `windows_index.html`) و اندروید با Capacitor (`mobile_index.html`). نسخهٔ وب عمداً آمار دائمی، مدال‌ها و ذخیره‌سازی مرورگر ندارد؛ نتیجهٔ هر بازی فقط تا پایان همان نشست نمایش داده می‌شود. نسخه‌های ویندوز و موبایل قابلیت‌های ذخیره‌سازی و پشتیبان‌گیری مخصوص خود را دارند.

## فایل‌های فعال

- `web_index.html` — نسخهٔ مستقل وب؛ بدون آمار و مدال‌های دائمی.
- `windows_app.py`, `windows_index.html`, `update_config.py` — برنامه و رابط ویندوز و تنظیمات به‌روزرسانی HTML.
- `mobile_index.html`, `www/index.html` — رابط Capacitor؛ در انتشار اندروید، `www/index.html` از `mobile_index.html` ساخته/همگام می‌شود.
- `capacitor.config.json`, `package.json`, `package-lock.json` — پیکربندی و وابستگی‌های Capacitor.
- `capacitor/native/PeriodicTrainerNativePlugin.java`, `capacitor/scripts/prepare_android.py` — پل بومی اندروید برای پشتیبان‌گیری، بررسی نسخه، نصب به‌روزرسانی و ساخت آیکون‌های لانچر.
- `capacitor/android_icon_background.png`, `capacitor/android_icon_foreground.png` — لایهٔ گرادیان تمام‌صفحه و نشان شفافِ آیکون اندروید.
- `.github/workflows/build.yml`, `installer/PeriodicTableTrainer.iss` — ساخت نصب‌کنندهٔ امضاشدهٔ ویندوز و APK/AAB اندروید با Capacitor؛ نصب‌کننده در Program Files نصب می‌کند و میان‌بر دسکتاپ می‌سازد. Pillow برای تولید منابع آیکون APK در مرحلهٔ build نصب می‌شود.
- `version.json` — manifest نسخه و نشانی‌های به‌روزرسانی.
- `windows_logo.png` — لوگوی دایره‌ای گرادیانی با بیرون شفاف؛ `app.ico` نسخهٔ ۲۵۶×۲۵۶ آن برای EXE ویندوز است.
- `app_logo.png` — پیش‌نمایش لوگوی موبایل با همان نشان و گرادیانِ کشیده‌شده تا لبه‌های تصویر.
- `convert_fonts.py`, `font_sources/` — منابع و ابزار بازتولید فونت‌های تعبیه‌شده.

فایل ریشهٔ `index.html` دست‌نخورده نگه داشته شده است؛ منبع نسخهٔ وب جاری `web_index.html` است.

## ساخت نسخهٔ ویندوز

Workflow ویندوز، برنامه را به‌شکل onedir می‌سازد، EXE اصلی و نصب‌کننده را با Authenticode امضا می‌کند و با Inno Setup یک نصب‌کننده تولید می‌کند. فایل `PeriodicTableTrainer-windows.zip` شامل `PeriodicTableTrainer-Setup-<version>.exe` و راهنمای نصب است. برای فعال‌شدن امضا، در GitHub Secrets مقدارهای `WINDOWS_SIGNING_CERTIFICATE_BASE64` (فایل PFX به Base64) و `WINDOWS_SIGNING_CERTIFICATE_PASSWORD` را تعریف کنید؛ گواهی را هرگز در مخزن قرار ندهید. امضا هویت ناشر را نشان می‌دهد و به ساخته‌شدن اعتبار کمک می‌کند، اما تضمین نمی‌کند هشدار SmartScreen برای نخستین انتشار فوراً ناپدید شود. نصب‌کننده به‌طور پیش‌فرض برنامه را در `Program Files\PeriodicTableTrainer` نصب می‌کند، میان‌بر دسکتاپ می‌سازد و میان‌بر منوی Start را نیز اضافه می‌کند. برای نصب، کاربر باید پنجرهٔ مجوز Windows را تأیید کند.

به‌روزرسانی درون‌برنامه‌ای همچنان **فقط HTML** را دانلود می‌کند؛ HTML جدید در پوشهٔ قابل‌نوشتن کاربر در `%LOCALAPPDATA%\PeriodicTableTrainer` جایگزین می‌شود و EXE دست‌نخورده می‌ماند. بنابراین نصب در Program Files به دسترسی نوشتن در آن پوشه نیاز ندارد و داده‌ها/WebView profile در AppData حفظ می‌شوند. نسخه‌های قدیمی onefile که خطای Python DLL می‌دهند با updater ترمیم نمی‌شوند؛ باید یک‌بار ZIP را دریافت و نصب‌کنندهٔ جدید را اجرا کرد. نصب جدید فایل‌های برنامه را در پوشهٔ نصب قرار می‌دهد و داده‌های ذخیره‌شدهٔ کاربر را پاک نمی‌کند.

## ساخت Android با Capacitor

ساخت اندروید در GitHub Actions با Node.js 22، Capacitor 8، Java 21 و target/compile API 36 انجام می‌شود. Workflow هم APK امضاشده برای updater داخل برنامه و هم AAB امضاشده برای بارگذاری دستی در Google Play Console می‌سازد. AAB به‌تنهایی برنامه را در Play منتشر نمی‌کند؛ انتشار/تأیید نهایی در Play Console انجام می‌شود. روند اصلی:

```bash
npm ci
python3 -m pip install "Pillow>=10,<13"
cp mobile_index.html www/index.html
npx cap add android
python3 capacitor/scripts/prepare_android.py
npx cap sync android
cd android
./gradlew --no-daemon assembleRelease bundleRelease
```

پیکربندی فعلی با شناسهٔ `com.amirgfno.periodictrainer` است. همین شناسه و همان کلید خصوصی release باید برای به‌روزرسانی درجا حفظ شوند. APK باید با secrets زیر امضا شود:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

کلید keystore و رمزها را در مخزن commit نکنید؛ فقط در GitHub Secrets نگه دارید و از کلید نسخهٔ پشتیبان امن داشته باشید. APKهای قبلی Buildozer شناسهٔ متفاوتی داشتند و داده‌هایشان خودکار به نسخهٔ Capacitor منتقل نمی‌شود.

## به‌روزرسانی نسخه‌ها

برای انتشار بعدی، نسخهٔ `package.json` و فیلدهای متناظر در `version.json` را هماهنگ کنید. `windows_app.py` از نشانی `windows_html_url` استفاده می‌کند؛ `capacitor/native/PeriodicTrainerNativePlugin.java` manifest را برای بررسی و دریافت APK می‌خواند. `update_config.py` تنظیمات به‌روزرسانی Windows را نگه می‌دارد.

Workflow انتشار در `.github/workflows/build.yml` با اجرای push یا دستی، نصب‌کنندهٔ امضاشدهٔ ویندوز، HTML جایگزین ویندوز، APK اندروید و AAB برای Google Play را می‌سازد و به GitHub Release همان اجرا می‌فرستد. برای Google Play، برنامه باید همان شناسهٔ بسته و کلید بارگذاری مورد تأیید Play Console را داشته باشد؛ APK نصب‌شده از بیرون Play ممکن است به‌دلیل تفاوت کلید امضا قابل به‌روزرسانی مستقیم از Play نباشد.
