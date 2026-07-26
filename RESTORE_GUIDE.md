# RESTORE_GUIDE.md — Sauvegarde & restauration (V7)

## 1. Avant toute mise à jour V7 — sauvegarder

```bash
# Base PostgreSQL (prod / docker)
docker compose exec db pg_dump -U feba feba > backup_pre_v7.sql

# Médias uploadés (logos, reçus, bulletins générés)
tar czf backup_media_pre_v7.tgz backend/media/

# Étiquette Git de repli
git tag pre-v7 && git rev-parse pre-v7
```

## 2. Contenu concerné par V7

- **Schéma** : aucune nouvelle table/colonne. Deux migrations de **données**
  seulement (`website/0003`, `schools/0011`) — réversibles.
- **Données** : `School.name` et `SiteSettings.school_name`/`meta_title`
  peuvent être mises à jour (anciens libellés → nouveaux).
- **Fichiers** : cachet + façade + vidéo ajoutés/optimisés (packagés dans le
  dépôt, pas dans la base).

## 3. Restauration complète (retour à l'état pré-V7)

```bash
# 1. Code
git checkout pre-v7          # ou la branche V6.2 : claude/v4-vitrine-fixes

# 2. Base (si des migrations de données avaient été appliquées)
docker compose exec -T db psql -U feba -d feba < backup_pre_v7.sql

# 3. Médias
tar xzf backup_media_pre_v7.tgz
```

## 4. Restauration ciblée (annuler seulement les renommages V7)

Les deux migrations de données sont réversibles :

```bash
python manage.py migrate website 0002
python manage.py migrate schools 0010
```

→ `School.name` redevient « Groupe Scolaire FEBA », `SiteSettings.school_name`
l'ancien libellé (uniquement pour les lignes non modifiées manuellement depuis).

## 5. Vérification post-restauration

```bash
cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations -q
```

## 6. Garantie de non-perte

- Aucune migration **destructive** en V7 (pas de `DROP`, pas de suppression de
  colonne). Les migrations de données ne touchent qu'aux **libellés exacts**
  ciblés et sont **réversibles**.
- Comptes, permissions, notes, paiements, bulletins existants : **inchangés**.
