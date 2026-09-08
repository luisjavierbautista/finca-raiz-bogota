# -*- coding: utf-8 -*-
"""Normaliza el nombre de barrio que publican los portales.

En modo radio el barrio no viene de una lista nuestra: es la cadena que el portal
haya escrito. Metrocuadrado y Ciencuadras pegan la localidad, la UPZ y la zona
comercial del buscador al nombre, parten los sectores en numerales romanos y a
veces mandan la frase entera del aviso. Sin limpiar, 414 avisos producen 155
nombres distintos y los filtros de la página dejan de servir.

Lo que se recorta es ruido de catálogo, nunca información: «Occidental» u
«Oriental» distinguen barrios de verdad y se conservan; «II Sector» o «Etapa III»
son subdivisiones internas y se colapsan.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import sinacento

# Localidad, UPZ o zona del buscador pegada al nombre.
COLAS = ["zona urbana", "zona occidental", "castilla marsella", "timiza la alqueria",
         "salitre modelia", "puente aranda", "engativa", "fontibon", "kennedy",
         "teusaquillo", "castilla", "normandia", "modelia", "tintal", "techo",
         "capellania"]

# Si al quitar la cola solo queda esto, la cola era el sustantivo del nombre
# («Ciudad Techo», «Bosques de Castilla») y no se toca.
CALIFICATIVOS = {"ciudad", "nueva", "nuevo", "condado", "bosque", "bosques", "torres",
                 "portal", "portales", "alto", "altos", "bajo", "villa", "parque",
                 "conjunto", "unidad", "el", "la", "los", "las", "de", "del", "y",
                 # posicionales: distinguen barrios pero nunca nombran uno solos
                 "occidental", "oriental", "norte", "sur", "central", "real", "primer",
                 "primera", "segundo", "segunda", "sector", "etapa", "i", "ii", "iii"}

MENUDAS = {"de", "del", "la", "las", "los", "el", "y"}

NUMERAL = r"(?:i{1,3}|iv|vi{0,3}|ix|xi{0,2}|x|\d{1,2}|[ab])"
ORDINAL = r"(?:primer|primera|segundo|segunda|tercer|tercera|cuarto|cuarta)"
SUBDIV = [
    re.compile(r"\s+sector\s+(?:sur|norte|oriental|occidental)$"),
    re.compile(r"\s+(?:et|etapa|sector|sec)\.?\s*(?:%s|%s)?$" % (NUMERAL, ORDINAL)),
    re.compile(r"\s+(?:%s|%s)\s+(?:sector|etapa)$" % (NUMERAL, ORDINAL)),
    re.compile(r"\s+(?:%s|%s|y|se|ir)(?:\s+(?:%s|%s|y|se|ir))*$"
               % (NUMERAL, ORDINAL, NUMERAL, ORDINAL)),
]

FRASE = re.compile(r"^apartamento\s+en\s+(?:arriendo|venta)(?:\s+o\s+venta)?\s+en\s+")
# Sin barrio: el portal manda la ciudad.
SIN_BARRIO = {"bogota", "bogota dc", "bogota d c", "colombia", "cundinamarca",
              "zona occidental", "zona urbana", "occidente", "sur", "norte"}
# Nombres donde el numeral sí es parte del nombre.
PROTEGIDOS = {"pio xii"}

TILDES = {
    "fontibon": "Fontibón", "normandia": "Normandía", "engativa": "Engativá",
    "galan": "Galán", "boyaca": "Boyacá", "capellania": "Capellanía",
    "americas": "Américas", "alqueria": "Alquería", "belen": "Belén",
    "nicolas": "Nicolás", "maria": "María", "jose": "José", "joaquin": "Joaquín",
    "hipodromo": "Hipódromo", "metropolis": "Metrópolis", "campina": "Campiña",
    "cabana": "Cabaña", "paez": "Páez", "pio": "Pío", "campin": "Campín",
    "veronica": "Verónica", "rincon": "Rincón", "angeles": "Ángeles",
    "jardin": "Jardín", "muzu": "Muzú", "andalucia": "Andalucía", "peru": "Perú",
}
ROMANOS = {"ii": "II", "iii": "III", "iv": "IV", "vi": "VI", "vii": "VII",
           "viii": "VIII", "ix": "IX", "xi": "XI", "xii": "XII"}


# El mismo barrio escrito de dos formas por portales distintos.
SINONIMOS = {"pradera": "La Pradera", "tejar": "El Tejar", "americas": "Las Américas",
             "el galan": "Galán", "nueva marcella": "Nueva Marsella",
             "ciudadela la felicidad": "La Felicidad"}


def _sustantivo(texto):
    """¿Queda algo que nombre un barrio, o solo calificativos y conectores?"""
    palabras = texto.split()
    if not palabras or palabras[-1] in MENUDAS:      # «Hipódromo de» no es un nombre
        return False
    return any(w not in CALIFICATIVOS for w in palabras)


def _quita_colas(s):
    cambio = True
    while cambio:
        cambio = False
        for cola in COLAS:
            if not s.endswith(" " + cola):
                continue
            resto = s[: -len(cola) - 1].strip()
            if resto and _sustantivo(resto):
                s, cambio = resto, True
                break
    return s


def limpia_barrio(crudo):
    s = FRASE.sub("", sinacento(crudo))
    s = re.sub(r"^ub\s+", "", s).strip()        # «UB Castilla Real»: unidad básica
    if not s or s in SIN_BARRIO:
        return ""

    s = _quita_colas(s)

    # Palabras repetidas por concatenación del portal.
    vistas, limpio = set(), []
    for w in s.split():
        if w not in vistas:
            vistas.add(w)
            limpio.append(w)
    s = " ".join(limpio)

    if s not in PROTEGIDOS:
        for pat in SUBDIV:
            nuevo = pat.sub("", s).strip()
            if nuevo and _sustantivo(nuevo):
                s = nuevo
        s = _quita_colas(s)

    if not s or s in SIN_BARRIO:
        return ""

    if s in SINONIMOS:
        return SINONIMOS[s]

    protegido = s in PROTEGIDOS
    salida = []
    for i, w in enumerate(s.split()):
        if protegido and w in ROMANOS:
            salida.append(ROMANOS[w])
        elif w in TILDES:
            salida.append(TILDES[w] if (i == 0 or w not in MENUDAS) else TILDES[w].lower())
        elif i > 0 and w in MENUDAS:
            salida.append(w)
        else:
            salida.append(w.capitalize())
    return " ".join(salida)
