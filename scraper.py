"""
Revisa el API real de empleospublicos.cl (descubierto por inspeccion de red)
y avisa por correo cuando aparece una oferta nueva relacionada con "abogado".

Guarda el estado (ids ya vistos) en seen_jobs.json, que el workflow de
GitHub Actions vuelve a commitear despues de cada corrida.
"""

import json
import os
import re
import smtplib
from email.mime.text import MIMEText

import requests

API_URL = "https://www.empleospublicos.cl/apiConvocatorias.ashx"

# Se hace una consulta por cada palabra clave y se combinan los resultados.
KEYWORDS = ["abogado", "abogada"]

STATE_FILE = "seen_jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def load_seen() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def _extract_id(url: str) -> str:
    match = re.search(r"[?&]i=(\d+)", url)
    return match.group(1) if match else url


def fetch_jobs_for_keyword(keyword: str) -> dict:
    params = {
        "page": 1,
        "pageSize": 100,
        "q": keyword,
        "status": "Abierta",
        "sort": "relevant",
    }
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    jobs = {}
    for item in payload.get("data", []):
        url = item.get("url", "")
        job_id = _extract_id(url)
        jobs[job_id] = {
            "title": item.get("Cargo", "Oferta sin titulo"),
            "institution": item.get("Institución / Entidad", ""),
            "region": item.get("Región", ""),
            "city": item.get("Ciudad", ""),
            "closes": item.get("Fecha Cierre Convocatoria", ""),
            "link": url,
        }
    return jobs


def fetch_jobs() -> dict:
    all_jobs = {}
    for kw in KEYWORDS:
        try:
            jobs = fetch_jobs_for_keyword(kw)
            print(f"[info] busqueda '{kw}': {len(jobs)} oferta(s) abiertas encontradas")
            all_jobs.update(jobs)
        except requests.RequestException as e:
            print(f"Aviso: fallo la busqueda '{kw}' ({e})")
    return all_jobs


def send_email(new_jobs: dict) -> None:
    user = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASS"]
    # Admite uno o varios correos separados por coma en el secret EMAIL_TO,
    # ej: "correo1@gmail.com,correo2@gmail.com"
    to_list = [addr.strip() for addr in os.environ["EMAIL_TO"].split(",") if addr.strip()]

    lines = ["Se publicaron nuevas ofertas de trabajo para abogados:", ""]
    for data in new_jobs.values():
        lines.append(f"- {data['title']}")
        if data.get("institution"):
            lines.append(f"  Institucion: {data['institution']}")
        if data.get("city") or data.get("region"):
            lines.append(f"  Lugar: {data.get('city', '')}, {data.get('region', '')}")
        if data.get("closes"):
            lines.append(f"  Cierra: {data['closes']}")
        lines.append(f"  {data['link']}")
        lines.append("")

    body = "\n".join(lines)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Nueva(s) oferta(s) de abogado en empleospublicos.cl ({len(new_jobs)})"
    msg["From"] = user
    msg["To"] = ", ".join(to_list)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.sendmail(user, to_list, msg.as_string())


def main() -> None:
    seen = load_seen()
    current = fetch_jobs()

    if not current:
        print("No se encontro ninguna oferta abierta en este momento.")

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
