"""
Revisa empleospublicos.cl (área Jurídica/Legal/Fiscalía) y avisa por correo
cuando aparece una oferta nueva.

Guarda el estado (ids ya vistos) en seen_jobs.json, que el workflow de
GitHub Actions vuelve a commitear después de cada corrida.
"""

import json
import os
import re
import smtplib
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# Dos fuentes combinadas:
# 1) Listado general de TODAS las convocatorias (se filtra por palabra "abogado" en el título).
# 2) Listado ya filtrado por área "Jurídica-Legal-Fiscalía" (por si el título no dice
#    literalmente "abogado" pero igual es un cargo del área legal).
GENERAL_URL = "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx"
AREA_URL = (
    "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx"
    "?area=Jur%C3%ADdica--Legal--Fiscal%C3%ADa&i=28"
)

# Palabras clave para filtrar el listado general (minúsculas, sin tildes ya normalizadas abajo)
KEYWORDS = ["abogado", "abogada"]

STATE_FILE = "seen_jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def load_seen() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def _parse_jobs(html: str) -> dict:
    """Extrae {id_oferta: {title, link}} desde el HTML de un listado."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        match = re.search(r"[Cc]onv[Ff]icha\.aspx\?i=(\d+)", href)
        if not match:
            continue

        job_id = match.group(1)
        title = a.get_text(strip=True)
        if not title:
            title = a.get("title", "").strip() or f"Oferta {job_id}"

        if href.startswith("http"):
            link = href
        else:
            link = "https://www.empleospublicos.cl" + (
                href if href.startswith("/") else "/pub/convocatorias/" + href
            )

        jobs[job_id] = {"title": title, "link": link}

    return jobs


def _get_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_jobs() -> dict:
    """Combina el listado general (filtrado por palabra clave) con el área legal."""
    all_jobs = {}

    # Fuente 1: listado general, filtrado por título que contenga alguna keyword
    try:
        html = _get_html(GENERAL_URL)
        print(f"[debug] listado general: {len(html)} caracteres descargados")
        general_jobs = _parse_jobs(html)
        print(f"[debug] listado general: {len(general_jobs)} links tipo convFicha encontrados")
        if len(general_jobs) == 0:
            # Diagnóstico: mostrar una muestra de los <a href> reales que sí encontró,
            # para saber qué patrón usa el sitio en verdad.
            soup = BeautifulSoup(html, "html.parser")
            hrefs = [a["href"] for a in soup.find_all("a", href=True)][:15]
            print(f"[debug] primeros hrefs encontrados en la página: {hrefs}")
            print(f"[debug] contiene 'Cargando'?: {'Cargando' in html}")
            print(f"[debug] contiene 'abogado' (texto plano)?: {'abogado' in html.lower()}")
        for job_id, data in general_jobs.items():
            title_lower = data["title"].lower()
            if any(kw in title_lower for kw in KEYWORDS):
                all_jobs[job_id] = data
    except requests.RequestException as e:
        print(f"Aviso: no se pudo leer el listado general ({e})")

    # Fuente 2: área Jurídica-Legal-Fiscalía completa (respaldo, sin filtrar por título)
    try:
        area_jobs = _parse_jobs(_get_html(AREA_URL))
        print(f"[debug] listado área legal: {len(area_jobs)} links encontrados")
        all_jobs.update(area_jobs)
    except requests.RequestException as e:
        print(f"Aviso: no se pudo leer el listado del área legal ({e})")

    return all_jobs


def send_email(new_jobs: dict) -> None:
    user = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASS"]
    to = os.environ["EMAIL_TO"]

    lines = ["Se publicaron nuevas ofertas de trabajo para abogados:", ""]
    for data in new_jobs.values():
        lines.append(f"- {data['title']}")
        lines.append(f"  {data['link']}")
        lines.append("")

    body = "\n".join(lines)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"⚖️ {len(new_jobs)} nueva(s) oferta(s) de abogado en empleospublicos.cl"
    msg["From"] = user
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.sendmail(user, [to], msg.as_string())


def main() -> None:
    seen = load_seen()
    current = fetch_jobs()

    if not current:
        print(
            "No se encontró ninguna oferta en la página. "
            "Puede que la estructura del HTML haya cambiado, "
            "revisa el selector en fetch_jobs()."
        )
        return

    new_jobs = {jid: data for jid, data in current.items() if jid not in seen}

    if new_jobs:
        print(f"Encontradas {len(new_jobs)} oferta(s) nueva(s). Enviando correo...")
        send_email(new_jobs)
    else:
        print("No hay ofertas nuevas.")

    seen.update(current)
    save_seen(seen)


if __name__ == "__main__":
    main()
