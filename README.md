[README.md](https://github.com/user-attachments/files/30365915/README.md)
# 📊 Almocrypto — Brief crypto automatique pour Discord

Bot de suivi crypto **100 % gratuit et sans serveur**, propulsé par GitHub Actions.
Il poste automatiquement dans un salon Discord (via webhook) des briefs quotidiens
et des bilans périodiques sur 8 cryptomonnaies.

> Généré par **almohad789** 🚀

---

## 🪙 Cryptos suivies

| Symbole | Nom | ID CoinGecko |
|---|---|---|
| BTC | Bitcoin | `bitcoin` |
| ETH | Ethereum | `ethereum` |
| SOL | Solana | `solana` |
| XRP | Ripple | `ripple` |
| LTC | Litecoin | `litecoin` |
| ONDO | Ondo | `ondo-finance` |
| HBAR | Hedera | `hedera-hashgraph` |
| XDC | XDC Network | `xdce-crowd-sale` |

Données : [API publique CoinGecko](https://www.coingecko.com) (aucune clé requise).

---

## 🕕 Ce que le bot envoie

### 1. Brief quotidien — 6h et 20h (heure de Paris)

Fichier : `crypto_brief_gh.py` · Workflow : `.github/workflows/crypto.yml`

Deux fois par jour, un message compact (optimisé mobile) avec :
- 🧠 un **résumé automatique** du marché (tendance, meilleur/pire performeur)
- 📋 un tableau : variation **24h**, prix en **€** et en **$**
- 🔁 une colonne **vs** : l'évolution depuis le brief précédent
  - le brief de **6h** se compare au brief de **20h de la veille** (la nuit)
  - le brief de **20h** se compare au brief de **6h du matin** (la journée)

```
Crypto    24h   Prix €   Prix $      vs
───────────────────────────────────────
BTC    ▼-1.6%   56 332   64 106  ▼-0.1%
ETH    ▼-1.2%    1 636    1 862  ▲+0.0%
...
───────────────────────────────────────
vs = depuis brief du matin 25/07 06h00
```

La comparaison fonctionne grâce au fichier **`previous_prices.json`**,
mis à jour automatiquement après chaque brief (commits "maj prix brief").
⚠️ Ne pas supprimer ni modifier ce fichier.

### 2. Bilans périodiques — 12h (heure de Paris)

Fichier : `bilan_crypto.py` · Workflow : `.github/workflows/bilan.yml`

Indépendant du brief quotidien. Poste selon le calendrier :

| Bilan | Quand | Période affichée |
|---|---|---|
| 📈 Semaine | chaque **lundi** | 7 derniers jours |
| 📈 Mois | le **1er du mois** | 30 derniers jours |
| 📈 3 mois | 1er **janv / avril / juil / oct** | 90 derniers jours |
| 📈 Année | le **1er janvier** | 365 derniers jours |

Les jours où plusieurs bilans tombent en même temps (ex. 1er janvier),
ils sont envoyés à la suite. Les autres jours : rien n'est posté.

---

## ⚙️ Comment ça marche

- **GitHub Actions** déclenche les scripts aux horaires prévus (crons en UTC,
  doublés pour couvrir heure d'été et heure d'hiver ; le script vérifie
  lui-même l'heure de Paris avant de poster).
- Les scripts interrogent **CoinGecko**, construisent le message et l'envoient
  au salon Discord via un **webhook**.
- Aucun serveur, aucun PC allumé, aucun coût.

### Secrets requis

Dans *Settings → Secrets and variables → Actions* :

| Secret | Contenu |
|---|---|
| `DISCORD_WEBHOOK` | l'URL du webhook Discord du salon (à garder privée !) |

---

## 🧪 Tester manuellement

Onglet **Actions** → choisir le workflow → **Run workflow** :

- **Brief crypto Discord** → envoie le brief immédiatement (ignore l'horaire 6h/20h).
- **Bilans crypto Discord** → envoie **les 4 bilans d'un coup** (ignore le calendrier).
  Le bilan 3 mois prend 1-2 minutes (une requête par crypto).

---

## 🛠️ Personnaliser

- **Ajouter/retirer une crypto** : modifier le dictionnaire `COINS` en haut de
  `crypto_brief_gh.py` et `bilan_crypto.py` (symbole → ID CoinGecko, trouvable
  sur la page CoinGecko de la crypto, champ "API ID").
- **Changer les horaires** : modifier les lignes `cron` dans les fichiers
  `.github/workflows/*.yml` (⚠️ en UTC) **et** l'heure vérifiée dans la
  fonction `heure_autorisee()` / `bilans_du_jour()` du script correspondant.

---

## 📁 Structure du repo

```
crypto-brief/
├── crypto_brief_gh.py        # brief quotidien 6h/20h
├── bilan_crypto.py           # bilans semaine/mois/3mois/année
├── previous_prices.json      # mémoire du brief (auto-généré, ne pas toucher)
└── .github/workflows/
    ├── crypto.yml            # planning du brief quotidien
    └── bilan.yml             # planning des bilans
```

---

## ⚠️ Limites connues

- GitHub Actions peut déclencher avec **quelques minutes de retard** (rarement plus).
- L'API gratuite CoinGecko a une **limite de débit** : les scripts patientent et
  réessaient automatiquement en cas de blocage temporaire (429).
- Les périodes des bilans sont des **fenêtres glissantes** (30 derniers jours,
  365 derniers jours...), très proches mais pas exactement calendaires.

---

*Ce bot fournit des informations, pas des conseils d'investissement. DYOR 😉*
