"""
DIAGNOSTICO: usa un navegador real (Playwright) para cargar empleospublicos.cl,
hacer una busqueda de "abogado", y capturar todas las respuestas de red tipo JSON.

Esto es temporal, para descubrir el endpoint real que usa el sitio y asi poder
conectarnos directo a el (mucho mas rapido y confiable que controlar un navegador
en cada corrida).
"""

from playwright.sync_api import sync_playwright

HOME_URL = "https://www.empleospublicos.cl/"


def main():
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            ctype = response.headers.get("content-type", "")
            if "json" in ctype.lower():
                try:
                    body = response.text()
                except Exception:
                    body = "<no se pudo leer el body>"
                captured.append((response.url, ctype, body[:1500]))

        page.on("response", on_response)

        print(f"[debug] navegando a {HOME_URL}")
        page.goto(HOME_URL, wait_until="networkidle", timeout=45000)
        print(f"[debug] titulo de la pagina: {page.title()}")

        try:
            page.wait_for_selector("#main-search", timeout=10000)
            page.fill("#main-search", "abogado")
            page.keyboard.press("Enter")
            print("[debug] busqueda 'abogado' enviada")
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception as e:
            print(f"[debug] no se pudo interactuar con el buscador: {e}")

        page.wait_for_timeout(3000)

        print(f"[debug] URL final: {page.url}")
        print(f"[debug] total de respuestas JSON capturadas: {len(captured)}")
        for url, ctype, body in captured:
            print(f"[debug] --- {url} ({ctype}) ---")
            print(body)
            print("[debug] --- fin snippet ---")

        browser.close()


if __name__ == "__main__":
    main()
