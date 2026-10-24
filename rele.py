#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
رلهٔ مشترک انتشار تلگرام برای سیمان‌باز، آهن‌حساب و ملک‌دان (D:\\moshtarak\\RESANE.md بخش ۴-الف، ۲۵ مهر ۱۴۰۵).

سرور هر پروژه در ایران است و به api.telegram.org نمی‌رسد؛ پست را خودش می‌سازد و در صف نگه می‌دارد. این رله از اجراگر
گیت‌هاب (بیرون ایران) هر نوبت:
  ۱. GET  <SITE>/api/resane/montazer?bastar=telegram   (سرآیند X-Rele-Key)  ← پست‌های منتظر امروز
  ۲. sendMessage تلگرام برای هر پست، یک پیام در ثانیه
  ۳. POST <SITE>/api/resane/natije  {"id","bastar","vaziat":"sent|failed","shenase"?,"khata"?}
رله بی‌حالت است: اگر نوبتی شکست، نوبت بعد همان پست را می‌فرستد (صف روی سرور می‌ماند).

متغیرها (از Secrets مخزن، با پیشوند نام پروژه در گردش‌کار): SITE، RELE_KEY، TELEGRAM_TOKEN، TELEGRAM_CHANNEL.
فقط کتابخانهٔ استاندارد پایتون.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "resane-rele/1 (+https://github.com)"
# ویدئوی روزانه (ملک‌دان، ۲ آبان ۱۴۰۵): سرور در پست صف فیلد `video` (مسیر فایل روی سایت) می‌دهد؛ مسیر فقط با این الگوی سخت پذیرفته می‌شود
VIDEO_RE = re.compile(r"/video/[a-z0-9-]{1,80}\.mp4")
SAGHF_VIDEO = 49_000_000  # سقف بارگذاری ربات تلگرام ۵۰ مگابایت است


