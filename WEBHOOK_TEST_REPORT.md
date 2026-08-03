# Webhook de paiement — rapport de test

## Statut, en une ligne

**Éprouvé contre un prestataire SIMULÉ. Jamais confronté à un webhook
réellement émis par Stripe.** Aucun identifiant de test valide n'est
disponible dans cet environnement — voir la section finale.

Ce que ce rapport démontre : la logique de réception, d'authentification,
de déduplication et de rapprochement fait ce qu'elle prétend. Ce qu'il ne
démontre pas : que Stripe, en conditions réelles, envoie exactement ce que
la simulation lui prête.

## Pourquoi le webhook est le seul point qui encaisse

L'URL de retour du navigateur est devinable, et un paiement peut être
annulé après coup. **Aucun appel de l'API ne permet de déclarer un succès
depuis le navigateur.** La page de retour dit « Paiement en cours de
vérification », pas « payé ».

Premier test de la liste : après une redirection, sans webhook, la
transaction reste `pending` et **aucun `Payment` n'existe**.

## Authentification par signature

La signature est vérifiée sur le **corps brut**. Re-sérialiser le JSON
parsé changerait un espace ou l'ordre des clés, et invaliderait des
événements parfaitement légitimes.

| Situation | Réponse | Effet |
|---|---|---|
| Signature valide | 200 | encaissement créé |
| Signature absente ou forgée | **400** | rien créé, rien journalisé |
| `STRIPE_WEBHOOK_SECRET` non configuré | **503** | tous les événements refusés |

Le 503 est délibéré. Sans secret, aucun événement ne peut être
authentifié : les accepter reviendrait à laisser quiconque connaissant
l'URL déclarer un paiement réussi.

La vérification de signature elle-même est testée avec **la bibliothèque
officielle Stripe**, sans appel réseau — une signature de webhook se
calcule localement :

| Test | Résultat |
|---|---|
| signature correcte acceptée | ✓ |
| corps modifié après signature refusé | ✓ |
| secret absent → aucun événement accepté | ✓ |

## Déduplication

`UniqueConstraint(provider, event_id)` — **en base**, pas dans le code.
Deux instances du serveur peuvent recevoir le même événement au même
instant ; un verrou applicatif ne les coordonnerait pas.

## Résultats — 15 tests, tous verts

```
$ pytest tests/test_card_payments.py::WebhookTests -v

test_la_redirection_seule_n_encaisse_rien                        ✓
test_un_evenement_signe_cree_l_encaissement                      ✓
test_un_evenement_non_signe_ne_cree_rien                         ✓
test_un_evenement_rejoue_n_encaisse_qu_une_fois                  ✓
test_deux_evenements_distincts_n_encaissent_qu_une_fois          ✓
test_un_echec_est_enregistre_sans_encaissement                   ✓
test_une_authentification_bancaire_est_un_statut_a_part          ✓
test_une_session_expiree_est_distinguee_d_un_refus               ✓
test_un_abandon_est_enregistre_comme_annulation                  ✓
test_un_succes_arrive_apres_un_echec_l_emporte                   ✓
test_un_echec_arrive_apres_un_succes_n_efface_pas_la_recette     ✓
test_un_evenement_orphelin_est_journalise_sans_erreur            ✓
test_le_rapprochement_fonctionne_sans_metadonnees                ✓
test_aucune_donnee_de_carte_n_est_stockee                        ✓
test_les_metadonnees_stockees_ne_contiennent_pas_de_donnees_de_carte ✓
```

### Ce que chacun protège

| Test | Défaut évité |
|---|---|
| redirection seule | un paiement annulé après coup compté comme encaissé |
| événement rejoué | un parent crédité deux fois pour un seul débit |
| deux événements distincts | `checkout.session.completed` **et** `payment_intent.succeeded` décrivent le même encaissement ; Stripe envoie souvent les deux |
| succès après échec | l'argent est réellement parti : le succès l'emporte |
| échec après succès | ignoré — il n'efface pas une recette réelle |
| authentification bancaire | « action requise » n'est pas un refus ; les confondre ferait recommencer un paiement en cours |
| session expirée | distinguée d'un refus : la relance n'est pas la même |
| événement orphelin | journalisé et renvoyé en 200 ; un 500 ferait rejouer l'événement en boucle |
| rapprochement sans métadonnées | un événement relayé ou rejoué manuellement peut les perdre |
| aucune donnée de carte | le modèle n'a **aucun champ** pouvant recevoir un PAN, une date d'expiration ou un cryptogramme — vérifié en énumérant les champs déclarés |

## Diagnostic en exploitation

```bash
make payments-webhook-check
```

Répond aux trois questions dans l'ordre où elles se posent : le point de
terminaison est-il protégé, des événements arrivent-ils, des tentatives
sont-elles restées en attente sans jamais aboutir.

Une tentative ouverte depuis plus d'une heure est le signe exact d'un
webhook qui n'arrive pas. La session du prestataire expire au bout de 24 h,
mais le silence, lui, commence tout de suite.

## Ce qui reste non validé

**Aucun webhook réellement émis par Stripe n'a été reçu.**

Il faudrait, dans l'ordre :

1. un compte marchand Stripe validé ;
2. `make payments-setup` avec les clés du tableau de bord ;
3. `stripe listen --forward-to …` (développement) ou un point de
   terminaison public déclaré (production) ;
4. un paiement de test réel avec `4242 4242 4242 4242`.

L'environnement de cette livraison ne dispose d'aucun identifiant Stripe :

```
$ env | grep -i stripe          → aucune variable
$ grep STRIPE_SECRET_KEY=sk_ .env.dev  → 0 clé renseignée
$ which stripe                  → absent
$ curl https://api.stripe.com/v1/account
  → HTTP 401   (le réseau atteint bien Stripe ; il manque une clé, pas une route)
```

Le projet **n'invente pas de clé**. Tant que l'étape 1 n'est pas faite,
cette validation externe reste ouverte, et elle est comptée comme telle
dans le rapport final.
