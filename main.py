import os
import csv
import pandas as pd
from tqdm import tqdm
import logging
from src.validator import is_valid_rut, clean_rut
from src.scraper import obtener_giros_sii
from src.classifier import RubrosClassifier

# Configuración básica de logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def setup_files(output_dir: str):
    """Crea los encabezados de los archivos DWH/Resultados si no existen."""
    os.makedirs(output_dir, exist_ok=True)
    
    exitosos_path = os.path.join(output_dir, "resultados_exitosos.csv")
    cuarentena_path = os.path.join(output_dir, "cuarentena.csv")
    
    if not os.path.exists(exitosos_path):
        with open(exitosos_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['rut', 'dv', 'familia', 'multi_giro', 'codigo_ganador', 'trazabilidad'])
            
    if not os.path.exists(cuarentena_path):
        with open(cuarentena_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['rut_raw', 'motivo_fallo'])
            
    return exitosos_path, cuarentena_path

def procesar_lote():
    input_file = "inputs/ruts_entrada.csv"
    mapa_file = "inputs/mapa_rubros.csv"
    output_dir = "outputs/"
    
    # Inicia motor de negocio
    classifier = RubrosClassifier(mapa_file)
    exitosos_path, cuarentena_path = setup_files(output_dir)
    
    # Leer input
    df_ruts = pd.read_csv(input_file)
    col_name = df_ruts.columns[0] # Usualmente 'rut'
    ruts_a_procesar = df_ruts[col_name].dropna().tolist()
    
    logging.info(f"Procesando batch de {len(ruts_a_procesar)} RUTs...")
    
    for rut_raw in tqdm(ruts_a_procesar, desc="ETL Pipeline"):
        try:
            # 1. Validación (Filtra la basura rápido de la Cuarentena)
            if not is_valid_rut(str(rut_raw)):
                with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, "RUT Inválido (Fallo Módulo 11 o formato)"])
                continue
                
            rut_clean = clean_rut(str(rut_raw))
            rut_formateado = f"{rut_clean[:-1]}-{rut_clean[-1]}"
            
            # 2. Extracción Web
            try:
                giros = obtener_giros_sii(rut_formateado)
            except Exception as e:
                # Regla de Oro: El Batch no se cae. Mandamos a cuarentena y sigue.
                with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, f"Fallo extracción (Posible Captcha/Timeout SII)"])
                continue
                
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
                    resultado['motivo']
                ])
                
        except Exception as e:
             # Cualquier otro bug grave a nivel registro
             with open(cuarentena_path, 'a', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerow([rut_raw, f"Error Inesperado: {str(e)}"])
             logging.error(f"Error procesando {rut_raw}: {e}")

if __name__ == "__main__":
    procesar_lote()
    print("\nProcesamiento Batch completado. Revisa la carpeta outputs/.")
