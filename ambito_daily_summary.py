#!/usr/bin/env python3
"""
Daily Ámbito Summary — Argentina
Runs at 8 AM, scrapes ambito.com, summarizes with Claude API, sends email.
"""

import os
import smtplib
import schedule
import time
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
RECIPIENT     = "lucasmoya1993@gmail.com"
SENDER_EMAIL  = os.environ["GMAIL_USER"]
SENDER_PASS   = os.environ["GMAIL_APP_PASSWORD"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

URLS = [
    "https://www.ambito.com/economia",
    "https://www.ambito.com/finanzas",
    "https://www.ambito.com/politica",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}

# ── SCRAPER ───────────────────────────────────────────────────────────────────
def scrape_ambito() -> str:
    """Scrape headlines and summaries from ambito.com sections."""
    collected = []

    for url in URLS:
        section = url.split("/")[-1].upper()
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Ámbito article cards — various selectors they use
            selectors = [
                "article",
                ".news-card",
                ".article-item",
                "[class*='article']",
                "[class*='nota']",
                "[class*='news']",
            ]

            articles_found = []
            for sel in selectors:
                found = soup.select(sel)
                if found:
                    articles_found = found[:12]
                    break

            for article in articles_found:
                title  = article.select_one("h2, h3, h4, [class*='title'], [class*='titulo']")
                teaser = article.select_one("p, [class*='summary'], [class*='bajada']")

                title_text  = title.get_text(strip=True)  if title  else ""
                teaser_text = teaser.get_text(strip=True) if teaser else ""

                if title_text and len(title_text) > 15:
                    collected.append(
                        f"[{section}] TÍTULO: {title_text}\n"
                        f"BAJADA: {teaser_text}"
                    )

            # Fallback: grab all h2/h3 on the page
            if not articles_found:
                for tag in soup.find_all(["h2", "h3"])[:15]:
                    text = tag.get_text(strip=True)
                    if len(text) > 20:
                        collected.append(f"[{section}] {text}")

        except Exception as e:
            collected.append(f"[No se pudo acceder a {url}: {e}]")

    return "\n\n".join(collected) if collected else "Sin contenido."


# ── SUMMARIZER ────────────────────────────────────────────────────────────────
def summarize(raw_content: str) -> str:
    """Send scraped content to Claude and get a 5-bullet summary in Spanish."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    prompt = f"""Sos un analista económico especializado en Argentina.
A continuación hay titulares y noticias extraídos de ambito.com hoy.
Tu tarea: escribir exactamente 5 bullets con los temas más importantes del día
en economía, finanzas, mercados y política argentina.

Formato de cada bullet:
• [CATEGORÍA] Oración concisa con los datos y cifras más relevantes.

Categorías a usar: ECONOMÍA · MERCADOS · POLÍTICA · DÓLAR · INTERNACIONAL

Contenido scrapeado:
{raw_content[:8000]}
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


# ── EMAIL BUILDER ─────────────────────────────────────────────────────────────
def build_email(bullets: str) -> MIMEMultipart:
    """Build a clean HTML email styled for Ámbito."""
    today = datetime.now().strftime("%A %d de %B de %Y").capitalize()

    # Map category tags to colors
    colored = bullets.strip()
    tag_colors = {
        "ECONOMÍA":      "#1E3A5F",
        "MERCADOS":      "#166534",
        "POLÍTICA":      "#7C2D12",
        "DÓLAR":         "#92400E",
        "INTERNACIONAL": "#1E40AF",
    }
    for tag, color in tag_colors.items():
        colored = colored.replace(
            f"[{tag}]",
            f'<span style="background:{color};color:#fff;font-size:10px;'
            f'font-weight:700;padding:2px 7px;border-radius:4px;'
            f'letter-spacing:0.5px;margin-right:6px">{tag}</span>'
        )

    bullet_html = "".join(
        f'<div style="display:flex;align-items:flex-start;margin-bottom:16px">'
        f'<span style="color:#E63946;font-size:18px;line-height:1;margin-right:10px;'
        f'flex-shrink:0;margin-top:1px">•</span>'
        f'<p style="margin:0;color:#1a1a1a;font-size:15px;line-height:1.65">{line.lstrip("•").strip()}</p>'
        f'</div>'
        for line in colored.split("\n")
        if line.strip() and line.strip() != "•"
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">

  <div style="max-width:620px;margin:32px auto;background:#fff;border-radius:10px;
              overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.09)">

    <!-- header -->
    <div style="background:#1E3A5F;padding:26px 32px 22px">
      <div style="display:flex;align-items:center;margin-bottom:10px">
        <span style="background:#E63946;color:#fff;font-size:12px;font-weight:800;
                     padding:3px 10px;border-radius:4px;letter-spacing:1px;
                     text-transform:uppercase;margin-right:10px">Ámbito</span>
        <span style="color:#93C5FD;font-size:12px;letter-spacing:1px;
                     text-transform:uppercase">Resumen Diario</span>
      </div>
      <h1 style="color:#fff;margin:0;font-size:24px;font-weight:700;
                 line-height:1.25">Argentina · Briefing Matutino</h1>
      <p style="color:#93C5FD;margin:6px 0 0;font-size:13px">{today} · 08:00 hs</p>
    </div>

    <!-- intro -->
    <div style="padding:22px 32px 0">
      <p style="color:#6B7280;font-size:13px;margin:0;line-height:1.6;
                border-bottom:1px solid #E5E7EB;padding-bottom:18px">
        Los <strong>5 temas del día</strong> extraídos de
        <a href="https://www.ambito.com" style="color:#1E3A5F;text-decoration:none;
           font-weight:600">ambito.com</a> —
        economía, mercados, dólar y política argentina.
      </p>
    </div>

    <!-- bullets -->
    <div style="padding:20px 32px 8px">
      {bullet_html}
    </div>

    <!-- cta row -->
    <div style="padding:8px 32px 28px;display:flex;gap:10px">
      <a href="https://www.ambito.com/economia"
         style="display:inline-block;background:#1E3A5F;color:#fff;
                text-decoration:none;padding:9px 18px;border-radius:6px;
                font-size:12px;font-weight:700;margin-right:8px">
        Economía →
      </a>
      <a href="https://www.ambito.com/finanzas"
         style="display:inline-block;background:#E63946;color:#fff;
                text-decoration:none;padding:9px 18px;border-radius:6px;
                font-size:12px;font-weight:700;margin-right:8px">
        Finanzas →
      </a>
      <a href="https://www.ambito.com/politica"
         style="display:inline-block;background:#374151;color:#fff;
                text-decoration:none;padding:9px 18px;border-radius:6px;
                font-size:12px;font-weight:700">
        Política →
      </a>
    </div>

    <!-- footer -->
    <div style="background:#F9FAFB;padding:14px 32px;border-top:1px solid #E5E7EB">
      <p style="margin:0;color:#9CA3AF;font-size:11px;line-height:1.6">
        Automatizado con Claude · Anthropic &nbsp;·&nbsp;
        Fuente: ambito.com &nbsp;·&nbsp;
        Enviado a {RECIPIENT}
      </p>
    </div>

  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"📰 Ámbito · Resumen Argentina · "
        f"{datetime.now().strftime('%d/%m/%Y')}"
    )
    msg["From"] = SENDER_EMAIL
    msg["To"]   = RECIPIENT
    msg.attach(MIMEText(html, "html"))
    return msg


# ── SENDER ────────────────────────────────────────────────────────────────────
def send_email(msg: MIMEMultipart) -> None:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, RECIPIENT, msg.as_string())
    print(f"[{datetime.now()}] ✓ Email enviado a {RECIPIENT}")


# ── MAIN JOB ──────────────────────────────────────────────────────────────────
def daily_job():
    print(f"[{datetime.now()}] Iniciando job diario...")
    raw     = scrape_ambito()
    bullets = summarize(raw)
    msg     = build_email(bullets)
    send_email(msg)
    print(f"[{datetime.now()}] Listo.")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # pip install anthropic requests beautifulsoup4 schedule

    # Variables de entorno requeridas:
    # export ANTHROPIC_API_KEY="sk-ant-..."
    # export GMAIL_USER="tu@gmail.com"
    # export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"

    print("Scheduler iniciado. Corre todos los días a las 08:00.")
    print("Ctrl+C para detener.\n")

    schedule.every().day.at("08:00").do(daily_job)

    # Para probar ahora sin esperar, descomentá esta línea:
    # daily_job()

    while True:
        schedule.run_pending()
        time.sleep(30)
