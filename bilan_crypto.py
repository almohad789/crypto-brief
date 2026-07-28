#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilans crypto Discord — hebdo / mensuel / 3 mois / annuel.
Indépendant du brief quotidien 6h/20h.

Échéances :
  - lundi                      -> bilan semaine (7 jours)
  - 1er du mois                -> bilan mois (30 jours)
  - 1er janv/avril/juil/oct    -> bilan 3 mois (90 jours)
  - 1er janvier                -> bilan année (1 an)

RATTRAPAGE : un bilan dû reste dû tant qu'il n'a pas été posté, pendant
plusieurs jours après son échéance (3 j pour la semaine, 7 j pour les
autres). Si GitHub retarde tous les runs du jour J, le bilan part à J+1,
J+2... au lieu d'être perdu. Le jour de l'échéance, on attend 12h (Paris) ;
les jours de rattrapage, on poste dès 8h. bilan_state.json mémorise la
date du dernier envoi de chaque bilan : zéro doublon possible.

FORCE=1 (lancement manuel) -> poste les 4 bilans pour tester,
sans toucher à l'état (les bilans planifiés restent dus).

Dépendances : pip install requests
"""

import os
import sys
import json
import time
import datetime
from zoneinfo import ZoneInfo

import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")
API = "https://api.coingecko.com/api/v3"
STATE_FILE = "bilan_state.json"

COINS = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "SOL":  "solana",
    "XRP":  "ripple",
    "LTC":  "litecoin",
    "ONDO": "ondo-finance",
    "HBAR": "hedera-hashgraph",
    "XDC":  "xdce-crowd-sale",
}

# période -> (titre, libellé colonne, jours, clé API markets ou None)
PERIODS = {
    "semaine": ("Bilan semaine", "7j",  7,   "price_change_percentage_7d_in_currency"),
    "mois":    ("Bilan mois",    "30j", 30,  "price_change_percentage_30d_in_currency"),
    "3mois":   ("Bilan 3 mois",  "90j", 90,  None),   # calculé via market_chart
    "annee":   ("Bilan année",   "1an", 365, "price_change_percentage_1y_in_currency"),
}


def fmt(v):
    if v is None:
        return "—"
    if v >= 1000:
        return f"{v:,.0f}".replace(",", " ")
    if v >= 1:
        return f"{v:,.2f}".replace(",", " ")
    return f"{v:.4f}"


def fetch_json(url, params=None, retries=4):
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"[info] limite API, attente {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def derniere_echeance(period, today):
    """Date de la dernière échéance calendaire pour cette période."""
    if period == "semaine":                       # dernier lundi (ou aujourd'hui)
        return today - datetime.timedelta(days=today.weekday())
    if period == "mois":                          # dernier 1er du mois
        return today.replace(day=1)
    if period == "3mois":                         # dernier 1er de trimestre
        m = ((today.month - 1) // 3) * 3 + 1
        return datetime.date(today.year, m, 1)
    if period == "annee":                         # dernier 1er janvier
        return datetime.date(today.year, 1, 1)
    return None


# Jours de rattrapage après l'échéance (échéance = jour 0)
CATCHUP = {"semaine": 3, "mois": 7, "3mois": 7, "annee": 7}


def bilans_du_jour(now, state):
    """Bilans dus et pas encore envoyés, avec rattrapage.

    Un bilan est dû si sa dernière échéance date de moins de CATCHUP jours
    et qu'aucun envoi n'a eu lieu depuis cette échéance. Le jour même de
    l'échéance on attend 12h (Paris) ; en rattrapage on poste dès 8h."""
    if os.environ.get("FORCE") == "1":
        return ["semaine", "mois", "3mois", "annee"]
    today = now.date()
    due = []
    for period in ("semaine", "mois", "3mois", "annee"):
        ech = derniere_echeance(period, today)
        if ech is None:
            continue
        age = (today - ech).days
        if age > CATCHUP[period]:
            continue                              # échéance trop ancienne
        last = state.get(period)                  # date ISO du dernier envoi
        if last and last >= ech.isoformat():
            continue                              # déjà posté pour ce cycle
        if age == 0 and now.hour < 12:
            continue                              # jour J : pas avant midi
        if age > 0 and now.hour < 8:
            continue                              # rattrapage : pas avant 8h
        due.append(period)
    return due


