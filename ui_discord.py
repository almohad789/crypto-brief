#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Couche d'affichage Discord (embeds) partagée par les 3 scripts.

Seul l'affichage passe par ici : la récupération des données, les créneaux,
la déduplication et les fichiers d'état restent dans chaque script.

Choix de mise en page :
  - une "field" inline par crypto : 3 colonnes sur PC, empilées proprement
    sur mobile (fini les tableaux en bloc de code qui débordent sur téléphone)
  - couleur de la barre latérale selon la tendance du marché
  - timestamp natif Discord : chaque membre voit l'heure dans son fuseau
"""

import requests

# Couleurs de la barre latérale
VERT = 0x2ECC71
ROUGE = 0xE74C3C
JAUNE = 0xF1C40F
BLURPLE = 0x5865F2

SOURCE = "Données CoinGecko"


def pastille(v):
    """Pastille de couleur selon le signe d'une variation."""
    if v is None:
        return "⚪"
    return "🟢" if v >= 0 else "🔴"


def pct(v, fleche=True):
    """Variation formatée : ▲ +1.6% / ▼ -2.3% (arrondi à l'unité au dela de 100%)."""
    if v is None:
        return "n/d"
    txt = f"{v:+.1f}%" if abs(v) < 100 else f"{v:+.0f}%"
    if not fleche:
        return txt
    return f"{'▲' if v >= 0 else '▼'} {txt}"


def prix(v, devise, fmt):
    """Prix formaté avec la fonction fmt du script, ou n/d."""
    return f"{fmt(v)} {devise}" if v is not None else "n/d"


def couleur_tendance(valeurs):
    """Vert si >= 70% des cryptos montent, rouge si >= 70% baissent, jaune sinon."""
    vals = [v for v in valeurs if v is not None]
    if not vals:
        return BLURPLE
    ups = sum(1 for v in vals if v >= 0)
    if ups >= len(vals) * 0.7:
        return VERT
    if (len(vals) - ups) >= len(vals) * 0.7:
        return ROUGE
    return JAUNE


NBSP = "\u00a0"


def fmt_fr(v):
    """Nombre au format français : 73 585 / 105,33 / 0,4453."""
    if v is None:
        return "n/d"
    if v >= 1000:
        txt = f"{v:,.0f}"
    elif v >= 1:
        txt = f"{v:,.2f}"
    else:
        txt = f"{v:.4f}"
    return txt.replace(",", " ").replace(".", ",").replace(" ", NBSP)


def pct_fr(v, fleche=False):
    """Variation au format français : +1,5 % (ou ▲ +1,5 %)."""
    if v is None:
        return "n/d"
    txt = (f"{v:+.1f}" if abs(v) < 100 else f"{v:+.0f}").replace(".", ",") + NBSP + "%"
    if fleche:
        txt = ("▲" if v >= 0 else "▼") + NBSP + txt
    return txt


def ligne_crypto(sym, v, principal, details=None):
    """Présentation compacte : grande ligne (pastille, nom, valeur, variation en gras)
    puis petite ligne grise (sous texte Discord) avec les détails."""
    l1 = f"{pastille(v)} **{sym}**{NBSP}{NBSP}{principal}{NBSP}{NBSP}**{pct_fr(v)}**"
    details = [d for d in (details or []) if d]
    return l1 + ("\n-# " + " · ".join(details) if details else "")


def groupes(items):
    """items = [(variation, texte)] -> blocs « En hausse » / « En baisse », triés."""
    tri = sorted(items, key=lambda x: x[0] if x[0] is not None else 0, reverse=True)
    hausses = [t for v, t in tri if (v or 0) >= 0]
    baisses = [t for v, t in tri if (v or 0) < 0]
    blocs = []
    if hausses:
        blocs.append("**📈 En hausse**\n" + "\n".join(hausses))
    if baisses:
        blocs.append("**📉 En baisse**\n" + "\n".join(baisses))
    return blocs


def field(nom, valeur, inline=True):
    return {"name": nom[:256], "value": (valeur or "\u200b")[:1024], "inline": inline}


def post_embeds(webhook_url, embeds):
    """Envoie jusqu'à 10 embeds en un message, sans aucune mention possible."""
    payload = {"embeds": embeds[:10], "allowed_mentions": {"parse": []}}
    resp = requests.post(webhook_url, json=payload, timeout=30)
    if resp.status_code >= 400:
        print(f"[erreur] Discord {resp.status_code} : {resp.text[:500]}")
    resp.raise_for_status()
