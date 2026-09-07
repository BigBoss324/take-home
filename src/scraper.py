import time
import random
import logging
import re
from playwright.sync_api import sync_playwright, TimeoutError

logger = logging.getLogger(__name__)

def obtener_giros_sii(rut_formateado: str) -> list[str]:
    """
    Consulta el portal del SII para extraer los códigos de giro vigentes de un RUT.
    Se ejecuta en modo HEADLESS=FALSE para permitir la resolución humana del CAPTCHA
    durante la demo (tiempo de espera: hasta 45 segundos).
    """
    url = "https://www2.sii.cl/stc/noauthz"
    cuerpo, dv = rut_formateado.split("-") if "-" in rut_formateado else (rut_formateado[:-1], rut_formateado[-1])
    
    # FORMATO CRÍTICO: El SPA del SII usa una máscara que requiere puntos de miles
    cuerpo_formateado = "{:,.0f}".format(int(cuerpo)).replace(",", ".")
    rut_con_puntos = f"{cuerpo_formateado}-{dv}"
    
    with sync_playwright() as p:
        # HEADLESS=FALSE para la demostración en vivo
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="commit", timeout=15000)
            
            rut_input_selector = "input.rut-form"
            submit_btn = "input[name='Consultar'], button:has-text('Consultar')"
            
            page.wait_for_selector(rut_input_selector, timeout=10000)
            
            # Simulamos el tipeo humano con el formato estricto
            page.type(rut_input_selector, rut_con_puntos, delay=100)
            
            page.click(submit_btn)
            
            # --- ESPERA SEGURA ---
            try:
                # 100% Cierto: El texto 'RUT Contribuyente:' siempre es un nodo de texto en el resultado del SII.
                page.wait_for_selector("text='RUT Contribuyente:'", timeout=10000)
            except TimeoutError:
                # Si falla, es porque apareció CAPTCHA real u otro bloqueo de Angular.
                page.wait_for_selector("text='RUT Contribuyente:'", timeout=30000)
                
            # 🔴 EL SECRETO REVELADO: Expandir el menú de Acordeón
            try:
                # El selector text sin comillas internas hace substring match en Playwright!
                page.click("text=VER ACTIVIDADES ECONÓMICAS", timeout=4000) 
            except Exception:
                pass # Si no tiene botón, no hacemos nada
                    
            time.sleep(2) # Pausa segura post-renderizado para el llamado HTTP asíncrono
            # Usar page.content() incluye TODOS los datos en el HTML
            html_content = page.content()
            
            # Extraer giros (números de 5 a 6 dígitos en el resultado)
            giros = re.findall(r'\b\d{5,6}\b', html_content)
            
            return list(set(giros))

        except TimeoutError as e: 
            logger.error(f"[TIMEOUT] Carga fallida o CAPTCHA no resuelto para RUT {rut_formateado}.")
            raise Exception(f"Timeout SII: {e}")
        except Exception as e:
            logger.error(f"[ERROR] Falló la extracción para RUT {rut_formateado}: {e}")
            raise
        finally:
            browser.close()
