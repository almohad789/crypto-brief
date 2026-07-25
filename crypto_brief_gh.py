#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brief crypto Discord — 6h et 20h (heure de Paris), version texte simple.
Pour chaque crypto : nom, variation 24h (%), prix en € et $, et évolution
par rapport au brief précédent (sauvegardé dans previous_prices.json).
 
Dépendances : pip install requests
"""
 
import os
import sys
import json
import time
import datetime
from zoneinfo import ZoneInfo
 
import requests
 
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
    """Évite un doublon : le 2e cron saisonnier ne reposte pas le même créneau."""
    ts = previous.get("timestamp")
    if not ts:
        return False
    try:
        jour = ts.split(" ")[0]
        heure = int(ts.split(" ")[1].split("h")[0])
        prev_slot = "matin" if heure < 12 else "soir"
        return jour == now.strftime("%d/%m") and prev_slot == slot
    except Exception:
        return False
 
 
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
 
 
def save_current(eur):
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    data = {"timestamp": now.strftime("%d/%m %Hh%M"), "eur": eur}
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
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m %Hh%M")
    prev_eur = previous.get("eur", {})
    prev_ts = previous.get("timestamp")
 
    # Libellé du brief précédent : soir ou matin selon son heure
    prev_label = None
    if prev_ts:
        try:
            prev_hour = int(prev_ts.split(" ")[1].split("h")[0])
            moment = "soir" if prev_hour >= 12 else "matin"
            prev_label = f"brief du {moment} {prev_ts}"
        except Exception:
            prev_label = f"brief du {prev_ts}"
 
    lines = [f"**📊 Brief crypto — {now}**"]
    resume = build_summary_line(eur, var24, prev_eur)
    if resume:
        lines.append(resume)
    lines.append("```")
    header = f"{'Crypto':<6}{'24h':>7} {'Prix €':>8} {'Prix $':>8}"
    if prev_ts:
        header += f" {'vs':>7}"
    lines.append(header)
    lines.append("─" * len(header))
 
    for sym, cid in COINS.items():
        v = var24.get(cid)
        arrow = "▲" if (v or 0) >= 0 else "▼"
        pct = f"{arrow}{v:+.1f}%" if v is not None else "—"
        row = f"{sym:<6}{pct:>7} {fmt(eur.get(cid)):>8} {fmt(usd.get(cid)):>8}"
        if prev_ts:
            p = prev_eur.get(cid)
            c = eur.get(cid)
            if p and c:
                delta = (c / p - 1) * 100
                da = "▲" if delta >= 0 else "▼"
                row += f" {da}{delta:+.1f}%".rjust(8)
            else:
                row += f"{'—':>8}"
        lines.append(row)
 
    if prev_label:
        lines.append("─" * len(header))
        lines.append(f"vs = depuis {prev_label}")
    lines.append("```")
    return "\n".join(lines)
 
 
def post_to_discord(message):
    resp = requests.post(WEBHOOK_URL, json={"content": message}, timeout=30)
    resp.raise_for_status()
    print("Posté sur Discord ✔")
 
 
def main():
    if not WEBHOOK_URL:
        print("Erreur : secret DISCORD_WEBHOOK manquant.")
        sys.exit(1)

    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    previous = load_previous()

    if os.environ.get("FORCE") != "1":
        slot = slot_actuel(now)
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
 
    previous = load_previous()
    message = build_message(eur, var24, usd, previous)
    post_to_discord(message)
    save_current(eur)   # mémorise pour le prochain brief
 
 
if __name__ == "__main__":
    main()
 
