# Limites connues — V9

Ce fichier ne recycle pas des fonctionnalités inachevées en « limites ».
Chaque point ci-dessous dépend d'une ressource que l'établissement seul
peut fournir, ou d'un choix assumé qui est expliqué. Tout ce qui pouvait
être fait sans elles l'a été.

---

## 1. Aucun e-mail n'est parti sur Internet

**Ce qui manque** : un fournisseur d'envoi et des identifiants.

Le backend de cette instance est `console` : les messages sont composés,
journalisés, horodatés, et écrits dans la console du serveur.

**Ce qui est vérifié malgré tout** : composition, deux formats (texte et
HTML), deux langues, pièce jointe, journal d'acheminement avec identifiant
de suivi, cinq états explicites, politique de reprise, action de relance,
et le comportement en cas d'échec — éprouvé avec un backend qui lève.

**Ce que l'application refuse de faire** : présenter un envoi comme réel.
`manage.py email_check` sort en erreur, et l'écran affiche « Sans
fournisseur » plutôt que « Envoyé ».

**Pour lever la réserve** : renseigner `EMAIL_HOST`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD` et `EMAIL_BACKEND`, puis
`python manage.py email_check --to vous@exemple.test`.

---

## 2. Aucune signature officielle n'est fournie

Les zones `director_signature` des deux gabarits restent vides.

Le moteur ne dessine, ne reconstitue et n'approche **jamais** une
signature. Une signature inventée sur un diplôme n'est pas une
approximation graphique : c'est un faux.

**Pour lever la réserve** : déposer le fichier officiel dans
`backend/feba_project/static_files/signature_direction.png`. Il sera apposé
automatiquement, et `branding_check` cessera de le signaler.

---

## 3. L'académie en ligne n'a pas de fond de diplôme

Les deux gabarits sont réservés à FEBA : leur fond porte son identité
visuelle. Proposer un diplôme au fond FEBA à un élève de FEBA French
Heritage Academy produirait un document au nom de l'une et à l'effigie de
l'autre — exactement le défaut que P0 corrige.

L'écran ne masque pas le gabarit : il affiche la raison.

**Pour lever la réserve** : fournir le fond de l'académie en ligne. Il fera
l'objet d'un gabarit distinct, avec son propre calibrage — pas d'un partage.

---

## 4. Les fonds installés ne sont pas les PNG d'origine

Inchangé depuis V8. Les deux visuels sont installés — dimensions exactes
(1492 × 1054 et 1491 × 1055), géométrie intacte, calibrage valide — mais le
canal de transmission les a ré-encodés avec perte : les empreintes
déclarées sont structurellement inatteignables.

Le moteur les a **refusés**, puis ils ont été acceptés **nommément**, avec
motif et responsable, inscrits dans `background.accepted_variants`.
L'empreinte d'origine reste l'autorité ; chaque document produit conserve
`background_sha256`.

**Conséquence pratique : aucune.** Le calibrage repose sur la géométrie,
qui est exacte.

---

## 5. Le paiement par carte reste non éprouvé en conditions réelles

Inchangé depuis V8. Aucune clé Stripe valide n'est disponible. 54 tests
couvrent la création de tentative, le webhook, l'idempotence, l'ordre des
événements, les remboursements, les reçus et les permissions — sans jamais
toucher Stripe, sauf la vérification de signature, qui utilise la
bibliothèque officielle sans réseau.

**Pour lever le blocage** : `STRIPE_CONFIGURATION_GUIDE.md`, étapes 1 à 8.

---

## Points mineurs, sans blocage

### Les libellés d'état des dossiers FHA restent en français

`APPLICATION_STATUSES`, dans `FhaAdmissions.jsx`, est une liste écrite en
dur : sur une session en anglais, la colonne « Status » affiche « Fiche
reçue ». Visible sur `e2e/captures/v9-2-admin-fha-admissions.png`.

Défaut d'affichage seulement — l'état stocké et transmis est le code
interne (`form_received`), jamais le libellé. Antérieur à cette itération,
laissé tel quel pour ne pas mêler une refonte d'internationalisation aux
corrections demandées.

### Redis doit tourner

`django-ratelimit` et l'authentification passent par le cache. Sans Redis,
le formulaire public et la connexion renvoient 500. Constaté pendant les
vérifications navigateur, sur ce conteneur, avant démarrage du service.
Ce n'est pas un défaut du code — mais l'installation doit le savoir.

### 83 avertissements ESLint

Tous préexistants (variables inutilisées, `setState` dans un effet sur des
pages du site vitrine). **0 erreur.** Aucun n'a été introduit par cette
itération.

### Test ignoré sur SQLite

`test_parent_student.py::…concurrence` : SQLite en mémoire verrouille la
table entière. Le test s'exécute sur PostgreSQL, où il passe.

### La police d'interface vient de Google Fonts

`fonts.googleapis.com` est injoignable derrière le proxy de ce conteneur :
l'application retombe alors sur la police système, sans rien casser. Deux
raisons de le signaler tout de même — un déploiement hors ligne perdra la
typographie voulue, et chaque visiteur est vu par un tiers au chargement de
la page. Constaté pendant les vérifications navigateur (14 messages de
console, tous imputables à cette requête ou à des requêtes volontairement
annulées à la navigation).

### Ni téléphone ni e-mail ne sont renseignés pour les deux académies

Les documents ne les affichent donc pas : `address_line` omet ce qui est
vide plutôt que d'inventer. C'est une donnée que l'établissement doit
saisir dans les paramètres de son académie — désormais exposés par l'API
(voir le défaut corrigé sur `SchoolSerializer`).
