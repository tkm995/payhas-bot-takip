"""
Mosaic Visa Randevu Takip Botu - Cloud Versiyonu
"""

import os
import time
import requests
import logging
from datetime import datetime, date

TELEGRAM_BOT_TOKEN = "8681089221:AAEJISrx7ppZOchHjtOiFoSGg0mMIr20iao"
TELEGRAM_CHAT_ID   = "8011613197"

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
EMAIL_RECEIVERS = ["nagmatberdiyev@gmail.com"]

OFFICE_IDS = [11, 12]
CHECK_INTERVAL_MINUTES = 5
MONTHS_AHEAD = 1

OFFICE_NAMES = {
    11: "Ashgabat (Normal)",
    12: "Ashgabat (VIP)",
}

BASE_URL = "https://appointment.mosaicvisa.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)


def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            log.info("Telegram bildirimi gonderildi.")
        else:
            log.warning("Telegram hatasi: " + str(r.status_code))
    except Exception as e:
        log.error("Telegram gonderilemedi: " + str(e))


def send_email(office_name, new_slots, now_str, office_id):
    try:
        slots_list = "".join("<li>" + s + "</li>" for s in sorted(new_slots))
        randevu_url = BASE_URL + "/calendar/" + str(office_id)

        html_body = """
        <html>
        <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; border-radius: 10px; padding: 25px;">
                <h2 style="color: #e74c3c;">YENI RANDEVU SLOTU!</h2>
                <p><strong>Ofis:</strong> """ + office_name + """</p>
                <p><strong>Tarih:</strong> """ + now_str + """</p>
                <hr>
                <p><strong>Musait Tarihler:</strong></p>
                <ul style="line-height: 2;">""" + slots_list + """</ul>
                <hr>
                <a href='""" + randevu_url + """'
                   style="display: inline-block; margin-top: 10px; padding: 12px 24px;
                          background: #2ecc71; color: white; text-decoration: none;
                          border-radius: 6px; font-weight: bold;">
                    Randevu Al
                </a>
            </div>
        </body>
        </html>
        """

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer " + RESEND_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "from": "Mosaic Bot <nagmatberdiyev@gmail.com>",
                "to": EMAIL_RECEIVERS,
                "subject": "Yeni Randevu Slotu - " + office_name,
                "html": html_body
            },
            timeout=15
        )

        if response.status_code == 200:
            log.info("E-posta gonderildi.")
        else:
            log.error("E-posta hatasi: " + str(response.status_code) + " " + response.text)

    except Exception as e:
        log.error("E-posta gonderilemedi: " + str(e))


def get_available_slots(office_id, month=None):
    from bs4 import BeautifulSoup

    url = BASE_URL + "/calendar/" + str(office_id)
    if month:
        url += "?month=" + month

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            log.warning("HTTP " + str(r.status_code))
            return []
    except Exception as e:
        log.warning("Baglanti hatasi: " + str(e))
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    available = []
    today = date.today()

    months_en = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    for cell in soup.find_all(["td", "tr", "div", "li", "a"]):
        text = cell.get_text(separator=" ", strip=True)

        if "Available" not in text:
            continue
        if "Reserved" in text:
            continue
        if "2026" not in text:
            continue
        if len(text) > 60:
            continue

        try:
            for month_name, month_num in months_en.items():
                if month_name in text:
                    parts = text.split()
                    day = int(parts[0])
                    slot_date = date(2026, month_num, day)
                    if slot_date < today:
                        break
                    if text not in available:
                        available.append(text)
                    break
        except:
            pass

    return available


def get_months():
    months = [None]
    now = date.today()
    for i in range(1, MONTHS_AHEAD + 1):
        m = now.month + i
        y = now.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        months.append(str(y) + "-" + str(m).zfill(2))
    return months


def main():
    log.info("Mosaic Visa Bot Baslatildi")

    send_telegram(
        "Mosaic Visa Bot Baslatildi\n"
        + ", ".join(OFFICE_NAMES.get(i, "") for i in OFFICE_IDS) + "\n"
        + "Her " + str(CHECK_INTERVAL_MINUTES) + " dakikada kontrol ediyorum..."
    )

    previously_available = {oid: set() for oid in OFFICE_IDS}
    check_count = 0

    while True:
        check_count += 1
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        log.info("Kontrol #" + str(check_count) + " - " + now_str)

        for office_id in OFFICE_IDS:
            office_name = OFFICE_NAMES.get(office_id, str(office_id))
            all_slots = []

            for month in get_months():
                slots = get_available_slots(office_id, month)
                all_slots.extend(slots)
                time.sleep(1)

            all_slots_set = set(all_slots)
            new_slots = all_slots_set - previously_available[office_id]

            if all_slots:
                log.info(office_name + ": " + str(len(all_slots)) + " musait slot")
            else:
                log.info(office_name + ": Musait slot yok")

            if new_slots:
                slots_text = "\n".join("  " + s for s in sorted(new_slots))
                randevu_url = BASE_URL + "/calendar/" + str(office_id)

                send_telegram(
                    "<b>YENI RANDEVU SLOTU!</b>\n\n"
                    "<b>" + office_name + "</b>\n"
                    "<a href='" + randevu_url + "'>Randevu Al</a>\n\n"
                    "<b>Musait Tarihler:</b>\n" + slots_text + "\n\n"
                    + now_str
                )

                send_email(office_name, new_slots, now_str, office_id)

            previously_available[office_id] = all_slots_set

        log.info(str(CHECK_INTERVAL_MINUTES) + " dakika bekleniyor...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
