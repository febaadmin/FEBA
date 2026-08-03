# Rapport V9 — multi-académies, inscription FHA, documents
## Itération V9-bis — le nom long, le calibrage, et deux défauts trouvés au navigateur

### Ce qui est corrigé

| # | Défaut | Trouvé par | Preuve |
|---|---|---|---|
| 1 | Un nom de plus de 76 caractères était REFUSÉ : la hauteur d'une ligne était estimée, pas mesurée | trois tentatives de repli sur deux lignes, toutes recouvrant la phrase gravée | `test_textfit.py` — 50 tests, 147 sous-tests, dont une analyse de pixels |
| 2 | Les deux gabarits FEBA FHA écrivaient le nom sur une largeur héritée du fond de Cotonou, plus large que leur propre règle de 11 mm | mesure du trait sur le fond | `test_le_nom_reste_a_l_interieur_de_sa_regle_d_ecriture` |
| 3 | Signatures du diplôme FEBA FHA 8,3 mm au-dessus de leur trait ; date du certificat FEBA FHA 5,2 mm | inspection visuelle du rendu | `document_analyze`, recalibrage consigné |
| 4 | Un fleuron centré de 4,4 mm, propre au fond FEBA FHA, traversé par la signature | inspection visuelle du rendu corrigé | recalibrage sur le sommet du fleuron |
| 5 | `getAscent()` divisée par 1000 puis remultipliée par le corps | relecture du placement vertical | placement conservé, écrit sans détour |
| 6 | Une ligne à 14,75 pt préférée à deux lignes à 20,5 pt | lecture des résultats gabarit par gabarit | `test_deux_lignes_valent_mieux_qu_une_ligne_minuscule` |
| 7 | **Un administrateur qui rechargeait sa page atterrissait dans l'espace élève** | parcours navigateur | `roleRedirect.test.jsx`, 2 tests |
| 8 | Un identifiant de gabarit inconnu renvoyait le chemin absolu du serveur | parcours navigateur | `test_le_message_d_erreur_n_expose_aucun_chemin` (e2e) |

**Six de ces huit défauts n'ont été trouvés qu'en regardant** — un rendu,
un fond, un navigateur. Aucun n'était visible dans le code, et aucun
n'était attrapé par les suites d'alors.

### Le nom de 79 caractères, sur les quatre gabarits

| Gabarit | Lignes | Corps | Encre | Zone mesurée |
|---|---|---|---|---|
| `diploma_feba` | 2 | 22,75 pt | 120,83 – 136,79 mm | 119,93 – 136,85 mm |
| `diploma_feba_fha` | 2 | 21,00 pt | 127,84 – 142,57 mm | 126,50 – 142,62 mm |
| `certificate_feba` | 2 | 19,75 pt | 122,05 – 135,90 mm | 121,62 – 135,95 mm |
| `certificate_feba_fha` | 2 | 15,00 pt | 126,68 – 137,20 mm | 126,30 – 137,24 mm |

Le détail du calibrage — coordonnées en pixels et en millimètres, méthode
de neutralisation, zones interdites, essais — est dans
`DOCUMENT_TEMPLATE_CALIBRATION.md`.

### Chiffres

1044 tests backend PostgreSQL (529 sous-tests) · 1043 + 1 ignoré sous
SQLite · 163 tests frontend · ESLint 0 erreur · build de production
réussi · 126 migrations sur base neuve · 17 contrôles de démarrage des
documents · 54 contrôles navigateur · 8 rendus inspectés à l'œil.

---

Tout ce qui suit a été exécuté sur cette instance. Aucune sortie n'est
reconstituée. Ce qui n'a pas pu être fait est dit à la fin, sans détour.

---

## 1. Champs — chaque saisie traverse toute la chaîne

Produit par `manage.py field_mapping_audit` (voir `FIELD_MAPPING_AUDIT.md`
pour le tableau complet, 143 lignes).

| Formulaire | Champs | Saisis | Relus | Exportés | Champ saisi jamais relu |
|---|---|---|---|---|---|
| Fiche d'inscription FEBA FHA | 66 | 58 | 66 | 62 | **0** |
| Message de contact | 15 | 12 | 15 | 15 | **0** |
| Préinscription FEBA | 13 | 9 | 13 | 13 | **0** |

Champs corrigés cette itération :

| Champ | Défaut | État |
|---|---|---|
| `ContactMessage.whatsapp` (FEBA) | Absent du formulaire ET du serializer | ✅ Corrigé et vérifié |
| `ContactMessage.whatsapp` (FHA) | Enregistré, jamais affiché | ✅ Corrigé et vérifié |
| `ContactMessage.country/state/timezone/language/category` | Enregistrés, jamais affichés | ✅ Corrigés et vérifiés |
| `School.legal_name/code/entity_type/whatsapp/timezone/currency_code/default_language/matricule_prefix` | Exposés par aucun serializer | ✅ Corrigés et vérifiés |
| `parent1_*` dans la liste FHA | La liste lisait `parent_*`, inexistant | ✅ Corrigé et vérifié |

---

## 2. Documents — chacun porte son académie

Vérification par extraction du texte de PDF réellement produits.

| Document | Académie | Nom | Devise | Ville | Cachet | Contamination |
|---|---|---|---|---|---|---|
| `recu-feba.pdf` | FEBA | Faith & Excellence | FCFA | Cotonou | secrétariat | **aucune** |
| `recu-fha.pdf` | FEBA FHA | FEBA French Heritage Academy | `$` | — | secrétariat | **aucune** |
| `bulletin-feba.pdf` | FEBA | FAITH & EXCELLENCE | — | Cotonou | direction | **aucune** |
| `bulletin-fha.pdf` | FEBA FHA | FEBA FRENCH HERITAGE ACADEMY | — | — | direction | **aucune** |
| `diplome-feba.pdf` | FEBA | fond FEBA | — | — | direction | **aucune** |
| `certificat-feba.pdf` | FEBA | fond FEBA | — | — | direction | **aucune** |
| `FHA-2026-0009-fiche-inscription.pdf` | FEBA FHA | FEBA French Heritage Academy | — | — | — | **aucune** |

