"""
=====================================================================
 GRIDIRON LAB — MOMIOS DE VEGAS POR JUGADOR (props)
=====================================================================
Lo corre una GitHub Action (.github/workflows/momios.yml) cada 6 horas.
Necesita la clave gratis de The Odds API en el secreto ODDS_API_KEY.

Qué hace en cada corrida:
  1. Pide la lista de partidos de la NFL (gratis: no gasta créditos).
  2. Para cada partido que empieza en las próximas 36 horas y que todavía
     NO tiene foto, pide los props de jugador (1 foto por partido).
  3. Resume cada línea: la mediana de las casas (la "línea de Vegas"), la
     probabilidad sin comisión (sin "vig") de que la supere y cuántas casas
     la ofrecen. Guarda momios/nfl/<temporada>/<fecha>_<VISITA>_<LOCAL>.json

Costo (The Odds API): mercados × regiones por partido = 5 × 1 = 5 créditos.
Unos 15 partidos por semana → ~75 créditos; el plan gratis da 500 al mes.

Uso local (para probar):  ODDS_API_KEY=... python momios/bajar_momios.py
                          python momios/bajar_momios.py --ensayo carpeta/  (sin internet: lee JSON guardados)
"""

import os
import sys
import json
import glob
import statistics
import datetime
import urllib.request
import urllib.parse
from zoneinfo import ZoneInfo

RAIZ = os.environ.get("MOMIOS_DESTINO", os.path.dirname(os.path.abspath(__file__)))   # carpeta momios/
API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
MERCADOS = {                       # mercado de The Odds API -> estadística de Gridiron Lab
    "player_pass_yds": "passing_yards",
    "player_rush_yds": "rushing_yards",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
    "player_anytime_td": "td",
}
VENTANA_H = 36                     # se toma la foto en las 36 h antes del kickoff
ET = ZoneInfo("America/New_York")
EQUIPOS = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Los Angeles Rams": "LA", "Los Angeles Chargers": "LAC", "Las Vegas Raiders": "LV", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def pedir(ruta, **params):
    """GET a The Odds API. Devuelve (json, créditos que quedan)."""
    params["apiKey"] = os.environ["ODDS_API_KEY"]
    url = f"{API}{ruta}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        quedan = r.headers.get("x-requests-remaining")
        return json.load(r), (int(float(quedan)) if quedan else None)


def prob(precio):
    """Momio americano -> probabilidad implícita (con la comisión de la casa)."""
    return 100 / (precio + 100) if precio > 0 else -precio / (-precio + 100)


def resumir(evento):
    """De la respuesta de un partido a una línea por jugador y estadística."""
    lineas = {}                    # (jugador, stat) -> lista de (casa, linea, p_mas_sin_vig)
    for casa in evento.get("bookmakers", []):
        for m in casa.get("markets", []):
            stat = MERCADOS.get(m["key"])
            if not stat:
                continue
            por_jugador = {}
            for o in m.get("outcomes", []):
                por_jugador.setdefault(o.get("description", ""), {})[o["name"]] = o
            for jugador, oc in por_jugador.items():
                if stat == "td":
                    si, no = oc.get("Yes"), oc.get("No")
                    if not si:
                        continue
                    p = prob(si["price"])
                    if no:                                   # con las dos caras se quita la comisión
                        p = p / (p + prob(no["price"]))
                        lineas.setdefault((jugador, stat), []).append((casa["key"], None, p, True))
                    else:
                        lineas.setdefault((jugador, stat), []).append((casa["key"], None, p, False))
                    continue
                mas, menos = oc.get("Over"), oc.get("Under")
                if not mas or mas.get("point") is None:
                    continue
                p = prob(mas["price"])
                if menos:
                    p = p / (p + prob(menos["price"]))
                lineas.setdefault((jugador, stat), []).append((casa["key"], float(mas["point"]), p, bool(menos)))
    out = []
    for (jugador, stat), xs in sorted(lineas.items()):
        if stat == "td":
            sin_vig = [x[2] for x in xs if x[3]]
            out.append({"jugador": jugador, "stat": stat, "linea": None,
                        "p": round(statistics.median(sin_vig or [x[2] for x in xs]), 4),
                        "sin_vig": bool(sin_vig), "casas": len(xs)})
            continue
        linea = statistics.median(x[1] for x in xs)
        # probabilidad de "más" de las casas que ofrecen justo esa línea (si ninguna, todas)
        exactas = [x[2] for x in xs if x[1] == linea] or [x[2] for x in xs]
        out.append({"jugador": jugador, "stat": stat, "linea": linea, "p": round(statistics.mean(exactas), 4),
                    "min": min(x[1] for x in xs), "max": max(x[1] for x in xs), "casas": len(xs)})
    return out


def archivo(ev):
    ko = datetime.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
    et = ko.astimezone(ET)
    temporada = et.year if et.month >= 3 else et.year - 1
    vis, loc = EQUIPOS.get(ev["away_team"], ev["away_team"]), EQUIPOS.get(ev["home_team"], ev["home_team"])
    return os.path.join(RAIZ, "nfl", str(temporada), f"{et:%Y%m%d}_{vis}_{loc}.json"), ko, et, vis, loc


def guardar(ev, odds, ahora):
    ruta, ko, et, vis, loc = archivo(ev)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    datos = {"fuente": "The Odds API (región us; mediana de las casas)", "evento": ev["id"],
             "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "fecha_et": f"{et:%Y-%m-%d}",
             "visita": vis, "local": loc, "foto_utc": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "casas": sorted({b["key"] for b in odds.get("bookmakers", [])}), "lineas": resumir(odds)}
    json.dump(datos, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return ruta, len(datos["lineas"])


def main():
    ahora = datetime.datetime.now(datetime.timezone.utc)
    if len(sys.argv) > 2 and sys.argv[1] == "--ensayo":          # prueba sin internet
        for f in sorted(glob.glob(os.path.join(sys.argv[2], "*.json"))):
            ev = json.load(open(f))
            print("ensayo:", *guardar(ev, ev, ahora))
        return
    eventos, _ = pedir("/events")
    pendientes = []
    for ev in eventos:
        ruta, ko, *_ = archivo(ev)
        horas = (ko - ahora).total_seconds() / 3600
        if 0 < horas <= VENTANA_H and not os.path.exists(ruta):
            pendientes.append(ev)
    print(f"{len(eventos)} partidos en la lista · {len(pendientes)} para foto (empiezan en ≤{VENTANA_H} h)")
    quedan = None
    for ev in pendientes:
        if quedan is not None and quedan < len(MERCADOS):
            print(f"Sin créditos suficientes ({quedan}); se detiene.")
            break
        odds, quedan = pedir(f"/events/{ev['id']}/odds", regions="us", markets=",".join(MERCADOS),
                             oddsFormat="american")
        ruta, n = guardar(ev, odds, ahora)
        print(f"  {ev['away_team']} @ {ev['home_team']}: {n} líneas → {os.path.relpath(ruta, RAIZ)} (quedan {quedan} créditos)")


if __name__ == "__main__":
    main()
