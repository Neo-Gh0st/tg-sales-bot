# -*- coding: utf-8 -*-
"""Два бота: продажи (@File_Delivery_Neo_Bot) + админ-подтверждения (отдельный бот)."""
import json, os, threading, time, requests

SALES_TOKEN = os.environ.get("SALES_TOKEN", "8649688924:AAFmx_gd5NAHT9WSehvuhLxQwv3o2FwJyR4")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "8875214637:AAHQ--t86L12A7xi8q9Jfcy8LWZNSl2u9nM")
SALES_API = f"https://api.telegram.org/bot{SALES_TOKEN}"
ADMIN_API = f"https://api.telegram.org/bot{ADMIN_TOKEN}"

CARD = "5355 2802 2276 9364"
PRICE = "1200 грн (≈ $29)"
ZIP_PATH = os.environ.get("ZIP_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "n8n-automations-pack.zip"))
HERE = os.path.dirname(os.path.abspath(__file__))
ADMIN_FILE = os.path.join(HERE, "admin_id.txt")
SALES_LOG = os.path.join(HERE, "sales_log.json")

STATE_FILE_P = os.path.join(HERE, "state.json")
state = {}

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

state = load_json(STATE_FILE_P, {})

def get_admin():
    try:
        with open(ADMIN_FILE, encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def api(base, method, **kw):
    try:
        r = requests.post(f"{base}/{method}", json=kw, timeout=40).json()
        if not r.get("ok", True): print("API FAIL:", method, r.get("description"), flush=True)
        return r
    except Exception as e:
        print("API error:", method, e, flush=True)
        return {}

def send_admin(text, **kw):
    a = get_admin()
    return api(ADMIN_API, "sendMessage", chat_id=a, text=text, parse_mode="HTML", **kw) if a else {}

def send_sales(chat_id, text, **kw):
    return api(SALES_API, "sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kw)

def kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in r] for r in rows]}

# ---------- БОТ ПРОДАЖ (покупатели) ----------

def sales_handle(u):
    msg = u.get("message")
    cb = u.get("callback_query")
    if msg:
        chat = msg["chat"]["id"]
        if (msg.get("photo") or msg.get("document")) and state.get(chat) == "await_screenshot":
            state.pop(chat, None); save_json(STATE_FILE_P, state)
            is_doc = bool(msg.get("document"))
            file_id = (msg["document"]["file_id"] if is_doc else msg["photo"][-1]["file_id"])
            gf = api(SALES_API, "getFile", file_id=file_id).get("result", {})
            fp = gf.get("file_path")
            kind = "Квитанция (файл) ⬆️" if is_doc else "Квитанция ⬆️"
            caption = (f"💰 <b>Новая продажа!</b>\n"
                       f"Покупатель: <a href='tg://user?id={chat}'>чат</a> (<code>{chat}</code>)\n"
                       f"{kind}")
            markup = kb([[("✅ Выдать файл", f"ok_{chat}"),
                          ("❌ Отклонить", f"no_{chat}")]])
            if fp:
                blob = requests.get(f"https://api.telegram.org/file/bot{SALES_TOKEN}/{fp}", timeout=60).content
                fname = fp.split("/")[-1]
                method = "sendDocument" if is_doc else "sendPhoto"
                field = "document" if is_doc else "photo"
                rr = requests.post(f"{ADMIN_API}/{method}",
                    data={"chat_id": get_admin(), "caption": caption, "parse_mode": "HTML",
                          "reply_markup": json.dumps(markup)},
                    files={field: (fname, blob)}, timeout=60)
                if not rr.json().get("ok"):
                    print("ADMIN UPLOAD FAIL:", rr.text, flush=True)
            else:
                send_admin(caption + "\n(файл квитанции не удалось получить)", reply_markup=markup)
                send_admin("Повтор квитанции:", reply_markup=markup)
                api(SALES_API, "forwardMessage", chat_id=get_admin(),
                    from_chat_id=chat, message_id=msg["message_id"])
                send_admin("Кнопки подтверждения:", reply_markup=markup)
            send_sales(chat, "⏳ Квитанция получена. Файл придёт сюда сразу после подтверждения оплаты.")
        elif (msg.get("photo") or msg.get("document")) and state.get(chat) != "await_screenshot":
            send_sales(chat, "Сначала нажми «💳 Купить» и «✅ Я оплатил», потом присылай квитанцию.")
        elif msg.get("text", "") == "/start":
            state.pop(chat, None)
            send_sales(chat,
                 "👋 <b>20 готовых n8n-автоматизаций для бизнеса</b>\n\n"
                 "✔ AI-сценарии, мониторинг, лиды, отчёты, бэкапы\n"
                 "✔ Импорт в n8n за 2 минуты\n"
                 "✔ Экономия 3–6 часов сборки на каждом сценарии\n\n"
                 "Жми кнопку ниже 👇",
                 reply_markup=kb([[("💳 Купить — " + PRICE, "buy")]]))
        return

    if cb:
        chat = cb["from"]["id"]
        data = cb["data"]
        if data == "buy":
            state[chat] = "await_paid"; save_json(STATE_FILE_P, state)
            send_sales(chat,
                 "💳 <b>Оплата переводом на карту</b>\n\n"
                 f"<code>{CARD}</code>  ← нажми, чтобы скопировать\n\n"
                 f"Сумма: <b>{PRICE}</b>\n\n"
                 "После перевода жми кнопку 👇",
                 reply_markup=kb([[("✅ Я оплатил", "paid")]]))
        elif data == "paid" and state.get(chat) == "await_paid":
            state[chat] = "await_screenshot"; save_json(STATE_FILE_P, state)
            send_sales(chat,
                 "📷 <b>Пришли сюда фото квитанции/скриншот перевода</b> — просто отправь картинку в этот чат.\n\n"
                 "Без квитанции файл не выдаётся.")

