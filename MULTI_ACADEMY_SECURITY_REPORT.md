# Audit global multi-académies

Portée : l'ensemble du dépôt, après P0, P2 et P3. Chaque ligne de ce
rapport correspond à une commande réellement exécutée ; les nombres sont
ceux qu'elle a affichés.

---

## 1. Ce que l'audit a trouvé

### 1.1 Le nom de l'autre académie, incrusté dans une image

**Trouvé en regardant un rapport mensuel produit, pas en lisant le code.**

Les deux académies partageaient `logo_feba.jpeg`. Cette image ne porte
pas seulement le blason du groupe : le libellé « Faith & Excellence
Bilingual Academy » y est incrusté sous le bouclier. Chaque document de
FEBA French Heritage Academy — fiche d'inscription, reçu de paiement,
rapport mensuel — affichait donc en tête le nom de l'école de Cotonou.

Aucun test textuel ne pouvait l'attraper : le nom était dans une image
matricielle, invisible à l'extraction de texte. Les tests existants
vérifiaient bien « `Faith & Excellence Bilingual Academy` n'apparaît pas
dans le texte du PDF » — et passaient, à juste titre, pendant que le nom
s'affichait en toutes lettres.

**Correction.** `logo_groupe_feba.png` est la même image, coupée dans la
bande blanche **mesurée** entre le bouclier (dernier pixel de contenu
y=392) et le libellé (premier pixel y=412). Le blason et son ruban
« Faith & Excellence » sont conservés au pixel près ; seul le nom de
l'autre académie est retiré. Le nom correct est déjà imprimé juste en
dessous, en texte, par le générateur.

**Non-régression.** Deux tests : l'un compare les *fichiers* utilisés par
les deux académies, l'autre compare les pixels conservés un à un, pour
qu'une recompression ou un redimensionnement du blason fasse échouer la
suite.

### 1.2 Une vue exposant un modèle d'académie sans restriction

`manage.py academy_scope_audit` part du **routeur**, pas d'une liste
écrite à la main : il voit toutes les vues, y compris celle qu'on
ajoutera sans écrire de test.

Résultat : 13 vues examinées, 11 exemptées avec motif écrit, **0 vue sans
restriction**.

La seule vue signalée au premier passage — `TechnicalIncidentViewSet` —
a été examinée puis exemptée : elle est réservée au super administrateur
(`IsSuperAdmin`), et un incident technique décrit une panne
d'infrastructure, pas le dossier d'un élève. Le masquer selon l'académie
affichée empêcherait de voir qu'un serveur tombe.

Une exemption sans raison écrite fait échouer le test : c'est la seule
chose qui distingue un choix d'un oubli, six mois plus tard.

---

## 2. Ce que l'audit a confirmé

