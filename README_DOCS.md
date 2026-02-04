# Documentación de fases del pipeline

Enlaces a los README de cada fase y documentación relacionada.

## Fases del pipeline
- **Fase 01 — Explore**: [READMEs/README-01_explore.md](READMEs/README-01_explore.md)
  - Exploración y limpieza del dataset RAW
  - Genera dataset intermedio listo para Fase 02

- **Fase 02 — PrepareEventsDS**: [READMEs/README-02_prepareeventsds.md](READMEs/README-02_prepareeventsds.md)
  - Generación del dataset de eventos a partir del dataset explorado
  - Detecta eventos mediante niveles, transiciones o ambas estrategias
  - Genera dataset intermedio listo para Fase 03

- **Fase 03 — PrepareWindowsDS**: [READMEs/README-03_preparewindowsds.md](READMEs/README-03_preparewindowsds.md)
  - Generación del dataset FINAL de ventanas temporales
  - Crea ventanas de observación y predicción materializadas
  - Dataset listo para modelos predictivos

## Documentación adicional
- **Setup del proyecto**: [setup/README-setup.md](READMEs/README-setup.md)
  - Configuración inicial del entorno virtual y dependencias

## Notas importantes
- `dvc.yaml` ha sido movido a `legacy/dvc.yaml` porque la configuración actual no coincide con las rutas de los scripts del repositorio.
- El pipeline sigue un modelo de **variantes**: cada fase puede tener múltiples variantes identificadas como `vNNN`, permitiendo experimentación controlada.
- Las variantes de una fase dependen de variantes padre de la fase anterior (ej.: F02 padre F01).
