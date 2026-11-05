# Validation des paiements — phase 7

Dernière mise à jour : 05/11/2026. Ce rapport distingue strictement :
**local** (tests exécutés sur le poste), **CI** (GitHub Actions), **production**
(globalfeba.com), **prestataire externe** (FedaPay réel) et **bloqué** (action humaine).

## 1. Graphique des paiements du tableau de bord (chantier B)

| Élément | État | Preuve |
|---|---|---|
| Périodes : aujourd'hui, hier, cette semaine, semaine précédente, ce mois, mois précédent, 7/30 j, 3/6/12 mois, année civile, année scolaire, personnalisée | CI + production | `tests/test_paiements_recherche.py::PeriodesEtGranularitesTests` ; E2E `paiements` (6 périodes appelées, 200) |
| Granularité adaptée et choisissable : heure (1 jour), jour (≤ 92 j), semaine (8 j–2 ans), mois (> 31 j) ; refus d'une granularité inadaptée (400) | CI | `test_granularite_adaptee_jamais_artificielle`, `test_api_granularite_invalide` |
| Granularité horaire : paiements sans heure enregistrée comptés dans les indicateurs, signalés, jamais placés arbitrairement | CI | `test_journee_heure_par_heure` |
| Types et modes à choix multiples ; proposés d'après les données réelles (types payés ou tarifés, modes utilisés, carte seulement si configurée) | CI + production | `test_options_natures_et_modes_reels` ; production (lecture seule) : FEBA modes = `cash`, types = inscription, mensualité, cantine, transport |
| Filtres combinables, puces, réinitialisation, comparaison période précédente, infobulles détaillées, chargement, états vides | CI | tests frontend `GraphiquePaiements.test.jsx` (10) |
| Indicateurs : encaissé net, brut, remboursements, annulés, en attente / échoués carte, attendu, restant, recouvrement, **montant moyen**, **élèves payeurs** ; répartitions par nature et par mode | CI | `test_repartitions_par_nature_et_mode` (somme des modes = encaissé) |

## 2. Page « Paiements » (chantier C)

| Élément | État | Preuve |
|---|---|---|
| Recherche différée (350 ms), sans casse ni accents : nom, prénom, matricule, référence, montant, date (jj/mm/aaaa, jj/mm), classe, type, mode, statut | CI + production | `test_recherche_*` ; production (lecture seule) : « maela » et « MAËLA akoyi » → 5 paiements |
| Filtres : période, année, cycle, niveau, classe (classe de l'année), élève, type, mode, statut (dont remboursés), montant min / max / exact | CI | `test_filtres_combinables` |
| Tri serveur stable (date, montant, élève sans accents, type, mode, statut), pagination serveur, récapitulatif de toute la sélection par devise | CI + E2E local | `test_tri_stable_et_pagination`, `test_totaux_de_toute_la_selection` ; E2E « aucun doublon entre deux pages » |
| Export Excel (.xlsx) respectant filtres et tri | CI + E2E local | `test_export_excel_respecte_les_filtres` ; E2E téléchargement `.xlsx` |
| Isolation : administrateur limité à son académie, parent limité à ses enfants (recherche et filtre élève compris) | CI | `test_isolation_academie_et_parent` |

**Anomalie corrigée en passant** : un élève **sans compte utilisateur** (jeune enfant) masquait ses paiements à ses parents (`student__user__is_active=True` excluait `user` vide).

## 3. Cohérence financière entre modules

- Même code de filtrage pour le graphique et la page (`tableau_bord.lire_filtres` / `bornes`).
- Test `test_coherence_tableau_de_bord_et_page_paiements` : 5 combinaisons de filtres → mêmes montants nets, mêmes nombres de paiements, mêmes annulations.
- Remboursement carte compté une seule fois (déduit du net) : `test_remboursement_compte_une_fois`, `test_remboursement_constate_hors_ligne_par_l_administration`.
- **Production, lecture seule (05/11, 15 h)** : FEBA, 12 mois → page 11 645 440 FCFA / 240 paiements = graphique 11 645 440 / 240 ; mêmes égalités pour `mode=cash`, `nature=mensualite` (9 000 440 / 86), `periode=mois` (603 000 / 19) ; FHA : 0 = 0.
- Non mesurable en production : attendu et reste à payer (aucun tarif saisi ; voir phase 6).

## 4. Paiement par carte (chantier F)

### 4.1 Audit de l'existant
L'architecture V8 était correcte (tentative distincte de l'encaissement, montant décidé par le serveur, idempotence, webhooks dédoublonnés, page hébergée), mais **le seul prestataire branché était Stripe**, qui n'accepte pas les entreprises établies au Bénin : le paiement en ligne était inutilisable pour les deux académies (Cotonou). En production, le paiement carte est désactivé (`CARD_PAYMENTS_ENABLED` absent) : aucun bouton trompeur.

### 4.2 Comparatif des prestataires (sources publiques, à confirmer contractuellement)

