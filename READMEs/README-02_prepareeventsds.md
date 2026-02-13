# Fase 02: PrepareEventsDS: Discretización y Eventos

En esta fase transformamos las señales continuas de la Fase 01 (potencias, voltajes, etc.) en un **dataset de eventos discretos**. Cada fila del nuevo dataset representará un instante temporal con los eventos que han ocurrido en él.

> **Prerequisito:** Necesitas haber completado exitosamente una ejecución de Fase 01 (tendrás una variante `vNNN` en `executions/01_explore/`)

## 0. Conceptos clave: De Señales a Eventos

### Discretización en Bandas

Las señales originales (potencia, frecuencia, voltaje) son continuas. Para "digitalizar" su comportamiento, las dividimos en bandas (rangos de valores) usando umbrales.

Si configuramos `BANDS="40 60 90"`, estamos creando 4 zonas:

- **Banda 1:** 0–40%
- **Banda 2:** 40–60%
- **Banda 3:** 60–90%
- **Banda 4:** >90%

Estas bandas son el "diccionario" que nos permite nombrar lo que ocurre en el sistema.

### Tipos de Eventos

Una vez definidas las bandas, el pipeline detecta dos tipos de información en cada instante temporal:

- **Evento de Estado (Level):** Nos dice en qué banda está la señal en ese momento. Ejemplo: `GE_Active_Power_Level_2` (la señal está en el rango 40-60%).
- **Evento de Transición (Transition):** Nos dice si la señal ha saltado de una banda a otra respecto al instante anterior. Ejemplo: `GE_Active_Power_B1-to-B2` (la potencia acaba de subir cruzando el umbral del 40%).

### ¿Cómo luce el dataset final de fase 02?

Cada fila representa un **instante temporal** y puede contener **cero, uno o varios eventos simultáneamente**.

| índice | segs       | events    |
|--------|------------|-----------|
| 2026   | 1651383461 | []        |
| 2027   | 1651383671 | [113,120] |
| 2028   | 1651383691 | [127]     |
| 2029   | 1651383701 | []        |
| 2030   | 1651387711 | []        |
| 2031   | 1651388101 | [129]     |

En la columna `events` se almacenan los identificadores (`event_id`) de los eventos que ocurren en ese instante temporal, que serán guardados en el catálogo de eventos.

## 1. Configuración de Variantes

Una variante de Fase 02 depende directamente de una variante "padre" de la Fase 01. Parte del dataset generado por esta: `executions/01_explore/vNNN/01_explore_dataset.parquet`

```bash
make variant2 VARIANT=v010 PARENT=v001 BANDS="40 60 90" STRATEGY=both NAN=keep
```

### Parámetros

| Parámetro | Descripción | Ejemplo |
|-----------|-------------|---------|
| `VARIANT` | Identificador de la nueva variante (Fase 02) | `v010` |
| `PARENT` | Variante de Fase 01 sobre la que se construye | `v001` o `v002` |
| `BANDS` | Umbrales (%) para discretizar en bandas | `"40 60 90"` |
| `STRATEGY` | Cómo detectar eventos (`levels`, `transitions`, `both`) | `both` |
| `NAN` | Cómo tratar valores nulos (`keep` o `discard`) | `keep` |

El archivo generado `params/02_prepareeventsds/v010/params.yaml` contendrá:

```yaml
parent_variant: v001
bands_thresholds: [40, 60, 90]
strategy: both
nan_handling: keep
```

## 2. Flujo de Trabajo Recomendado

### Paso 1: Inicialización

```bash
make variant2 VARIANT=v011 PARENT=v001 BANDS="10 25 50 75 90" STRATEGY=both NAN=keep
```

### Paso 2: Ejecución

El código reside en `scripts/02_prepareeventsds.py` y el notebook en `notebooks/02_prepareeventsds.ipynb`. Elige tu vía:

**Opción A: Ejecución automática del Notebook**

```bash
make nb2-run VARIANT=v011
```

**Opción B: Ejecución mediante Script (Producción)**

```bash
make script2-run VARIANT=v011
```

**Opción C: Ejecución manual en Notebook**

Abre el notebook y configura la segunda celda:

```python
env_variant = "v011"  # Descomenta y asigna tu variante
```

### Paso 3: Verificación

Asegúrate de que todos los archivos se han generado correctamente:

```bash
make script2-check-results VARIANT=v011
```

## 3. Artefactos Generados (Salidas)

Tras ejecutar la fase, todos los resultados se centralizan en la carpeta de la variante: `executions/02_prepareeventsds/<VARIANT>/`

| Archivo | Contenido |
|---------|-----------|
| `02_prepareeventsds_dataset.parquet` | Dataset final de eventos. Contiene los instantes temporales y los IDs de los eventos detectados. Es el archivo principal para la Fase 03. |
| `02_prepareeventsds_event_catalog.json` | Diccionario de traducción. Mapea cada `event_id` numérico con su nombre legible (ej: 102 → BATT_Power_Level_High). |
| `02_prepareeventsds_report.html` | Informe interactivo con visualizaciones de la frecuencia de eventos, análisis de intervalos entre llegadas y estadísticas de distribución. |
| `02_prepareeventsds_bands.json` | Registro de discretización. Detalla los umbrales específicos aplicados a cada señal para generar las bandas. |
| `02_prepareeventsds_metadata.json` | Metadatos técnicos. Información sobre tiempos de ejecución, volumen de datos procesados y versiones del código. |
| `params.yaml` | Configuración. Copia de los parámetros utilizados (incluyendo el `parent_variant`) para asegurar la trazabilidad. |
| `figures/` | Gráficos. Directorio con las imágenes estáticas generadas durante el análisis. |

