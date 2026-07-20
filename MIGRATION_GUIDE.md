# MIGRATION_V6.md — Guide de migration vers V6 (20/07/2026)

## 1. Résumé — aucune migration de schéma

**V6 n'ajoute aucune migration.** Vérifié :

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python manage.py makemigrations --check --dry-run
# → No changes detected
```

La saisie groupée (P7) est un **nouvel endpoint** qui réutilise le modèle
`Grade` existant : aucun champ ajouté, aucune donnée à convertir.
La dernière migration du site vitrine reste celle de V5
(`website/0002_galleryitem_focal_x_galleryitem_focal_y_and_more.py`, points
focaux). Une montée depuis V5 est donc **sans risque de schéma**.

## 2. Procédure de mise à jour depuis V5

```bash
# 1. Sauvegarder la base (toujours)
docker compose exec db pg_dump -U feba feba > backup_pre_v6.sql

# 2. Récupérer le code V6
git pull            # ou : dézipper feba_v1_v6_complet.zip

# 3. Reconstruire et démarrer
make dev

# 4. Appliquer les migrations (no-op si vous veniez de V5)
docker compose exec backend python manage.py migrate

# 5. Rafraîchir le contenu du site vitrine (IMPORTANT — voir §3)
docker compose exec backend python manage.py seed_website

# 6. Reconstruire le frontend
cd frontend && npm ci && npx vite build
```

## 3. Point d'attention — re-seed du site vitrine

`seed_website` est **idempotent** mais V6 y ajoute un **élagage anti-doublon** :
pour chaque album, les médias qui ne figurent plus dans la liste voulue sont
supprimés.

```python
album.items.filter(kind="image").exclude(image_path__in=wanted_paths).delete()
```

Conséquences attendues au premier re-seed V6 :

| Album | Effet |
|---|---|
| Notre campus | `hero-campus` retiré (doublon du carrousel) → `−1 obsolète` |
| Moments FEBA | `valeurs-projet` retiré, `admissions-visite` ajouté → `−1 obsolète` |

> ⚠️ Si vous avez **ajouté vos propres médias** à ces albums via l'admin, ils
> seront supprimés par l'élagage. Dans ce cas : exportez-les avant, ou ajoutez
> leurs chemins à la liste voulue dans
> `apps/website/management/commands/seed_website.py` avant de re-seeder.

Les points focaux seedés sont également mis à jour, notamment
`academique-participation` : `(82, 28)` → **`(26, 64)`** (recadrage V6 sur
l'enseignante, hors mur crème). Si vous aviez ajusté ce focal manuellement en
base, votre valeur sera écrasée par le re-seed.

## 4. Nouveauté fonctionnelle — saisie groupée

Nouvel endpoint `POST /api/grades/bulk-create/` (voir
`BULK_GRADES_REPORT.md`). Rien à migrer, mais à connaître :

- protégé par `IsAdminOrTeacher` (parent/élève `403`, anonyme `401`) ;
- **atomique** : une ligne invalide ⇒ `400` et **aucune** note créée ;
- permissions vérifiées côté serveur (enseignant limité à ses
  matières/classes, filtrage par établissement anti-IDOR).

La **saisie simple existante est inchangée** — aucun changement de contrat sur
l'endpoint de création unitaire.

## 5. Vérification post-migration

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q     # 300 passed, 1 skipped
cd frontend && npx vitest run                            # 56 passed
```

Navigateur : carrousel 5 slides, galerie remplie sans vignette dupliquée, menu
desktop sur une ligne (1280/1920), hamburger propre (375), bouton
« Saisie groupée » présent sur les pages Notes enseignant et administrateur.

## 6. Retour arrière

Aucune migration n'ayant été appliquée, un retour à V5 se fait en redéployant
le code V5 puis en relançant `seed_website` de la version V5 (pour restaurer
les médias élagués). La sauvegarde `backup_pre_v6.sql` reste la garantie
ultime.
