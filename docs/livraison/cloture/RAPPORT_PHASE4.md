# Phase 4 : aide personnalisée, graphique des paiements, incidents, audit de l'API

Date : 04/11/2026. Dépôt `febaadmin/FEBA`, branche `main`. Production `globalfeba.com`.

Légende des environnements :
- **U** : tests unitaires et d'intégration sur PostgreSQL local ;
- **N** : navigateur local, base jetable ;
- **CI** : GitHub Actions ;
- **PL** : production en lecture seule ;
- **PE** : écriture en production autorisée par la mission.

## État initial vérifié

- `main` et production étaient à `84f4544`, identiques. Aucune migration en attente.
- Celery et son planificateur : 0 redémarrage depuis 8 h. Disque à 29 %.
- Aucune PR ouverte.
- Une branche locale `fix/aide-recherche-pertinence` existait, vide (identique à `main`) : réutilisée.

## A. Centre d'aide (PR #81)

| Profil | Articles visibles |
|---|---|
| Super administrateur | **52**, toute la documentation, quelle que soit l'académie |
| Administrateur | 43, moins les modules désactivés de son académie |
| Enseignant | 19, même règle |
| Parent | 13 |
| Élève | 13 |

**Visibilité** (`peutVoir`) :
- super administrateur : tout ;
- autres profils : les articles de leur rôle, et seulement si le module de l'article est activé pour leur académie.

Le filtrage dépend du profil connecté et de l'académie active : il est recalculé à chaque changement de compte, de profil, d'académie ou de langue.

**Moteur de recherche** (local, sans service externe) :
- index pondéré par champ ; langue de l'interface, et l'autre langue à demi-poids ;
- correspondances exactes, par préfixe et par racine FR/EN ;
- synonymes FR/EN, y compris les expressions de plusieurs mots ;
- correction des fautes de frappe vers les mots les plus proches seulement ;
- tous les mots significatifs exigés, classement par score, seuil relatif de 30 % ;
- termes surlignés, nombre de résultats, suggestions quand rien n'est trouvé.

**Cause du problème « message »** : la recherche portait sur une simple sous-chaîne, et 27 articles écrivaient « Message « … » » pour décrire leur résultat. Ces formulations deviennent « Confirmation affichée ».

| Recherche | Avant | Après |
|---|---|---|
| message (superadmin) | 34 articles | 2 : messagerie, puis messages du site |
| message (parent) | — | 1 : messagerie |
| visioconférence | — | 1 : salles virtuelles |
| bulettin (faute) | 0 | bulletins en tête |
| paiemnt (faute) | 0 | paiements (et non « parents ») |
| password (interface FR) | 0 | 4 articles sur le mot de passe |

**Matrice** : `MATRICE_AIDE_FONCTIONNALITES.md` est générée par `frontend/scripts/generer_matrice.mjs`. Elle relie chaque menu à sa route, son écran, son module, les API qu'il utilise et ses articles. Résultat : **0 écran sans article**.

**Tests** :
- `recherche.test.js` : 38 tests (27 requêtes de référence sur les 5 profils en FR et EN, visibilité, fautes, langues croisées, suggestions) [U, CI] ;
- `aide.test.js` : chaque écran de menu documenté, liens vers des routes réelles, deux langues [U, CI] ;
- E2E `aide` : 42 contrôles [N, CI].

**Limites** :
- les procédures décrivent les écrans au 04/11 ; une relecture humaine par profil reste à faire ;
- le filtrage par permission fine (au-delà du rôle et du module) n'existe pas dans FEBA, donc pas non plus dans l'aide.

## B. Graphique des paiements (PR #80)

**Endpoint** : `GET /api/payments/tableau-de-bord/?periode=…`. Réservé au super administrateur (403 pour un admin, 401 sans connexion). Il suit le sélecteur d'académie.

| Indicateur | Définition |
|---|---|
| Encaissé | `Payment` confirmés et non supprimés, à leur date de paiement, **nets** des remboursements des transactions carte liées. Une transaction réussie crée son `Payment` : elle n'est jamais comptée deux fois. |
| Remboursé | `PaymentTransaction.amount_refunded_minor`, affiché à part |
| Annulé | `Payment.is_confirmed=False`, non supprimé |
| En attente / échoué | transactions carte ouvertes ; échouées, annulées ou expirées |
| Attendu, restant, taux de recouvrement | échéances de `reminders.compute_dues` (tarifs, réductions, exonérations, imputation). **Non calculable** sans échéancier, jamais 0. |

