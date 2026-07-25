# OFFICIAL_NAMING_REPORT.md — Noms officiels (V7-P1/P2, 25/07/2026)

## Source de vérité centralisée

`backend/feba_project/branding.py` :
- `OFFICIAL_SCHOOL_NAME = "Faith & Excellence Bilingual Academy"`
- `SCHOOL_GROUP_NAME   = "GROUPE ÉDUCATIF FEBA"`

## P1 — « Faith & Excellence Bilingual Academy » (avec « & »)

Recherche **avant** : « Faith Excellence Bilingual Academy » (sans « & »)
présent dans 12 fichiers de source active.
Recherche **après** : **0** occurrence sans « & » dans la source active
(`grep -rn "Faith Excellence Bilingual Academy" backend/apps frontend/src
frontend/index.html | grep -v "Faith & Excellence"` → vide).

Fichiers corrigés :
- **Backend** : `website/models.py` (défauts `school_name`, `meta_title`),
  `seed_website.py`, `seed_demo_data.py` (`School.name`), fallback des
  générateurs PDF ; migrations de données `website/0003`, `schools/0011`.
- **Frontend** : `index.html`, `SiteLayout.jsx` (header + footer), `Seo.jsx`
  (title + OG), `HomePage.jsx`, `AboutPage.jsx`, `LegalPages.jsx`,
  `siteDefaults.js`.

Vérifié navigateur : titre d'onglet « FEBA — Faith & Excellence Bilingual
Academy », header/footer du site, bulletin & reçu générés (« FAITH &
EXCELLENCE BILINGUAL ACADEMY »).

## P2 — « GROUPE SCOLAIRE FEBA » → « GROUPE ÉDUCATIF FEBA »

- L'école dans l'ERP n'est plus nommée « Groupe Scolaire FEBA » : elle prend
  son **nom officiel** (`School.name = "Faith & Excellence Bilingual Academy"`).
- La ligne **« GROUPE ÉDUCATIF FEBA »** est rendue en tête des **bulletins** et
  des **reçus** (au-dessus du nom officiel), depuis la source centralisée.
- Migration de données `schools/0011` : renomme en base les écoles encore
  nommées « Groupe Scolaire FEBA » (sûre, ciblée sur le libellé exact).

Vérifié (extraction de texte PDF) : « GROUPE ÉDUCATIF FEBA » **présent**,
« GROUPE SCOLAIRE FEBA » **absent** sur bulletin **et** reçu.

## Migration des données existantes

- `website/0003_official_name_amp` : met à jour `SiteSettings.school_name` et
  `meta_title` s'ils valent encore l'ancien libellé + aligne les défauts.
- `schools/0011_official_school_name` : `School.name` « Groupe Scolaire FEBA »
  → « Faith & Excellence Bilingual Academy ».

Une **installation neuve** (seed) comme une **base existante** (migration)
aboutissent au même résultat.

## Tests

`tests/test_document_branding.py` (6 cas), `tests/test_website.py` (school_name
= nom officiel). Frontend : `site.test.jsx` (header/footer avec « & »).
