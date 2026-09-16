#!/usr/bin/env python3
"""
Бот "Какой сегодня праздник".

Раз в день берёт список праздников на сегодня из открытого RSS-фида
calend.ru и отправляет сообщение в Telegram.

Почему calend.ru, а не kakoysegodnyaprazdnik.ru:
сайт kakoysegodnyaprazdnik.ru блокирует автоматические запросы
(бот-защита), а у calend.ru есть открытый RSS без каких-либо
ограничений: http://www.calend.ru/img/export/today-holidays.rss

Требуются переменные окружения:
    TELEGRAM_BOT_TOKEN — токен бота от @BotFather
    TELEGRAM_CHAT_ID   — id чата/канала, куда слать сообщение
"""

import os
import sys
import html
import datetime
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError

RSS_URL = "http://www.calend.ru/img/export/today-holidays.rss"
USER_AGENT = "Mozilla/5.0 (compatible; HolidayBot/1.0)"

# Русские названия месяцев в родительном падеже — для сверки с заголовками RSS
MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def fetch_rss(url: str = RSS_URL, timeout: int = 15) -> str:
    """Скачивает RSS-фид и возвращает его текст."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def today_prefix(date: datetime.date) -> str:
    """"16 сентября 2026" — так, как выглядит начало заголовка в RSS."""
    return f"{date.day} {MONTHS_RU[date.month - 1]} {date.year}"


def parse_today_holidays(rss_text: str, date: datetime.date) -> list[dict]:
    """
    Разбирает RSS и возвращает список праздников, у которых заголовок
    начинается с сегодняшней даты (лента содержит сегодня + завтра).
    """
    prefix = today_prefix(date)
    root = ET.fromstring(rss_text)
    items = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is None or title_el.text is None:
            continue
        title = html.unescape(title_el.text.strip())
        if not title.startswith(prefix):
            continue
        # Заголовок вида "16 сентября 2026 - Название праздника"
        name = title.split(" - ", 1)[-1].strip()
        link_el = item.find("link")
        category_el = item.find("category")
        items.append(
            {
                "name": name,
                "link": link_el.text.strip() if link_el is not None and link_el.text else "",
                "category": category_el.text.strip() if category_el is not None and category_el.text else "",
            }
        )
    return items


def build_message(holidays: list[dict], date: datetime.date) -> str:
    """Формирует текст сообщения для Telegram (HTML-разметка)."""
    header = f"🎉 <b>Праздники сегодня, {today_prefix(date)}</b>"
    if not holidays:
        return header + "\n\nСегодня без особых поводов — обычный рабочий день 🙂"

    lines = [header, ""]
    for h in holidays:
        line = f"• {h['name']}"
        if h["category"]:
            line += f" <i>({h['category']})</i>"
        lines.append(line)
    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    """Отправляет сообщение через Telegram Bot API (без внешних библиотек)."""
    import json
    from urllib.request import urlopen, Request

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Telegram API вернул статус {resp.status}")


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Не заданы TELEGRAM_BOT_TOKEN и/или TELEGRAM_CHAT_ID", file=sys.stderr)
        return 1

    today = datetime.date.today()

    try:
        rss_text = fetch_rss()
    except URLError as e:
        print(f"Не удалось скачать RSS: {e}", file=sys.stderr)
        return 1

    holidays = parse_today_holidays(rss_text, today)
    message = build_message(holidays, today)

    try:
        send_telegram_message(token, chat_id, message)
    except Exception as e:
        print(f"Не удалось отправить сообщение в Telegram: {e}", file=sys.stderr)
        return 1

    print(f"Отправлено {len(holidays)} праздник(ов) за {today_prefix(today)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
