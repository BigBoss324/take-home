from playwright.sync_api import sync_playwright
import re

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www2.sii.cl/stc/noauthz", wait_until="networkidle")
        
        page.fill("input.rut-form", "76.839.700-0")
        page.click("input[name='Consultar'], button:has-text('Consultar')")
        
        try:
            # Esperar ancla robusta del footer de resultados del SII
            page.wait_for_selector("text='informada en esta consulta'", timeout=15000)
            html = page.locator("body").inner_text()
            giros = re.findall(r'\b\d{5,6}\b', html)
            print("Giros extraídos:", set(giros))
        except Exception as e:
            print("Error:", e)
            
        browser.close()

if __name__ == "__main__":
    test()
