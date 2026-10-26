# FEBA — Rapport final : fiche d'inscription FHA, académies typées, appréciations administrables

26 octobre 2026 · branche `feat/academies-inscriptions-appreciations`.
Départ : commit `7627e70` (archive `FEBA_VERSION_BULLETINS_BRANDING_FAVICON_CORRIGEE.zip`,
empreinte identique à celle fournie). Commit livré : `SOURCE_COMMIT.txt` dans l'archive.

Statuts : **PASS** · **FAIL** · **BLOCKED** · **NOT RUN** · **SIMULATED**.
Détail des tests : `TEST_REPORT.md`. Limites : `KNOWN_LIMITATIONS.md` § 000000.
Actions de l'exploitant : `MANUAL_PRODUCTION_ACTIONS.md` § 00000.
Création d'une académie : `ACADEMIES_GUIDE.md`.

**Lieu des validations : en local uniquement** (piles Docker du poste,
PostgreSQL 16, Mailpit, plugNmeet v2.5.3 local, Chrome réel). Ni
préproduction ni Hetzner (accès SSH refusé). Rien n'a été déployé, migré
ni envoyé en production.

---

## A. Fiche de renseignements FEBA FHA

**Cause racine** : le champ n'avait jamais existé — ni dans le modèle
`FHAEnrollmentApplication`, ni dans le sérialiseur public, ni dans l'étape 1
du formulaire React ; il ne pouvait donc figurer ni dans le dossier ni dans
la fiche PDF.

**Correction** : champ `child_gender` (codes `F` / `M`, ceux de
`Student.gender`), étape 1 « Informations sur l'enfant », juste après l'âge :
- formulaire FR/EN (« Sexe » : Féminin / Masculin — « Sex » : Female / Male),
  bloquant à l'étape 1 et revérifié à l'envoi, brouillon local sauvegardé et
  restauré, récapitulatif ;
- serveur : obligatoire pour toute nouvelle fiche (valeur vide ou inconnue
  refusée), enregistré, renvoyé par la liste et le détail d'administration,
  affiché dans « Admissions FEBA FHA », dans l'alerte e-mail aux
  administrateurs et dans la **fiche PDF** ;
- migration `website.0012_fha_child_gender` : les dossiers déjà reçus
  restent vides et s'affichent « Non renseigné » — rien n'est inventé.

**Audit des 12 étapes** : identité, date de naissance, coordonnées et
résidence, école et niveau, origines et langues, niveau de français,
expérience, objectifs, deux responsables (lien, téléphones, WhatsApp,
e-mails, adresses, fuseau), contact d'urgence, disponibilités, équipement,
besoins particuliers (confidentiels), formule, consentements datés et
versionnés : déjà collectés. Le **sexe** était la seule information
essentielle manquante. Nationalité, lieu de naissance et données médicales
n'ont **pas** été ajoutés : un programme 100 % en ligne n'en a pas l'usage
dans son parcours d'inscription, et la consigne était de ne pas collecter de
données sensibles sans finalité.

**Vérifié en navigateur réel** : options Féminin/Masculin, blocage sans
sexe, valeur restaurée après rechargement, récapitulatif, soumission
(dossier `FHA-2026-0006`), brouillon effacé après envoi, liste et détail
administrateur (« Sex : Female » — interface de l'administratrice FHA en
anglais), fiche PDF téléchargée relue : « Sexe : Féminin ».

## B. Création et configuration des académies

**Avant** : aucun écran ne créait d'académie ; l'API acceptait un POST sans
type ni initialisation ; un DELETE supprimait en cascade élèves, notes et
paiements ; le code interne restait modifiable par le super administrateur.

**Modèle** : `School.academy_type` (`online`, `physical_primary`,
`physical_secondary` ; NULL = non classée), dont `entity_type` (matrice des
fonctionnalités) est dérivé. Migration `schools.0020_academy_type` : classe
chaque académie **d'après ses données** (en ligne ; niveaux uniquement
maternelle/primaire ; uniquement collège/lycée) et laisse **non classée**
une académie ambiguë (primaire ET secondaire, ou sans niveau), avec le motif
(`manage.py academy_types_report`). FEBA (démonstration : CP1 à 3ème) est
dans ce cas : aucun des trois types ne la couvre ; elle fonctionne comme
avant.

