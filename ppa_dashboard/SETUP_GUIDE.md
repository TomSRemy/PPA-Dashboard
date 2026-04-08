# Guide de déploiement complet — PPA Dashboard avec mise à jour automatique

## ARCHITECTURE FINALE

```
GitHub Repository (code + données)
        │
        ├── GitHub Actions (tourne chaque matin à 08h UTC)
        │       └── Appelle ENTSO-E API → met à jour hourly_spot.csv
        │
        └── Streamlit Cloud (lit les CSV depuis GitHub)
                └── Votre dashboard en ligne
```

Flux : ENTSO-E → GitHub → Streamlit Cloud → Votre navigateur

---

## ÉTAPE 1 — Obtenir votre clé API ENTSO-E (5 min)

1. Aller sur https://transparency.entsoe.eu
2. Créer un compte (gratuit)
3. Aller dans **My Account Settings** → **Web API Security Token**
4. Cliquer **Generate a new token** → copier la clé
5. Garder cette clé, vous en aurez besoin à l'étape 4

---

## ÉTAPE 2 — Créer le repository GitHub (3 min)

1. Aller sur https://github.com → se connecter
2. Cliquer **New repository** (bouton vert)
3. Nom : `ppa-dashboard`
4. Visibilité : **Public** (requis pour Streamlit Cloud gratuit)
5. Cliquer **Create repository**

---

## ÉTAPE 3 — Uploader les fichiers (5 min)

Dans votre repository GitHub :

1. Cliquer **Add file → Upload files**
2. Dézipper le fichier `ppa_dashboard.zip` que vous avez téléchargé
3. Uploader **tous** les fichiers en respectant cette structure :

```
(racine du repo)
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── hourly_spot.csv
│   ├── nat_reference.csv
│   └── last_update.txt        ← créer un fichier texte vide
├── scripts/
│   └── update_entsoe.py
└── .github/
    └── workflows/
        └── update_data.yml
```

> ⚠️ Le dossier `.github/workflows/` est important — c'est lui qui déclenche la mise à jour automatique.

4. Cliquer **Commit changes**

---

## ÉTAPE 4 — Configurer la clé API ENTSO-E (2 min)

La clé API ne doit JAMAIS être écrite en dur dans le code.
GitHub la stocke de façon sécurisée dans les "Secrets".

1. Dans votre repository GitHub, aller dans **Settings**
2. Dans le menu gauche : **Secrets and variables → Actions**
3. Cliquer **New repository secret**
4. Name : `ENTSOE_API_KEY`
5. Secret : coller votre clé ENTSO-E
6. Cliquer **Add secret**

---

## ÉTAPE 5 — Tester la mise à jour manuelle (2 min)

Avant d'attendre 8h du matin, déclencher une mise à jour manuelle :

1. Dans votre repository, aller dans **Actions**
2. Dans le menu gauche, cliquer sur **Update ENTSO-E Data**
3. Cliquer le bouton **Run workflow** → **Run workflow**
4. Attendre ~2 minutes → vérifier que c'est vert ✅
5. Aller dans `data/hourly_spot.csv` → vérifier que les dates récentes sont là

Si c'est rouge ❌ :
- Cliquer sur le run échoué → voir les logs
- Erreur 401 = clé API invalide → vérifier l'étape 4
- Erreur 429 = rate limit ENTSO-E → attendre 1h et réessayer

---

## ÉTAPE 6 — Déployer sur Streamlit Cloud (5 min)

1. Aller sur https://share.streamlit.io
2. Se connecter avec **Continue with GitHub**
3. Cliquer **New app**
4. Sélectionner votre repository `ppa-dashboard`
5. Branch : `main`
6. Main file path : `app.py`
7. Cliquer **Deploy!**
8. Attendre ~3 minutes → votre app est en ligne !

Votre URL sera :
```
https://[username]-ppa-dashboard-app-XXXX.streamlit.app
```

---

## FONCTIONNEMENT QUOTIDIEN

```
08:00 UTC (10:00 Paris)  GitHub Actions se déclenche automatiquement
        ↓
08:02                    Script update_entsoe.py récupère les prix J-1 depuis ENTSO-E
        ↓
08:04                    hourly_spot.csv et nat_reference.csv mis à jour sur GitHub
        ↓
08:05                    Streamlit Cloud détecte le changement → rafraîchit le cache
        ↓
08:06                    Votre dashboard affiche les données du jour
```

---

## FORMAT DE LA COURBE DE CHARGE (votre asset)

Fichier Excel ou CSV avec exactement 2 colonnes :

| Date                | Prod_MWh |
|---------------------|----------|
| 2024-01-01 00:00:00 | 0.0      |
| 2024-01-01 01:00:00 | 0.0      |
| 2024-01-01 10:00:00 | 4.2      |
| 2024-01-01 11:00:00 | 7.8      |

- Pas horaire (1h)
- Noms de colonnes flexibles (détection automatique)
- kWh ou MWh (conversion automatique si valeurs > 10 000)

---

## QUESTIONS FRÉQUENTES

**Q : Les données se mettent à jour même si je n'ouvre pas le dashboard ?**
R : Oui. GitHub Actions tourne en arrière-plan indépendamment.

**Q : Que se passe-t-il si l'API ENTSO-E est down ?**
R : Le script détecte l'erreur, GitHub Actions marque le run en rouge,
mais les anciennes données restent intactes. La mise à jour reprend le lendemain.

**Q : Peut-on rendre le dashboard privé ?**
R : Oui, avec Streamlit Cloud Teams (payant, ~40$/mois) ou en auto-hébergeant
sur un serveur avec authentification.

**Q : Comment ajouter une nouvelle année de données en backdating ?**
R : Le script `update_entsoe.py` est incrémental : il récupère toujours depuis
la dernière date stockée. Si vous voulez aller plus loin dans le passé,
modifier la ligne `START = pd.Timestamp("2014-01-01", tz="UTC")` dans le script.

**Q : Quelle est la fraîcheur des prix DA ENTSO-E ?**
R : Les prix Day-Ahead sont publiés par EPEX/ENTSO-E vers 13h CET le jour J-1.
Notre GitHub Action tourne à 10h Paris (08h UTC) — elle récupère donc les prix
de avant-hier. Pour avoir J-1, décaler le cron à `0 14 * * *` (16h Paris).
