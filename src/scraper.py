import os
import asyncio
import random
import logging
import re
from playwright.async_api import async_playwright, TimeoutError
from playwright_stealth import Stealth
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def obtener_giros_sii(rut_formateado: str) -> list[str]:
    """
    Consulta el portal del SII para extraer los códigos de giro vigentes de un RUT.
    Modo headless configurable por variable de entorno SII_HEADLESS (default: false).
    Incluye retry automático con backoff exponencial (3 intentos).
    """
    url = "https://www2.sii.cl/stc/noauthz"
    cuerpo, dv = rut_formateado.split("-") if "-" in rut_formateado else (rut_formateado[:-1], rut_formateado[-1])
    
    # FORMATO CRÍTICO: El SPA del SII usa una máscara que requiere puntos de miles
    cuerpo_formateado = "{:,.0f}".format(int(cuerpo)).replace(",", ".")
    rut_con_puntos = f"{cuerpo_formateado}-{dv}"
    
    async with async_playwright() as p:
        # Configurable: SII_HEADLESS=true para CI/servidores, false para demo con captcha manual
        # Usamos channel='msedge' para usar el Edge local de Windows y saltar el error de certificado al descargar Chromium
        browser = await p.chromium.launch(
            headless=os.getenv('SII_HEADLESS', 'false').lower() == 'true',
            channel="msedge"
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Ocultar rastro de que somos un robot (WebDriver)
        await Stealth().apply_stealth_async(page)
        
        try:
            await page.goto(url, wait_until="commit", timeout=15000)
            
            rut_input_selector = "input.rut-form"
            submit_btn = "input[name='Consultar'], button:has-text('Consultar')"
            
            await page.wait_for_selector(rut_input_selector, timeout=10000)
            
            # Simulamos el tipeo humano con el formato estricto
            await page.type(rut_input_selector, rut_con_puntos, delay=100)
            
            await page.click(submit_btn)
            
            # --- ESPERA SEGURA ---
            try:
                # 100% Cierto: El texto 'RUT Contribuyente:' siempre es un nodo de texto en el resultado del SII.
                await page.wait_for_selector("text='RUT Contribuyente:'", timeout=10000)
            except TimeoutError:
                # Si falla, es porque apareció CAPTCHA real u otro bloqueo de Angular.
                await page.wait_for_selector("text='RUT Contribuyente:'", timeout=30000)
                
            # 🔴 EL SECRETO REVELADO: Expandir el menú de Acordeón
            try:
                # El selector text sin comillas internas hace substring match en Playwright!
                await page.click("text=VER ACTIVIDADES ECONÓMICAS", timeout=4000) 
            except Exception:
                pass # Si no tiene botón, no hacemos nada
                    
            await asyncio.sleep(2) # Pausa segura post-renderizado para el llamado HTTP asíncrono
            # Usar page.content() incluye TODOS los datos en el HTML
            html_content = await page.content()
            
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
            await browser.close()
