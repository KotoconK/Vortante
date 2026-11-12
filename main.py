"""Editor de texto para escribir en esperanto.

Ventana con formato, caracteres especiales (botones y atajos Alt), búsqueda con clic derecho,
conjugaciones, panel de sugerencias con palabras mal escritas, pestaña de gramática,
ayuda y configuración.
"""
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QSettings, QTimer, QUrl
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QTextCharFormat,
                           QTextCursor)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from analisis import Analizador

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "diccionario.db"
TEORIA = BASE / "theory" / "gramatica.html"

ESPERANTO_CHARS = ["ĉ", "ĝ", "ĥ", "ĵ", "ŝ", "ŭ", "Ĉ", "Ĝ", "Ĥ", "Ĵ", "Ŝ", "Ŭ"]

# Atajos Alt: tecla → letra base → carácter con acento
MAPA_ALT = {Qt.Key_C: "c", Qt.Key_G: "g", Qt.Key_H: "h",
            Qt.Key_J: "j", Qt.Key_S: "s", Qt.Key_U: "u"}
ACENTO = {"c": "ĉ", "g": "ĝ", "h": "ĥ", "j": "ĵ", "s": "ŝ", "u": "ŭ"}

# ---------- Paletas ----------
PALETAS = {
    "Terracota": {"accent": "#E0702C", "accent_dark": "#B5532A", "accent_soft": "#F6D9C6",
                  "bg": "#F4F1EC", "panel": "#E9E3DB", "card": "#FBF9F6", "border": "#D9CFC4",
                  "text": "#3E3833", "muted": "#8A817C", "green": "#6B8F4E"},
    "Salvia": {"accent": "#7E9A5B", "accent_dark": "#56703A", "accent_soft": "#DDE5C8",
               "bg": "#F3F1E7", "panel": "#E2DCCB", "card": "#FAF9F3", "border": "#CFC6B2",
               "text": "#363A2E", "muted": "#7F8170", "green": "#56703A"},
    "Malva": {"accent": "#B4608C", "accent_dark": "#8E4670", "accent_soft": "#F4D6E3",
              "bg": "#FBF0E8", "panel": "#F1DCCB", "card": "#FDF8F4", "border": "#E6CDBB",
              "text": "#3F2E37", "muted": "#8F7682", "green": "#7C8F5E"},
    "Cielo": {"accent": "#5F86B0", "accent_dark": "#3F6289", "accent_soft": "#D2E0EE",
              "bg": "#F5F3E4", "panel": "#E4E9D8", "card": "#FBFAF2", "border": "#CDD5C2",
              "text": "#2F3A45", "muted": "#7A8593", "green": "#7DA06A"},
}
DARK_BG = "#2D2927"
DARK_TEXT = "#ECE5DE"
COLOR_ERROR = "#C0392B"


def mezclar(c1: str, c2: str, t: float) -> str:
    """Mezcla dos colores hex. t=0 es c1, t=1 es c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    m = [round(x + (y - x) * t) for x, y in zip(a, b)]
    return "#{:02X}{:02X}{:02X}".format(*m)


def tokens(paleta: str, modo: str) -> dict:
    p = PALETAS[paleta]
    if modo == "oscuro":
        return {
            "bg": DARK_BG, "panel": "#383331", "card": "#413B38", "border": "#554C48",
            "text": DARK_TEXT, "muted": "#A89D95",
            "accent": p["accent"],
            "accent_dark": mezclar(p["accent"], DARK_TEXT, 0.25),
            "accent_soft": mezclar(p["accent"], DARK_BG, 0.45),
            "green": mezclar(p["green"], DARK_TEXT, 0.2),
        }
    return {k: p[k] for k in ("bg", "panel", "card", "border", "text", "muted",
                              "accent", "accent_dark", "accent_soft", "green")}


def estilo(t: dict) -> str:
    return f"""
QMainWindow, QWidget {{ background: {t['bg']}; color: {t['text']};
    font-family: "Segoe UI", sans-serif; font-size: 10pt; }}
QToolBar {{ background: {t['panel']}; border: none; spacing: 6px; padding: 6px; }}
QWidget#caracteres {{ background: {t['panel']}; border-top: 1px solid {t['border']}; }}
QPushButton, QToolButton {{
    background: {t['card']}; border: 1px solid {t['border']}; border-radius: 14px;
    padding: 5px 12px; color: {t['text']}; }}
QPushButton:hover, QToolButton:hover {{ background: {t['accent_soft']}; border-color: {t['accent']}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {t['accent']}; color: {t['bg']}; }}
QPushButton#eo {{ min-width: 30px; border-radius: 16px; font-weight: bold; color: {t['accent_dark']}; }}
QToolButton:checked {{ background: {t['accent']}; color: {t['bg']}; border-color: {t['accent']}; }}
QToolButton#menu {{ font-size: 12pt; padding: 0px 8px; border: none; background: transparent;
    color: {t['muted']}; border-radius: 12px; }}
QToolButton#menu:hover {{ background: {t['accent_soft']}; color: {t['text']}; }}
QPushButton#tam {{ padding: 2px 0px; border-radius: 12px; font-weight: bold; }}
QToolButton#flecha {{ padding: 2px 10px; border-radius: 12px; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}
QTextEdit, QTextBrowser {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 14px; padding: 10px; selection-background-color: {t['accent_soft']}; }}
QComboBox, QSpinBox {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 12px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {t['card']}; color: {t['text']}; border-radius: 10px;
    selection-background-color: {t['accent_soft']}; }}