# ---------- АДМИН-БОТ (подтверждения) ----------

def admin_handle(u):
    msg = u.get("message")
    cb = u.get("callback_query")
    if msg and msg.get("text", "") == "/start":
        chat = msg["chat"]["id"]
        if get_admin() is None:
            with open(ADMIN_FILE, "w", encoding="utf-8") as f:
                f.write(str(chat))
            api(ADMIN_API, "sendMessage", chat_id=chat,
                text="👑 Ты администратор. Заявки на продажу будут приходить сюда.")
        else:
            api(ADMIN_API, "sendMessage", chat_id=chat,
                text="Это админ-бот. Сюда приходят заявки: ✅ выдать / ❌ отклонить.")
        return
    if msg and msg.get("text", "") == "/stats":
        log = load_json(SALES_LOG, {"sales": 0})
        api(ADMIN_API, "sendMessage", chat_id=msg["chat"]["id"],
            text=f"📊 Продаж выдано: {log.get('sales', 0)}")
        return
    if cb:
        chat = cb["from"]["id"]
        data = cb["data"]
        mid = cb["message"]["message_id"]
        if chat != get_admin():
            return
        if data.startswith("ok_"):
            buyer = int(data.split("_")[1])
            if os.path.exists(ZIP_PATH):
                with open(ZIP_PATH, "rb") as f:
                    requests.post(f"{SALES_API}/sendDocument",
                        data={"chat_id": buyer,
                              "caption": "🎉 Спасибо за покупку! Внутри 20 workflow + инструкция по установке."},
                        files={"document": ("n8n-automations-pack.zip", f)}, timeout=60)
            else:
                api(SALES_API, "sendDocument", chat_id=buyer, document=ZIP_URL,
                    caption="🎉 Спасибо за покупку! Внутри 20 workflow + инструкция по установке.")
            log = load_json(SALES_LOG, {"sales": 0})
            log["sales"] = log.get("sales", 0) + 1
            save_json(SALES_LOG, log)
            api(ADMIN_API, "editMessageText", chat_id=chat, message_id=mid,
                text=f"✅ Файл выдан покупателю <code>{buyer}</code>", parse_mode="HTML")
        elif data.startswith("no_"):
            buyer = int(data.split("_")[1])
            send_sales(buyer, "❌ Оплата не подтверждена. Если ты точно оплатил — напиши администратору.")
            api(ADMIN_API, "editMessageText", chat_id=chat, message_id=mid,
                text=f"❌ Отказано покупателю <code>{buyer}</code>", parse_mode="HTML")

# ---------- ПУЛИНГ ----------

def poll(base, handler):
    offset = None
    while True:
        kw = {"timeout": 30}
        if offset:
            kw["offset"] = offset
        r = api(base, "getUpdates", **kw)
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            try:
                handler(u)
            except Exception as e:
                print("Update error:", e, flush=True)
        time.sleep(0.5)

if __name__ == "__main__":
    print("Sales bot + Admin bot polling...")
    threading.Thread(target=poll, args=(ADMIN_API, admin_handle), daemon=True).start()
    poll(SALES_API, sales_handle)
