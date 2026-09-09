# 🚀 Nubox Data Engineering Take-Home: ETL Pipeline Asíncrono

Este repositorio contiene la resolución del caso práctico para el rol de Data Engineer Semi-Senior. Consiste en un pipeline ETL asíncrono diseñado para extraer datos del Servicio de Impuestos Internos (SII), validarlos, cruzarlos con reglas de negocio (multi-giro) y generar reportes estructurados con alta tolerancia a fallos.

---

## 🏗️ Arquitectura del Pipeline

El pipeline se construyó utilizando **Python 3.13**, `asyncio` para concurrencia, `playwright` para web scraping y `pandas` para el procesamiento tabular de datos. 

### Flujo de Datos (Data Flow):
1. **Validación Temprana (Módulo 11):** Todo RUT de entrada es limpiado (se remueven puntos, espacios, se estandariza el dígito verificador) y validado matemáticamente. Si es inválido, va directo a la *Dead Letter Queue* (Cuarentena).
2. **Extracción (Scraping Asíncrono):** Se consultan múltiples RUTs en paralelo en el portal de terceros del SII. Se utilizan navegadores *headless* (invisibles) orquestados mediante un **Semáforo** para limitar el consumo de memoria RAM.
3. **Transformación (Reglas de Negocio):** Se mapean los códigos extraídos contra un diccionario base. Si existen múltiples giros, se aplica un motor de priorización estricto (`contador` > `pyme` > `otro`).
4. **Carga (Resultados):** Se escriben los datos en dos archivos CSV (`resultados_exitosos.csv` y `cuarentena.csv`), garantizando **Idempotencia** (cada ejecución sobrescribe datos antiguos, sin generar duplicados).

---

## 🛡️ Sistemas Avanzados Implementados

### 1. Asincronía y Concurrencia Controlada
- **`asyncio` + Semáforo:** En lugar de procesar los RUTs secuencialmente, se procesan en ráfagas. Un semáforo (`MAX_CONCURRENCY=3`) restringe que no haya más de 3 navegadores abiertos simultáneamente, evitando el colapso de la memoria RAM del servidor.
- **Rendimiento:** Redujo el tiempo de procesamiento en más de un 60% en pruebas locales (de 54 segundos a ~20 segundos para 12 registros).

### 2. Evasión de WAF (Web Application Firewall) y Rate Limiting
El SII está protegido por *Queue-It* y Cloudflare. Para evadir ser detectados como bots, implementamos:
- **Stealth (`playwright-stealth`):** Oculta la bandera `navigator.webdriver` y enmascara variables del navegador para simular a un usuario humano real.
- **Jitter (Retraso Aleatorio):** Se inyectan esperas aleatorias `asyncio.sleep(random.uniform(0.0, 3.5))` antes de lanzar peticiones concurrentes para evitar que todas lleguen al SII en el mismo milisegundo exacto, lo cual activaría alarmas de DDoS.
- **Retries con Backoff Exponencial (`tenacity`):** Si una red falla temporalmente, el código no crashea. Espera (2s, 4s, 8s) y reintenta de forma automática hasta 3 veces antes de enviarlo a cuarentena.

### 3. Tolerancia a Fallos y DLQ (Dead Letter Queue)
- Si un RUT falla por error de formato, o si el SII bloquea la petición por CAPTCHA, el pipeline **no se detiene**. El registro se aísla automáticamente en un archivo de Cuarentena (incluyendo el motivo del fallo) para revisión manual posterior, permitiendo que el resto del batch de 10.000 RUTs termine con éxito.

### 4. Pruebas Unitarias (TDD)
- Se desarrolló una batería de **41 tests unitarios** con `pytest` que cubren el 100% de la lógica síncrona.
- Casos borde cubiertos: RUTs con dígito K, dígito 0, RUTs inválidos intencionales, escenarios de empate multi-giro, y códigos de actividad económica no mapeados en el diccionario base.

---

## 📖 Glosario Técnico para la Defensa

Si te preguntan por términos específicos durante la entrevista, aquí está el contexto de por qué los usamos:

| Término | Explicación en nuestro código |
|---------|-----------------------------|
| **Idempotencia** | Si corremos el script 5 veces seguidas con el mismo archivo, el resultado será siempre el mismo (mismos archivos CSV, sin datos duplicados concatenados). |
| **Dead Letter Queue (DLQ)** | Es nuestro archivo `cuarentena.csv`. En Data Engineering, la basura o errores no deben botar el pipeline, se envían a una "cola de mensajes muertos" para analizarse luego. |
| **WAF / Rate-Limiting** | Firewall de Aplicaciones Web. El SII nos bloqueó (Timeout / URL `salaespera.sii.cl`) al intentar consultar 20 RUTs en 3 segundos. Nos bloquearon por IP. |
| **Jitter** | La inestabilidad intencional (random sleep) que le pusimos a nuestro código asíncrono para que nuestras peticiones al SII parezcan clicks humanos aleatorios. |
| **Proxy Rotation** | La solución definitiva que propondrías en la entrevista para escalar esto a 10.000 RUTs sin que el WAF bloquee tu IP: Enrutar cada navegador asíncrono a través de IPs residenciales distintas en todo el mundo. |

---

## 🛠️ Cómo Configurar y Ejecutar el Proyecto (Setup Rápido)

Sigue estos pasos para levantar el entorno desde cero en cualquier máquina (Windows / PowerShell):

### 1. Clonar el repositorio
```powershell
git clone https://github.com/BigBoss324/take-home.git
cd take-home
```

### 2. Crear y activar entorno virtual
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Instalar dependencias y navegadores
```powershell
pip install -r requirements.txt
playwright install msedge chromium
```

### 4. Cargar datos de prueba
Coloca tus archivos CSV en la carpeta `inputs/`:
- `inputs/ruts_entrada.csv` (RUTs a consultar)
- `inputs/mapa_rubros.csv` (Catálogo de rubros y prioridades)

*(Nota: La carpeta `inputs/` y `outputs/` están protegidas en `.gitignore` para cumplir con las políticas de privacidad y confidencialidad).*

### 5. Ejecutar Pruebas Unitarias (41 tests)
```powershell
pytest tests/ -v
```
*(Valida en menos de 1 segundo toda la lógica matemática de RUTs y clasificación multi-giro).*

### 6. Ejecutar el Pipeline
```powershell
# Modo headless (óptimo y rápido)
$env:SII_HEADLESS="true"; python main.py

# O con visualización del navegador:
$env:SII_HEADLESS="false"; python main.py
```
Los resultados se generarán automáticamente en `outputs/resultados_exitosos.csv` y los casos aislados en `outputs/cuarentena.csv`.

---

## ⚠️ Registro Histórico de Errores Documentados

Durante el desarrollo simulamos escenarios reales de estrés. A continuación, el comportamiento del sistema ante ellos:

- **Error: `Timeout 30000ms exceeded. waiting for locator("input[name='Consultar']")`**
  - **Causa:** Subimos la concurrencia a `MAX_CONCURRENCY=20`. El WAF del SII detectó un pico de red anómalo desde nuestra IP y nos redirigió a la Sala de Espera virtual (Queue-It).
  - **Solución implementada:** Se integró *Jitter*, *Stealth* y bajamos la concurrencia a `MAX_CONCURRENCY=3`. Para producción a gran escala, se debe anexar Rotación de IPs.
- **Error: `TypeError: 'module' object is not callable`**
  - **Causa:** Conflicto de sintaxis de la librería `playwright-stealth` en Python 3.13.
  - **Solución implementada:** Se reemplazó la invocación como módulo por instanciación de clase `Stealth().apply_stealth_async(page)`.