QCheckBox {{ spacing: 8px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {t['panel']}; border-radius: 12px; padding: 7px 16px;
    margin: 4px 3px; color: {t['text']}; }}
QTabBar::tab:selected {{ background: {t['accent']}; color: {t['bg']}; }}
QTabBar::tab:hover:!selected {{ background: {t['accent_soft']}; }}
QMenu {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 8px; color: {t['text']}; }}
QMenu::item:selected {{ background: {t['accent_soft']}; }}
QMenu::item:disabled {{ color: {mezclar(t['accent'], t['card'], 0.45)}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 5px 8px; }}
QDockWidget {{ color: {t['text']}; }}
QListWidget {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 12px; padding: 6px; }}
QListWidget::item {{ padding: 8px; border-radius: 8px; margin: 2px; }}
QListWidget::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
QListWidget::item:hover {{ background: {t['accent_soft']}; }}
QLabel#titulo {{ font-size: 15pt; font-weight: bold; color: {t['accent_dark']}; }}
QLabel#nota {{ color: {t['muted']}; }}
QLabel#estado {{ color: {t['muted']}; background: transparent; padding-right: 6px; }}
"""


def html_con_tema(texto: str, t: dict) -> str:
    """Cambia los colores fijos de un HTML de ejemplo por los del tema actual."""
    cambios = {
        "#fff8f0": t["bg"], "background: #fff;": f"background: {t['card']};",
        "#3d2b1f": t["text"], "#b5532a": t["accent_dark"], "#6b8f4e": t["green"],
        "#f0d9c4": t["border"], "#fbe9dc": t["panel"], "#8a3b1a": t["accent_dark"],
        "#7a6558": t["muted"],
    }
    for viejo, nuevo in cambios.items():
        texto = texto.replace(viejo, nuevo)
    return texto


def ayuda_html(t: dict) -> str:
    return f"""
<html><body style="font-family:'Segoe UI'; color:{t['text']}; background:{t['card']}; line-height:1.55;">
<h2 style="color:{t['accent_dark']};">Vortante</h2>
<p>Un editor de texto sencillo pensado para escribir en esperanto sin salir del flujo.
Mientras escribes puedes consultar palabras con el botón derecho y elegir la traducción.</p>

<h3 style="color:{t['green']};">Cómo se usa</h3>
<ul>
<li><b>Caracteres especiales.</b> La barra inferior inserta ĉ, ĝ, ĥ, ĵ, ŝ, ŭ y sus mayúsculas.
Con la flecha de esa barra la puedes ocultar o mostrar.</li>
<li><b>Atajos con Alt.</b> Si lo activas en Configuración, Alt+C escribe ĉ y Alt+Mayús+C escribe Ĉ.
Lo mismo con G, H, J, S y U.</li>
<li><b>Buscar una palabra.</b> Pulsa el botón derecho sobre una palabra (o selecciónala). Si está en castellano,
verás sus equivalentes en esperanto: pulsa uno y la palabra se sustituye.</li>
<li><b>Conjugaciones.</b> Reconoce los tiempos principales de unos 30 verbos y las formas en plural y acusativo.</li>
<li><b>Sugerencias.</b> El panel lateral subraya las palabras mal escritas (en rojo) y muestra notas de matiz.
Pulsa una sugerencia para aplicarla.</li>
<li><b>Gramática.</b> La pestaña Gramática explica terminaciones, verbos, pronombres, preguntas y formación de palabras.</li>
<li><b>Formato.</b> Negrita, cursiva, subrayado, tipo de letra y tamaño, con los botones − y + junto al tamaño.</li>
<li><b>Alineación.</b> Izquierda, centro, derecha o justificado, por párrafo.</li>
<li><b>PDF.</b> El botón PDF guarda el documento tal como lo ves.</li>
</ul>

<h3 style="color:{t['green']};">De dónde salen los datos</h3>
<ul>
<li>Diccionario de esperanto: kaikki.org, extraído de Wiktionary.</li>
<li>Traducciones al castellano: diccionario eo-es de aulex.org y traducciones propias.</li>
</ul>

