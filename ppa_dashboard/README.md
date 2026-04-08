# PPA Pricing Dashboard — France Solaire

Dashboard interactif de pricing PPA solaire, basé sur les données ENTSO-E France 2014–2025.

## Structure des fichiers

```
ppa_dashboard/
├── app.py                    ← Application Streamlit principale
├── requirements.txt          ← Dépendances Python
├── data/
│   ├── nat_reference.csv     ← National M0 annuel (2014–2025)
│   └── hourly_spot.csv       ← Prix spot horaire (2014–2025)
└── README.md
```

## Déploiement sur Streamlit Cloud (gratuit, 10 minutes)

### Étape 1 — Créer un compte GitHub
- Aller sur https://github.com
- Créer un compte gratuit si vous n'en avez pas

### Étape 2 — Créer un repository
- Cliquer **New repository**
- Nom : `ppa-dashboard` (ou ce que vous voulez)
- Visibilité : **Public** (requis pour Streamlit Cloud gratuit)
- Cliquer **Create repository**

### Étape 3 — Uploader les fichiers
Dans le repository GitHub :
- Cliquer **Add file → Upload files**
- Glisser-déposer tous les fichiers :
  - `app.py`
  - `requirements.txt`
  - Le dossier `data/` avec ses deux CSV

### Étape 4 — Déployer sur Streamlit Cloud
- Aller sur https://share.streamlit.io
- Se connecter avec votre compte GitHub
- Cliquer **New app**
- Sélectionner votre repository `ppa-dashboard`
- Main file path : `app.py`
- Cliquer **Deploy**
- Attendre ~2 minutes → votre app est en ligne !

### URL de votre app
```
https://[votre-username]-ppa-dashboard-app-XXXX.streamlit.app
```

## Format de la courbe de charge

Le fichier à uploader dans l'app doit avoir **exactement 2 colonnes** :

| Date | Prod_MWh |
|------|----------|
| 2024-01-01 00:00:00 | 0.0 |
| 2024-01-01 01:00:00 | 0.0 |
| 2024-01-01 10:00:00 | 4.2 |
| 2024-01-01 11:00:00 | 7.8 |
| ... | ... |

- **Date** : format datetime, pas horaire (UTC ou heure locale)
- **Prod_MWh** : production en MWh (ou kWh — le script détecte et convertit automatiquement)
- Formats acceptés : `.xlsx` ou `.csv`

> Le nom exact des colonnes n'a pas d'importance — le script détecte automatiquement
> la colonne date (contient "date" ou "time") et la colonne production (contient "prod", "mwh", "power" ou "gen").

## Logique de pricing

```
Shape Discount (%) = 1 − Captured Price %      ← cannibalisation
Total Discount (%) = Shape Disc + Imbalance % + Décote additionnelle
Multiplier         = 1 − Total Discount
PPA Price (€/MWh)  = Forward × Multiplier − Imbalance (€/MWh)

P&L (€/MWh)       = Captured Price − PPA Price
P&L (€/an)        = Volume (MWh) × P&L (€/MWh)
```

Source de la logique : format WPD Tender Summary + analyse SEFE Germany Financial Swap.

## Mise à jour des données

Pour mettre à jour les données ENTSO-E (ex. : ajouter l'année 2026) :
1. Utiliser le script `entsoe_extractor.py` (voir documentation séparée)
2. Remplacer `data/hourly_spot.csv` et `data/nat_reference.csv`
3. Git push → Streamlit Cloud se met à jour automatiquement

## Paramètres disponibles dans la sidebar

| Paramètre | Description |
|-----------|-------------|
| CAL Forward | Prix forward EEX (€/MWh) |
| Années de régression | Nombre d'années pour calibrer la tendance |
| Exclure 2022 | Retire la crise énergétique de la régression |
| Marge cible | Marge souhaitée (€/MWh) |
| Coût imbalance | Coût d'imbalance fixe (€/MWh) |
| Décote additionnelle | Décote supplémentaire si nécessaire |
| Percentile choisi | P1–P100 pour le pricing (WPD = P74) |
| Horizon projection | 1–10 ans |
| Stress volume | ±% pour les scénarios de volume |
| Stress spot | ±% pour les scénarios de prix spot |
