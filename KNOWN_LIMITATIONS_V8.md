# Limites connues — V8

Ce fichier ne recycle pas des fonctionnalités inachevées en « limites ».
Les trois points ci-dessous dépendent d'une ressource que l'établissement
seul peut fournir : les fichiers d'origine, une signature, un compte
marchand. Tout ce qui pouvait être fait sans eux l'a été, et chaque
réserve est vérifiable.

Les deux fonds graphiques, eux, **sont désormais installés** : les
documents sont réellement produits, avec un score de fidélité de
100,0000 %.

---

## 1. Les fonds installés ne sont pas les PNG d'origine

**Ce qui manque** : les fichiers PNG originaux, au bit près.

Les deux visuels ont été transmis, et ils sont **installés** : dimensions
exactes (1492 × 1054 et 1491 × 1055), géométrie intacte, calibrage valide.
Mais le canal de transmission les ré-encode en WebP avec perte : les
empreintes déclarées (`d0d52ee2…`, `6ff65e31…`) sont structurellement
inatteignables.

Le moteur les a **refusés**, puis ils ont été acceptés **nommément** avec
motif et responsable, inscrits dans `background.accepted_variants`.
L'empreinte d'origine reste l'autorité ; chaque document produit conserve
`background_sha256` ; les commandes affichent l'avertissement.

**Conséquence pratique : aucune.** Le calibrage et la comparaison
reposent sur la géométrie, qui est exacte. Le score de fidélité est de
**100,0000 %** sur les deux gabarits.

**Pour lever la réserve** : transmettre les PNG par un canal sans
transcodage (ZIP, dépôt Git, transfert de fichier), puis

```bash
python manage.py install_document_template --template diploma_feba \
    --file "…/Diplôme FEBA(2).png" --force
make documents-install
python manage.py document_compare --template diploma_feba
```

L'empreinte passera alors sans `--accept-variant`.

---

## 2. Aucun compte marchand n'est branché

**Ce qui manque** : des clés Stripe valides et un compte marchand validé.

**Conséquence** : aucun encaissement réel n'a été effectué. Observé en
direct avec des clés de démonstration :

```
POST /api/payments/card/checkout/
→ 502  Invalid API Key provided: sk_test_***********************LIDE
```

C'est le comportement correct. Le projet **n'invente pas de clé** et ne
simule pas d'encaissement : une interface qui afficherait « paiement
réussi » sans compte marchand serait un mensonge, pas une démonstration.

Les clés de cette démonstration (`sk_test_CLEDEDEMONSTRATIONNONVALIDE`)
étaient **volontairement invalides**. Le 502 qu'elles provoquent **n'est
pas une preuve que le paiement fonctionne** — seulement la preuve
qu'aucune interface factice ne simule un encaissement.

**Ce qui est vérifié malgré tout** : 54 tests couvrent la création de
tentative, le webhook, l'idempotence, l'ordre des événements, les
remboursements, les reçus et les permissions. La vérification de signature
utilise la **bibliothèque officielle Stripe**, sans appel réseau — une
signature de webhook se calcule localement.

**Ce qui reste à faire** : les 17 étapes du parcours réel, une fois les
clés disponibles.

**Pour lever le blocage** : `STRIPE_CONFIGURATION_GUIDE.md`, étapes 1 à 8.

---

## 3. Aucune signature officielle n'est fournie

Les zones `director_signature` des deux gabarits restent vides : aucun
fichier de signature n'existe dans les ressources du projet.

Le moteur ne dessine, ne reconstitue et n'approche **jamais** une
signature. Une signature inventée sur un diplôme n'est pas une
approximation graphique : c'est un faux.

La mention **« YOUR SEAL »** du certificat, elle, **est remplacée** : le
cachet officiel « FEBA · LA DIRECTION » existe dans les ressources du
projet et sert déjà aux bulletins. Seul le contenu du disque change ;
couronne dorée et rubans viennent du fond, intacts.

Sans ce cachet, la mention serait restée visible — ni masquée, ni
remplacée par un ersatz.

**Pour lever le blocage** : déposer le fichier officiel dans
`backend/feba_project/static_files/signature_direction.png`. Il sera apposé
automatiquement.

---

## Points mineurs, sans blocage

### Recettes FEBA à 0 sur le tableau de bord

Le KPI « recettes de l'année » filtre sur l'année **civile**, alors que les
paiements de démonstration sont datés du début de l'année **scolaire**
(septembre). Comportement antérieur à cette itération, conservé tel quel :
il n'affecte ni les montants ni les devises, seulement la fenêtre du KPI.

### `FeeSchedule` n'est pas un module de facturation

Il n'y a ni échéancier, ni solde, ni relance, ni avoir. Une facture au sens
comptable suppose une numérotation légale et des règles fiscales propres au
Bénin comme aux États-Unis ; l'inventer à moitié serait pire que de ne pas
l'avoir. La grille répond à une seule question — « combien coûte ceci, ici,
cette année » — ce qu'il faut pour qu'un paiement en ligne ne soit pas
falsifiable.

### La police calligraphique d'origine n'est pas fournie

Le placeholder « Nom Prénom » est composé en anglaise calligraphique. Cette
fonte n'accompagne pas le projet et n'a pas été identifiée. Crimson Pro
Italic est un choix **compatible** — serif, italique, même or, même ligne
de base — et non identique. La zone du nom étant variable, elle est exclue
de la comparaison des zones statiques : le score de 100 % ne porte pas sur
elle et ne prétend pas le contraire.

Pour lever ce point : déposer la fonte dans
`backend/feba_project/static_files/fonts/` et changer `font.family` dans
les deux gabarits.

### 83 avertissements ESLint

Tous préexistants (variables inutilisées, `setState` dans un effet sur des
pages du site vitrine). **0 erreur.** Aucun n'a été introduit par cette
itération.

### Test ignoré sur SQLite

`test_parent_student.py::…concurrence` : SQLite en mémoire verrouille la
table entière. Le test s'exécute sur PostgreSQL, où il passe.
