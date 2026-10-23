# Periodic Table Trainer

پروژه شامل سه نسخهٔ فعال است: وب (`web_index.html`)، ویندوز (`windows_app.py` و `windows_index.html`) و اندروید با Capacitor (`mobile_index.html`). نسخهٔ وب عمداً آمار دائمی، مدال‌ها و ذخیره‌سازی مرورگر ندارد؛ نتیجهٔ هر بازی فقط تا پایان همان نشست نمایش داده می‌شود. نسخه‌های ویندوز و موبایل قابلیت‌های ذخیره‌سازی و پشتیبان‌گیری مخصوص خود را دارند.

## فایل‌های فعال

- `web_index.html` — نسخهٔ مستقل وب؛ بدون آمار و مدال‌های دائمی.
- `windows_app.py`, `windows_index.html`, `update_config.py` — برنامه و رابط ویندوز و تنظیمات به‌روزرسانی HTML.
- `mobile_index.html`, `www/index.html` — رابط Capacitor؛ در انتشار اندروید، `www/index.html` از `mobile_index.html` ساخته/همگام می‌شود.
- `capacitor.config.json`, `package.json`, `package-lock.json` — پیکربندی و وابستگی‌های Capacitor.
- `capacitor/native/PeriodicTrainerNativePlugin.java`, `capacitor/scripts/prepare_android.py` — پل بومی اندروید برای پشتیبان‌گیری، بررسی نسخه، نصب به‌روزرسانی و ساخت آیکون‌های لانچر از لوگوی شفاف اندروید.
- `.github/workflows/build.yml` — ساخت EXE ویندوز و APK امضاشدهٔ Capacitor؛ Pillow فقط برای تولید منابع آیکون APK در مرحلهٔ build نصب می‌شود.
- `version.json` — manifest نسخه و نشانی‌های به‌روزرسانی.
- `windows_logo.png` — لوگوی دایره‌ای با گرادیان چندرنگ و بیرونِ دایرهٔ شفاف؛ `app.ico` نسخهٔ ۲۵۶×۲۵۶ آن برای EXE ویندوز است.
- `app_logo.png` — لوگوی اندرویدِ مشکی/نارنجی با پس‌زمینهٔ شفاف؛ اسکریپت build آن را به آیکون‌های launcher و adaptive icon تبدیل می‌کند.
- `convert_fonts.py`, `font_sources/` — منابع و ابزار بازتولید فونت‌های تعبیه‌شده.

فایل ریشهٔ `index.html` دست‌نخورده نگه داشته شده است؛ منبع نسخهٔ وب جاری `web_index.html` است.

## ساخت نسخهٔ ویندوز

در ویندوز، از ریشهٔ پروژه اجرا کنید:

```powershell
python -m pip install --upgrade pip "pywebview[winforms]" pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "PeriodicTableTrainer" --icon=app.ico --add-data "windows_index.html;." --collect-all webview --hidden-import=clr windows_app.py
```

خروجی `dist/PeriodicTableTrainer.exe` است. برای به‌روزرسانی HTML، برنامه `windows_html_url` را از `version.json` می‌خواند و فایل جدید را با handoff دسته‌ای جایگزین می‌کند؛ خود EXE دانلود یا جایگزین نمی‌شود. پوشهٔ نصب باید اجازهٔ نوشتن داشته باشد.

## ساخت Android با Capacitor

ساخت رسمی APK در GitHub Actions و با Node.js 20، Capacitor 6 و Java 17 انجام می‌شود. روند اصلی:

```bash
npm ci
python3 -m pip install "Pillow>=10,<13"
cp mobile_index.html www/index.html
npx cap add android
python3 capacitor/scripts/prepare_android.py
npx cap sync android
cd android
./gradlew --no-daemon assembleRelease
```

پیکربندی فعلی با شناسهٔ `com.amirgfno.periodictrainer` است. همین شناسه و همان کلید خصوصی release باید برای به‌روزرسانی درجا حفظ شوند. APK باید با secrets زیر امضا شود:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

کلید keystore و رمزها را در مخزن commit نکنید؛ فقط در GitHub Secrets نگه دارید و از کلید نسخهٔ پشتیبان امن داشته باشید. APKهای قبلی Buildozer شناسهٔ متفاوتی داشتند و داده‌هایشان خودکار به نسخهٔ Capacitor منتقل نمی‌شود.

## به‌روزرسانی نسخه‌ها

برای انتشار بعدی، نسخهٔ `package.json` و فیلدهای متناظر در `version.json` را هماهنگ کنید. `windows_app.py` از نشانی `windows_html_url` استفاده می‌کند؛ `capacitor/native/PeriodicTrainerNativePlugin.java` manifest را برای بررسی و دریافت APK می‌خواند. `update_config.py` تنظیمات به‌روزرسانی Windows را نگه می‌دارد.

Workflow انتشار در `.github/workflows/build.yml` هر دو خروجی را می‌سازد. انتشار یا push از این workspace انجام نشده است.
