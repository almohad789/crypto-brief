#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alertes Market Cap — Discord.
Vérifie toutes les 30 min : si la market cap d'une crypto bouge de
±SEUIL % sur 24h, envoie une alerte immédiate.

SEUIL est configurable via la variable d'environnement SEUIL_ALERTE
(défaut : 10). Astuce : 10 % sur 24h est rare pour BTC/ETH — si tu veux
des alertes plus fréquentes, mets par exemple SEUIL_ALERTE=5.

FORCE=1 (lancement manuel) : envoie un message de test récapitulant les
variations actuelles, pour vérifier que le webhook fonctionne, sans
toucher à l'état anti-spam.

Anti-spam : pas de nouvelle alerte pour la même crypto pendant
COOLDOWN_H heures, sauf si le mouvement s'amplifie de 5 points ou plus.

État sauvegardé dans alerte_state.json (commité par le workflow).

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
STATE_FILE = "alerte_state.json"

try:
    SEUIL = float(os.environ.get("SEUIL_ALERTE", "10"))
except ValueError:
    SEUIL = 10.0
COOLDOWN_H = 12     # heures sans re-alerter la même crypto
AMPLIF = 5.0        # points de % supplémentaires qui court-circuitent le cooldown

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


def fmt_cap(v):
    """Market cap lisible : 1.23 T€, 45.6 Md€, 789 M€."""
    if v is None:
        return "—"
    if v >= 1e12:
        return f"{v/1e12:.2f} T€"
    if v >= 1e9:
        return f"{v/1e9:.1f} Md€"
    if v >= 1e6:
        return f"{v/1e6:.0f} M€"
    return f"{v:,.0f} €".replace(",", " ")


def fmt_prix(v):
    if v is None:
        return "—"
    if v >= 1000:
        return f"{v:,.0f}".replace(",", " ")
    if v >= 1:
        return f"{v:,.2f}".replace(",", " ")
    return f"{v:.4f}"


def fetch_json(url, params=None, retries=3):
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


def doit_alerter(cid, change, state, now_ts):
    """True si on alerte : seuil dépassé + cooldown respecté ou amplification."""
    if abs(change) < SEUIL:
        return False
    last = state.get(cid)
    if not last:
        return True
    elapsed_h = (now_ts - last["ts"]) / 3600
    if elapsed_h >= COOLDOWN_H:
        return True
    # même fenêtre de cooldown : on re-alerte seulement si ça s'amplifie
    if abs(change) >= abs(last["change"]) + AMPLIF:
        return True
    return False


def build_alert(sym, change, cap, prix_eur, prix_usd):
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m %Hh%M")
    sens = "📈 HAUSSE" if change >= 0 else "📉 CHUTE"
    arrow = "▲" if change >= 0 else "▼"
    return (
        f"🚨 **Alerte Market Cap — {sym}** ({now})\n"
        f"{sens} drastique : cap {arrow}{change:+.1f}% sur 24h\n"
        f"```\n"
        f"Market cap : {fmt_cap(cap)}\n"
        f"Prix       : {fmt_prix(prix_eur)} € / {fmt_prix(prix_usd)} $\n"
        f"```"
    )


def build_test_message(markets, sym_by_id):
    """Récap de contrôle envoyé lors d'un lancement manuel (FORCE=1)."""
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m %Hh%M")
    lines = [f"🧪 **Test alertes market cap — {now}** (seuil : ±{SEUIL:.0f}%)",
             "```",
             f"{'Crypto':<6}{'Cap 24h':>9}  {'Market cap':>10}",
             "─" * 28]
    for m in markets:
        sym = sym_by_id.get(m["id"], m["id"])
        ch = m.get("market_cap_change_percentage_24h")
        pct = f"{ch:+.1f}%" if ch is not None else "—"
        lines.append(f"{sym:<6}{pct:>9}  {fmt_cap(m.get('market_cap')):>10}")
    lines.append("```")
    lines.append("Le webhook et le script fonctionnent ✔ "
                 "Une vraie alerte partira dès qu'une cap dépasse le seuil.")
    return "\n".join(lines)


def post_to_discord(message):
    resp = requests.post(WEBHOOK_URL, json={"content": message}, timeout=30)
    resp.raise_for_status()


def main():
    if not WEBHOOK_URL:
        print("Erreur : secret DISCORD_WEBHOOK manquant.")
        sys.exit(1)

    ids = ",".join(COINS.values())
    try:
        markets = fetch_json(f"{API}/coins/markets", {
            "vs_currency": "eur", "ids": ids,
        })
    except Exception as e:
        print(f"[warn] marchés : {e}")
        return

    sym_by_id = {cid: sym for sym, cid in COINS.items()}

    # Mode test : lancement manuel -> message de contrôle, état intact
    if os.environ.get("FORCE") == "1":
        post_to_discord(build_test_message(markets, sym_by_id))
        print("Message de test envoyé ✔")
        return

    time.sleep(2)
    usd = {}
    try:
        data = fetch_json(f"{API}/simple/price", {"ids": ids, "vs_currencies": "usd"})
        for cid, v in data.items():
            usd[cid] = v.get("usd")
    except Exception as e:
        print(f"[warn] prix USD : {e}")

    state = load_state()
    now_ts = time.time()
    alertes = 0

    for m in markets:
        cid = m["id"]
        sym = sym_by_id.get(cid, cid)
        change = m.get("market_cap_change_percentage_24h")
        if change is None:
            continue
        if doit_alerter(cid, change, state, now_ts):
            msg = build_alert(sym, change, m.get("market_cap"),
                              m.get("current_price"), usd.get(cid))
            try:
                post_to_discord(msg)
                state[cid] = {"ts": now_ts, "change": change}
                alertes += 1
                print(f"Alerte {sym} ({change:+.1f}%) envoyée ✔")
                time.sleep(1)
            except Exception as e:
                print(f"[warn] envoi {sym} : {e}")
        else:
            print(f"{sym}: {change:+.1f}% — RAS")

    save_state(state)
    if alertes == 0:
        print("Aucune alerte à envoyer.")


if __name__ == "__main__":
    main()
