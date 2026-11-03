# Tests end-to-end (navigateur réel)

Ces trois scénarios rejouent, dans un navigateur Chromium, les parcours que
les tests unitaires ne peuvent pas couvrir : ce que l'utilisateur voit
réellement à l'écran après un changement d'académie ou de langue.

Ils ont été écrits parce que trois défauts de cette itération étaient
invisibles autrement — l'API répondait correctement, mais l'interface
affichait autre chose.

| Scénario | Ce qu'il vérifie |
|---|---|
| `academies.mjs` | Bascule FEBA / FEBA FHA / Toutes les Académies : délai réel, absence de rechargement, absence de réponse tardive, badge d'académie sur douze écrans, séparation des deux emplois du temps. |
| `espaces-anglais.mjs` | L'application privée en anglais pour les profils enseignant, parent et élève — aucun libellé français résiduel. |
| `parcours-gabarits.mjs` | Gabarits téléversés : faux PNG et PDF corrompu refusés, diplôme PDF placé à la souris, vérifié, activé, produit, délivré et téléchargé ; certificat PNG portrait ; remplacement sans altérer le document délivré ; accès croisés de l'administrateur FHA en 404. Exige `E2E_TEMPLATE_DIR`, rempli par `python e2e/fabriquer_gabarits_test.py <dossier>`. |
| `site-public-anglais.mjs` | Les treize pages du site vitrine en anglais après un clic sur « EN », carrousel et galerie compris. |

## Lancer

```bash
# 1. Backend et frontend démarrés (make dev, ou serveurs locaux)
# 2. Base peuplée : make seed
npm --prefix ../frontend install --no-save playwright-core   # une seule fois
node academies.mjs
node espaces-anglais.mjs
node site-public-anglais.mjs
```

Variables d'environnement :

- `E2E_BASE_URL` — adresse du frontend (défaut `http://127.0.0.1:5173`) ;
- `CHROMIUM_PATH` — binaire Chromium (défaut `/opt/pw-browsers/chromium`) ;
- `E2E_SHOTS` — dossier des captures (défaut `e2e/captures`).

Chaque script sort avec un code non nul si un point échoue : ils sont donc
utilisables tels quels en intégration continue.

## Comptes utilisés

Ceux du jeu de démonstration (`make seed`) : leurs mots de passe viennent de `DEMO_PASSWORD_*`, ou sont générés et affichés par `seed_demo_data`.
Les scripts ne créent aucun compte et ne modifient aucune donnée
persistante : ils basculent d'académie, ce qui est réversible, et lisent.

## Suite de la CI (`e2e/ci`)

Lancée à chaque PR par le job « Parcours navigateur (E2E) » de `.github/workflows/ci.yml`, sur une base jetable.
Scénarios : connexion (5 profils, latence, 429, 502, 504, coupures, session expirée), sélecteur d'académie, toutes les
pages sur ordinateur et téléphone, formulaires et double envoi, recherche, tri, pagination, messagerie, notes, bulletins,
paiements, fichiers, rôles, suivi pédagogique, examen complet, absence de flash.

En local, avec une base de démonstration créée par `seed_demo_data` et les mêmes mots de passe dans
`DEMO_PASSWORD_*` et `E2E_PWD_*` :

```bash
cd e2e/ci && npm ci && node lancer.mjs            # tous les scénarios
node lancer.mjs connexion examens                  # quelques-uns
```

`E2E_BASE_URL`, `E2E_API_URL` et `CHROMIUM_PATH` indiquent les serveurs et le navigateur.
