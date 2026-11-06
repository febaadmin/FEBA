# Rapport des tests (clôture)

Seuls les tests **réellement exécutés** figurent ici. L'environnement local est composé de :
- PostgreSQL 16 dans Docker ;
- un backend Django monté sur le dépôt ;
- le frontend compilé (`vite build`) et servi en aperçu ;
- Chrome piloté par Playwright ;
- e-mails en mémoire (locmem), sans fournisseur de paiement ni IMAP.

## 1. Résultats

| Suite | Exécution | Résultat |
|---|---|---|
| Backend complet (PostgreSQL) | `manage.py test` | **2255 tests OK** (7 ignorés) |
| Nouveaux tests finance | `tests/test_finance_cloture.py` | **30 OK** |
| Tests finance existants (relances, situation, tableau de bord, tarifs, carte, comptabilité) | 6 modules | **OK** (126 tests avant modification, de nouveau OK après) |
| Balayages API (toutes les routes, 5 profils) | `test_balayage_api`, `test_balayage_fuites` | **OK** : aucune 500, aucune fuite |
| Frontend (Vitest) | 93 fichiers | **OK** (dont 6 tests de la cloche, 5 de la situation, 3 des remises et barème) |
| Lint | ESLint | 0 erreur |
| E2E complet (20 scénarios, dont le nouveau `finance`) | `node lancer.mjs` | 461 contrôles : 458 OK, 3 KO dus à MES données d'essai locales (voir § 3) ; après nettoyage, les scénarios concernés (`tableau`, `finance`) donnent **48/48** |
| CI GitHub de #108 (a3c4d57) | 2 exécutions | **12 contrôles verts** (backend PostgreSQL, frontend, E2E, images Docker, sécurité, configuration) |

## 2. Couverture des cas demandés (backend, sauf mention)

| Cas | Test |
|---|---|
| Création et modification d'un tarif ; réenregistrement des échéances, échange de dates | `EcheancesTarifTests`, `test_tarifs_historique` |
| Remise fixe et remise en pourcentage | `test_remise_fixe_…`, `test_remise_pourcentage_…` |
| Exonération totale, partielle, temporaire ; exonération puis remise | `ExonerationsTests` |
| Remise individuelle, familiale, fratrie, par classe | `test_fratrie_famille_et_classe` |
| Règles de cumul et conflits (non cumulable, raison affichée) | `test_cumul_et_non_cumul` |
| Une règle jamais appliquée deux fois ; jamais de montant négatif | `test_une_regle_ne_compte_qu_une_fois`, `test_remise_fixe_…` |
| Paiement anticipé et paiement intégral (conditions) | `test_paiement_anticipe_et_integral` |
| Échéancier personnalisé (paiements intacts, somme contrôlée, motif, historique, retour au standard, relances sans collision) | `EcheancierPersonnelTests` |
| Paiement partiel, intégral, multiples, remboursement, annulation, retard | `test_partiel_integral_multiple_remboursement_annulation_retard` |
| Changement d'année scolaire, changement de classe | `test_changement_d_annee_et_de_classe` |
| Cohérence des totaux (somme des classes = académie, somme des élèves) | `test_totaux_coherents_et_statuts` |
| Filtres (classe, statut, recherche, nature, période) | `test_filtres` ; interface : `SituationFinanciere.test.jsx` |
| Exports | `test_export_csv` ; E2E (téléchargement réel) |
| Permissions par profil, cloisonnement entre académies, parent sans données internes | `test_permissions_par_profil_et_cloisonnement` ; E2E |
| Données existantes non altérées | `test_donnees_existantes_non_alterees` |
| Journal inaltérable ; dispositions tracées | `test_journal_inalterable`, `test_disposition_…` |
| Non calculable sans tarif ; encaissements réels toujours visibles | `test_non_calculable_sans_tarif`, `test_encaissements_reels_meme_sans_echeancier` |
| Barème : aperçu, import explicite, aucun remplacement | `test_bareme_apercu_puis_import_explicite_sans_remplacement` ; interface |
| Cloche : clic extérieur (même avec arrêt de propagation), Échap, recliquer, changement de page, aucun changement de statut | `NotificationBell.test.jsx` ; E2E bureau et mobile (375 px) |

## 3. Échecs rencontrés et corrections

- **E2E `finance`, 1er passage** : le formulaire de remise ne s'envoyait pas. C'était un vrai défaut (catégorie par défaut exigeant une justification masquée) ; il est corrigé.
- **E2E `finance`, 2e passage** : la mise à jour d'un tarif était refusée, parce que les échéances étaient réenregistrées avec une date existante. C'était un **vrai défaut**, corrigé et couvert par un test.
- **E2E `messages_site` et `finance`** : un tarif `examen` restait d'un passage interrompu ; le scénario le réutilise désormais.
- **Suite E2E complète** : 3 échecs (`tableau` et `finance`) causés par une remise et un tarif d'essai que j'avais créés localement pour les captures d'écran. Ces données locales ont été annulées et le scénario `finance` a été rendu indépendant de l'état existant. Les deux scénarios repassent à 48/48.
- **Test `test_situation_financiere`** : l'attente du taux de recouvrement a été mise à jour **volontairement** (nouvelle définition demandée) ; l'ancien taux reste testé sous son nouveau nom.

## 4. Parcours non vérifiés

- **Production** : aucune remise, exonération ou échéancier n'a été créé, et aucun barème importé. Ce sont des décisions de l'administration, et aucune donnée réelle ne doit être modifiée sans elle.
- **Comptes réels des cinq profils** : non utilisés (aucun mot de passe réel ne doit être manipulé).
- **Captures d'écran à 4 tailles** (1600, 1280, 768, 375 px) : examinées sur l'environnement local.
- **Restauration d'une sauvegarde** : non rejouée.