« Contamination » = un élément de l'autre académie trouvé dans le texte.

Numérotation : `FEBA-DIP-2026-0001`, `FEBA-CER-2026-0001`,
`FHA-2026-0009` — chaque préfixe vient de l'identité de son académie.

---

## 3. E-mails

| Message | Destinataire | Texte | HTML | fr | en | Pièce jointe | État observé |
|---|---|---|---|:-:|:-:|---|---|
| Accusé de réception | Responsable 1 | ✅ | ✅ | ✅ | ✅ | fiche PDF | `sent` |
| Alerte admission | Admins de l'académie | ✅ | ✅ | ✅ | — | fiche PDF | `sent` |
| Alerte admission | Super administrateurs | ✅ | ✅ | ✅ | — | fiche PDF | `sent` |
| Admins de l'AUTRE académie | — | — | — | — | — | — | **jamais destinataires** |

**Réserve, redite ici parce qu'elle est importante :** `sent` signifie
« remis au backend d'envoi sans erreur ». Le backend de cette instance est
`console` : les messages n'ont **pas** quitté le serveur. L'interface
affiche « Sans fournisseur », jamais « Envoyé », tant que
`used_real_provider` est faux. Voir `EMAIL_DELIVERY_REPORT.md`.

---

## 4. Permissions

| Ressource | Admin FEBA | Admin FHA | Super Admin | Anonyme |
|---|---|---|---|---|
| Messages de contact FEBA | ✅ | **404** | ✅ | 401/403 |
| Messages de contact FHA | **404** | ✅ | ✅ | 401/403 |
| Dossiers d'inscription FHA | aucun | ✅ | ✅ | 401/403 |
| Fiche PDF d'un dossier FHA | **404** | ✅ | ✅ | 401/403 |
| Photo d'un enfant FHA | **404** | ✅ | ✅ | 401/403 |
| Export CSV des dossiers FHA | vide | ✅ | ✅ | 401/403 |
| Documents officiels FEBA | ✅ | aucun | ✅ | 401/403 |
| Produire un document FEBA pour un élève FHA | **400** | **400** | **400** | 401/403 |
| Modifier le contenu d'un message reçu | **refusé** | **refusé** | **refusé** | 401/403 |
| Élargir sa portée par `?school_id=` | **ignoré** | **ignoré** | s/o | s/o |

Aucune fiche, aucune photo, aucun document n'est atteignable par une URL
publique : tous vivent hors du répertoire servi et passent par une vue
authentifiée.

---

## 5. Tests

| Suite | Résultat |
|---|---|
| pytest PostgreSQL 16 | **794 passés**, 296 sous-tests |
| pytest SQLite | **793 passés, 1 ignoré**, 296 sous-tests |
| Vitest | **123 passés** (15 fichiers) |
| ESLint | **0 erreur**, 83 avertissements hérités |
| Build de production | ✅ `built in 11.27s` |
| Parcours navigateur | **34 vérifications, toutes vertes** |

Le test ignoré sur SQLite est un test de concurrence multi-threads : SQLite
en mémoire verrouille la table entière. Il s'exécute sur PostgreSQL.

### Ajoutés cette itération

| Fichier | Tests | Ce qu'il empêche |
|---|---|---|
| `test_branding_source.py` | 16 | Le retour d'une identité en dur dans un générateur |
| `test_diploma_ready_after_install.py` | 16 | Le diplôme bloqué après installation |
| `test_contact_forms_fields.py` | 11 | La perte silencieuse d'un champ saisi |
| `test_fha_enrollment_workflow.py` | 43 | Une inscription perdue, un e-mail promis à tort |
| `test_documents_academy_scope.py` | 13 | Un document à l'effigie de la mauvaise académie |
| `test_field_mapping_audit.py` | 4 | Un champ ajouté au modèle mais pas au serializer |
| `test_private_storage.py` | 6 | Un document confidentiel dans un répertoire public |
| `LongText.test.jsx` | 14 | Un message tronqué sans que rien ne le signale |
| **Total** | **123** | |

---

## Ce qui n'a pas pu être fait

**Aucun e-mail n'est parti sur Internet.** Aucun fournisseur n'est
configuré sur cette instance. Tout ce qui pouvait l'être sans fournisseur a
été vérifié — composition, formats, langues, pièces jointes, journal,
échecs, relance — et l'application refuse de présenter un envoi comme réel
dans cet état.

**Aucune signature officielle n'est fournie.** Les zones
`director_signature` restent vides. Le moteur ne dessine, ne reconstitue et
n'approche jamais une signature : une signature inventée sur un diplôme
n'est pas une approximation graphique, c'est un faux.

**Les deux gabarits sont réservés à FEBA.** Leur fond porte son identité
visuelle. L'académie en ligne n'a pas fourni le sien ; produire ses
diplômes sur le fond de l'autre serait précisément le défaut que P0 corrige.

**Les fonds installés ne sont pas les PNG d'origine** — variantes
transcodées, acceptées nommément et tracées. Géométrie exacte, donc
calibrage valide. Voir `KNOWN_LIMITATIONS_V9.md`.

**Le paiement par carte reste non éprouvé en conditions réelles** : aucune
clé Stripe valide n'est disponible. Inchangé depuis V8.