<h3 style="color:{t['green']};">Autoría</h3>
<p>Desarrollado por <b>Álvaro Aliste</b>.</p>
</body></html>
"""


# ---------- Diccionario ----------

CATEGORIAS = {
    "noun": "sustantivo", "verb": "verbo", "adj": "adjetivo", "adv": "adverbio",
    "intj": "interjección", "prep": "preposición", "pron": "pronombre",
    "conj": "conjunción", "num": "numeral", "name": "nombre propio",
    "prefix": "prefijo", "suffix": "sufijo", "particle": "partícula",
    "det": "determinante", "phrase": "expresión", "proverb": "refrán",
    "affix": "afijo", "punct": "puntuación", "article": "artículo",
}


def _conectar():
    if not DB.exists():
        return None
    return sqlite3.connect(DB)


def _registrar_no_encontrada(con, palabra):
    con.execute(
        """CREATE TABLE IF NOT EXISTS no_encontradas (
               palabra TEXT PRIMARY KEY,
               veces   INTEGER DEFAULT 0,
               ultima  TEXT)"""
    )
    con.execute(
        """INSERT INTO no_encontradas (palabra, veces, ultima) VALUES (?, 1, datetime('now'))
           ON CONFLICT(palabra) DO UPDATE SET veces = veces + 1, ultima = datetime('now')""",
        (palabra,),
    )
    con.commit()


# ---------- Conjugaciones y formas ----------

PERSONAS = ["yo", "tú", "él / ella / usted", "nosotros", "ellos / ustedes"]

# Verbos irregulares frecuentes: presente de indicativo
VERBOS_IRREGULARES = {
    "querer": ["quiero", "quieres", "quiere", "queremos", "quieren"],
    "poder": ["puedo", "puedes", "puede", "podemos", "pueden"],
    "tener": ["tengo", "tienes", "tiene", "tenemos", "tienen"],
    "venir": ["vengo", "vienes", "viene", "venimos", "vienen"],
    "ir": ["voy", "vas", "va", "vamos", "van"],
    "ser": ["soy", "eres", "es", "somos", "son"],
    "estar": ["estoy", "estás", "está", "estamos", "están"],
    "hacer": ["hago", "haces", "hace", "hacemos", "hacen"],
    "decir": ["digo", "dices", "dice", "decimos", "dicen"],
    "ver": ["veo", "ves", "ve", "vemos", "ven"],
    "saber": ["sé", "sabes", "sabe", "sabemos", "saben"],
    "dar": ["doy", "das", "da", "damos", "dan"],
    "entender": ["entiendo", "entiendes", "entiende", "entendemos", "entienden"],
    "volver": ["vuelvo", "vuelves", "vuelve", "volvemos", "vuelven"],
    "poner": ["pongo", "pones", "pone", "ponemos", "ponen"],
    "salir": ["salgo", "sales", "sale", "salimos", "salen"],
    "traer": ["traigo", "traes", "trae", "traemos", "traen"],
}

# Verbos regulares frecuentes (se conjugan a partir de la raíz)
VERBOS_REGULARES = [
    "hablar", "trabajar", "estudiar", "necesitar", "llamar", "escuchar", "mirar",
    "comprar", "tomar", "llegar", "cantar", "bailar", "jugar", "preguntar", "usar",
    "buscar", "encontrar", "pagar", "comer", "beber", "aprender", "comprender",
    "correr", "leer", "escribir", "vivir", "abrir", "responder", "pensar", "creer",
]

PRETERITO_IRREG = {
    "querer": ["quise", "quisiste", "quiso", "quisimos", "quisieron"],
    "poder": ["pude", "pudiste", "pudo", "pudimos", "pudieron"],
    "tener": ["tuve", "tuviste", "tuvo", "tuvimos", "tuvieron"],
    "venir": ["vine", "viniste", "vino", "vinimos", "vinieron"],
    "hacer": ["hice", "hiciste", "hizo", "hicimos", "hicieron"],
    "decir": ["dije", "dijiste", "dijo", "dijimos", "dijeron"],
    "ir": ["fui", "fuiste", "fue", "fuimos", "fueron"],
    "ser": ["fui", "fuiste", "fue", "fuimos", "fueron"],
    "estar": ["estuve", "estuviste", "estuvo", "estuvimos", "estuvieron"],
    "saber": ["supe", "supiste", "supo", "supimos", "supieron"],
    "dar": ["di", "diste", "dio", "dimos", "dieron"],
    "poner": ["puse", "pusiste", "puso", "pusimos", "pusieron"],
    "ver": ["vi", "viste", "vio", "vimos", "vieron"],
    "traer": ["traje", "trajiste", "trajo", "trajimos", "trajeron"],
}
IMPERFECTO_IRREG = {
    "ser": ["era", "eras", "era", "éramos", "eran"],
    "ir": ["iba", "ibas", "iba", "íbamos", "iban"],
    "ver": ["veía", "veías", "veía", "veíamos", "veían"],
}
# Futuro y condicional se forman sobre una raíz; estas son las irregulares
FUTURO_RAIZ_IRREG = {
    "querer": "querr", "poder": "podr", "tener": "tendr", "venir": "vendr",
    "hacer": "har", "decir": "dir", "saber": "sabr", "poner": "pondr",
    "salir": "saldr", "valer": "valdr", "haber": "habr",
}
DESINENCIAS_PRES = {"ar": ["o", "as", "a", "amos", "an"],
                    "er": ["o", "es", "e", "emos", "en"],
                    "ir": ["o", "es", "e", "imos", "en"]}
DESINENCIAS_PRET = {"ar": ["é", "aste", "ó", "amos", "aron"],
                    "er": ["í", "iste", "ió", "imos", "ieron"],
                    "ir": ["í", "iste", "ió", "imos", "ieron"]}
DESINENCIAS_IMP = {"ar": ["aba", "abas", "aba", "ábamos", "aban"],
                   "er": ["ía", "ías", "ía", "íamos", "ían"],
                   "ir": ["ía", "ías", "ía", "íamos", "ían"]}
DESINENCIAS_FUT = ["é", "ás", "á", "emos", "án"]
DESINENCIAS_COND = ["ía", "ías", "ía", "íamos", "ían"]

# Terminaciones verbales del esperanto
EO_VERBO = [("as", "presente"), ("is", "pasado"), ("os", "futuro"),
            ("us", "condicional"), ("u", "imperativo")]
# Plural, acusativo y plural del acusativo
EO_FORMAS = [("ajn", "plural y acusativo"), ("aj", "plural"), ("jn", "plural y acusativo"),
             ("j", "plural"), ("n", "acusativo")]


def _normalizar(s: str) -> str:
    """Quita acentos y pasa a minúsculas, para comparar formas sin tildes."""
    sin = "".join(c for c in unicodedata.normalize("NFD", s)
                  if unicodedata.category(c) != "Mn")
    return sin.lower()


def _construir_formas_es():
    """Devuelve {forma_sin_tilde: (infinitivo, tiempo, persona, terminacion_eo)}."""
    formas = {}

    def add(forma, inf, tiempo, pers, eo_fin):
        formas.setdefault(_normalizar(forma), (inf, tiempo, pers, eo_fin))

    todos = sorted(set(VERBOS_IRREGULARES) | set(VERBOS_REGULARES))
    for inf in todos:
        raiz, fin = inf[:-2], inf[-2:]
        pres = VERBOS_IRREGULARES.get(inf) or [raiz + d for d in DESINENCIAS_PRES[fin]]
        for p, f in zip(PERSONAS, pres):
            add(f, inf, "presente", p, "as")

        pret = PRETERITO_IRREG.get(inf) or [raiz + d for d in DESINENCIAS_PRET[fin]]
        for p, f in zip(PERSONAS, pret):
            add(f, inf, "pretérito", p, "is")

        imp = IMPERFECTO_IRREG.get(inf) or [raiz + d for d in DESINENCIAS_IMP[fin]]
        for p, f in zip(PERSONAS, imp):
            add(f, inf, "imperfecto", p, "is")

        rf = FUTURO_RAIZ_IRREG.get(inf, inf)
        for p, d in zip(PERSONAS, DESINENCIAS_FUT):
            add(rf + d, inf, "futuro", p, "os")
        for p, d in zip(PERSONAS, DESINENCIAS_COND):
            add(rf + d, inf, "condicional", p, "us")
    return formas


FORMAS_ES = _construir_formas_es()


def _existe_eo(con, palabra):
    return con.execute("SELECT 1 FROM entradas WHERE eo_norm = ? LIMIT 1",
                       (palabra,)).fetchone() is not None


def _traducciones_eo(con, eo):
    trad = [r[0] for r in con.execute(
        "SELECT es_norm FROM es_a_eo_propio WHERE eo = ?", (eo,))]
    for (es,) in con.execute("SELECT es FROM entradas WHERE eo_norm = ?", (eo,)):
        for parte in (es or "").split(";"):
            p = parte.strip().lower()
            if p and p not in trad:
                trad.append(p)
    return trad


def _analizar_eo(con, w):
    """Si w es una forma flexionada en esperanto, devuelve (lema, descripción)."""
    for fin, tiempo in EO_VERBO:
        if w.endswith(fin) and len(w) > len(fin) + 1:
            inf = w[:-len(fin)] + "i"
            if _existe_eo(con, inf):
                return inf, f"forma verbal ({tiempo}) de «{inf}»"
    for fin, tipo in EO_FORMAS:
        if w.endswith(fin) and len(w) > len(fin) + 1:
            base = w[:-len(fin)]
            for cand in (base + "o", base + "a", base + "e", base):
                if _existe_eo(con, cand):
                    return cand, f"{tipo} de «{cand}»"
    return None


def consultar2(texto: str):
    """Devuelve (titulo, informacion, opciones), todo en castellano."""
    limpio = re.sub(r"[^\wĈĉĜĝĤĥĴĵŜŝŬŭ' -]", "", texto).strip().lower()
    if not limpio:
        return None, [], []
    if " " in limpio:
        return None, ["Traducción de frases: pendiente (fase 2)"], []

    con = _conectar()
    if con is None:
        return None, ["No encuentro data/diccionario.db"], []
    try:
        titulo, info, opciones = None, [], []

        # 1) Palabra en esperanto con entrada propia
        if _existe_eo(con, limpio):
            cat = con.execute(
                "SELECT categoria FROM entradas WHERE eo_norm = ? AND categoria IS NOT NULL LIMIT 1",
                (limpio,)).fetchone()
            if cat:
                info.append(f"Categoría: {CATEGORIAS.get(cat[0], cat[0])}")
            trad = _traducciones_eo(con, limpio)
            info.append("Castellano: " + ", ".join(trad) if trad
                        else "Sin traducción al castellano todavía")
            titulo = "Definición"

        # 2) Palabra en castellano con traducciones
        opciones = [r[0] for r in con.execute(
            "SELECT eo FROM es_a_eo_propio WHERE es_norm = ? ORDER BY eo", (limpio,))]
        if opciones:
            titulo = "Traducción"

        # 3) Forma flexionada en esperanto (volas, hundon, grandaj…)
        if not info and not opciones:
            forma = _analizar_eo(con, limpio)
            if forma:
                lema, desc = forma
                info.append(desc.capitalize())
                trad = _traducciones_eo(con, lema)
                info.append("Castellano: " + ", ".join(trad) if trad
                            else "Sin traducción al castellano todavía")
                titulo = "Definición"

        # 4) Forma conjugada en castellano (querré, puedo, fueron…)
        clave = _normalizar(limpio)
        if not info and not opciones and clave in FORMAS_ES:
            inf, tiempo, pers, fin_eo = FORMAS_ES[clave]
            infinitivos = [r[0] for r in con.execute(
                "SELECT eo FROM es_a_eo_propio WHERE es_norm = ? ORDER BY eo", (inf,))]
            titulo = "Conjugación"
            info.append(f"Verbo: {inf}")
            info.append(f"Tiempo: {tiempo} ({pers})")
            if infinitivos:
                info.append("En esperanto: " + " / ".join(infinitivos))
                # En esperanto el tiempo se marca con la terminación: voli → volos (futuro)
                opciones = [v[:-1] + fin_eo for v in infinitivos if v.endswith("i")]
            else:
                info.append(f"«{inf}» sin traducción todavía")

        if not info and not opciones:
            _registrar_no_encontrada(con, limpio)
            return None, [f"No encontrada: {limpio}"], []
        return titulo, info, opciones
    finally:
        con.close()


def cargar_analizador():
    """Carga las palabras conocidas una sola vez para el análisis del texto."""
    con = _conectar()
    if con is None:
        return Analizador(set(), set(), FORMAS_ES, {})
    try:
        eo = {r[0] for r in con.execute("SELECT eo_norm FROM entradas")}
        try:
            es = {r[0] for r in con.execute("SELECT es_norm FROM es_a_eo_propio")}
        except sqlite3.OperationalError:
            es = set()
        trad = {}
        try:
            for eo_w, es_w in con.execute("SELECT eo, es_norm FROM es_a_eo_propio"):
                trad.setdefault(eo_w, []).append(es_w)
        except sqlite3.OperationalError:
            pass
        return Analizador(eo, es, FORMAS_ES, trad)
    finally:
        con.close()


# ---------- Editor ----------

def _abrir_glosbe(direccion: str, texto: str):
    """Abre Glosbe con la palabra o la frase. direccion: 'eo/es' o 'es/eo'."""
    url = f"https://es.glosbe.com/{direccion}/{quote(texto, safe='')}"
    QDesktopServices.openUrl(QUrl(url))


class Editor(QTextEdit):
    """QTextEdit con búsqueda en el menú contextual, sustitución y atajos Alt."""

    atajos_eo = False

    def keyPressEvent(self, event):
        if self.atajos_eo and (event.modifiers() & Qt.AltModifier) and event.key() in MAPA_ALT:
            letra = ACENTO[MAPA_ALT[event.key()]]
            if event.modifiers() & Qt.ShiftModifier:
                letra = letra.upper()
            self.insertPlainText(letra)
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()

        cursor = self.cursorForPosition(event.pos())
        sel = self.textCursor()
        if sel.hasSelection() and sel.selectionStart() <= cursor.position() <= sel.selectionEnd():
            cursor = sel
        else:
            cursor.select(QTextCursor.WordUnderCursor)

        texto = cursor.selectedText().replace(" ", " ").strip()
        titulo, info, opciones = consultar2(texto)

        primera = menu.actions()[0] if menu.actions() else None
        bloque = []
        if titulo:
            # La cabecera abre Glosbe: en castellano (es/eo) o en esperanto (eo/es)
            cab = QAction(f"{titulo}  ↗ ver en Glosbe", menu)
            direccion = "es/eo" if titulo in ("Traducción", "Conjugación") else "eo/es"
            cab.triggered.connect(lambda _=False, d=direccion, t=texto: _abrir_glosbe(d, t))
            bloque.append(cab)
        for linea in info:
            accion = QAction(linea, menu)
            accion.setEnabled(False)
            bloque.append(accion)
        for opcion in opciones:
            accion = QAction(opcion, menu)
            accion.triggered.connect(
                lambda _=False, o=opcion, c=QTextCursor(cursor), t=texto:
                self._sustituir(c, o, t)
            )
            bloque.append(accion)
        if texto and " " in texto:
            ver = QAction("Ver frase en Glosbe ↗", menu)
            ver.triggered.connect(lambda _=False, t=texto: _abrir_glosbe("eo/es", t))
            bloque.append(ver)

        if bloque:
            for accion in reversed(bloque):
                menu.insertAction(primera, accion)
            menu.insertSeparator(primera)

        menu.exec(event.globalPos())

    def _sustituir(self, cursor: QTextCursor, opcion: str, original: str):
        if original[:1].isupper():
            opcion = opcion[:1].upper() + opcion[1:]
        cursor.insertText(opcion)
        self.setTextCursor(cursor)


# ---------- Diálogos ----------

class AyudaDialog(QDialog):
    def __init__(self, parent, t: dict):
        super().__init__(parent)
        self.setWindowTitle("Ayuda")
        self.resize(580, 660)
        lay = QVBoxLayout(self)
        navegador = QTextBrowser()
        navegador.setOpenExternalLinks(True)
        navegador.setHtml(ayuda_html(t))
        lay.addWidget(navegador)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        lay.addWidget(cerrar, alignment=Qt.AlignRight)


class ConfigDialog(QDialog):
    def __init__(self, ventana: "EditorWindow"):
        super().__init__(ventana)
        self.setWindowTitle("Configuración")
        self.resize(460, 280)
        lay = QVBoxLayout(self)

        titulo = QLabel("Configuración")
        titulo.setObjectName("titulo")
        lay.addWidget(titulo)

        form = QFormLayout()
        combo_paleta = QComboBox()
        combo_paleta.addItems(list(PALETAS.keys()))
        combo_paleta.setCurrentText(ventana.paleta)
        combo_paleta.currentTextChanged.connect(ventana.cambiar_paleta)
        form.addRow("Paleta de colores:", combo_paleta)

        combo_modo = QComboBox()
        combo_modo.addItem("Claro", "claro")
        combo_modo.addItem("Oscuro", "oscuro")
        combo_modo.setCurrentIndex(0 if ventana.modo == "claro" else 1)
        combo_modo.currentIndexChanged.connect(
            lambda i: ventana.cambiar_modo(combo_modo.itemData(i)))
        form.addRow("Modo:", combo_modo)
        lay.addLayout(form)

        check = QCheckBox("Activar caracteres especiales con Alt")
        check.setChecked(ventana.atajos)
        check.toggled.connect(ventana.cambiar_atajos)
        lay.addWidget(check)

        nota = QLabel("Alt+C → ĉ · Alt+G → ĝ · Alt+H → ĥ · Alt+J → ĵ · Alt+S → ŝ · Alt+U → ŭ\n"
                      "Con Mayús se escriben en mayúscula. Los cambios se aplican al momento.")
        nota.setObjectName("nota")
        nota.setWordWrap(True)
        lay.addWidget(nota)
        lay.addStretch()

        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        lay.addWidget(cerrar, alignment=Qt.AlignRight)


# ---------- Ventana principal ----------

class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vortante")
        self.setWindowIcon(QIcon(str(BASE / "icono" / "vortante.svg")))
        self.resize(1080, 700)
        self.current_path: Path | None = None
        self._chars_visibles = True
        self.issues = []

        self.ajustes = QSettings("Alvaro Aliste", "EditorEsperanto")
        self.paleta = self.ajustes.value("paleta", "Terracota")
        self.modo = self.ajustes.value("modo", "claro")
        self.atajos = self.ajustes.value("atajos", True, type=bool)
        if self.paleta not in PALETAS:
            self.paleta = "Terracota"

        self.editor = Editor()
        self.editor.setAcceptRichText(True)
        self.editor.atajos_eo = self.atajos
        self.editor.document().modificationChanged.connect(self._update_title)

        # Análisis del texto con retardo, para no recalcular en cada tecla
        self.analizador = cargar_analizador()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self._analizar)
        self.editor.textChanged.connect(self.timer.start)

        self.teoria = QTextBrowser()

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_escritura(), "Escribir")
        self.tabs.addTab(self.teoria, "Gramática")
        self._build_panel_sugerencias()
        self._build_toolbar()
        self._build_special_chars_bar()
        self._update_title(False)
        self.aplicar_tema()
        self.timer.start()

    # ---------- Pestañas ----------

    def _build_escritura(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(self.editor)
        return w

    # ---------- Panel de sugerencias ----------

    def _build_panel_sugerencias(self):
        self.dock = QDockWidget("Sugerencias", self)
        self.dock.setObjectName("sugerencias")
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista.itemClicked.connect(self._aplicar_item)
        self.dock.setWidget(self.lista)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        visible = self.ajustes.value("sugerencias", True, type=bool)
        self.dock.setVisible(visible)

    def _analizar(self):
        texto = self.editor.toPlainText()[:20000]
        self.issues = self.analizador.analizar(texto)
        tema = tokens(self.paleta, self.modo)

        seleccion = []
        for it in self.issues:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(it["ini"])
            cursor.setPosition(it["fin"], QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            if it["tipo"] == "error":
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                fmt.setUnderlineColor(QColor(COLOR_ERROR))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
                fmt.setUnderlineColor(QColor(tema["accent"]))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            seleccion.append(sel)
        self.editor.setExtraSelections(seleccion)

        self.lista.clear()
        if not self.issues:
            item = QListWidgetItem("Sin sugerencias por ahora.")
            item.setFlags(Qt.NoItemFlags)
            self.lista.addItem(item)
            return
        for it in self.issues:
            prefijo = "✗ " if it["tipo"] == "error" else "ℹ "
            item = QListWidgetItem(prefijo + it["mensaje"])
            item.setData(Qt.UserRole, (it, None))
            if it["tipo"] == "error":
                item.setForeground(QColor(COLOR_ERROR))
            self.lista.addItem(item)
            if it["tipo"] == "error":
                for s in it["sugerencias"]:
                    sub = QListWidgetItem(f"      → cambiar por «{s}»")
                    sub.setData(Qt.UserRole, (it, s))
                    self.lista.addItem(sub)

    def _aplicar_item(self, item: QListWidgetItem):
        datos = item.data(Qt.UserRole)
        if not datos:
            return
        it, sugerencia = datos
        if it is None or it["tipo"] != "error" or sugerencia is None:
            return
        doc = self.editor.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(it["ini"])
        cursor.setPosition(it["fin"], QTextCursor.KeepAnchor)
        if cursor.selectedText() != it["texto"]:
            return  # el texto cambió desde el último análisis
        cursor.insertText(sugerencia)
        self.editor.setTextCursor(cursor)

    # ---------- Temas y ajustes ----------

    def aplicar_tema(self):
        t = tokens(self.paleta, self.modo)
        self.setStyleSheet(estilo(t))
        if TEORIA.exists():
            self.teoria.setHtml(html_con_tema(TEORIA.read_text(encoding="utf-8"), t))
        else:
            self.teoria.setPlainText("No encuentro theory/gramatica.html")

    def cambiar_paleta(self, nombre: str):
        self.paleta = nombre
        self.ajustes.setValue("paleta", nombre)
        self.aplicar_tema()
        self._analizar()

    def cambiar_modo(self, modo: str):
        self.modo = modo
        self.ajustes.setValue("modo", modo)
        self.aplicar_tema()
        self._analizar()

    def cambiar_atajos(self, activo: bool):
        self.atajos = activo
        self.editor.atajos_eo = activo
        self.ajustes.setValue("atajos", activo)
        self._actualizar_estado_chars()

    def abrir_ayuda(self):
        AyudaDialog(self, tokens(self.paleta, self.modo)).exec()

    def abrir_configuracion(self):
        ConfigDialog(self).exec()

    def _cambiar_sugerencias(self, visible: bool):
        self.dock.setVisible(visible)
        self.ajustes.setValue("sugerencias", visible)

    # ---------- Barras ----------

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_open = QAction("Abrir", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self.open_file)
        tb.addAction(act_open)

        act_save = QAction("Guardar", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self.save_file)
        tb.addAction(act_save)

        act_pdf = QAction("PDF", self)
        act_pdf.setToolTip("Exportar a PDF")
        act_pdf.triggered.connect(self.exportar_pdf)
        tb.addAction(act_pdf)

        tb.addSeparator()

        self.act_bold = QAction("N", self)
        self.act_bold.setCheckable(True)
        self.act_bold.setShortcut(QKeySequence.Bold)
        f = self.act_bold.font()
        f.setBold(True)
        self.act_bold.setFont(f)
        self.act_bold.triggered.connect(self._toggle_bold)
        tb.addAction(self.act_bold)

        self.act_italic = QAction("K", self)
        self.act_italic.setCheckable(True)
        self.act_italic.setShortcut(QKeySequence.Italic)
        f = self.act_italic.font()
        f.setItalic(True)
        self.act_italic.setFont(f)
        self.act_italic.triggered.connect(self._toggle_italic)
        tb.addAction(self.act_italic)

        self.act_underline = QAction("S", self)
        self.act_underline.setCheckable(True)
        self.act_underline.setShortcut(QKeySequence.Underline)
        f = self.act_underline.font()
        f.setUnderline(True)
        self.act_underline.setFont(f)
        self.act_underline.triggered.connect(self._toggle_underline)
        tb.addAction(self.act_underline)

        tb.addSeparator()

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._set_font_family)
        tb.addWidget(self.font_combo)

        btn_menos = QPushButton("−")
        btn_menos.setObjectName("tam")
        btn_menos.setFixedWidth(30)
        btn_menos.setFocusPolicy(Qt.NoFocus)
        btn_menos.setToolTip("Reducir letra")

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 96)
        self.size_spin.setValue(12)
        self.size_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.size_spin.setAlignment(Qt.AlignCenter)
        self.size_spin.setFixedWidth(52)
        self.size_spin.valueChanged.connect(self._set_font_size)

        btn_mas = QPushButton("+")
        btn_mas.setObjectName("tam")
        btn_mas.setFixedWidth(30)
        btn_mas.setFocusPolicy(Qt.NoFocus)
        btn_mas.setToolTip("Aumentar letra")

        btn_menos.clicked.connect(lambda: self.size_spin.setValue(self.size_spin.value() - 1))
        btn_mas.clicked.connect(lambda: self.size_spin.setValue(self.size_spin.value() + 1))

        tb.addWidget(btn_menos)
        tb.addWidget(self.size_spin)
        tb.addWidget(btn_mas)

        tb.addSeparator()

        # Alineación del párrafo (grupo exclusivo)
        self.align_group = QActionGroup(self)
        self.align_group.setExclusive(True)
        self._acciones_alineacion = []
        for etiqueta, flag, tip in [("Izq.", Qt.AlignLeft, "Alinear a la izquierda"),
                                    ("Centro", Qt.AlignHCenter, "Centrar"),
                                    ("Der.", Qt.AlignRight, "Alinear a la derecha"),
                                    ("Justif.", Qt.AlignJustify, "Justificar")]:
            act = QAction(etiqueta, self)
            act.setCheckable(True)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, f=flag: self.editor.setAlignment(f))
            self.align_group.addAction(act)
            tb.addAction(act)
            self._acciones_alineacion.append((act, flag))
        self.editor.cursorPositionChanged.connect(self._sync_align)

        self.editor.currentCharFormatChanged.connect(self._sync_format_controls)

        # Espacio flexible y botón de menú a la derecha del todo
        tb.addWidget(self._espacio())
        boton = QToolButton()
        boton.setObjectName("menu")
        boton.setText("☰")
        boton.setToolTip("Ayuda, configuración y sugerencias")
        boton.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(boton)

        act_sug = menu.addAction("Panel de sugerencias")
        act_sug.setCheckable(True)
        act_sug.setChecked(self.dock.isVisible())
        act_sug.toggled.connect(self._cambiar_sugerencias)
        self.dock.visibilityChanged.connect(act_sug.setChecked)

        menu.addSeparator()
        act_ayuda = menu.addAction("Ayuda")
        act_ayuda.triggered.connect(self.abrir_ayuda)
        act_conf = menu.addAction("Configuración")
        act_conf.triggered.connect(self.abrir_configuracion)

        boton.setMenu(menu)
        tb.addWidget(boton)

    def _build_special_chars_bar(self):
        # Barra inferior como widget normal (no QToolBar), para que la flecha responda siempre
        self.barra_chars = QWidget()
        self.barra_chars.setObjectName("caracteres")
        fila = QHBoxLayout(self.barra_chars)
        fila.setContentsMargins(10, 6, 10, 6)
        fila.setSpacing(6)

        # Contenedor plegable con los botones de caracteres
        self.panel_chars = QWidget()
        self.panel_chars.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self.panel_chars)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for ch in ESPERANTO_CHARS:
            btn = QPushButton(ch)
            btn.setObjectName("eo")
            btn.setFixedWidth(34)
            # No roba el foco: el texto sigue en el editor después de pulsar
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setToolTip(f"Insertar {ch}")
            btn.clicked.connect(lambda _=False, c=ch: self.editor.insertPlainText(c))
            lay.addWidget(btn)
        fila.addWidget(self.panel_chars)
        fila.addStretch(1)

        self.estado_chars = QLabel()
        self.estado_chars.setObjectName("estado")
        fila.addWidget(self.estado_chars)

        self.boton_chars = QPushButton("▼")
        self.boton_chars.setObjectName("flecha")
        self.boton_chars.setFixedWidth(44)
        self.boton_chars.setToolTip("Mostrar u ocultar los caracteres")
        self.boton_chars.setFocusPolicy(Qt.NoFocus)
        self.boton_chars.clicked.connect(self._toggle_chars)
        fila.addWidget(self.boton_chars)

        # Pantalla: pestañas arriba y barra de caracteres abajo
        central = QWidget()
        lay2 = QVBoxLayout(central)
        lay2.setContentsMargins(0, 0, 0, 0)
        lay2.setSpacing(0)
        lay2.addWidget(self.tabs)
        lay2.addWidget(self.barra_chars)
        self.setCentralWidget(central)

        self._actualizar_estado_chars()

    def _espacio(self):
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        w.setStyleSheet("background: transparent;")
        return w

    def _toggle_chars(self):
        self._chars_visibles = not self._chars_visibles
        self.panel_chars.setVisible(self._chars_visibles)
        self.boton_chars.setText("▼" if self._chars_visibles else "▲")

    def _actualizar_estado_chars(self):
        if self.atajos:
            self.estado_chars.setText("Caracteres con Alt: activados")
        else:
            self.estado_chars.setText("Caracteres con Alt: desactivados")

    # ---------- Formato ----------

    def _merge_format(self, fmt: QTextCharFormat):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_bold(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self._merge_format(fmt)

    def _toggle_italic(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._merge_format(fmt)

    def _toggle_underline(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._merge_format(fmt)

    def _set_font_family(self, font: QFont):
        fmt = QTextCharFormat()
        fmt.setFontFamilies([font.family()])
        self._merge_format(fmt)

    def _set_font_size(self, size: int):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_format(fmt)

    def _sync_format_controls(self, fmt: QTextCharFormat):
        self.act_bold.setChecked(fmt.fontWeight() >= QFont.Bold)
        self.act_italic.setChecked(fmt.fontItalic())
        self.act_underline.setChecked(fmt.fontUnderline())
        if fmt.fontPointSize() > 0:
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(int(fmt.fontPointSize()))
            self.size_spin.blockSignals(False)

    # ---------- Archivos ----------

    def _update_title(self, modified: bool):
        name = self.current_path.name if self.current_path else "Sin título"
        mark = " *" if modified else ""
        self.setWindowTitle(f"{name}{mark} - Vortante")

    def _maybe_save(self) -> bool:
        """Devuelve False si el usuario cancela."""
        if not self.editor.document().isModified():
            return True
        resp = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "¿Guardar los cambios antes de continuar?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if resp == QMessageBox.Cancel:
            return False
        if resp == QMessageBox.Yes:
            return self.save_file()
        return True

    def open_file(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir", "", "Texto enriquecido (*.html *.htm);;Texto plano (*.txt)"
        )
        if not path:
            return
        p = Path(path)
        content = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".html", ".htm"):
            self.editor.setHtml(content)
        else:
            self.editor.setPlainText(content)
        self.current_path = p
        self.editor.document().setModified(False)
        self._update_title(False)

    def save_file(self) -> bool:
        path = self.current_path
        if path is None:
            path_str, _ = QFileDialog.getSaveFileName(
                self, "Guardar", "", "Texto enriquecido (*.html);;Texto plano (*.txt)"
            )
            if not path_str:
                return False
            path = Path(path_str)
        if path.suffix.lower() in (".html", ".htm"):
            path.write_text(self.editor.toHtml(), encoding="utf-8")
        else:
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
        self.current_path = path
        self.editor.document().setModified(False)
        self._update_title(False)
        return True

    def _sync_align(self):
        alineacion = self.editor.alignment() & Qt.AlignHorizontal_Mask
        for act, flag in self._acciones_alineacion:
            act.setChecked(alineacion == flag)

    def exportar_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a PDF", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc = self.editor.document()
        imprimir = getattr(doc, "print_", None) or doc.print
        imprimir(printer)
        QMessageBox.information(self, "PDF", f"Documento exportado a:\n{path}")

    def closeEvent(self, event):
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Vortante")
    win = EditorWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
