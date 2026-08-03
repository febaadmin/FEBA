# Paiement par carte bancaire — rapport V8 (P1)

## Trois règles qui décident de tout le reste

### 1. Le serveur décide du montant

Le navigateur envoie ce qu'il veut payer ; le serveur décide combien.

Tant que le montant arrivait dans le corps de la requête, cette règle
n'était qu'une phrase : il suffisait d'ouvrir les outils de développement et
de remplacer `1250` par `1`.

Pour que le serveur puisse décider, il faut qu'il sache. C'est le rôle du
modèle `FeeSchedule` — une grille tarifaire qui associe académie, année,
niveau et nature de frais à un montant en unité mineure.

Le parent choisit une **ligne**, jamais une somme :

```
POST /api/payments/card/checkout/
{ "student": 12, "payment_type": "mensualite",
  "amount": "1.00", "amount_minor": 1, "currency": "XOF" }   ← falsifications

→ 201  { "amount_display": "$125.50", "currency": "USD" }
```

Vérifié en navigateur : la requête émise par le panneau de paiement ne
contient **aucun champ de montant**, et l'interface ne propose aucun champ
de saisie.

Hors grille, un montant explicite n'est accepté que d'un membre de
l'administration (`role_level >= 80`) et l'origine est tracée sur la
transaction (`amount_source = "staff"`). Un parent reçoit un 409 explicite.

**Ce que `FeeSchedule` n'est pas** : un module de facturation. Il n'y a ni
échéancier, ni solde, ni relance, ni avoir. Une facture au sens comptable
suppose une numérotation légale et des règles fiscales propres au Bénin
comme aux États-Unis ; l'inventer à moitié serait pire que de ne pas
l'avoir. La grille répond à une seule question : « combien coûte ceci, ici,
cette année ».

### 2. La redirection n'est pas une preuve

L'URL de succès est devinable et un paiement peut être annulé après coup.
**Aucun appel ne permet de déclarer un succès depuis le navigateur.**

Seul le webhook, dont la signature est vérifiée sur le **corps brut**, crée
l'encaissement. Re-sérialiser le JSON parsé changerait un espace ou l'ordre
des clés et invaliderait la signature — ce qui ferait rejeter des
événements parfaitement légitimes.

La page de retour dit « Paiement en cours de vérification », pas « payé ».

```
POST /api/payments/webhook/stripe/  (sans en-tête de signature)
→ 400  Signature de webhook invalide
```

Sans `STRIPE_WEBHOOK_SECRET`, **tous** les événements sont refusés (503).
C'est délibéré : sans signature, n'importe qui connaissant l'URL pourrait
déclarer un paiement réussi.

### 3. Tout est idempotent

| Situation | Protection |
|---|---|
| Double clic | une tentative ouverte pour le même élève, type et montant est **réutilisée** |
| Rejeu réseau | `idempotency_key` par tentative, transmise au prestataire |
| Webhook rejoué | `UniqueConstraint(provider, event_id)` — **en base**, car deux instances du serveur peuvent recevoir le même événement au même instant |
| Deux événements pour un même encaissement | `mark_succeeded()` ne crée qu'un seul `Payment` |
| Remboursement relancé | plafonné par `CheckConstraint(amount_refunded_minor <= amount_minor)` |

## Événements hors séquence

Les événements ne sont pas ordonnés. Deux cas sont traités explicitement :

- `succeeded` après `failed` → **le succès l'emporte**, l'argent est parti ;
- `failed` après `succeeded` → **ignoré**, il n'efface pas une recette réelle.

`charge.refunded` transmet le **cumul** remboursé, pas l'incrément : le
delta est calculé, sinon un remboursement partiel suivi de son webhook
serait compté deux fois.

## Ce qui est stocké — et ce qui ne l'est jamais

`PaymentTransaction` conserve : académie, payeur, élève, année scolaire,
ligne tarifaire, montant en unité mineure, devise, prestataire, identifiant
de session, identifiant d'intention, statut interne, statut brut du
prestataire, clé d'idempotence, dates (création, succès, échec, mise à
jour), motif d'échec, montant remboursé, métadonnées non sensibles.

**Jamais** : numéro de carte, date d'expiration, cryptogramme, jeton de
moyen de paiement brut. Le modèle n'a aucun champ pour les recevoir, et un
test le vérifie en énumérant les champs déclarés. Le formulaire est celui du
prestataire, affiché sur son domaine : ces données ne transitent même pas
par le serveur, ce qui maintient l'application hors du champ d'application
complet de PCI-DSS.

## Statuts

`created`, `pending`, `action_required`, `processing`, `succeeded`,
`failed`, `cancelled`, `expired`, `partially_refunded`, `refunded`,
`disputed`.

