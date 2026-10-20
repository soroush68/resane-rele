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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "resane-rele/1 (+https://github.com)"


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
    rh = {"X-Rele-Key": key}
    code, posts, err = http("GET", f"{site}/api/resane/montazer?bastar=telegram", headers=rh)
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
    shekast = 0
    for i, p in enumerate(posts):
        if i:
            time.sleep(1.1)
        tc, tr, terr = http("POST", f"https://api.telegram.org/bot{token}/sendMessage",
                            {"chat_id": chan, "text": str(p.get("matn", ""))[:4096]})
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
    return 1 if shekast else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
