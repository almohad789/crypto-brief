#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brief crypto Discord — 6h et 20h (heure française)
Poste UN graphique compact regroupant BTC ETH SOL XRP LTC ONDO HBAR XDC
(en variation %) + les annonces de hausse/baisse dans un salon Discord.

Dépendances :  pip install requests matplotlib
"""

import io
import os
import sys
import datetime
from zoneinfo import ZoneInfo
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
# Le webhook est lu depuis un secret GitHub (variable d'environnement),
# on ne l'écrit JAMAIS en clair dans le code.
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")

# Sécurité changement d'heure : GitHub réveille le script à plusieurs
# heures UTC, mais on ne poste QUE si l'heure de Paris est 6h ou 20h.
# Mets FORCE=1 en variable d'env pour ignorer ce garde (test manuel).
def heure_autorisee():
    if os.environ.get("FORCE") == "1":
        return True
    h = datetime.datetime.now(ZoneInfo("Europe/Paris")).hour
    return h in (6, 20)

# Fenêtre du graphique en jours (1 = dernières 24h). 0.5 possible aussi.
DAYS = 1

# Devise d'affichage
VS = "eur"   # "eur" ou "usd"

# Cryptos suivies : symbole affiché -> id CoinGecko + couleur
COINS = {
    "BTC":  ("bitcoin",         "#f7931a"),
    "ETH":  ("ethereum",        "#627eea"),
    "SOL":  ("solana",          "#14f195"),
    "XRP":  ("ripple",          "#00aae4"),
    "LTC":  ("litecoin",        "#a6a9aa"),
    "ONDO": ("ondo-finance",    "#4f7cff"),
    "HBAR": ("hedera-hashgraph","#8259ef"),
    "XDC":  ("xdce-crowd-sale", "#f4900c"),
}

API = "https://api.coingecko.com/api/v3"
# ─────────────────────────────────────────────────────────────


def fetch_series(coin_id):
    """Récupère les prix (timestamp, prix) sur la fenêtre DAYS."""
    r = requests.get(
        f"{API}/coins/{coin_id}/market_chart",
        params={"vs_currency": VS, "days": DAYS},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["prices"]  # [[ms, price], ...]


def build_chart_and_summary():
    """Une ligne horizontale (mini-graphe) par crypto, empilées."""
    # 1) On récupère d'abord toutes les données valides
    data = {}      # sym -> (xs, ys)
    summary = {}   # sym -> variation %
    for sym, (cid, color) in COINS.items():
        try:
            prices = fetch_series(cid)
        except Exception as e:
            print(f"[warn] {sym} ({cid}) : {e}")
            continue
        if not prices:
            continue
        t0 = prices[0][0]
        base = prices[0][1]
        xs = [(p[0] - t0) / 3_600_000 for p in prices]   # heures écoulées
        ys = [(p[1] / base - 1) * 100 for p in prices]    # variation %
        data[sym] = (xs, ys)
        summary[sym] = ys[-1]

    if not data:
        return None, {}

    # 2) Un sous-graphe par crypto
    plt.style.use("dark_background")
    nrows = len(data)
    fig, axes = plt.subplots(nrows, 1, figsize=(7.2, 0.72 * nrows),
                             dpi=140, sharex=True)
    if nrows == 1:
        axes = [axes]

    hours = int(DAYS * 24)
    for ax, sym in zip(axes, data):
        xs, ys = data[sym]
        color = COINS[sym][1]
        up = ys[-1] >= 0
        ax.plot(xs, ys, color=color, linewidth=1.8)
        ax.fill_between(xs, ys, 0, color=color, alpha=0.12)
        ax.axhline(0, color="#444", linewidth=0.6, linestyle="--")
        ax.text(-0.02, 0.5, sym, transform=ax.transAxes, ha="right", va="center",
                fontsize=10, fontweight="bold", color="#fff")
        arrow = "\u25b2" if up else "\u25bc"
        vcol = "#3ba55d" if up else "#ed4245"
        ax.text(1.015, 0.5, f"{arrow} {ys[-1]:+.1f}%", transform=ax.transAxes,
                ha="left", va="center", fontsize=9, fontweight="bold", color=vcol)
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.margins(x=0)

    axes[-1].set_xticks([0, hours // 4, hours // 2, 3 * hours // 4, hours])
    axes[-1].tick_params(colors="#777", labelsize=7)
    fig.suptitle(f"Brief crypto — {hours}h ({VS.upper()})",
                 fontsize=12, fontweight="bold", color="#fff", y=0.995)
    fig.subplots_adjust(left=0.10, right=0.86, top=0.93, bottom=0.06, hspace=0.35)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#1e1f22")
    plt.close(fig)
    buf.seek(0)
    return buf, summary


def build_message(summary):
    now = datetime.datetime.now().strftime("%d/%m %H:%M")
    hausses = sorted([(s, v) for s, v in summary.items() if v >= 0],
                     key=lambda x: -x[1])
    baisses = sorted([(s, v) for s, v in summary.items() if v < 0],
                     key=lambda x: x[1])

    lines = [f"**📊 Brief crypto — {now}**", "```"]
    if hausses:
        lines.append("✅ HAUSSES")
        for s, v in hausses:
            lines.append(f"   {s:<5} {v:+.1f}%")
    if baisses:
        if hausses:
            lines.append("")
        lines.append("🔻 BAISSES")
        for s, v in baisses:
            lines.append(f"   {s:<5} {v:+.1f}%")
    lines.append("```")
    return "\n".join(lines)


def post_to_discord(image_buf, message):
    resp = requests.post(
        WEBHOOK_URL,
        data={"content": message},
        files={"file": ("crypto.png", image_buf, "image/png")},
        timeout=30,
    )
    resp.raise_for_status()
    print("Posté sur Discord ✔")


def main():
    if not WEBHOOK_URL:
        print("Erreur : secret DISCORD_WEBHOOK manquant.")
        sys.exit(1)
    if not heure_autorisee():
        h = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M")
        print(f"Pas l'heure de poster (Paris {h}). On s'arrête.")
        return
    image_buf, summary = build_chart_and_summary()
    if not summary:
        print("Aucune donnée récupérée, rien posté.")
        return
    message = build_message(summary)
    post_to_discord(image_buf, message)


if __name__ == "__main__":
    main()