Plus nombreux que « ça marche / ça ne marche pas » à dessein :
« action requise » (authentification bancaire) n'est pas un échec, et le
confondre avec un refus ferait recommencer un paiement en cours.

## Reçu

Généré automatiquement à l'encaissement, dans la devise réellement
encaissée, chiffres **et** lettres. La génération est volontairement **non
bloquante** : un échec de rendu PDF ne doit pas faire échouer le webhook —
l'argent est encaissé, et un webhook en erreur serait rejoué en boucle par
le prestataire. Le reçu reste regénérable à la demande via
`/api/payments/card/<id>/receipt/`.

## Configuration

```bash
make payments-setup          # guidée, vérifiée
make payments-check          # identifiants soumis au prestataire
make payments-test           # suite de tests du paiement
make payments-webhook-check  # réception et traitement des événements
```

`payments_setup` refuse les combinaisons dangereuses, sans rien écrire :

```
$ ... --secret-key sk_test_… --publishable-key pk_live_…
  ✗ La clé secrète et la clé publique ne sont pas dans le même mode
    (test / production) : les paiements créés dans l'un ne seraient jamais
    confirmés dans l'autre.
CommandError: Configuration refusée. Aucune clé n'a été écrite : une
configuration à moitié juste est pire qu'absente.

$ ... --secret-key pk_test_… --publishable-key sk_test_…
  ✗ Les clés secrète et publique semblent inversées. Exposer une clé
    secrète au navigateur donnerait à quiconque le contrôle du compte
    marchand.
```

Clés déclarées dans `.env.example`, **aucune valeur réelle** :
`CARD_PAYMENTS_ENABLED`, `PAYMENT_PROVIDER`, `STRIPE_MODE`,
`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
`PUBLIC_BASE_URL`.

`payments_check` appelle réellement l'API du prestataire, en lecture seule.
Vérification exécutée sur cette instance :

```
  ✓ Paiement par carte activé
  ✓ STRIPE_SECRET_KEY renseignée
  ✓ Mode « test » cohérent avec la clé
  ✗ Identifiants acceptés par le prestataire
    Clé refusée par le prestataire (révoquée ou erronée).
```

## État réel de l'intégration

**Le code est complet et éprouvé ; aucun compte marchand n'est branché.**

Aucune clé Stripe valide n'a été fournie, et le projet n'en invente pas.
Conséquence, observée en direct :

```
POST /api/payments/card/checkout/
→ 502  Invalid API Key provided: sk_test_***********************LIDE

Journal des transactions :
  FEBA_FHA  $125.50  failed  | Invalid API Key provided: sk_test_…LIDE
```

C'est exactement le comportement attendu, et c'est la preuve qu'aucune
interface factice ne simule un encaissement : l'échec vient du prestataire,
il est tracé, et il est présenté à l'utilisateur.

**Pour encaisser réellement**, l'établissement doit :

1. ouvrir un compte marchand chez le prestataire et le faire valider ;
2. `make payments-setup` avec les clés du tableau de bord ;
3. `make payments-check` — doit passer au vert, y compris
   `charges_enabled` ;
4. déclarer le webhook sur `<PUBLIC_BASE_URL>/api/payments/webhook/stripe/`
   avec les six événements listés par la commande.

Tant que l'étape 1 n'est pas faite, aucun paiement réel n'est possible —
aucune configuration ne peut y suppléer.

## Tests

54 tests dans `backend/tests/test_card_payments.py` :

| Groupe | Ce qui est éprouvé |
|---|---|
| Création | montant issu de la grille, devise de l'académie, périmètre parent, type inconnu, double clic, refus prestataire, prestataire non configuré, clé d'idempotence |
| Tarifs | visibilité par académie, anti-IDOR |
| Webhook | encaissement, signature invalide, rejeu, deux événements pour un encaissement, échec, authentification bancaire, expiration, annulation, ordre inversé (deux sens), événement orphelin, rapprochement sans métadonnées, absence de données de carte |
| Reçu | génération automatique, libellé en dollars, centimes énoncés, accès parent, anti-IDOR, refus sans encaissement |
| Remboursement | partiel, total, plafond (vue **et** modèle), parent interdit, autre académie interdite, non encaissé, cumul par webhook |
| Journal | isolation par académie, devise par ligne, périmètre parent |
| Signature | **bibliothèque officielle Stripe**, signature correcte acceptée, corps modifié refusé, secret absent |
| Grille | devise de l'académie, frontière entre académies, priorité année > permanent, tarif désactivé, montant nul |

La vérification de signature est testée avec le vrai code de Stripe, sans
appel réseau : une signature de webhook se calcule localement.