def fetch_base():
    """Prix EUR + variations 7j/30j/1an (1 appel) et prix USD (1 appel)."""
    ids = ",".join(COINS.values())
    eur, usd, pcts = {}, {}, {}
    markets = fetch_json(f"{API}/coins/markets", {
        "vs_currency": "eur", "ids": ids,
        "price_change_percentage": "7d,30d,1y",
    })
    for m in markets:
        cid = m["id"]
        eur[cid] = m.get("current_price")
        pcts[cid] = {
            "price_change_percentage_7d_in_currency": m.get("price_change_percentage_7d_in_currency"),
            "price_change_percentage_30d_in_currency": m.get("price_change_percentage_30d_in_currency"),
            "price_change_percentage_1y_in_currency": m.get("price_change_percentage_1y_in_currency"),
        }
    time.sleep(3)
    data = fetch_json(f"{API}/simple/price", {"ids": ids, "vs_currencies": "usd"})
    for cid, v in data.items():
        usd[cid] = v.get("usd")
    return eur, usd, pcts


def fetch_90d():
    """Variation 90 jours via market_chart (1 appel par crypto).
    Note : pas de paramètre `interval` — il est réservé aux plans payants
    de CoinGecko et fait échouer l'appel sur l'API publique."""
    out = {}
    for sym, cid in COINS.items():
        try:
            data = fetch_json(f"{API}/coins/{cid}/market_chart",
                              {"vs_currency": "eur", "days": 90})
            prices = data.get("prices", [])
            if len(prices) >= 2 and prices[0][1]:
                out[cid] = (prices[-1][1] / prices[0][1] - 1) * 100
        except Exception as e:
            print(f"[warn] 90j {sym} : {e}")
        time.sleep(8)
    return out


def build_message(period, eur, usd, values):
    titre, col, _, _ = PERIODS[period]
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")

    vals = [(s, values.get(cid)) for s, cid in COINS.items() if values.get(cid) is not None]
    ups = [v for _, v in vals if v >= 0]
    downs = [v for _, v in vals if v < 0]
    resume = None
    if vals:
        best = max(vals, key=lambda x: x[1])
        worst = min(vals, key=lambda x: x[1])
        resume = (f"{len(ups)} hausse{'s' if len(ups) > 1 else ''}, "
                  f"{len(downs)} baisse{'s' if len(downs) > 1 else ''} sur la période. "
                  f"Meilleur : {best[0]} ({best[1]:+.1f}%), "
                  f"pire : {worst[0]} ({worst[1]:+.1f}%).")

    lines = [f"**📈 {titre} — {now}**"]
    if resume:
        lines.append(resume)
    lines.append("```")
    header = f"{'Crypto':<6}{col:>7} {'Prix €':>8} {'Prix $':>8}"
    lines.append(header)
    lines.append("─" * len(header))
    for sym, cid in COINS.items():
        v = values.get(cid)
        if v is None:
            pct = "—"
        else:
            arrow = "▲" if v >= 0 else "▼"
            pct = f"{arrow}{v:+.1f}%" if abs(v) < 100 else f"{arrow}{v:+.0f}%"
        lines.append(f"{sym:<6}{pct:>7} {fmt(eur.get(cid)):>8} {fmt(usd.get(cid)):>8}")
    lines.append("```")
    return "\n".join(lines)


def post_to_discord(message):
    resp = requests.post(WEBHOOK_URL, json={"content": message}, timeout=30)
    resp.raise_for_status()


def main():
    if not WEBHOOK_URL:
        print("Erreur : secret DISCORD_WEBHOOK manquant.")
        sys.exit(1)

    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    force = os.environ.get("FORCE") == "1"
    state = load_state()

    due = bilans_du_jour(now, state)
    if not due:
        print(f"Aucun bilan dû ({now.strftime('%d/%m %H:%M')}). On s'arrête.")
        return

    eur, usd, pcts = fetch_base()
    if not eur:
        print("Aucune donnée récupérée, rien posté.")
        return

    pct90 = fetch_90d() if "3mois" in due else {}

    today = now.date().isoformat()
    for period in due:
        key = PERIODS[period][3]
        if period == "3mois":
            values = pct90
        else:
            values = {cid: (pcts.get(cid) or {}).get(key) for cid in COINS.values()}
        msg = build_message(period, eur, usd, values)
        post_to_discord(msg)
        print(f"Bilan {period} posté ✔")
        if not force:           # les tests manuels ne consomment pas l'état
            state[period] = today
        time.sleep(2)

    if not force:
        save_state(state)


if __name__ == "__main__":
    main()
