package com.amirgfno.periodictrainer;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.util.AtomicFile;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

@CapacitorPlugin(name = "PeriodicTrainerNative")
public class PeriodicTrainerNativePlugin extends Plugin {
    private static final String VERSION_URL =
        "https://raw.githubusercontent.com/AmirGFno/PeriodicTableTrainer/main/version.json";
    private static final int CONNECT_TIMEOUT_MS = 20000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_MANIFEST_BYTES = 1024L * 1024L;
    private static final long MAX_APK_BYTES = 500L * 1024L * 1024L;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean updateRunning = new AtomicBoolean(false);

    private String appVersion() {
        try {
            String version = getContext().getPackageManager()
                .getPackageInfo(getContext().getPackageName(), 0).versionName;
            return version == null ? "0.0.0" : version;
        } catch (Exception error) {
            throw new IllegalStateException("Could not read installed app version", error);
        }
    }

    @PluginMethod
    public void backupData(PluginCall call) {
        String payload = call.getString("payload");
        if (payload == null || payload.length() > 2 * 1024 * 1024) {
            call.reject("Invalid or oversized backup payload");
            return;
        }
        try {
            JSONObject value = new JSONObject(payload);
            File target = new File(getContext().getFilesDir(), "records.json");
            AtomicFile atomic = new AtomicFile(target);
            FileOutputStream output = null;
            try {
                output = atomic.startWrite();
                output.write(value.toString().getBytes("UTF-8"));
                output.getFD().sync();
                atomic.finishWrite(output);
            } catch (Exception error) {
                if (output != null) atomic.failWrite(output);
                throw error;
            }
            JSObject result = new JSObject();
            result.put("ok", true);
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Could not save app data", error);
        }
    }

    @PluginMethod
    public void restoreData(PluginCall call) {
        JSObject result = new JSObject();
        File target = new File(getContext().getFilesDir(), "records.json");
        try {
            if (target.isFile()) {
                byte[] bytes = readBounded(new FileInputStream(target), 2L * 1024L * 1024L);
                result.put("data", new JSONObject(new String(bytes, "UTF-8")));
            } else {
                result.put("data", (JSONObject) null);
            }
            call.resolve(result);
        } catch (Exception error) {
            call.reject("Could not restore app data", error);
        }
    }

    @PluginMethod
    public void checkUpdate(PluginCall call) {
        executor.execute(() -> {
            try {
                JSONObject manifest = fetchManifest();
                String latest = manifest.getString("latest_version");
                boolean available = compareVersions(latest, appVersion()) > 0;
                JSObject result = new JSObject();
                result.put("available", available);
                result.put("current_version", appVersion());
                result.put("latest_version", latest);
                result.put("notes", manifest.optString("notes", ""));
                if (available) result.put("android_url", requireHttps(manifest.optString("android_url", "")));
                call.resolve(result);
            } catch (Exception error) {
                call.reject("بررسی نسخه ناموفق بود: " + error.getMessage(), error);
            }
        });
    }

    @PluginMethod
    public void updateAndroid(PluginCall call) {
        if (!updateRunning.compareAndSet(false, true)) {
            JSObject response = new JSObject();
            response.put("ok", true);
            response.put("message", "دانلود به‌روزرسانی در حال انجام است.");
            call.resolve(response);
            return;
        }
        JSObject response = new JSObject();
        response.put("ok", true);
        call.resolve(response);
        executor.execute(() -> {
            try {
                downloadAndInstall();
            } catch (Exception error) {
                emitError("دانلود/نصب به‌روزرسانی Android ناموفق بود: " + error.getMessage());
            } finally {
                updateRunning.set(false);
            }
        });
    }

    private JSONObject fetchManifest() throws Exception {
        HttpURLConnection connection = openHttps(VERSION_URL);
        try {
            byte[] bytes = readBounded(connection.getInputStream(), MAX_MANIFEST_BYTES);
            JSONObject manifest = new JSONObject(new String(bytes, "UTF-8"));
            String latest = manifest.optString("latest_version", "");
            if (latest.isEmpty()) throw new IllegalArgumentException("version.json has no latest_version");
            compareVersions(latest, latest); // Validate the version string.
            return manifest;
        } finally {
            connection.disconnect();
        }
    }

