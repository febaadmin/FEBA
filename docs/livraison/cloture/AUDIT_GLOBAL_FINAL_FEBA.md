# Audit global final de FEBA (6 novembre 2026)

Méthode : lecture du code, reproduction des parcours dans un navigateur réel (environnement local), balayages automatiques de **toutes** les routes de l'API, journaux et incidents de production (lecture seule), état des services, sauvegardes et certificats.

## 1. Modules audités

| Domaine | Comment | Résultat |
|---|---|---|
| Finance (tarifs, échéances, dispositions, situation, relances, tableau de bord) | lecture complète du moteur `compute_dues` et des vues ; tests ; navigateur | 6 anomalies, toutes corrigées (§ 2) |
| Menus et panneaux déroulants (5 mises en page) | recherche de tous les panneaux absolus et de leur gestion de fermeture | 1 anomalie (cloche), corrigée ; sélecteur d'académie conforme |
| API (toutes les routes, 5 profils) | `test_balayage_api` : aucune erreur 500 sur environ 7 600 requêtes ; `test_balayage_fuites` : aucune donnée d'une autre académie et aucune écriture ouverte non prévue | conforme ; la nouvelle route d'écriture est autorisée délibérément (personnel seulement) |
| Interface (20 parcours, 5 profils) | E2E en navigateur réel : navigation de toutes les pages par profil, formulaires, tableaux, filtres, téléchargements, mobile | voir RAPPORT_TESTS_FINAL.md |
| Traductions FR / EN | test de couverture (chaque libellé littéral) et ajout explicite des textes passés par variable | conforme |
| CI / déploiement | historique des exécutions (#107) | 1 anomalie (LibreOffice / apt), corrigée |
| Production | conteneurs, migrations, journaux (24 h), Celery, incidents, sauvegardes, certificat, disque | aucune erreur ; 5 incidents « corrigés » en attente de validation |

## 2. Anomalies identifiées, cause, correction

| # | Anomalie | Cause racine | Correction | Preuve |
|---|---|---|---|---|
| 1 | La cloche des notifications ne se fermait pas au clic extérieur (signalée) | aucun écouteur de clic extérieur ; quatre copies du panneau dans les mises en page | un seul composant pour les cinq profils, fermeture commune (`useFermetureExterieure` : capture, Échap, focus, changement de page) | 6 tests unitaires et E2E (bureau et mobile) |
| 2 | Supprimer une disposition (exonération, réduction, abonnement) ne laissait aucune trace | `ModelViewSet` sans journalisation | journal financier à la création, à la modification et à la suppression | test `test_disposition_creation_et_suppression_tracees` |
| 3 | Réenregistrer les échéances d'un tarif avec une date existante (sans identifiant), ou échanger deux dates, échouait (« existe déjà ») | création de la nouvelle ligne avant suppression, contrainte d'unicité (tarif, date) | rapprochement par identifiant puis par date, suppression d'abord, écriture en deux temps | E2E (découverte) et test `test_resoumettre_une_date_ou_echanger_deux_dates` |
| 4 | Tableau de bord des paiements : filtres classe, niveau et cycle appliqués à la classe ACTUELLE de l'élève, même pour une échéance d'une autre année | `_garde` lisait `student.current_class` | classe de l'année de l'échéance (inscription) | test `test_changement_d_annee_et_de_classe` (moteur commun) |
| 5 | Sans tarif, « Total encaissé 0 FCFA » alors que la production compte 240 paiements confirmés | encaissements calculés sur les seuls élèves ayant des échéances | encaissements réels sur la sélection d'élèves ; KPI et graphique toujours visibles | test `test_encaissements_reels_meme_sans_echeancier`, capture d'écran |
| 6 | Nouvelle remise : le formulaire ne s'envoyait pas | catégorie par défaut « exceptionnelle », qui exige une justification (champ obligatoire masqué) | catégorie par défaut « Autre » (remise) ou « sociale » (exonération) | E2E `finance` |
| 7 | Taux de recouvrement calculé sur les seules échéances passées, alors que la définition demandée est encaissé ÷ net attendu | définition historique | `taux_recouvrement` = encaissé ÷ net × 100 ; l'ancien taux reste disponible sous le nom `taux_recouvrement_echu` | test mis à jour, avec justification |
| 8 | Exécution CI 42134340770 de #107 en échec | étape apt « LibreOffice » au-delà de 15 min (miroir lent) | tentatives bornées, reprises, man-db désactivé | CI de #108 verte (2 exécutions) |
| 9 | Aucune remise, exonération (hors « totale »), exception familiale ni échéancier individuel ; aucune vue par élève, aucun KPI ni graphique de situation (signalé) | fonctionnalités absentes | module complet (voir RAPPORT_MODULE_FINANCIER.md et RAPPORT_SITUATION_FINANCIERE.md) | 30 tests backend, 8 tests d'interface, E2E |

## 3. Vérifications sans anomalie

- **Production** :
  - 0 erreur 5xx applicative et 0 trace d'exception sur 24 h ;
  - les seules erreurs sont des refus d'hôte (« Invalid HTTP_HOST » : robots visant l'adresse IP), ce qui est le comportement attendu ;
  - une 503 sur le webhook FedaPay provient d'un test manuel (`curl`), le fournisseur n'étant pas configuré.
- **Celery** : 0 échec sur 24 h. La synchronisation de la boîte contact et la surveillance de la plateforme réussissent (la surveillance renvoie `[]` : aucun constat).
- **Sauvegardes** : `feba-backup.timer` (restic) est quotidien ; dernière exécution réussie (`Result=success`).
- **Certificat TLS** de globalfeba.com : valide jusqu'au 7 décembre 2026. Le renouvellement automatique par certbot est présent ; la surveillance alerte en dessous du seuil.
- **Disque** : 36 %.
- **Sélecteur d'académie** : il se fermait déjà correctement (même mécanisme, réutilisé pour la cloche).

## 4. Risques restants (non corrigés, avec la raison)

| Risque | Pourquoi ce n'est pas corrigé | Action proposée |
|---|---|---|
| Niveau « MARTERNELLE 2 » mal orthographié en production : le barème ne peut pas y rattacher la scolarité | donnée réelle : correction par l'administration | renommer en « MATERNELLE 2 » avant l'import |
| Aucun tarif en production : la situation financière reste « non calculable » | les dates exactes du barème 2026-2027 sont « à confirmer » (affiche sans jour précis) ; décision de l'administration | importer le barème depuis « Tarifs et échéances » après vérification (bouton prévu à cet effet) |
| Modifier le montant d'un tarif déjà payé s'applique rétroactivement à ses échéances (un motif est déjà exigé) | figer des instantanés par élève est une évolution de modèle à décider | pour une nouvelle année, créer un nouveau tarif ; à arbitrer avec FEBA |
| 5 incidents « corrigés » non validés (ERR-310AC0, ERR-A036A8, ERR-5D12BE, ERR-FC6DC7, ERR-4744E2) | la validation est une décision du super administrateur ; les causes sont corrigées et la surveillance est propre | les valider dans « Incidents techniques » |
| Le scénario E2E `messagerie` a échoué une fois (sur trois passages) en phase 9 | cause non reproduite | à surveiller |
| Le restic local et la restauration n'ont pas été rejoués dans le cadre de cette mission | restaurer suppose des droits root et ne doit pas toucher la production | test de restauration sur un serveur de test |
