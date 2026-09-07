# Diccionario de Datos - Clasificador de RUTs Nubox

Este documento describe la estructura y semántica de los datos generados por el pipeline local.

---

## Tabla: `resultados_exitosos.csv`

| Campo | Valor |
|-------|-------|
| **Capa** | Silver / Gold (Clasificados listos para el consumo) |
| **Formato** | CSV (Codificación UTF-8) |
| **Grano** | 1 fila por RUT válido analizado por corrida. |
| **Clave natural** | `rut` |
| **Idempotencia** | Actualmente *append-only* en batch mode local. Para idempotencia estricta en producción se recomienda hacer "Upsert" borrando la llave `rut` antes de insertar una re-corrida, o añadir `execution_ds` al esquema particionado. |
| **Origen** | Derivado. Cruce dinámico entre `mapa_rubros.csv` y portal público SII. |

### Columnas

| nombre | tipo | nullable | descripción | reglas / ejemplos |
|--------|------|----------|-------------|-------------------|
| rut | string | no | Cuerpo del RUT (sin puntos ni guiones) | Ej. `10444555` |
| dv | string | no | Dígito Verificador del RUT (Módulo 11) | Ej. `K` o `2` |
| familia | string | no | Clasificación final de negocio | Valores: `contador`, `pyme`, `otro / sin_clasificar` |
| multi_giro | bool | no | Indica si el contribuyente poseía 2 o más giros en el SII. | `True` o `False` |
| codigo_ganador | integer | sí | Código de actividad del SII que definió la tipología (por mínima prioridad). | Ej. `692000`, `None` si no hubo giros validados. |
| trazabilidad | string | no | Motivo textual de cómo se asignó la familia. | Ej. `Regla Prioridad (1)` |

---

## Tabla: `cuarentena.csv`

| Campo | Valor |
|-------|-------|
| **Capa** | Cuarentena (Dead Letter Queue) |
| **Formato** | CSV (Codificación UTF-8) |
| **Grano** | 1 fila por RUT fallido analizado. |
| **Clave natural** | `rut_raw` + `timestamp` (técnicamente append sequential). |
| **Idempotencia** | Append-only. Los fallos pueden reprocesarse tomando este archivo como Input. |
| **Origen** | Excepciones capturadas durante la extracción o validación. |

### Columnas

| nombre | tipo | nullable | descripción | reglas / ejemplos |
|--------|------|----------|-------------|-------------------|
| rut_raw | string | no | El input literal (sucio) que falló en procesarse. | Puede venir con errores de formato del CSV origen. |
| motivo_fallo | string | no | Causa raíz aislada de por qué el RUT falló el ETL. | `RUT Inválido`, `Fallo extracción (Posible Captcha/Timeout SII)`. |

### Calidad de datos y Comportamiento de Manejo de Errores

| Check | Acción si falla |
|-------|-----------------|
| **RUT inválido (formato/Mód. 11)** | No envía requests al SII (evita rate limits inútiles). Va directo a `cuarentena.csv` |
| **Sin actividades en SII** | Registra como `otro / sin_clasificar` |
| **Código no mapeado en CSV** | Registra como `otro / sin_clasificar` y setea `codigo_ganador` al giro sin mapear dominante (documentado) |
| **Excepción durante Scraping (Captcha/Timeout)** | Try/Catch en módulo `scraper.py`. Falla de forma aislada e inserta en `cuarentena.csv`. *El batch continúa ejecutándose*. |
| **Duplicados** | El script actual confía en la unicidad del dataset de entrada para optimizar memoria local. |

### Notas / decisiones de diseño

- **Por qué validamos antes del scrapeo:** Múltiples RUTs corruptos son intencionales (*edge cases*). Realizar *hits* HTTP para validarlo quema ancho de banda y aumenta riesgo de baneos de IP.
- **Cuarentena en Caliente:** Usamos modo escritura *append* transaccional (registro a registro). Si la máquina se apaga a mitad del batch, ningún registro exitoso procesado se pierde de disco. No se tumba el batch entero por 1 error (cumpliendo con la restricción "Evita esto" de los diapositivos).
