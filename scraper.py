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

GENERAL_URL = "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx"
AREA_URL = (
    "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx"
    "?area=Jur%C3%ADdica--Legal--Fiscal%C3%ADa&i=28"
)

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


def
