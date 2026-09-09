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
        browser = await p.chromium.launch(
            headless=os.getenv('SII_HEADLESS', 'false').lower() == 'true',
            channel="msedge"
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # Ocultar rastro de automatización
        await Stealth().apply_stealth_async(page)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 1. Bucle robusto para llenar el formulario y lidiar con la Sala de Espera si aparece sorpresivamente
            intentos_formulario = 0
            while intentos_formulario < 3:
                intentos_formulario += 1
                try:
                    # Comprobar si nos mandaron a sala de espera al cargar o recargar
                    if "salaespera.sii.cl" in page.url or await page.locator("text='Pronto será tu turno'").count() > 0:
                        logger.warning(f"RUT {rut_formateado}: En Sala de Espera SII. Esperando turno pacientemente (hasta 10 min)...")
                        await page.wait_for_url(re.compile(r"^https://www2\.sii\.cl/.*"), timeout=600000) # 10 mins de tolerancia
                        logger.info(f"RUT {rut_formateado}: Fin de sala de espera. Procediendo...")

                    # Esperar que la página principal cargue detectando el título oficial
                    await page.wait_for_selector("text=CONSULTAR SITUACIÓN TRIBUTARIA", timeout=30000)
                    
                    # Esperar el campo de RUT y el botón
                    rut_input = page.locator("input.rut-form").first
                    await rut_input.wait_for(state="visible", timeout=15000)
                    submit_btn = page.locator("input[name='Consultar'], input[value='Consultar'], button:has-text('Consultar')").first
                    
                    # Limpiamos y tipeamos el RUT
                    await rut_input.fill("")
                    await rut_input.type(rut_con_puntos, delay=80)
                    
                    # Click en Consultar forzando la acción
                    await submit_btn.click(timeout=15000, force=True)
                    break # Si el click es exitoso sin TimeoutError, salimos del bucle
                    
                except TimeoutError:
                    # Si falló por Timeout, verificamos si fue porque Queue-It nos interrumpió en medio de la escritura/click
                    if "salaespera.sii.cl" in page.url or await page.locator("text='Pronto será tu turno'").count() > 0:
                        logger.info(f"RUT {rut_formateado}: Interrumpido por Sala de Espera durante el formulario. Reintentando loop...")
                        continue
                    else:
                        raise # Si fue un Timeout real por lentitud y no por Sala de Espera, que actúe Tenacity
            
            # --- ESPERA SEGURA ---
            try:
                # 100% Cierto: El texto 'RUT Contribuyente:' siempre es un nodo de texto en el resultado del SII.
                await page.wait_for_selector("text='RUT Contribuyente:'", timeout=15000)
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
