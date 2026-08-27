# 📊 Almocrypto : brief crypto automatique pour Discord

Suivi crypto **100 % gratuit et sans serveur**, propulsé par GitHub Actions.
Trois automatisations indépendantes postent dans un salon Discord via webhook :
un **brief** deux fois par jour, des **bilans** périodiques, et des **alertes**
market cap en temps quasi réel.

> Généré par **almohad789** 🚀

---

## 🪙 Cryptos suivies

| Symbole | Nom         | ID CoinGecko       |
| ------- | ----------- | ------------------ |
| BTC     | Bitcoin     | `bitcoin`          |
| ETH     | Ethereum    | `ethereum`         |
| SOL     | Solana      | `solana`           |
| XRP     | Ripple      | `ripple`           |
| LTC     | Litecoin    | `litecoin`         |
| ONDO    | Ondo        | `ondo-finance`     |
| HBAR    | Hedera      | `hedera-hashgraph` |
| XDC     | XDC Network | `xdce-crowd-sale`  |

Données : [API publique CoinGecko](https://www.coingecko.com), aucune clé requise.

---

## 🕕 Ce que le bot envoie

### 1. Brief quotidien : matin et soir

Fichier : `crypto_brief_gh.py` · Workflow : `.github/workflows/crypto.yml`

Deux messages par jour, compacts et optimisés mobile :

* 🧠 un **résumé automatique** du marché (tendance sur 24h, meilleur et pire performeur,
  évolution moyenne depuis le brief précédent)
* 📋 un tableau : variation **24h**, prix en **€** et en **$**
* 🔁 une colonne **vs** : l'évolution depuis le brief précédent
  * le brief du **matin** se compare à celui du **soir de la veille** (la nuit)
  * le brief du **soir** se compare à celui du **matin** (la journée)

```
Crypto    24h   Prix €   Prix $      vs
───────────────────────────────────────
BTC    ▼-1.6%   56 332   64 106  ▼-0.1%
ETH    ▼-1.2%    1 636    1 862  ▲+0.0%
...
───────────────────────────────────────
vs = depuis brief du matin 25/07 06h00
```

**Créneaux, pas horaires fixes.** GitHub retarde souvent ses crons, parfois de
plusieurs heures. Le workflow tente donc sa chance toutes les 30 minutes sur
deux plages larges : **matin de 6h à 11h59** et **soir de 20h à 23h59** (heure
de Paris). Le premier passage qui tombe dans la plage poste le brief et marque
le créneau comme fait dans `previous_prices.json` ; tous les suivants s'arrêtent
en deux secondes sans rien envoyer. Résultat : jamais de doublon, jamais de
brief perdu à cause d'un retard.

⚠️ `previous_prices.json` sert à la fois de mémoire des prix et de verrou
anti doublon (clé `posted`). Ne pas le supprimer ni l'éditer à la main.

### 2. Bilans périodiques

Fichier : `bilan_crypto.py` · Workflow : `.github/workflows/bilan.yml`

| Bilan      | Échéance                          | Période affichée   |
| ---------- | --------------------------------- | ------------------ |
| 📈 Semaine | chaque **lundi**                  | 7 derniers jours   |
| 📈 Mois    | le **1er du mois**                | 30 derniers jours  |
| 📈 3 mois  | 1er **janv / avril / juil / oct** | 90 derniers jours  |
| 📈 Année   | le **1er janvier**                | 365 derniers jours |

**Rattrapage automatique.** Un bilan dû reste dû tant qu'il n'a pas été posté :
3 jours de rattrapage pour le bilan semaine, 7 jours pour les autres. Le jour de
l'échéance, l'envoi attend **12h** (heure de Paris) ; les jours de rattrapage,
il part dès **8h**. `bilan_state.json` mémorise la date du dernier envoi de
chaque bilan, ce qui rend tout doublon impossible.

Quand plusieurs bilans tombent le même jour (le 1er janvier par exemple), ils
sont envoyés à la suite. Les autres jours, rien n'est posté.

### 3. Alertes market cap

Fichier : `alerte_crypto.py` · Workflow : `.github/workflows/alerte.yml`

Contrôle toutes les 30 minutes. Si la **capitalisation** d'une crypto bouge de
**±10 %** sur 24h, une alerte part immédiatement :

```
🚨 Alerte Market Cap — SOL (25/07 14h43)
📉 CHUTE drastique : cap ▼-12.4% sur 24h
Market cap : 45.6 Md€
Prix       : 128,40 € / 146,20 $
```

* **Seuil** : 10 % par défaut, réglable via la variable d'environnement
  `SEUIL_ALERTE` (une ligne commentée dans `alerte.yml` attend une valeur de 5
  pour des alertes plus fréquentes ; 10 % sur 24h reste rare pour BTC et ETH).
* **Anti spam** : pas de seconde alerte sur la même crypto pendant **12 heures**,
  sauf si le mouvement s'amplifie d'au moins **5 points** de pourcentage.
* L'état vit dans `alerte_state.json`, commité par le workflow.

---

## ⚙️ Comment ça marche

* **GitHub Actions** déclenche les scripts. Les crons sont en UTC et volontairement
  larges : c'est chaque script qui vérifie l'heure de Paris, son créneau et son
  état avant de décider s'il poste.
* Les scripts interrogent **CoinGecko**, construisent le message et l'envoient au
  salon Discord via un **webhook**.
* Les fichiers d'état (`previous_prices.json`, `bilan_state.json`,
  `alerte_state.json`) sont recommités automatiquement après chaque envoi.
  Les trois workflows partagent le même groupe de concurrence
  (`crypto-brief-repo`) pour ne jamais pousser deux commits en même temps.