**Écran « Académies »** (super administrateur) : liste (type, motif des non
classées, élèves, statut), création typée, « Configuration restante »
(année, niveaux, matières, classes, administrateur, barème, logo — d'après
la base), modification (code immuable, type refusé si des niveaux le
contredisent), désactivation sans perte, suppression réservée à une
académie vide (sinon 409 avec la liste de ce qu'elle contient).

**Initialisation** (`apps/schools/academy_setup.py`, transaction unique) :
niveaux du type (primaire : Maternelle 1-2, CI à CM2 ; secondaire : 6ème à
3ème, Seconde à Terminale ; en ligne : aucun), copie du barème
d'appréciations, première année facultative. Rien n'est copié d'une autre
académie (élèves, notes, paiements, dossiers, salles, logo, cachets — testé).

**Barèmes** : le barème /10 ou /20 reste décidé par le **cycle** du niveau
(règle existante, conservée). Défaut corrigé : l'écran « Niveaux » ne
proposait pas le cycle ; tout niveau créé depuis l'interface était
« primaire », donc noté sur 10 même dans un lycée. Désormais : cycle proposé
selon le type, cycle par défaut du type (collège pour un secondaire), cycle
incompatible refusé par le serveur, colonne « Cycle · barème ».

**Isolation 2 / 7 / 19 académies** (`tests/test_isolation_2_7_19_academies.py`,
académies créées par le service réel, types alternés, chacune peuplée :
élève noté, parent, enseignant, paiement, bulletin) :
| Académies | Requêtes vérifiées (listes + détails) | Fuites | Erreurs 5xx | Écritures croisées abouties |
|---|---|---|---|---|
| 2 | 2 528 | 0 | 0 | 0 |
| 7 | 6 500 | 0 | 0 | 0 |
| 19 | 11 388 | 0 | 0 | 0 |

Écritures croisées tentées pour chaque paire : note (modifier, supprimer,
créer sur l'élève ou la matière d'une autre académie), élève, paiement,
commentaire et aperçu de bulletin, académie, niveau, barème — toutes
refusées, données intactes.

## C. Appréciations

**Avant** : seuils et libellés codés en dur (`APPRECIATION_SCALE`) et
recopiés côté React.

**Modèle** `AppreciationRule` (académie, cycle facultatif, seuil, libellé
FR, libellé EN, actif) ; service unique `apps/grades/appreciations.py` ;
bulletins, API des notes, tableaux de bord parent/élève, saisie groupée
branchés dessus. **Représentation** : seuil bas inclusif en **pourcentage de
la note maximale** (95 % = 19/20 = 9,5/10), comparaison sans division
(n × 100 ≥ seuil × m) : exactement le barème historique, indépendant de
l'échelle d'affichage, déterministe aux bornes. Migration
`grades.0013_appreciation_rules` : copie du barème actuel dans chaque
académie (aucun bulletin ne change).

**Écran « Appréciations »** (admin de l'académie, super admin avec académie
choisie) : brouillon, ajout / modification / suppression, intervalles
affichés en % et sur /20 et /10, validation locale et serveur (seuils en
double, pas de palier à 0 %, libellé vide ou en double, hors 0–100 %),
enregistrement atomique du barème entier, erreurs affichées, succès
seulement après la réponse, palier utilisé par des bulletins émis non
supprimable (désactivable), barème propre à un cycle, rétablissement par
défaut avec confirmation, aperçu d'une note (même non enregistré).

**Vérifié** : en navigateur réel (lycée créé par l'écran : libellé modifié,
relu après rechargement, autre académie intacte, incohérence bloquée) ;
bulletin FEBA réel (même moteur que la génération) : libellés modifiés
imprimés, moyennes identiques avant/après ; tests backend sur le PDF
(libellé imprimé, /10 et /20, bornes, barème de cycle, bulletin émis
inchangé, API des notes).

## D. Audit global — défauts confirmés et corrigés

| Défaut (reproduit) | Correction | Test |
|---|---|---|
| `/api/notifications/email-config/` renvoyait à tout administrateur la liste de **toutes** les académies (codes, noms, expéditeurs) — trouvé par la campagne d'isolation | liste limitée à son académie (super admin : toutes) | `EmailConfigScopeTests` |
| « Paramètres » prenait le premier établissement de la liste : un super administrateur modifiait le nom et l'adresse d'une **autre** académie que celle sélectionnée | académie active ; aucun formulaire en vue « toutes » | `Settings.academy.test.jsx` |
| « Niveaux » : pas de cycle, académie présélectionnée = première école | voir B | `LevelCycleRulesTests` |
| Suppression d'une académie en cascade (élèves, notes, paiements) | refus si données, désactivation proposée | `DeletionTests` |
| Code interne modifiable | immuable | `test_le_code_interne_est_immuable` |
| Académie indépendante : numéro institutionnel du groupe FEBA et ville par défaut « Cotonou » sur ses documents ; `init_academies` lui recopiait ce numéro | numéro du groupe réservé aux académies du groupe ; ville et pays obligatoires | `NewAcademyDocumentsIdentityTests`, `AddressLineTests` |
| Académie sans logo : image cassée (alt « FEBA ») dans les barres latérales, favicons annoncés en 404 — l'onglet gardait celui de FEBA | monogramme ; favicon généré à ses couleurs | `AcademyLogo.test.jsx`, `LogoLessAcademyPublicBrandingTests` |
| Jeu de démonstration en échec (valeur posée sur le mauvais modèle) — aucun test ne l'exécutait | corrigé ; test qui exécute tout le seed | `DemoSeedTests` |
| Académies créées par `init_academies` / le seed sans barème modifiable | copie du barème ; écran « personnaliser » | `InitAcademiesScaleTests` |

Calculs (audités, **non modifiés**) : moyenne d'une matière = moyenne
arithmétique de ses notes (poids 1) ; moyenne générale et moyennes de
section pondérées par les coefficients des matières **notées** ; matière non
notée exclue (jamais 0), sans appréciation ; bilingue 60/40 ; annuelle =
moyenne des trimestres notés ; interne /20, conversion unique à
l'affichage selon le cycle. Les mêmes fonctions servent page Notes, API,
tableaux de bord et bulletins (tests de cohérence existants, tous verts).

## E. Livraison

Voir `DELIVERY_VERIFICATION_ACADEMIES.txt` à côté de l'archive : commit,
taille, SHA-256, vérification depuis une extraction neuve, déploiement
« prodlike » local.

**BLOCKED** : Hetzner, préproduction, plugNmeet de production (SSH refusé) ;
SMTP Hostinger ; Twilio. **NOT RUN** : partage d'écran, réunion entre
réseaux distincts, CDN de production.
