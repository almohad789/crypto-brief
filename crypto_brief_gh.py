#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brief crypto Discord : 6h et 20h (heure de Paris), affiché en embed.
Pour chaque crypto : nom, variation 24h (%), prix en € et $, et évolution
par rapport au brief précédent (sauvegardé dans previous_prices.json).

Déduplication : previous_prices.json mémorise, par créneau ("matin"/"soir"),
la date ISO du dernier envoi. Un lancement manuel (FORCE=1) poste toujours,
mais ne marque un créneau comme "fait" que s'il a lieu pendant ce créneau —
un test à 12h ou 15h ne bloquera donc jamais le brief du soir.

Dépendances : pip install requests
"""

import os
import sys
import json
import time
import datetime
from zoneinfo import ZoneInfo

import requests

import ui_discord as ui

# ─────────────────────────────────────────────────────────────
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")
API = "https://api.coingecko.com/api/v3"
STATE_FILE = "previous_prices.json"

# symbole -> id CoinGecko
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


def slot_actuel(now):
    """Créneau du brief, tolérant au retard de GitHub Actions.
    matin = 6h→11h59, soir = 20h→23h59 (heure de Paris)."""
    h = now.hour
    if 6 <= h < 12:
        return "matin"
    if 20 <= h < 24:
        return "soir"
    return None


def deja_poste(previous, slot, now):
    """True si ce créneau a déjà été posté aujourd'hui (état explicite)."""
    posted = previous.get("posted", {})
    return posted.get(slot) == now.date().isoformat()


def fmt(v):
    if v is None:
        return "n/d"
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


def fetch_data():
    """Prix EUR + variation 24h en un appel, prix USD en un autre."""
    ids = ",".join(COINS.values())
    eur, var24, usd = {}, {}, {}
    try:
        markets = fetch_json(f"{API}/coins/markets",
                             {"vs_currency": "eur", "ids": ids})
        for m in markets:
            eur[m["id"]] = m.get("current_price")
            var24[m["id"]] = m.get("price_change_percentage_24h")
    except Exception as e:
        print(f"[warn] marchés EUR : {e}")
    time.sleep(3)
    try:
        data = fetch_json(f"{API}/simple/price",
                          {"ids": ids, "vs_currencies": "usd"})
        for cid, v in data.items():
            usd[cid] = v.get("usd")
    except Exception as e:
        print(f"[warn] prix USD : {e}")
    return eur, var24, usd


