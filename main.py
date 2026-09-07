import os
import csv
import pandas as pd
import asyncio
import random
from datetime import datetime
try:
    from tqdm.asyncio import tqdm
except ImportError:
    from tqdm import tqdm
import logging
from src.validator import is_valid_rut, clean_rut
from src.scraper import obtener_giros_sii
from src.classifier import RubrosClassifier

# Configuración básica de logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def setup_files(output_dir: str):
    """Crea los archivos de salida con encabezados frescos (idempotencia por corrida)."""
    os.makedirs(output_dir, exist_ok=True)
    
    exitosos_path = os.path.join(output_dir, "resultados_exitosos.csv")
    cuarentena_path = os.path.join(output_dir, "cuarentena.csv")
    
    # Siempre sobrescribimos → cada corrida genera resultados limpios (idempotencia)
    with open(exitosos_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['rut', 'dv', 'familia', 'multi_giro', 'codigo_ganador', 'trazabilidad', 'procesado_en'])
            
    with open(cuarentena_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['rut_raw', 'motivo_fallo', 'procesado_en'])
            
    return exitosos_path, cuarentena_path

async def procesar_rut(rut_raw, classifier, exitosos_path, cuarentena_path, semaphore):
    # JITTER: Retraso aleatorio (0 a 3.5 segundos) antes de intentar entrar al semáforo
    # Esto desincroniza las ráfagas para que los navegadores no golpeen al SII en el mismo milisegundo exacto
    await asyncio.sleep(random.uniform(0.0, 3.5))
    
    async with semaphore:
        try:
            # 1. Validación (Filtra la basura rápido de la Cuarentena)
            if not is_valid_rut(str(rut_raw)):
                with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, "RUT Inválido (Fallo Módulo 11 o formato)", datetime.now().isoformat()])
                return
                
            rut_clean = clean_rut(str(rut_raw))
            rut_formateado = f"{rut_clean[:-1]}-{rut_clean[-1]}"
            
            # 2. Extracción Web
            try:
                giros = await obtener_giros_sii(rut_formateado)
            except Exception as e:
                # Regla de Oro: El Batch no se cae. Mandamos a cuarentena y sigue.
                with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, f"Fallo extracción (Posible Captcha/Timeout SII)", datetime.now().isoformat()])
                return
                
            # 3. Clasificación
            resultado = classifier.get_tipologia(giros)
            
            # 4. Persistencia en Resultados
            with open(exitosos_path, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([
                    rut_clean[:-1], # Cuerpo
                    rut_clean[-1],  # DV
                    resultado['familia'],
                    resultado['multi_giro'],
                    resultado['codigo_ganador'],
                    resultado['motivo'],
                    datetime.now().isoformat(),
                ])
                
        except Exception as e:
             # Cualquier otro bug grave a nivel registro
             with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, f"Error Inesperado: {str(e)}", datetime.now().isoformat()])
             logging.error(f"Error procesando {rut_raw}: {e}")

async def procesar_lote():
    input_file = "inputs/ruts_entrada.csv"
    mapa_file = "inputs/mapa_rubros.csv"
    output_dir = "outputs/"
    
    # Inicia motor de negocio
    classifier = RubrosClassifier(mapa_file)
    exitosos_path, cuarentena_path = setup_files(output_dir)
    
    # Leer input
    df_ruts = pd.read_csv(input_file)
    col_name = df_ruts.columns[0] # Usualmente 'rut'
    ruts_raw = df_ruts[col_name].dropna().tolist()
    ruts_a_procesar = list(dict.fromkeys(str(r) for r in ruts_raw))  # Dedup preservando orden
    
    logging.info(f"Procesando batch de {len(ruts_a_procesar)} RUTs únicos (de {len(ruts_raw)} entradas)...")
    
    # Máximo de navegadores concurrentes. configurable por variable de entorno (por defecto 20 para lotes chicos).
    max_concurrency = int(os.getenv('MAX_CONCURRENCY', '20'))
    semaphore = asyncio.Semaphore(max_concurrency)
    
    tasks = [
        procesar_rut(rut_raw, classifier, exitosos_path, cuarentena_path, semaphore)
        for rut_raw in ruts_a_procesar
    ]
    
    # tqdm wrapper para asyncio.gather
    if hasattr(tqdm, 'gather'):
        await tqdm.gather(*tasks, desc="ETL Pipeline Asíncrono")
    else:
        # Fallback if tqdm.asyncio is not available
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(procesar_lote())
    print("\nProcesamiento Batch completado. Revisa la carpeta outputs/.")
