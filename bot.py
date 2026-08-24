# -*- coding: utf-8 -*-
"""Автопродажа n8n-пака через Telegram Stars: оплата -> мгновенная выдача файла."""
import json, os, requests

SALES_TOKEN = os.environ["SALES_TOKEN"]          # только из переменных окружения!
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
STARS = int(os.environ.get("STARS", "2000"))
ZIP_URL = os.environ.get("ZIP_URL", "https://neo-gh0st.github.io/1c-skd-pack/n8n-automations-pack.zip")
API = f"https://api.telegram.org/bot{SALES_TOKEN}"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales_log.json")

def api(method, **kw):
    try:
        r = requests.post(f"{API}/{method}", json=kw, timeout=40).json()
        if not r.get("ok", True):
            print("API FAIL:", method, r.get("description"), flush=True)
        return r
    except Exception as e:
        print("API error:", method, e, flush=True)
        return {}

def send(chat_id, text, **kw):
    return api("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kw)

def kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in r] for r in rows]}

def bump_sales():
    try:
        log = json.load(open(LOG, encoding="utf-8"))
    except Exception:
        log = {"sales": 0}
    log["sales"] = log.get("sales", 0) + 1
    json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False)

def handle(u):
    msg = u.get("message")
    cb = u.get("callback_query")
    pq = u.get("pre_checkout_query")
    sp = msg.get("successful_payment") if msg else None

    if pq:
        api("answerPreCheckoutQuery", pre_checkout_query_id=pq["id"], ok=True)
        return

    if sp:
        chat = msg["chat"]["id"]
        api("sendDocument", chat_id=chat, document=ZIP_URL,
            caption="🎉 Спасибо за покупку! Внутри 20 workflow + инструкция по установке.")
        bump_sales()
        if ADMIN_ID:
            send(ADMIN_ID, f"💰 <b>Продажа!</b> {sp.get('total_amount', '?')} Stars\n"
                           f"Покупатель: <code>{chat}</code>")
        return

    if msg:
        chat = msg["chat"]["id"]
        text = msg.get("text", "")

        if text == "/start":
            api("sendInvoice", chat_id=chat, title="20 готовых n8n-автоматизаций",
                description="AI-сценарии, мониторинг, лиды, отчёты, бэкапы. Импорт за 2 минуты.",
                payload="n8n_pack_v1", provider_token="", currency="XTR",
                prices=[{"label": "Пак из 20 n8n workflow", "amount": STARS}])
        elif text == "/stats" and chat == ADMIN_ID:
            try:
                log = json.load(open(LOG, encoding="utf-8"))
            except Exception:
                log = {"sales": 0}
            send(chat, f"📊 Продаж выдано: {log.get('sales', 0)}")

    if cb and cb["data"] == "buy":
        api("sendInvoice", chat_id=cb["from"]["id"], title="20 готовых n8n-автоматизаций",
            description="AI-сценарии, мониторинг, лиды, отчёты, бэкапы. Импорт за 2 минуты.",
            payload="n8n_pack_v1", provider_token="", currency="XTR",
            prices=[{"label": "Пак из 20 n8n workflow", "amount": STARS}])

def main():
    print("Stars bot started. Polling...", flush=True)
    offset = None
    while True:
        kw = {"timeout": 30}
        if offset:
            kw["offset"] = offset
        r = api("getUpdates", **kw)
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            try:
                handle(u)
            except Exception as e:
                print("Update error:", e, flush=True)
        import time
        time.sleep(0.5)

if __name__ == "__main__":
    main()
