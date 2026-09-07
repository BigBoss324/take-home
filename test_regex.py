from playwright.sync_api import sync_playwright
import time, re

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www2.sii.cl/stc/noauthz", wait_until="networkidle")
        
        page.type("input.rut-form", "76.839.700-0", delay=50)
        page.click("input[name='Consultar'], button:has-text('Consultar')")
        
        page.wait_for_selector("text='RUT Contribuyente:'", timeout=15000)
        
        try:
            page.click("text='VER ACTIVIDADES'", timeout=2000) 
        except Exception:
            pass 
            
        time.sleep(2)
        html_content = page.content()
        giros = re.findall(r'\b\d{5,6}\b', html_content)
        print("GIROS EXTRAIDOS:", giros)
        
        browser.close()

if __name__ == "__main__":
    test()
