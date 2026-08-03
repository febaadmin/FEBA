# Documents officiels — disponibles dès l'installation

## Le message reproché

L'application était livrée avec son diplôme bloqué :

> Le gabarit déclare 1 mention(s) d'exemple à neutraliser, mais le fond
> dérivé n'existe pas encore. Sans lui, le document sortirait avec la
> mention d'origine visible sous le vrai contenu. Lancez :
> `manage.py document_neutralize --template diploma_feba`

Demander à l'utilisateur d'une application finie de lancer une commande
d'atelier n'est pas une dégradation acceptable : c'est un défaut
d'installation déguisé en message d'aide.

## La cause

Un seul choix : « le fichier se régénère, donc on ne le versionne pas ».
Le fond neutralisé n'était pas dans le dépôt, donc pas dans l'archive, donc
absent de chaque installation.

## La correction

Le fond neutralisé est **versionné**, son empreinte SHA-256 est **déclarée
dans le gabarit**, et elle est **vérifiée avant chaque émission**.

```
backend/document_templates/derived/diplome_feba_2.neutralise.png
SHA-256 : f233b6bcfe3d56724773793e8f7394eccbbb307ef2eadc005e4ace9de2cbc902
```

`git archive` suit ce que git suit : le fichier part avec l'archive sans
traitement particulier.

## Le vrai danger, et sa suppression

`render_background_path` retombait sur l'ORIGINAL quand le dérivé manquait.
Ce repli silencieux était plus dangereux que le blocage : le diplôme
sortait avec « Nom Prénom » visible sous le vrai nom, sans erreur, sans
signe, sans que personne ne puisse le voir sur un fichier fini.

Le repli est supprimé. Un dérivé absent **ou altéré** bloque l'émission ;
il ne dégrade pas le rendu.

## Trois contrôles, à trois moments

| Moment | Bloquant ? | Pourquoi |
|---|---|---|
| Démarrage du serveur | non | Une école dont le diplôme n'est pas prêt doit pouvoir faire l'appel et saisir des notes |
| Installation (`bootstrap.sh`) | oui, avec réparation automatique | Une installation qui se termine « réussie » avec un diplôme bloqué n'est pas réussie |
| Émission d'un document | oui, toujours | C'est là que le document faux partirait |

## Vérifié en cassant l'installation

**Fichier supprimé :**
```
✗ diploma_feba · fond neutralisé — Le fond neutralisé du gabarit
  « diploma_feba » est absent de l'installation. Il est livré avec le
  projet ; son absence signale une archive incomplète ou un fichier
  supprimé. Réparation : « make documents-install ».
```

**Fichier altéré (14 octets ajoutés) :**
```
✗ diploma_feba · fond neutralisé — ne correspond pas à son empreinte
  (installée cdd15cd89d6d12d8…, attendue f233b6bcfe3d5672…). Il a été
  modifié ou régénéré depuis un autre original.
```

**Réparation :** `document_neutralize` redonne exactement la même empreinte
`f233b6bc…`. C'est ce déterminisme qui autorise à empreindre le dérivé : si
la neutralisation variait d'une exécution à l'autre, l'empreinte déclarée
ne pourrait rien vérifier.

## État sur cette installation

```
$ python manage.py documents_ready
  ✓ polices — 3 embarquées
  ✓ stockage privé — /home/user/FEBA/backend/private_media
  ✓ certificate_feba · fond original — variante acceptée
  ✓ certificate_feba · calibrage — tolérance 0.2 mm
  ✓ certificate_feba · rendu — 997 Ko produits
  ✓ diploma_feba · fond original — variante acceptée
  ✓ diploma_feba · fond neutralisé — empreinte f233b6bcfe3d5672… conforme
  ✓ diploma_feba · calibrage — tolérance 0.2 mm
  ✓ diploma_feba · rendu — 1684 Ko produits

9 contrôles passés — les documents officiels sont produisibles dès
maintenant, sans commande supplémentaire.
```

## Mesure pixel de la neutralisation

Contrôle PIXEL, pas textuel : « Nom Prénom » est **dessiné dans le fond**,
il n'existe dans aucune couche de texte. Un test qui chercherait la chaîne
passerait même avec la mention parfaitement visible.

| Image | Pixels dorés dans la zone de la mention |
|---|---|
| Original | **4 220** |
| Fond neutralisé | **0** |
| Document rendu (nom réel écrit) | **> 500** |

La mesure est bornée à la zone de la mention et exclut la règle d'écriture,
explicitement préservée : prise sur toute la largeur de la page, elle
compterait le filet doré de l'encadrement, qui doit évidemment rester.

## Confirmé dans le navigateur

```
5. Documents officiels
  ✓ aucun message ne demande de lancer « document_neutralize »
  ✓ aucun gabarit n'est bloqué faute de fond dérivé
  ✓ le diplôme est présent sur la page
  ✓ au moins un gabarit se déclare émissible
```

## Tests

`backend/tests/test_diploma_ready_after_install.py` — 16 tests couvrant les
douze étapes demandées, dont le test 7 qui vérifie que **le texte du message
reproché n'existe plus dans le code source**. Il ne suffit pas qu'il ne
s'affiche pas aujourd'hui : sans cela, il reviendrait à la première
installation incomplète.