- **Devises** : XOF et USD ne sont jamais additionnées ; elles s'affichent une à une, avec le détail par académie.
- **Périodes** : 7 jours, 30 jours, 3, 6 et 12 mois, année scolaire, période personnalisée.
- **Constat en production** [PL] : aucun échéancier configuré dans les deux académies. L'attendu et le reste à payer s'affichent donc « Non calculable » tant qu'aucun tarif n'est saisi dans « Relances de paiement ».
- **Correctif visuel** : les montants complets de l'axe se chevauchaient (vérifié dans le navigateur). L'axe passe en notation compacte, avec la devise indiquée sous le titre.
- **Tests** :
  - 8 tests backend, totaux comparés à des requêtes indépendantes : confirmés, annulés, supprimés, hors période, montant nul, carte réussie sans double comptage puis remboursée, en attente, échoués, échéancier présent ou absent, filtre par académie, périodes, droits [U] ;
  - 108/108 avec les tests des relances et de la carte [U] ;
  - 3 tests frontend [U] ;
  - E2E `tableau` : 14 contrôles, dont le nombre de paiements identique entre l'écran et l'API, sur ordinateur et sur téléphone [N].

## C. Incidents

| Référence | Cause racine | Correctif | Statut réel au 04/11 |
|---|---|---|---|
| ERR-310AC0 | Course au démarrage de MariaDB dans la restauration d'essai | PR #69 ; sauvegardes VALIDES le 04/11 à 02:04 et 02:40 UTC [PE] | **Corrigé, à valider**. Les 4 niveaux techniques sont prouvés ; il manque la validation utilisateur. |
| ERR-A036A8, ERR-FC6DC7, ERR-4744E2 | `mutationFn: gradesAPI.delete` : le contexte React Query arrivait comme justification | `400dd0d` (31/10) | Corrigé, à valider. **Test en production renseigné le 04/11** : 10 suppressions réussies le 01/11 entre 14:44 et 14:49 UTC, après le déploiement du correctif. Il manque la validation utilisateur. |
| ERR-5D12BE | Enseignant sans fiche `Teacher` | `400dd0d` | Corrigé, à valider |
| ERR-72B72D, ERR-FF13EF, ERR-291699, ERR-CBAA57 | Même cause que la suppression de note | idem | Résolu (inchangé) |

Aucun incident n'a été supprimé. Les statuts ont été modifiés uniquement avec preuve, et l'historique est conservé.