| Critère | FedaPay | Kkiapay | CinetPay | Stripe |
|---|---|---|---|---|
| Siège / compte marchand au Bénin | Oui (Cotonou) | Oui (Bénin) | Côte d'Ivoire, Bénin couvert | **Non** (Bénin non pris en charge) |
| Devise | XOF (seule documentée) | XOF | XOF, XAF, USD… | — |
| Cartes Visa/Mastercard | Oui | Oui | Oui | — |
| Mobile Money Bénin (MTN, Moov…) | Oui | Oui | Oui | — |
| Page hébergée | Oui (lien de paiement + jeton) | Oui (widget) | Oui | — |
| Webhook signé | Oui (HMAC-SHA256, horodatage) | Oui | Oui | — |
| Remboursement par API | **Non documenté** (tableau de bord, MTN) | À vérifier | À vérifier | — |
| Bac à sable | Oui (clés `sk_sandbox`) | Oui | Oui | — |
| Frais carte (indicatifs, non contractuels) | ≈ 3 % + fixe | ≈ 2,9–3,2 % + fixe | ≈ 3,5 % | — |

**Choix : FedaPay**, pour sa présence au Bénin, l'encaissement XOF, une API documentée avec vérification de transaction par appel serveur et webhooks signés. Le choix n'est pas définitif tant que les conditions contractuelles (frais, reversement, KYC) ne sont pas obtenues : l'abstraction `providers.py` permet d'ajouter Kkiapay ou CinetPay sans toucher au reste.

Sources : docs.fedapay.com (intégration API, webhooks, création de transaction et de jeton, moyens de paiement, remboursements), SDK PHP officiel FedaPay (`WebhookSignature.php`), support.fedapay.com (pays et moyens), comparatifs publics de frais (indicatifs).

### 4.3 Architecture et sécurité
- Création : montant du **tarif publié** (jamais du navigateur), devise de l'académie ; FedaPay ne prenant que XOF, FHA (USD) obtient un refus explicite (409) et le panneau de paiement explique l'indisponibilité.
- Redirection vers la page hébergée FedaPay : **aucune donnée de carte dans FEBA** (PCI DSS : SAQ A).
- Confirmation : webhook authentifié (`X-FEDAPAY-SIGNATURE`, HMAC-SHA256 de `t.corps`, tolérance 300 s, comparaison à temps constant), dédoublonné en base ; puis **relecture de la transaction chez FedaPay** (statut, montant, devise) avant toute écriture.
- Retour navigateur : demande de vérification serveur à serveur ; l'écran n'affiche « confirmé » que si le serveur l'a constaté.
- Verrou de ligne : webhook, retour et rapprochement simultanés → un seul `Payment`.
- Écart de montant ou de devise : aucun encaissement, échec « vérification manuelle requise », alerte au journal.
- Rapprochement Celery (30 min) et expiration au-delà de `CARD_ATTEMPT_EXPIRY_HOURS` (24 h).
- Remboursement : constaté par l'administration après remboursement dans le tableau de bord FedaPay ; déduit partout (graphique, page, situation).
- Secrets : `FEDAPAY_SECRET_KEY`, `FEDAPAY_WEBHOOK_SECRET` en variables d'environnement, jamais journalisés ni exposés.

### 4.4 Tests
| Cas | Résultat | Où |
|---|---|---|
| Accepté, refusé, abandonné, expiré | OK | local + CI, réseau FedaPay **simulé** |
| Webhook reçu deux fois / autre événement pour la même transaction | 1 seul encaissement | idem |
| Webhook invalide, mal formé, mauvais secret, horodatage périmé | 400, rien écrit | idem |
| Événement « approuvé » alors que FedaPay dit « en attente » | rien encaissé | idem |
| Retour navigateur sans confirmation | « en attente », rien encaissé | idem |
| Montant modifié, devise incorrecte | aucun encaissement | idem |
| Double soumission | même tentative réutilisée | idem |
| Prestataire injoignable au webhook | 503, rejeu traité ensuite | idem |
| Remboursement | refus API explicite, constat hors ligne OK, net déduit | idem |
| Élève d'un autre parent | 404 | idem |

### 4.5 Ce qui n'est PAS validé
- **Aucune transaction en bac à sable FedaPay réel** : il faut un compte FedaPay et ses clés de test (`sk_sandbox_…`, `wh_sandbox_…`). Aucune clé n'a été inventée.
- **Aucune transaction réelle** en production.
- Format exact de certains champs FedaPay non entièrement documenté (enveloppe `v1/transaction`, nom de l'événement `name` / `type`) : le code accepte les deux formes ; à confirmer au premier test en bac à sable.

### 4.6 Actions humaines nécessaires
1. Ouvrir le compte marchand FedaPay de l'académie (KYC : pièces de l'entreprise) et accepter ses conditions.
2. Fournir, par le gestionnaire de secrets du serveur (jamais par la conversation), `FEDAPAY_SECRET_KEY` et `FEDAPAY_WEBHOOK_SECRET` **de bac à sable**, avec `PAYMENT_PROVIDER=fedapay`, `FEDAPAY_ENVIRONMENT=sandbox`, `CARD_PAYMENTS_ENABLED=True`.
3. Déclarer le webhook `https://globalfeba.com/api/payments/webhook/fedapay/` dans le tableau de bord FedaPay.
4. Saisir les tarifs (« Tarifs et échéances ») : sans tarif publié, aucun paiement en ligne n'est proposé à un parent.
5. Après validation en bac à sable, passer en `live` avec les clés de production.