def http(method: str, url: str, body: dict | None = None, headers: dict | None = None,
         timeout: int = 20) -> tuple[int | None, dict | list | None, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    h = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null"), ""
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null"), f"HTTP {e.code}"
        except ValueError:
            return e.code, None, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, None, type(e).__name__
    except ValueError:
        return None, None, "پاسخ نامعتبر"


def aks_bgir(site: str, rh: dict, pid: str) -> bytes | None:
    """PNG کارت تصویری پست از سایت، پشت همان کلید رله؛ هر شکستی None (متن تنها)."""
    req = urllib.request.Request(f"{site}/api/resane/tasvir?id={urllib.parse.quote(pid)}",
                                 headers={"User-Agent": UA, **rh})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        return data if data[:8] == b"\x89PNG\r\n\x1a\n" else None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def aks_befrest(token: str, chan: str, matn: str, png: bytes, qaleb: str = "") -> tuple[int | None, dict | None, str]:
    """sendPhoto چندبخشی با متن پست در زیرنویس (سرور فقط وقتی tasvir می‌دهد که متن در سقف زیرنویس جا شود)."""
    marz = "rele" + os.urandom(8).hex()
    body = b"".join([f'--{marz}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
                     for k, v in (("chat_id", chan), ("caption", matn), *((("parse_mode", qaleb),) if qaleb else ()))]
                    + [f'--{marz}\r\nContent-Disposition: form-data; name="photo"; filename="kart.png"\r\n'
                       f'Content-Type: image/png\r\n\r\n'.encode() + png + b"\r\n", f"--{marz}--\r\n".encode()])
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": f"multipart/form-data; boundary={marz}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null"), ""
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null"), f"HTTP {e.code}"
        except ValueError:
            return e.code, None, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, None, type(e).__name__
    except ValueError:
        return None, None, "پاسخ نامعتبر"


def video_bgir(site: str, masir: str) -> bytes | None:
    """mp4 ویدئوی پست از سایت (مسیر عمومی `/video/…`)؛ هر شکستی یا فایل غیر mp4 None (پست بی ویدئو، متن تنها)."""
    if not VIDEO_RE.fullmatch(masir):
        return None
    req = urllib.request.Request(f"{site}{masir}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read(SAGHF_VIDEO + 1)
        return data if len(data) <= SAGHF_VIDEO and data[4:8] == b"ftyp" else None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def video_befrest(token: str, chan: str, matn: str, mp4: bytes, qaleb: str = "") -> tuple[int | None, dict | None, str]:
    """sendVideo چندبخشی با متن پست در زیرنویس (سرور فقط وقتی video می‌دهد که متن در سقف ۱۰۲۴ زیرنویس جا شود)."""
    marz = "rele" + os.urandom(8).hex()
    body = b"".join([f'--{marz}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
                     for k, v in (("chat_id", chan), ("caption", matn[:1024]), ("supports_streaming", "true"),
                                  *((("parse_mode", qaleb),) if qaleb else ()))]
                    + [f'--{marz}\r\nContent-Disposition: form-data; name="video"; filename="video.mp4"\r\n'
                       f'Content-Type: video/mp4\r\n\r\n'.encode() + mp4 + b"\r\n", f"--{marz}--\r\n".encode()])
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendVideo", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": f"multipart/form-data; boundary={marz}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "null"), ""
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "null"), f"HTTP {e.code}"
        except ValueError:
            return e.code, None, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, None, type(e).__name__
    except ValueError:
        return None, None, "پاسخ نامعتبر"


def video_yekbar(site: str, token: str, chan: str) -> int:
    """فرستادن یک‌بارهٔ ویدئو با تلنگر `client_payload.video_once` ({"video": "/video/x.mp4", "caption": "...", "qaleb": "HTML"}) برای وقتی که
    سرور هنوز فیلد `video` را در صف نمی‌دهد. بی صف و بی اعلام به سرور؛ خروجی کار شناسهٔ پیام را نگه می‌دارد. 0 یعنی رفت یا چیزی نبود."""
    raw = os.environ.get("VIDEO_ONCE", "").strip()
    if not raw:
        return 0
    try:
        v = json.loads(raw)
        masir, cap = str(v["video"]), str(v["caption"])
    except (ValueError, KeyError, TypeError):
        print("::error::VIDEO_ONCE نامعتبر است")
        return 1
    mp4 = video_bgir(site, masir)
    if not mp4:
        print(f"::error::ویدئوی یک‌بار گرفته نشد: {masir}")
        return 1
    qaleb = v.get("qaleb") if v.get("qaleb") in ("HTML", "MarkdownV2") else ""
    tc, tr, terr = video_befrest(token, chan, cap, mp4, qaleb)
    ok = tc == 200 and isinstance(tr, dict) and tr.get("ok")
    print(f"ویدئوی یک‌بار: {'رفت ' + str((tr.get('result') or {}).get('message_id', '')) if ok else 'نرفت ' + terr}")
    return 0 if ok else 1


def main() -> int:
    site = os.environ.get("SITE", "").rstrip("/")
    key = os.environ.get("RELE_KEY", "").strip()
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_CHANNEL", "").strip()
    nabood = [n for n, v in (("SITE", site), ("RELE_KEY", key), ("TELEGRAM_TOKEN", token),
                             ("TELEGRAM_CHANNEL", chan)) if not v]
    if nabood:
        # پروژه‌ای که هنوز رازهایش گذاشته نشده، اجرای بقیه را قرمز نمی‌کند
        print(f"::warning::رازهای این پروژه گذاشته نشده: {', '.join(nabood)}")
        return 0
    if token.lower().startswith("bot"):
        token = token[3:]
    # X-Rele-Video: رله ویدئو می‌فرستد؛ سرور بی این سرآیند پست ویدئویی را در صف نگه می‌دارد (ملک‌دان، ۲ آبان ۱۴۰۵)
    rh = {"X-Rele-Key": key, "X-Rele-Video": "1"}
    shekast = video_yekbar(site, token, chan)
    # جبران: سرور پست‌های روزهای گذشته را که به بله رفته و به تلگرام نرفته به ترتیب زمان می‌دهد (سروری که این را نشناسد صف عادی را می‌دهد)
    jobran = os.environ.get("JOBRAN", "").strip() == "1"
    code, posts, err = http("GET", f"{site}/api/resane/montazer?bastar=telegram{'&jobran=1' if jobran else ''}",
                            headers=rh, timeout=40)
    if code != 200 or not isinstance(posts, list):
        print(f"::error::صف خوانده نشد: {code or ''} {err}")
        return 1
    print(f"{len(posts)} پست منتظر")
    # نام عمومی و عضو کانال (هر دو عمومی‌اند): اگر نام عمومی برداشته شود، پیوند سایت به کانال بی‌صدا می‌میرد
    q = urllib.parse.quote(chan)
    gc, gr, gerr = http("GET", f"https://api.telegram.org/bot{token}/getChat?chat_id={q}")
    mc, mr, _ = http("GET", f"https://api.telegram.org/bot{token}/getChatMemberCount?chat_id={q}")
    if gc == 200 and isinstance(gr, dict) and gr.get("ok"):
        nam = (gr.get("result") or {}).get("username")
        ozv = mr.get("result") if isinstance(mr, dict) and mr.get("ok") else "?"
        print(f"کانال: {'@' + nam if nam else 'بی نام عمومی'}، عضو {ozv}")
        if not nam:
            print("::warning::کانال تلگرام نام عمومی ندارد؛ پیوند t.me سایت کار نمی‌کند")
    else:
        print(f"::warning::getChat کانال نشد: {gc or ''} {gerr}")
    for i, p in enumerate(posts):
        if i:
            # تلگرام در کانال حدود ۲۰ پیام در دقیقه می‌پذیرد؛ جبرانِ یک‌جا آرام‌تر می‌رود
            time.sleep(3.5 if jobran else 1.1)
        matn = str(p.get("matn", ""))
        # qaleb: سرور متن را HTML ساخته (پیوند روی واژه، سیمان‌باز ۲۹ مهر ۱۴۰۵)؛ سرور بی این فیلد متن ساده می‌دهد
        qaleb = p.get("qaleb") if p.get("qaleb") in ("HTML", "MarkdownV2") else ""
        # ویدئوی روزانه: سرور مسیرش را در `video` می‌دهد و زیرنویس را در `zirnevis`؛ نگرفتنش یعنی متن تنها
        mp4 = video_bgir(site, str(p.get("video") or "")) if p.get("video") else None
        aks = None if mp4 else (aks_bgir(site, rh, str(p.get("id", ""))) if p.get("tasvir") else None)
        # زیر عکس متن کوتاه پست (عددها روی تصویرند)؛ سرور قدیمی‌تر zirnevis ندارد و همان matn می‌رود
        if mp4:
            tc, tr, terr = video_befrest(token, chan, str(p.get("zirnevis") or matn), mp4, qaleb)
        else:
            tc, tr, terr = (aks_befrest(token, chan, str(p.get("zirnevis") or matn), aks, qaleb) if aks else (0, None, ""))
        if (aks or mp4) and tc != 200 and tc is not None:
            print(f"::warning::{p.get('id')}: {'ویدئو' if mp4 else 'عکس'} نرفت ({terr}); متن تنها")
        if not (aks or mp4) or (tc != 200 and tc is not None):
            tc, tr, terr = http("POST", f"https://api.telegram.org/bot{token}/sendMessage",
                                {"chat_id": chan, "text": matn[:4096],
                                 # پیش‌نمایش پیوند فقط وقتی سرور بخواهد؛ سرور قدیمی‌تر این فیلد را ندارد و پیش‌نمایش می‌ماند
                                 "link_preview_options": {"is_disabled": p.get("pishnamayesh") is False},
                                 **({"parse_mode": qaleb} if qaleb else {})})
        if tc == 200 and isinstance(tr, dict) and tr.get("ok"):
            natije = {"vaziat": "sent", "shenase": str((tr.get("result") or {}).get("message_id", ""))}
        elif tc is None:
            # تلگرام شاید پذیرفته باشد و پاسخ نرسیده؛ چیزی اعلام نمی‌شود و نوبت بعد دوباره می‌فرستد (شاید یک بار تکراری،
            # همان که سند پذیرفته)؛ شناسهٔ پست این‌جا در خروجی کار می‌ماند تا تکرار دیده شود
            print(f"::warning::{p.get('id')}: نتیجهٔ تلگرام نامعلوم ({terr}); اعلام نشد")
            shekast += 1
            continue
        else:
            desc = (tr or {}).get("description", "") if isinstance(tr, dict) else ""
            natije = {"vaziat": "failed", "khata": f"{terr} {desc}".strip()[:200]}
        nc, _, nerr = http("POST", f"{site}/api/resane/natije",
                           {"id": p.get("id"), "bastar": "telegram", **natije}, headers=rh)
        print(f"{p.get('id')}: {natije['vaziat']} {natije.get('shenase') or natije.get('khata') or ''}"
              f" · اعلام به سرور: {nc or nerr}")
        if natije["vaziat"] != "sent" or nc != 200:
            shekast += 1
    try:
        khosoosi(site, rh, token)
    except Exception as e:  # noqa: BLE001 — رونوشت خصوصی هرگز انتشار کانال را قرمز نمی‌کند
        print(f"::warning::رونوشت خصوصی: {type(e).__name__}")
    return 1 if shekast else 0


def khosoosi(site: str, rh: dict, token: str) -> None:
    """رونوشت گزارش شبانهٔ بله در گفت‌وگوی خصوصی سروش با ربات همین کانال (BALE.md بخش ۱۱، ۲ آبان ۱۴۰۵)، سوار همین اجرا.

    سرور این بستر را نشناسد (فهرست می‌دهد، نه شیء) ← بی‌صدا هیچ. گفت‌وگو را فقط پیامی وصل می‌کند که واژهٔ رمز سرور را دارد،
    و آن رمز فقط در گزارش بلهٔ خود سروش می‌آید. مخزن عمومی است: شناسهٔ گفت‌وگو، رمز و متن گزارش هرگز در خروجی کار چاپ نمی‌شوند.
    """
    tg = f"https://api.telegram.org/bot{token}"
    natije_url = f"{site}/api/resane/natije"
    code, v, _ = http("GET", f"{site}/api/resane/montazer?bastar=khosoosi", headers=rh, timeout=40)
    if code != 200 or not isinstance(v, dict):
        return
    chat = str(v.get("chat") or "")
    if not chat:
        if not v.get("bot"):
            mc, mr, _ = http("GET", f"{tg}/getMe")
            nam = (mr.get("result") or {}).get("username") if mc == 200 and isinstance(mr, dict) else None
            if nam:
                http("POST", natije_url, {"id": "bot", "bastar": "khosoosi", "vaziat": "sent", "shenase": nam}, headers=rh)
        ramz = str(v.get("ramz") or "")
        if not ramz:
            return
        # بی offset: به‌روزرسانی‌ها مصرف نمی‌شوند و هر نوبت (تا ۲۴ ساعت، نگهداری تلگرام) دوباره دیده می‌شوند
        uc, ur, _ = http("GET", f"{tg}/getUpdates?limit=100&allowed_updates=%5B%22message%22%5D")
        if uc != 200 or not isinstance(ur, dict) or not ur.get("ok"):
            print("رونوشت خصوصی: getUpdates نشد")
            return
        for u in reversed(ur.get("result") or []):
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") == "private" and ramz in str(m.get("text", "")):
                chat = str(m["chat"]["id"])
                break
        if not chat:
            print("رونوشت خصوصی: هنوز وصل نشده")
            return
        nc, _, _ = http("POST", natije_url, {"id": "chat", "bastar": "khosoosi", "vaziat": "sent", "shenase": chat}, headers=rh)
        if nc != 200:
            return
        http("POST", f"{tg}/sendMessage", {"chat_id": chat, "text": "✅ وصل شد: از این پس رونوشت گزارش شبانهٔ بله اینجا هم می‌آید."})
        print("رونوشت خصوصی: گفت‌وگو وصل شد")
        code, v, _ = http("GET", f"{site}/api/resane/montazer?bastar=khosoosi", headers=rh, timeout=40)
        if code != 200 or not isinstance(v, dict):
            return
    for i, p in enumerate(v.get("payamha") or []):
        if i:
            time.sleep(1.1)
        tc, tr, terr = http("POST", f"{tg}/sendMessage", {"chat_id": chat, "text": str(p.get("matn", ""))[:4096],
                                                       "link_preview_options": {"is_disabled": True}})
        if tc == 200 and isinstance(tr, dict) and tr.get("ok"):
            http("POST", natije_url, {"id": p.get("id"), "bastar": "khosoosi", "vaziat": "sent"}, headers=rh)
            print("رونوشت خصوصی: یک گزارش رفت")
        elif tc == 403:
            # سروش ربات را بست: گفت‌وگو کنار می‌رود و گزارش بعدی رمز تازه می‌آورد
            http("POST", natije_url, {"id": "chat", "bastar": "khosoosi", "vaziat": "failed"}, headers=rh)
            print("رونوشت خصوصی: ربات بسته شده؛ وصل دوباره لازم است")
            return
        else:
            print(f"رونوشت خصوصی: نرفت ({terr})")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