**Notifications en double (PR #82)** :
- **Constat** : les deux notifications de 06:00 et 07:00 correspondaient à la 1ʳᵉ et à la 5ᵉ occurrence d'une même panne continue (paliers 1, 5, 25…), et non à deux événements.
- **Nouvelle règle** : une alerte à la création, à la réapparition après correction, et au retour après 6 h de silence. Toutes les occurrences restent comptées. La décision ne dépend que de l'état en base, donc un redémarrage de Celery n'a aucun effet.
- **Tests** : 29/29 [U].

## D. Audit global : défauts trouvés sans signalement

| # | Défaut | Preuve | Correctif |
|---|---|---|---|
| 1 | 14 endpoints répondaient 500 sur des données mal formées : identifiants bruts, valeurs non hachables, dates « 2026-02-30 », mot de passe de l'auteur reçu en objet (mon ajout de #70), liste attendue mais entier reçu | Balayage de toutes les routes avec les 184 clés lues dans le code [N] | PR #83 : `identifiant()` borné, `date_field`, contrôles de type |
| 2 | Résultat du test de placement FHA : n'importe quel groupe ou niveau était **enregistré** | Balayage [N] ; aucune valeur hors liste en production [PL] | PR #83 : validation des choix |
| 3 | `/api/teachers/` : **1 099 requêtes SQL** ; `/api/classes/` : 227 ; `my_classes` : 226 | Mesure [N] | PR #84 : 6, 6 et 4 requêtes ; JSON identique avant et après (hors ordre) |
| 4 | Pagination instable des compétences et des classes (agrégat sans ordre) | Avertissement Django [N] | Ordre explicite et stable (PR #83 et #84) |
| 5 | Bouton de fermeture de la fenêtre d'annonce sans nom accessible | Balayage de tous les boutons-icônes [U] | PR #84 |

**Protection permanente** :
- `tests/test_balayage_api.py` : 6 804 requêtes sur les 5 profils, 0 erreur 500. Le test découvre seul les routes et les clés, et il a trouvé à lui seul la bascule d'académie.
- `tests/test_requetes_sql.py` : plafonds de requêtes sur les listes.

**Contrôles sans défaut** :
- GET de toutes les routes avec des comptes sans profil : 0 erreur 500 ;
- clés de cache invalidées sans lecteur : aucune ;
- images sans texte alternatif : aucune ;
- serveur vidéo : conteneurs sains, sans redémarrage, certificat valide jusqu'au 27/01/2027, sauvegardes programmées [PL].

**Restent mesurés, non modifiés** : tableau de bord parent (132 requêtes) et liste du suivi (123 requêtes, bornée par la pagination). Les corriger demande de refondre les calculs de moyennes : ce sera un lot à part.

## E. GitHub et production

| PR | Objet | Statut |
|---|---|---|
| #80 | Graphique des paiements | fusionnée (`7fb060d`) |
| #81 | Centre d'aide : recherche et visibilité | fusionnée (`3eac3fb`) |
| #82 | Une alerte par panne | fusionnée (`2e9ab5c`) |
| #83 | API sans erreur 500 ; balayage permanent | fusionnée (`8236774`) |
| #84 | Listes en requêtes constantes ; accessibilité | fusionnée (`4b8b165`) |
| #85 | E2E `comptes` indépendant de l'académie mémorisée | fusionnée |

**Déploiements** : `2e9ab5c`, `3eac3fb` et `4b8b165` ont réussi (04/11 entre 12:13 et 13:00 UTC). Les fusions intermédiaires ont été regroupées par la file de déploiement. Commit en production vérifié : `4b8b165`.

**Vérifications en production après déploiement** [PL] :
- services : backend, Celery, planificateur et nginx en marche, 0 redémarrage ; `inspect ping` donne « 1 node online » ; aucune migration en attente ;
- nginx **conservé** aux trois déploiements (« nginx inchangé : conservé ») ;
- graphique des paiements, comparé à une requête indépendante sur la base réelle : XOF 11 645 440 sur 240 paiements, identique ; USD 0 ; aucun échéancier ;
- liste des enseignants : 6 requêtes ; liste des classes : 5 ;
- sonde de disponibilité en lecture seule : 5 367 requêtes de 12:22 à 13:02 UTC, médiane 148 ms, p99 213 ms ; 1 réponse 502 sur `/login` à 12:37:10, au remplacement du frontend (risque résiduel connu, 1 requête par bascule), et 1 coupure réseau isolée hors déploiement ;
- suite E2E complète en local sur `4b8b165` : 229 contrôles, 2 échecs dus à une dépendance d'ordre du scénario `comptes`. Corrigée par #85, puis 50/50 sur les scénarios concernés.

## F. État final

| Sujet | Classement |
|---|---|
| Aide personnalisée par profil et moteur de recherche | **Déployé et vérifié** (tests et E2E) ; relecture humaine du contenu par profil souhaitée |
| Graphique des paiements | **Déployé et vérifié** : chiffres identiques à une requête indépendante en production ; attendu et restant non calculables tant qu'aucun échéancier n'est saisi (décision métier) |
| Notifications d'incident sans redondance | **Déployé et vérifié** par tests ; le comportement réel se constatera à la prochaine panne |
| ERR-310AC0 | **Corrigé, validation humaine nécessaire** (scénario : `RAPPORT_SAUVEGARDES_PLUGNMEET.md`, § 7) |
| ERR-A036A8, FC6DC7, 4744E2, 5D12BE | **Corrigés, validation humaine nécessaire** (scénarios : `RAPPORT_INCIDENTS_FINAL.md`, § 4) |
| 14 endpoints en erreur 500 et choix FHA non validés | **Déployé et vérifié** : balayage permanent en CI |
| N+1 des listes d'enseignants et de classes | **Déployé et vérifié** en production (6 et 5 requêtes) |
| Tableau de bord parent (132 requêtes), liste du suivi (123) | **Risque résiduel documenté**, lot à part |
| 1 requête en échec par bascule du backend ou du frontend | **Risque résiduel documenté** ; correctif à éprouver sur la mini-pile avant toute modification de nginx |
| Surveillance de la sauvegarde Restic de FEBA | **Non corrigé** : nécessite root (voir `SUIVI_REPRISE.md`) |
| Parcours réels des 5 profils en production | **Non fait** : aucun compte de production créé, aucun mot de passe demandé ; couvert par l'E2E sur base jetable |

La matrice (`MATRICE_AIDE_FONCTIONNALITES.md`) indique les API appelées directement par chaque écran, pas celles de ses composants importés (par exemple le graphique du tableau de bord).
