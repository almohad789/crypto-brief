#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brief crypto Discord — 6h et 20h (heure française)
Poste un graphique (une ligne horizontale par crypto) avec logo, prix € et $,
variation %, sur fond transparent, dans un salon Discord via webhook.
 
Dépendances : pip install requests matplotlib pillow
"""
 
import io
import os
import sys
import time
import datetime
from zoneinfo import ZoneInfo
 
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
 
# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "")
DAYS = 1            # fenêtre du graphique (1 = 24h)
API = "https://api.coingecko.com/api/v3"
 
# symbole -> (id CoinGecko, couleur de la courbe)
COINS = {
    "BTC":  ("bitcoin",          "#f7931a"),
    "ETH":  ("ethereum",         "#627eea"),
    "SOL":  ("solana",           "#14f195"),
    "XRP":  ("ripple",           "#00aae4"),
    "LTC":  ("litecoin",         "#a6a9aa"),
    "ONDO": ("ondo-finance",     "#4f7cff"),
    "HBAR": ("hedera-hashgraph", "#8259ef"),
    "XDC":  ("xdce-crowd-sale",  "#f4900c"),
}
 
 
def heure_autorisee():
    if os.environ.get("FORCE") == "1":
        return True
    return datetime.datetime.now(ZoneInfo("Europe/Paris")).hour in (6, 20)
 
 
def fmt(v):
    if v is None:
        return "—"
    if v >= 1000:
        return f"{v:,.0f}".replace(",", " ")
    if v >= 1:
        return f"{v:,.2f}".replace(",", " ")
    return f"{v:.4f}"
 
 
# ─────────────────────────────────────────────────────────────
# RÉCUPÉRATION DES DONNÉES
# ─────────────────────────────────────────────────────────────
def fetch_json(url, params=None, retries=4):
    """GET avec réessais automatiques si limite de débit (429)."""
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            wait = 20 * (attempt + 1)   # 20s, 40s, 60s...
            print(f"[info] limite API atteinte, on attend {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return r.json()
 
 
def fetch_all():
    ids = ",".join(cid for cid, _ in COINS.values())
 
    # Prix USD (une seule requête)
    try:
        usd = fetch_json(f"{API}/simple/price",
                         {"ids": ids, "vs_currencies": "usd"})
    except Exception as e:
        print(f"[warn] prix USD : {e}")
        usd = {}
 
    # Prix EUR + URL des logos (une seule requête)
    logos_url = {}
    eur = {}
    try:
        markets = fetch_json(f"{API}/coins/markets",
                             {"vs_currency": "eur", "ids": ids})
        for m in markets:
            eur[m["id"]] = m.get("current_price")
            logos_url[m["id"]] = m.get("image")
    except Exception as e:
        print(f"[warn] marchés EUR : {e}")
 
    # Courbe (variation %) par crypto
    curves = {}
    for sym, (cid, _) in COINS.items():
        try:
            data = fetch_json(f"{API}/coins/{cid}/market_chart",
                              {"vs_currency": "eur", "days": DAYS})
            prices = data.get("prices", [])
            if prices:
                t0 = prices[0][0]
                base = prices[0][1]
                xs = [(p[0] - t0) / 3_600_000 for p in prices]
                ys = [(p[1] / base - 1) * 100 for p in prices]
                curves[sym] = (xs, ys)
                if eur.get(cid) is None:
                    eur[cid] = prices[-1][1]
        except Exception as e:
            print(f"[warn] courbe {sym} ({cid}) : {e}")
        time.sleep(8)  # pause généreuse pour rester sous la limite CoinGecko
 
    return curves, eur, usd, logos_url
 
 
def load_logo(sym, cid, url):
    """Télécharge et recadre le logo en carré transparent 96px."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        w, h = im.size
        s = max(w, h)
        canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        canvas.paste(im, ((s - w) // 2, (s - h) // 2), im)
        return canvas.resize((96, 96), Image.LANCZOS)
    except Exception as e:
        print(f"[warn] logo {sym} : {e}")
        return None
 
 
# ─────────────────────────────────────────────────────────────
# GRAPHIQUE
# ─────────────────────────────────────────────────────────────
def build_chart(curves, eur, usd, logos):
    syms = [s for s in COINS if s in curves]
    if not syms:
        return None, {}
 
    hours = int(DAYS * 24)
    ticks = [0, hours // 4, hours // 2, 3 * hours // 4, hours]
 
    plt.style.use("dark_background")
    nrows = len(syms)
    fig, axes = plt.subplots(nrows, 1, figsize=(7.2, 0.72 * nrows),
                             dpi=140, sharex=False)
    if nrows == 1:
        axes = [axes]
 
    summary = {}
    for ax, sym in zip(axes, syms):
        cid, color = COINS[sym]
        xs, ys = curves[sym]
        var = ys[-1]
        summary[sym] = var
        up = var >= 0
 
        box = FancyBboxPatch(
            (0.0, 0.0), 1.0, 1.0,
            boxstyle="round,pad=0,rounding_size=0.06",
            mutation_aspect=0.07,
            linewidth=0.8, edgecolor="#ffffff", facecolor="#1e1f22",
            transform=ax.transAxes, zorder=0, clip_on=False,
        )
        ax.add_patch(box)
 
        ax.plot(xs, ys, color=color, linewidth=1.8, zorder=3)
        ax.fill_between(xs, ys, 0, color=color, alpha=0.15, zorder=2)
        ax.axhline(0, color="#555", linewidth=0.6, linestyle="--", zorder=1)
 
        # Logo à gauche
        logo = logos.get(sym)
        if logo is not None:
            oi = OffsetImage(logo, zoom=0.28)
            ab = AnnotationBbox(oi, (-0.055, 0.5), xycoords=ax.transAxes,
                                frameon=False, box_alignment=(0.5, 0.5), zorder=5)
            ax.add_artist(ab)
 
        # Prix € et $ (gris) + variation % (couleur)
        usd_price = usd.get(cid, {}).get("usd") if isinstance(usd.get(cid), dict) else None
        ax.text(1.03, 0.80, f"{fmt(eur.get(cid))} €", transform=ax.transAxes,
                ha="left", va="center", fontsize=8, color="#6b7075")
        ax.text(1.03, 0.55, f"{fmt(usd_price)} $", transform=ax.transAxes,
                ha="left", va="center", fontsize=8, color="#6b7075")
        arrow = "\u25b2" if up else "\u25bc"
        vcol = "#3ba55d" if up else "#ed4245"
        ax.text(1.03, 0.20, f"{arrow} {var:+.1f}%", transform=ax.transAxes,
                ha="left", va="center", fontsize=9, fontweight="bold", color=vcol)
 
        ax.set_yticks([])
        ax.set_xticks(ticks)
        ax.set_xlim(0, hours)
        ax.tick_params(colors="#ffffff", labelsize=6.5, labelbottom=True,
                       length=2, pad=1)
        ax.patch.set_visible(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.margins(x=0)
 
    # En-tête : titre à gauche, date/heure à droite
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y %H:%M")
    fig.text(0.10, 0.965, "Brief crypto", ha="left", va="center",
             fontsize=13, fontweight="bold", color="#fff")
    fig.text(0.80, 0.965, now, ha="right", va="center",
             fontsize=10, color="#9aa0a6")
 
    fig.subplots_adjust(left=0.10, right=0.80, top=0.93, bottom=0.10, hspace=0.60)
 
    # Nom de chaque crypto en gris, au niveau du "0"
    fig.canvas.draw()
    for ax, sym in zip(axes, syms):
        x_disp, _ = ax.transAxes.transform((-0.055, 0.5))
        x_fig, _ = fig.transFigure.inverted().transform((x_disp, 0))
        lbls = ax.get_xticklabels()
        if lbls:
            bb = lbls[0].get_window_extent()
            _, y_fig = fig.transFigure.inverted().transform(
                ((bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2))
            fig.text(x_fig, y_fig, sym, ha="center", va="center",
                     fontsize=7, fontweight="bold", color="#6b7075")
 
    # Crédit en bas à droite
    fig.text(0.80, 0.045, "générée par almohad789", ha="right", va="center",
             fontsize=8, color="#6b7075", style="italic")
 
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf, summary
 
 
# ─────────────────────────────────────────────────────────────
# MESSAGE + ENVOI
# ─────────────────────────────────────────────────────────────
def build_message(summary):
    now = datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m %H:%M")
    hausses = sorted([(s, v) for s, v in summary.items() if v >= 0], key=lambda x: -x[1])
    baisses = sorted([(s, v) for s, v in summary.items() if v < 0], key=lambda x: x[1])
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
 
    curves, eur, usd, logos_url = fetch_all()
    logos = {}
    for sym, (cid, _) in COINS.items():
        if logos_url.get(cid):
            logos[sym] = load_logo(sym, cid, logos_url[cid])
 
    image_buf, summary = build_chart(curves, eur, usd, logos)
    if not summary:
        print("Aucune donnée récupérée, rien posté.")
        return
    post_to_discord(image_buf, build_message(summary))
 
 
if __name__ == "__main__":
    main()
 
