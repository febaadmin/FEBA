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

Ceux du jeu de démonstration (`make seed`) — voir `DEMO_ACCOUNTS.md`.
Les scripts ne créent aucun compte et ne modifient aucune donnée
persistante : ils basculent d'académie, ce qui est réversible, et lisent.
