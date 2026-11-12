# Vortante

Editor de texto sencillo para escribir en esperanto.

- Caracteres especiales (botones y atajos Alt: Alt+C → ĉ, Alt+G → ĝ, Alt+H → ĥ, Alt+J → ĵ, Alt+S → ŝ, Alt+U → ŭ).
- Búsqueda con el botón derecho: definiciones, traducciones y conjugaciones de verbos.
- Panel de sugerencias: subraya palabras mal escritas y explica formas verbales y matices.
- Formato (negrita, cursiva, subrayado, tipo y tamaño de letra), alineación y exportación a PDF.
- Pestaña de gramática, paletas de colores y modo claro/oscuro.

## Requisitos

- Windows 10 u 11
- Python 3.10 o superior
- PySide6 (`pip install -r requirements.txt`)

## Uso

```
pip install -r requirements.txt
python main.py
```

## Datos

- Diccionario de esperanto: [kaikki.org](https://kaikki.org), extraído de Wiktionary.
- Traducciones al castellano: diccionario eo-es de [aulex.org](https://aulex.org/eo-es/) y traducciones propias.
- Los scripts de `tools/` regeneran la base de datos `data/diccionario.db`.

## Autoría

Desarrollado por Álvaro Aliste.
