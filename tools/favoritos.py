#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Los avisos que el dueño marcó a mano, en favoritos.txt.

Marcar no filtra: solo pone una estrella en la ficha y resalta el pin. Lo que sí
aporta es memoria — cuando un marcado desaparece de los portales no se borra de la
página, pasa a «Marcados que ya no están» con lo último que se supo de él.

El archivo lo edita una persona; este módulo nunca lo reescribe. Lo que sí se guarda
es `favoritos-estado.json`: la última ficha conocida de cada marcado, para poder
contar qué era cuando se cayó.
"""
import io, json, os, re, subprocess

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTA = os.path.join(RAIZ, "favoritos.txt")
ESTADO = os.path.join(RAIZ, "favoritos-estado.json")


def clave(url):
    """Ruta comparable: los portales cambian dominio, query y ancla, no la ruta."""
    u = (url or "").strip()
    u = re.sub(r"^https?://[^/]+", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/").lower()


SECCION = re.compile(r"^#+[\s\u2500-]*(norte|occidente)[\s\u2500-]*$", re.I)


def lista(busqueda=None):
    """URLs de la búsqueda pedida.

    El archivo se divide con encabezados tipo `# ── norte ──`; sin encabezado,
    todo pertenece a la búsqueda del norte. Cada página solo muestra los suyos.
    """
    if not os.path.exists(LISTA):
        return []
    urls, actual = [], "norte"
    for linea in io.open(LISTA, encoding="utf-8"):
        linea = linea.strip()
        m = SECCION.match(linea)
        if m:
            actual = m.group(1).lower()
            continue
        if linea and not linea.startswith("#"):
            if busqueda is None or actual == busqueda:
                urls.append(linea)
    return urls


def estado():
    if not os.path.exists(ESTADO):
        return {}
    return json.load(io.open(ESTADO, encoding="utf-8")).get("marcados", {})


def guardar(memoria, fecha):
    with io.open(ESTADO, "w", encoding="utf-8") as fh:
        json.dump({"actualizado": fecha, "marcados": memoria}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)


def resolver(avisos, fecha, busqueda=None):
    """Cruza la lista con los avisos de hoy.

    Devuelve las urls de los avisos marcados que siguen vigentes, los que ya no
    aparecen (con su última ficha conocida) y la memoria actualizada.
    """
    memoria = estado()
    porclave = {}
    for a in avisos:
        porclave.setdefault(clave(a["url"]), a)
    # Identidad física: un aviso republicado con otro id sigue siendo el mismo apartamento.
    porsitio = {}
    for a in avisos:
        porsitio.setdefault("%.4f|%.4f|%d" % (a["lat"], a["lon"], int(a["m2"])), a)

    vigentes, perdidos = set(), []
    for url in lista(busqueda):
        k = clave(url)
        a = porclave.get(k)
        recuerdo = memoria.get(k)
        if a is None and recuerdo:
            # ¿Reapareció con otro enlace, en el mismo edificio y con la misma área?
            a = porsitio.get(recuerdo.get("sitio"))
        if a is not None:
            vigentes.add(a["url"])
            memoria[k] = {"url": url, "barrio": a["barrio"], "total": a.get("total"),
                          "m2": a["m2"], "src": a["src"], "visto": fecha,
                          "sitio": "%.4f|%.4f|%d" % (a["lat"], a["lon"], int(a["m2"])),
                          "vigente_como": a["url"]}
        elif recuerdo:
            perdidos.append(dict(recuerdo, url=url))
        else:
            # Marcado que nunca estuvo en la lista: o está fuera de criterios, o ya
            # no se publica. No se inventa una ficha para él.
            perdidos.append({"url": url, "barrio": None, "total": None, "m2": None,
                             "src": None, "visto": None})
    return vigentes, perdidos, memoria


# ─────────────────────────────────────────────────────────────────────────────
# Consulta directa del enlace
#
# Un marcado puede no estar en el barrido por dos razones muy distintas: se cayó,
# o el buscador del portal no lo devuelve aunque siga publicado. Ciencuadras, por
# ejemplo, responde vacío para ocho de los barrios de la búsqueda del norte. Sin
# preguntarle al enlace no se puede distinguir una cosa de la otra, y decir «se
# cayó» cuando sigue publicado es el peor error que puede cometer esta página.
# ─────────────────────────────────────────────────────────────────────────────

def _num(t):
    try:
        return float(re.sub(r"[^0-9.]", "", str(t)) or 0)
    except ValueError:
        return 0


def consultar(url, get):
    """Lee la ficha del portal. Devuelve un dict con lo que se pudo confirmar."""
    r = {"url": url, "estado": "ilegible", "barrio": None, "total": None, "m2": None,
         "hab": None, "lat": None, "lon": None, "portal": None}
    # El barrio va en el slug del enlace, que en Fincaraíz no es el último tramo.
    ruta_url = clave(url)
    m = re.search(r".*-en-([a-z0-9-]+?)-bogota", ruta_url) or re.search(r"bogota-([a-z-]+?)-\d", ruta_url)
    if m:
        r["barrio"] = m.group(1).replace("-", " ").title()

    host = re.sub(r"^https?://", "", url).split("/")[0]
    r["portal"] = ("Fincaraíz" if "fincaraiz" in host else
                   "Metrocuadrado" if "metrocuadrado" in host else
                   "Ciencuadras" if "ciencuadras" in host else host)

    if r["portal"] == "Fincaraíz":
        # Un aviso borrado no da 404: redirige al listado con ?addeletedid=<id>.
        final = subprocess.run(["curl", "-sL", "-o", "/dev/null", "-w", "%{url_effective}",
                                "--max-time", "40", "-A", UA, url],
                               capture_output=True, text=True).stdout
        if "addeletedid=" in final:
            r["estado"] = "caido"
            return r

    h = get(url, intentos=2)
    if not h:
        r["estado"] = "sin respuesta"
        return r
    s = h.replace('\\"', '"')

    if r["portal"] == "Fincaraíz":
        if '"status":"deactivated"' in s:
            r["estado"] = "caido"
            return r
        p = re.search(r'"price":\{"amount":(\d+),"admin_included":(\d+)', s)
        if p:
            r["total"] = int(p.group(2))
        a = re.search(r'\{"field":"m2Built","value":"([\d.,]+)', s)
        if a:
            r["m2"] = _num(a.group(1).replace(",", "."))
        b = re.search(r'\{"field":"bedrooms","value":"(\d+)', s)
        if b:
            r["hab"] = int(b.group(1))
    elif r["portal"] == "Ciencuadras":
        p = re.search(r'"price"\s*:\s*"?([\d.]+)', s)
        if p:
            r["total"] = int(float(p.group(1)))
        a = re.search(r'"floorSize"\s*:\s*\{[^}]*"value"\s*:\s*"?([\d.]+)', s)
        if a:
            r["m2"] = float(a.group(1))
        b = re.search(r'"numberOfRooms"\s*:\s*"?(\d+)', s)
        if b:
            r["hab"] = int(b.group(1))
    else:   # Metrocuadrado
        p = re.search(r'"mvalorarriendo"\s*:\s*"?([\d.]+)', s)
        if p:
            r["total"] = int(float(p.group(1)))
        a = re.search(r'"(?:mareac|marea|areaprivada)"\s*:\s*"?([\d.]+)', s)
        if a:
            r["m2"] = float(a.group(1))
        b = re.search(r'"mnrocuartos"\s*:\s*"?(\d+)', s)
        if b:
            r["hab"] = int(b.group(1))

    la = re.search(r'"lat(?:itude)?"\s*:\s*"?(-?\d+\.\d+)', s)
    lo = re.search(r'"lon(?:gitude)?"\s*:\s*"?(-?\d+\.\d+)', s)
    if la and lo:
        r["lat"], r["lon"] = float(la.group(1)), float(lo.group(1))

    r["estado"] = "publicado" if (r["total"] or r["m2"]) else "ilegible"
    return r