* Aucun serveur, aucun PC allumé, aucun coût.

### Secret requis

Dans *Settings → Secrets and variables → Actions* :

| Secret            | Contenu                                              |
| ----------------- | ---------------------------------------------------- |
| `DISCORD_WEBHOOK` | l'URL du webhook Discord du salon (à garder privée !) |

Variable optionnelle : `SEUIL_ALERTE` (nombre, défaut 10) pour le seuil d'alerte.

### Déclencheur externe conseillé pour les bilans

Les crons GitHub peuvent dériver de plusieurs heures. Pour les bilans, un ping
quotidien à 12h via [cron-job.org](https://cron-job.org) sur l'API
`workflow_dispatch` reste le déclencheur le plus fiable, la plage de crons
servant alors de filet de sécurité.

---

## 🧪 Tester manuellement

Onglet **Actions** → choisir le workflow → **Run workflow**. Un champ `mode`
apparaît :

| Mode             | Effet                                                                          |
| ---------------- | ------------------------------------------------------------------------------ |
| `test` (défaut)  | poste tout de suite, sans consommer l'état ni bloquer les envois planifiés     |
| `auto`           | se comporte exactement comme un cron : créneau, échéances et dédup respectés   |

En mode `test` :

* **Brief crypto Discord** envoie le brief immédiatement. S'il est lancé hors
  créneau (à 15h par exemple), il ne marque aucun créneau comme fait : le brief
  du soir partira quand même.
* **Bilans crypto Discord** envoie **les 4 bilans d'un coup**, sans toucher à
  `bilan_state.json`. Le bilan 3 mois prend une à deux minutes (un appel par
  crypto, espacé pour ménager l'API).
* **Alertes Market Cap** envoie un **message de contrôle** listant les variations
  de cap du moment, pour vérifier que le webhook répond, sans écrire dans l'état.

---

## 🛠️ Personnaliser

* **Ajouter ou retirer une crypto** : modifier le dictionnaire `COINS` en haut des
  **trois** scripts (`crypto_brief_gh.py`, `bilan_crypto.py`, `alerte_crypto.py`).
  L'identifiant CoinGecko se trouve sur la page de la crypto, champ "API ID".
* **Changer les créneaux du brief** : les plages sont définies dans
  `slot_actuel()` (`crypto_brief_gh.py`), pas dans le cron. Élargir ou déplacer
  la plage horaire là, puis ajuster les lignes `cron` du workflow (⚠️ en UTC).
* **Changer l'heure des bilans** : fonction `bilans_du_jour()` (`bilan_crypto.py`),
  constantes `CATCHUP` pour la durée de rattrapage.
* **Régler la sensibilité des alertes** : `SEUIL_ALERTE`, ou les constantes
  `COOLDOWN_H` et `AMPLIF` dans `alerte_crypto.py`.

---

## 📁 Structure du dépôt

```
crypto-brief/
├── crypto_brief_gh.py        # brief quotidien, créneaux matin et soir
├── bilan_crypto.py           # bilans semaine / mois / 3 mois / année
├── alerte_crypto.py          # alertes market cap, toutes les 30 min
├── previous_prices.json      # prix + créneaux déjà postés (auto, ne pas toucher)
├── bilan_state.json          # date du dernier envoi de chaque bilan (auto)
├── alerte_state.json         # dernière alerte par crypto (auto)
└── .github/workflows/
    ├── crypto.yml            # planning du brief
    ├── bilan.yml             # planning des bilans
    └── alerte.yml            # surveillance des market caps
```

---

## ⚠️ Limites connues

* GitHub Actions peut déclencher avec un retard important, parfois plusieurs
  heures. Toute la logique de créneaux, de rattrapage et de dédup existe pour
  absorber ça, mais un brief peut arriver à 9h plutôt qu'à 6h.
* L'API gratuite CoinGecko impose une **limite de débit** : les scripts patientent
  et réessaient automatiquement en cas de blocage temporaire (erreur 429).
* Les périodes des bilans sont des **fenêtres glissantes** (30 derniers jours,
  365 derniers jours), très proches mais pas exactement calendaires.
* Le bilan 3 mois est calculé crypto par crypto via `market_chart` : c'est le seul
  appel lent du dépôt.

---

*Ce bot fournit des informations, pas des conseils d'investissement. DYOR 😉*