def load_previous():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_current(eur, previous, slot, now):
    """Mémorise les prix + marque le créneau comme posté (si créneau réel)."""
    posted = dict(previous.get("posted", {}))
    if slot:  # None si lancement FORCE hors créneau : on ne bloque rien
        posted[slot] = now.date().isoformat()
    data = {
        "timestamp": now.strftime("%d/%m %Hh%M"),
        "posted": posted,
        "eur": eur,
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_summary_line(eur, var24, prev_eur):
    """Résumé synthétique du marché en 1-2 phrases."""
    vals = [(sym, var24.get(cid)) for sym, cid in COINS.items()
            if var24.get(cid) is not None]
    if not vals:
        return None

    ups = [(s, v) for s, v in vals if v >= 0]
    downs = [(s, v) for s, v in vals if v < 0]
    n = len(vals)

    # Tendance générale sur 24h
    if len(ups) == n:
        tone = "Marché entièrement dans le vert"
    elif len(downs) == n:
        tone = "Marché entièrement dans le rouge"
    elif len(ups) >= n * 0.7:
        tone = "Marché plutôt haussier"
    elif len(downs) >= n * 0.7:
        tone = "Marché plutôt baissier"
    else:
        tone = "Marché partagé"

    parts = [f"{tone} sur 24h ({len(ups)} hausse{'s' if len(ups) > 1 else ''}, "
             f"{len(downs)} baisse{'s' if len(downs) > 1 else ''})"]

    if ups:
        top = max(ups, key=lambda x: x[1])
        if top[1] >= 1:
            parts.append(f"{top[0]} mène à {top[1]:+.1f}%")
    if downs:
        worst = min(downs, key=lambda x: x[1])
        if worst[1] <= -1:
            parts.append(f"{worst[0]} recule le plus à {worst[1]:+.1f}%")

    phrase = ". ".join([parts[0]] + [", ".join(parts[1:])]) if len(parts) > 1 else parts[0]

    # Évolution moyenne depuis le brief précédent
    if prev_eur:
        deltas = []
        for sym, cid in COINS.items():
            p, c = prev_eur.get(cid), eur.get(cid)
            if p and c:
                deltas.append((c / p - 1) * 100)
        if deltas:
            avg = sum(deltas) / len(deltas)
            if avg >= 0.5:
                phrase += f". Depuis le dernier brief, l'ensemble progresse ({avg:+.1f}% en moyenne)"
            elif avg <= -0.5:
                phrase += f". Depuis le dernier brief, l'ensemble se replie ({avg:+.1f}% en moyenne)"
            else:
                phrase += ". Peu de mouvement depuis le dernier brief"

    return phrase + "."


def build_message(eur, var24, usd, previous):
    """Brief compact : hausses puis baisses, 2 lignes par crypto
    (prix € + variation 24h en gros, puis $ et écart depuis le dernier brief en petit)."""
    now_dt = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    prev_eur = previous.get("eur", {})
    prev_ts = previous.get("timestamp")          # ex. "30/09 06h01"
    prev_heure = prev_ts.split(" ")[-1] if prev_ts else None

    if now_dt.hour < 12:
        titre = "☀️ Brief crypto du matin"
    elif now_dt.hour >= 20:
        titre = "🌙 Brief crypto du soir"
    else:
        titre = "📊 Brief crypto"

    items = []
    for sym, cid in COINS.items():
        v = var24.get(cid)
        details = []
        if usd.get(cid) is not None:
            details.append(f"{ui.fmt_fr(usd.get(cid))}{ui.NBSP}$")
        p, c = prev_eur.get(cid), eur.get(cid)
        if prev_heure and p and c:
            details.append(f"depuis {prev_heure} : {ui.pct_fr((c / p - 1) * 100, fleche=True)}")
        items.append((v, ui.ligne_crypto(sym, v, f"{ui.fmt_fr(eur.get(cid))}{ui.NBSP}€", details)))

    parties = []
    resume = build_summary_line(eur, var24, prev_eur)
    if resume:
        parties.append(resume)
    parties += ui.groupes(items)

    return {
        "title": titre,
        "color": ui.couleur_tendance(var24.get(cid) for cid in COINS.values()),
        "description": "\n\n".join(parties),
        "footer": {"text": f"Gros chiffre = variation sur 24h · {ui.SOURCE}"},
        "timestamp": now_dt.isoformat(),
    }


def post_to_discord(embed):
    ui.post_embeds(WEBHOOK_URL, [embed])
    print("Posté sur Discord ✔")


def main():
    if not WEBHOOK_URL:
        print("Erreur : secret DISCORD_WEBHOOK manquant.")
        sys.exit(1)

    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    previous = load_previous()
    slot = slot_actuel(now)
    force = os.environ.get("FORCE") == "1"

    if not force:
        if slot is None:
            print(f"Pas l'heure de poster (Paris {now.strftime('%H:%M')}). On s'arrête.")
            return
        if deja_poste(previous, slot, now):
            print(f"Brief du {slot} déjà posté aujourd'hui. On s'arrête.")
            return

    eur, var24, usd = fetch_data()
    if not eur:
        print("Aucune donnée récupérée, rien posté.")
        return

    message = build_message(eur, var24, usd, previous)
    post_to_discord(message)
    save_current(eur, previous, slot, now)   # mémorise pour le prochain brief


if __name__ == "__main__":
    main()
