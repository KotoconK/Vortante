"""Análisis del texto: palabras mal escritas, formas verbales y notas de matiz.

- Palabras mal escritas: una palabra que no existe se marca como error si se parece a una
  palabra real (p. ej. «mangi» → «manĝi (comer)»).
- Formas: una forma flexionada reconocida (volas, hundon, grandaj…) se explica con su lema
  y su traducción (p. ej. «volas» → presente de «voli» (querer)).
- Notas: explicaciones de matiz para algunas palabras (p. ej. «poste», «iom poste»).

Las palabras en castellano (con tilde, ñ o mayúscula inicial) no se analizan.
"""
import difflib
import re
import unicodedata

PALABRA = re.compile(r"[A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ]+")
LETRAS_ES = set("áéíóúüñÁÉÍÓÚÜÑ")

# (terminación, descripción)
VERBO_TERMINACIONES = [("as", "presente"), ("is", "pasado"), ("os", "futuro"),
                       ("us", "condicional"), ("u", "imperativo")]
FLEXION_TERMINACIONES = [("ajn", "plural y acusativo"), ("aj", "plural"),
                         ("jn", "plural y acusativo"), ("j", "plural"), ("n", "acusativo")]


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def _es_x(w: str) -> bool:
    """True si la palabra usa el sistema x (cx, gx…) en vez de letras con acento."""
    return re.search(r"[cghjsu]x", w) is not None


def _clave(w: str) -> str:
    """Forma sin acentos: manĝi → mangi."""
    return (w.replace("ĉ", "c").replace("ĝ", "g").replace("ĥ", "h")
            .replace("ĵ", "j").replace("ŝ", "s").replace("ŭ", "u"))


class Analizador:
    def __init__(self, palabras_eo: set, palabras_es: set, formas_es: dict,
                 traducciones: dict):
        self.eo = palabras_eo
        self.es = palabras_es
        self.formas_es = formas_es
        self.traducciones = traducciones  # {eo: [castellano, ...]}
        # Índice sin sistema x y sin acentos: así «mangi» se compara con «manĝi», no con «mangxi»
        self.por_longitud = {}
        self.clave_a_palabras = {}
        for w in palabras_eo:
            if _es_x(w):
                continue
            clave = _clave(w)
            self.clave_a_palabras.setdefault(clave, []).append(w)
            self.por_longitud.setdefault(len(clave), []).append(clave)

    # ---------- Formas ----------

    def _lema_forma(self, w: str):
        """Devuelve (lema, descripción) si w es una forma flexionada de una palabra conocida."""
        for fin, tiempo in VERBO_TERMINACIONES:
            if w.endswith(fin) and len(w) > len(fin) + 1:
                inf = w[:-len(fin)] + "i"
                if inf in self.eo:
                    return inf, ("verbo", tiempo)
        for fin, tipo in FLEXION_TERMINACIONES:
            if w.endswith(fin) and len(w) > len(fin) + 1:
                base = w[:-len(fin)]
                for cand in (base + "o", base + "a", base + "e", base):
                    if cand in self.eo:
                        return cand, ("flexion", tipo)
        return None

    def _traduccion(self, eo: str) -> str:
        trad = self.traducciones.get(eo, [])
        return f" ({', '.join(trad[:2])})" if trad else ""

    def reconocida(self, w: str) -> bool:
        return (w in self.eo or w in self.es or _sin_tildes(w) in self.formas_es
                or self._lema_forma(w) is not None)

    def sugerencias(self, w: str):
        if len(w) < 3:
            return []
        clave = _clave(w)
        candidatas = []
        for longitud in (len(clave) - 1, len(clave), len(clave) + 1):
            candidatas += self.por_longitud.get(longitud, [])
        mejores = difflib.get_close_matches(clave, candidatas, n=3, cutoff=0.8)
        resultado = []
        for m in mejores:
            for palabra in self.clave_a_palabras.get(m, []):
                if palabra not in resultado:
                    resultado.append(palabra)
        return resultado[:3]

    # ---------- Análisis ----------

    def analizar(self, texto: str) -> list:
        """Devuelve una lista de dicts: tipo ('error' o 'nota'), ini, fin, texto, mensaje, sugerencias."""
        issues = []
        tokens = [(m.group(0), m.start(), m.end()) for m in PALABRA.finditer(texto)]

        for original, ini, fin in tokens:
            w = original.lower()
            if original[:1].isupper() or any(c in LETRAS_ES for c in original):
                continue  # nombres propios y palabras castellanas

            if w in self.eo or w in self.es or _sin_tildes(w) in self.formas_es:
                continue

            forma = self._lema_forma(w)
            if forma:
                lema, (clase, tipo) = forma
                if clase == "verbo":
                    mensaje = f"«{original}»: {tipo} del verbo «{lema}»{self._traduccion(lema)}."
                else:
                    mensaje = f"«{original}»: {tipo} de «{lema}»{self._traduccion(lema)}."
                issues.append({"tipo": "nota", "ini": ini, "fin": fin, "texto": original,
                               "mensaje": mensaje, "sugerencias": []})
                continue

            sug = self.sugerencias(w)
            if sug:
                opciones = " o ".join(f"«{s}»{self._traduccion(s)}" for s in sug)
                issues.append({"tipo": "error", "ini": ini, "fin": fin, "texto": original,
                               "mensaje": f"«{original}» no existe. ¿Quisiste decir {opciones}?",
                               "sugerencias": sug})

        for i, (original, ini, fin) in enumerate(tokens):
            if original.lower() != "poste":
                continue
            anterior = tokens[i - 1][0].lower() if i > 0 else ""
            if anterior == "iom":
                issues.append({"tipo": "nota", "ini": tokens[i - 1][1], "fin": fin,
                               "texto": "iom poste", "sugerencias": [],
                               "mensaje": "«iom poste» = un rato más tarde. Al negarte suena más "
                                          "amable que un «después» tajante."})
            else:
                issues.append({"tipo": "nota", "ini": ini, "fin": fin, "texto": original,
                               "sugerencias": [],
                               "mensaje": "«poste» = después, sin decir cuánto. Para «un poco "
                                          "después» usa «iom poste»."})
        issues.sort(key=lambda d: d["ini"])
        return issues