    private void downloadAndInstall() throws Exception {
        emitProgress(0, "در حال بررسی نسخهٔ جدید Android...");
        JSONObject manifest = fetchManifest();
        String latest = manifest.getString("latest_version");
        if (compareVersions(latest, appVersion()) <= 0) {
            throw new IllegalStateException("نسخهٔ جدیدی برای Android موجود نیست.");
        }
        String apkUrl = requireHttps(manifest.optString("android_url", ""));
        File updateDir = new File(getContext().getFilesDir(), "updates");
        if (!updateDir.exists() && !updateDir.mkdirs()) throw new IllegalStateException("ساخت پوشهٔ دانلود ممکن نشد.");
        File apk = new File(updateDir, "PeriodicTableTrainer.apk");
        File versionFile = new File(updateDir, "downloaded-version.txt");
        boolean reuse = apk.isFile() && versionFile.isFile()
            && latest.equals(readSmallText(versionFile));
        if (!reuse) downloadApk(apkUrl, latest, manifest.optString("android_sha256", ""), apk, versionFile);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            && !getContext().getPackageManager().canRequestPackageInstalls()) {
            Intent settings = new Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + getContext().getPackageName())
            );
            settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(settings);
            emitFinished("برای نصب APK اجازهٔ «Install unknown apps» را فعال کنید، سپس دوباره دکمهٔ به‌روزرسانی را بزنید.");
            return;
        }

        Uri apkUri = FileProvider.getUriForFile(
            getContext(), getContext().getPackageName() + ".fileprovider", apk
        );
        Intent install = new Intent(Intent.ACTION_VIEW);
        install.setDataAndType(apkUri, "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        emitFinished("دانلود کامل شد؛ تأیید نصب را در پنجرهٔ Android انجام دهید.");
        getContext().startActivity(install);
    }

    private void downloadApk(String url, String version, String expectedSha256, File apk, File versionFile) throws Exception {
        emitProgress(0, "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید");
        HttpURLConnection connection = openHttps(url);
        File temporary = new File(apk.getParentFile(), apk.getName() + ".part");
        try {
            long length = connection.getContentLength();
            if (length > MAX_APK_BYTES) throw new IllegalArgumentException("فایل APK از اندازهٔ مجاز بزرگ‌تر است.");
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            long received = 0;
            try (InputStream input = connection.getInputStream(); FileOutputStream output = new FileOutputStream(temporary)) {
                byte[] buffer = new byte[256 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    received += count;
                    if (received > MAX_APK_BYTES) throw new IllegalArgumentException("فایل APK از اندازهٔ مجاز بزرگ‌تر است.");
                    output.write(buffer, 0, count);
                    digest.update(buffer, 0, count);
                    int percent = length > 0 ? (int) Math.min(99, received * 100 / length) : 0;
                    emitProgress(percent, "در حال دانلود بروزرسانی... لطفاً برنامه را نبندید");
                }
                output.getFD().sync();
            }
            if (received < 4) throw new IllegalArgumentException("فایل APK خالی یا ناقص است.");
            try (FileInputStream input = new FileInputStream(temporary)) {
                byte[] signature = new byte[4];
                if (input.read(signature) != 4 || signature[0] != 'P' || signature[1] != 'K'
                    || signature[2] != 3 || signature[3] != 4) {
                    throw new IllegalArgumentException("فایل دریافت‌شده APK معتبر نیست.");
                }
            }
            String actualSha = toHex(digest.digest());
            if (!expectedSha256.isEmpty() && !actualSha.equalsIgnoreCase(expectedSha256)) {
                throw new IllegalArgumentException("تأیید SHA-256 فایل APK ناموفق بود.");
            }
            if (apk.exists() && !apk.delete()) throw new IllegalStateException("جایگزینی APK قبلی ممکن نشد.");
            if (!temporary.renameTo(apk)) throw new IllegalStateException("ذخیرهٔ APK دانلودشده ممکن نشد.");
            try (FileOutputStream output = new FileOutputStream(versionFile)) {
                output.write(version.getBytes("UTF-8"));
                output.getFD().sync();
            }
        } catch (Exception error) {
            if (temporary.exists()) temporary.delete();
            throw error;
        } finally {
            connection.disconnect();
        }
    }

    private HttpURLConnection openHttps(String value) throws Exception {
        URL url = new URL(requireHttps(value));
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setInstanceFollowRedirects(true);
        connection.setRequestProperty("User-Agent", "PeriodicTableTrainer/" + appVersion());
        int code = connection.getResponseCode();
        if (code < 200 || code >= 300) {
            connection.disconnect();
            throw new IllegalStateException("سرور به‌روزرسانی پاسخ " + code + " داد.");
        }
        if (!"https".equalsIgnoreCase(connection.getURL().getProtocol())) {
            connection.disconnect();
            throw new IllegalArgumentException("نشانی دانلود باید HTTPS باقی بماند.");
        }
        return connection;
    }

    private String requireHttps(String value) throws Exception {
        URL url = new URL(value);
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getHost() == null || url.getHost().isEmpty()) {
            throw new IllegalArgumentException("نشانی به‌روزرسانی باید HTTPS معتبر باشد.");
        }
        return value;
    }

    private int compareVersions(String left, String right) {
        String[] a = left.replaceFirst("^[vV]", "").split("\\.");
        String[] b = right.replaceFirst("^[vV]", "").split("\\.");
        if (a.length > 5 || b.length > 5) throw new IllegalArgumentException("نسخه نامعتبر است.");
        for (int i = 0; i < Math.max(a.length, b.length); i++) {
            int av = i < a.length ? parseVersionPart(a[i]) : 0;
            int bv = i < b.length ? parseVersionPart(b[i]) : 0;
            if (av != bv) return Integer.compare(av, bv);
        }
        return 0;
    }

    private int parseVersionPart(String value) {
        if (value.isEmpty() || !value.matches("\\d+")) throw new IllegalArgumentException("نسخه نامعتبر است.");
        return Integer.parseInt(value);
    }

    private byte[] readBounded(InputStream input, long maximum) throws Exception {
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            long total = 0;
            int count;
            while ((count = source.read(buffer)) != -1) {
                total += count;
                if (total > maximum) throw new IllegalArgumentException("پاسخ سرور بیش از اندازه بزرگ است.");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private String readSmallText(File file) {
        try (FileInputStream input = new FileInputStream(file)) {
            return new String(readBounded(input, 128), "UTF-8").trim();
        } catch (Exception ignored) {
            return "";
        }
    }

    private String toHex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) result.append(String.format(Locale.US, "%02x", value & 0xff));
        return result.toString();
    }

    private void emitProgress(int percent, String message) {
        JSObject event = new JSObject();
        event.put("percent", percent);
        event.put("message", message);
        notifyListeners("updateProgress", event);
    }

    private void emitFinished(String message) {
        JSObject event = new JSObject();
        event.put("message", message);
        notifyListeners("updateFinished", event);
    }

    private void emitError(String message) {
        JSObject event = new JSObject();
        event.put("message", message);
        notifyListeners("updateError", event);
    }
}
