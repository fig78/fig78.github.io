# Site du club — générateur statique Python

Site vitrine + galerie du club de peinture sur figurines.
Zéro backend, zéro base de données : du Markdown transformé en HTML.

## Démarrage rapide

```bash
pip install jinja2 pyyaml markdown pillow
python3 build.py
python3 -m http.server -d _site 8000   # puis http://localhost:8000
```

## Ajouter une figurine

1. Créer `content/figurines/ma-figurine.md` :

```markdown
---
titre: Seigneur-Célestant sur Dracoth
peintre: Pascal
jeu: Age of Sigmar
faction: Stormcast Eternals
techniques: [NMM, glacis]
tags: [concours]
date: 2026-07-01
palette:
  Bleu cobalt: "#2a4d8f"
  Or laiton: "#c9a227"
---
Description libre en **Markdown** : inspiration, difficultés, fierté...
```

2. (Optionnel) Ajouter des photos via le champ **Photos** dans
   l'éditeur web (`/admin/`) : ajout, suppression et réordonnancement
   par glisser-déposer se font directement dans ce champ — la première
   photo de la liste devient la photo principale. Vignettes et grands
   formats WebP sont générés automatiquement. Sans photo, un placeholder
   est affiché.
   En édition directe du Markdown (hors CMS), le dépôt manuel de fichiers
   dans `photos/ma-figurine/` reste possible : sans champ `photos` dans le
   front-matter, l'ordre alphabétique des fichiers est utilisé en secours.

3. `python3 build.py` — c'est en ligne au prochain push.

## Ajouter un événement

Éditer `content/evenements.yaml`. Les événements passés
disparaissent automatiquement.

## Personnaliser

- Nom du club, liens Discord/Instagram/e-mail : dictionnaire `SITE`
  en tête de `build.py`
- Couleurs et polices : variables CSS en tête de `static/style.css`

## Déploiement

Le workflow `.github/workflows/deploy.yml` construit et publie le site
sur GitHub Pages à chaque push sur `main`
(Settings → Pages → Source : "GitHub Actions" à activer une fois).

## Administration web (Sveltia CMS)

Les membres peuvent éditer le site via un formulaire web sur `/admin/`,
sans toucher à Git. Sveltia CMS est chargé depuis un CDN : rien à installer.

### Mise en service (une seule fois, ~20 min)

1. **Comptes GitHub des membres** : chaque contributeur crée un compte
   GitHub (gratuit) et vous l'ajoutez comme collaborateur du dépôt
   (Settings → Collaborators, rôle *Write*).

2. **Proxy OAuth** : Sveltia a besoin d'un petit relais d'authentification.
   Déployez [sveltia-cms-auth](https://github.com/sveltia/sveltia-cms-auth)
   sur Cloudflare Workers (gratuit, bouton "Deploy" dans leur README) :
   - créez une *GitHub OAuth App* (Settings → Developer settings) avec
     comme callback l'URL du worker ;
   - renseignez `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` dans le worker.

3. **Configuration** : dans `admin/config.yml`, remplacez `repo:` par
   votre dépôt et `base_url:` par l'URL de votre worker.

### Parcours d'un membre

1. Va sur `votresite.fr/admin/`, clique "Sign in with GitHub"
2. "Figurines" → "Créer" → remplit le formulaire (titre, techniques,
   palette avec sélecteur de couleurs, photos en glisser-déposer...)
3. Enregistre → commit sur `main` → le site est reconstruit et en ligne
   en ~2 minutes

### Relecture avant publication (optionnel)

Sveltia publie directement sur `main` (pas de mode brouillon/relecture
à ce jour). Pour imposer une validation : protégez la branche `main`
(Settings → Branches → *Require pull request*) — les contributions des
membres deviendront des pull requests que les admins fusionnent.
