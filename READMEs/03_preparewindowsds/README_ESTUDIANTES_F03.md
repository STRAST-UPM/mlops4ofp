# README — Estudiantes
Fase 03 · PrepareWindowsDS

## ¿Qué es esta fase?

En esta fase se construye el **dataset final** que usarás para entrenar modelos.

Cada fila del dataset corresponde a **una ventana temporal**
y contiene únicamente los eventos:
- observados en el pasado,
- ocurridos después.

No hay tiempos ni índices: solo eventos.

---

## Estructura del dataset

El dataset contiene **dos columnas**:

| Columna   | Contenido |
|-----------|-----------|
| OW_events | Lista de eventos observados |
| PW_events | Lista de eventos a predecir |

Ejemplo de una fila:

```
OW_events = [12, 3, 45, 3, 18]
PW_events = [7, 9]
```

Los números son **códigos de evento**.

---

## Cómo cargar el dataset

```python
import pandas as pd

df = pd.read_parquet("03_preparewindowsds_dataset.parquet")
```

Después podrás acceder a:

```python
df["OW_events"]
df["PW_events"]
```

---

## Cómo usarlo en ML

- `OW_events` → entrada del modelo
- `PW_events` → salida / etiqueta

Cada fila es un ejemplo independiente.

---

## Cosas importantes a tener en cuenta

- Las listas pueden tener longitudes distintas.
- No todos los eventos aparecen en todas las ventanas.
- Los códigos de evento no son consecutivos.

El significado de cada código está en el catálogo de eventos de F02.

---

## Advertencia

Si el dataset contiene columnas como:

```
t0, i_ow_0, i_pw_1, ...
```

entonces **no es el dataset correcto**
y la fase no se ha ejecutado correctamente.