| Contrôle | Commande | Résultat |
|---|---|---|
| Champ collecté mais perdu dans la chaîne | `manage.py field_mapping_audit --strict` | Aucun |
| Identité codée en dur hors de la source unique | `pytest tests/test_branding_source.py` | 17 tests, 5 sous-tests |
| Vue sans contrôle d'académie | `manage.py academy_scope_audit --strict` | 0 sur 13 examinées |
| Fichier privé dans le répertoire public | comparaison `PRIVATE_MEDIA_ROOT` / `MEDIA_ROOT` | Hors public |
| Permissions des fichiers privés | `stat` sur les PDF produits | Tous en `0600` |
| Secret réel versionné | `git ls-files` + recherche de motifs | Aucun |
| Bouton mort (méthode d'API inexistante) | analyse croisée `src/api` ↔ `*.jsx` | 0 sur 280 méthodes |
| Échappement dans les générateurs PDF | inspection des six générateurs | Voir §3 |

### Fichiers privés au moment de l'audit

```
PRIVATE_MEDIA_ROOT : backend/private_media   (hors MEDIA_ROOT)
  fha_applications        10 fichiers
  feba_preregistrations  116 fichiers
  monthly_reports         52 fichiers
```

Aucun n'est atteignable par une URL : ils sortent d'une vue authentifiée
qui vérifie l'académie du demandeur, avec `Cache-Control: private,
no-store`, et un identifiant d'une autre académie donne **404** et non
403 — répondre « interdit » confirmerait que le dossier existe.

---

## 3. Un faux positif, laissé tel quel et expliqué

L'inspection des générateurs PDF signale `apps/documents/renderer.py`
comme dépourvu d'échappement. C'est exact, et c'est correct : ce module
n'utilise pas `Paragraph` (qui lit son contenu comme du mini-XML) mais
`drawString` / `drawCentredString`, qui reçoivent du texte littéral. Il
n'y a rien à échapper.

Le noter plutôt que « corriger » : ajouter un échappement ici ferait
apparaître `&amp;` sur un diplôme au nom d'un élève dont le patronyme
contient une esperluette.

| Générateur | Échappement | Coupure de ligne haute |
|---|---|---|
| `website/fha_pdf.py` | oui | oui |
| `website/feba_prereg_pdf.py` | oui | oui |
| `monthly_reports/pdf.py` | oui | oui |
| `bulletins/pdf_generator.py` | oui | sans objet |
| `payments/pdf_generator.py` | oui | sans objet |
| `documents/renderer.py` | sans objet (`drawString`) | sans objet |

---

## 4. Idempotence et double envoi

| Risque | Protection | Vérifié par |
|---|---|---|
| Deux rapports pour la même période | Contrainte d'unicité en base sur (académie, élève, année, mois, version) | `test_la_base_refuse_le_doublon_meme_forcé` |
| Deux workers sur le même lot | Verrou distribué Redis par (académie, période), `cache.add()` atomique, expiration automatique | `batch_lock` ; si Redis est absent la tâche **ne s'exécute pas** |
| Deux courriers pour le même rapport | `really_sent` court-circuite l'envoi | `test_un_rapport_deja_accepte_n_est_pas_renvoye`, puis relance réelle vérifiée dans Mailpit |
| Numéro de dossier réattribué | Référence dérivée de la clé primaire, jamais d'un `count() + 1` | `test_le_numero_ne_derive_pas_d_un_comptage` |

---

## 5. Migrations reproductibles

La migration `website/0010` a été rejouée sur une base PostgreSQL neuve
contenant **déjà cinq préinscriptions** :

```
lignes avant migration : 5
références attribuées  : FEBA-2026-0001 … FEBA-2026-0005
index sur reference    : …_uniq, …_like
unicité active         : IntegrityError sur doublon forcé
aller-retour 0009 ⇄ 0010 : conforme
SQLite, base neuve     : migrations appliquées
```

Deux défauts de cette migration ont été trouvés en la rejouant, pas en la
relisant : elle échouait sur une base neuve (`_like` créé deux fois), et
la colonne `reference` ouvrait une fenêtre de collision entre l'insertion
d'une ligne et sa numérotation. Les deux sont corrigés et documentés dans
le fichier de migration.

---

## 6. Résultats des suites, tels qu'obtenus

| Suite | Commande | Résultat |
|---|---|---|
| Backend PostgreSQL | `pytest tests/ -q` | **960 réussis, 321 sous-tests** |
| Backend SQLite | `DJANGO_SETTINGS_MODULE=…test_sqlite pytest tests/ -q` | **957 réussis, 1 ignoré** |
| Frontend | `npx vitest run` | **161 réussis** |
| ESLint | `npx eslint src` | **0 erreur**, 83 avertissements (référence inchangée) |
| Build production | `npm run build` | réussi |
| Parcours navigateur — préinscriptions | `node e2e/parcours-preinscription-feba.mjs` | **41 contrôles** |
| Parcours navigateur — rapports mensuels | `node e2e/parcours-rapports-mensuels.mjs` | **30 contrôles** |
| Envoi réel via Mailpit | script de vérification SMTP | **19 contrôles** |

Le test ignoré sous SQLite est un test de concurrence multi-processus :
SQLite en mémoire verrouille la table entière. Il s'exécute sur
PostgreSQL.

---

## 7. Ce que cet audit ne prouve pas

- `academy_scope_audit` détecte une vue qui **ignore** l'académie. Il ne
  prouve pas qu'une vue qui la mentionne filtre correctement — cela
  relève des tests de cloisonnement dédiés, qui existent par module.
- La recherche de secrets porte sur les fichiers **suivis par Git** et
  sur des motifs connus. Un secret d'une forme inhabituelle passerait.
- Les parcours navigateur mesurent le débordement horizontal réel à cinq
  largeurs. Ils ne remplacent pas une relecture humaine de la mise en
  page.
- **Les gabarits FEBA FHA ne sont pas couverts** : les deux fonds PNG
  n'ont jamais atteint le disque du conteneur. Voir
  `backend/document_templates/sources/feba_fha/README.md`.
