# Rapport de clôture — V9

Ce rapport distingue **où** chaque chose a été vérifiée. C'est la seule
distinction qui compte : cinq défauts de cette itération n'apparaissaient
pas dans le dépôt source, seulement depuis l'archive extraite.

---

## Ce qui est testé, et où

| Vérification | Dépôt source | Archive extraite | SQLite | PostgreSQL | Navigateur | Vu à l'œil |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Suites backend | ✅ 806 | ✅ 806 | ✅ 805+1 | ✅ 806 | — | — |
| Suites frontend | ✅ 123 | ✅ 123 | — | — | — | — |
| ESLint / build | ✅ 0 erreur | ✅ 0 erreur | — | — | — | — |
| Installation propre | — | ✅ venv neuf, base vide | — | ✅ 0→69 tables | — | — |
| Diplôme produisible | ✅ | ✅ sans commande | — | ✅ | ✅ | ✅ capture |
| Certificat produisible | ✅ | ✅ | — | ✅ | ✅ | ✅ capture |
| Neutralisation du placeholder | ✅ | ✅ 4220→0 px | — | — | — | ✅ PDF |
| Identité par académie | ✅ | ✅ 7 documents | — | ✅ | ✅ | ✅ PDF |
| Inscription FEBA FHA | ✅ 43 tests | ✅ bout en bout | ✅ | ✅ SQL direct | ✅ | ✅ capture |
| Fiche PDF + téléchargement | ✅ | ✅ | — | ✅ | ✅ | ✅ PDF |
| Contacts + WhatsApp | ✅ 16 tests | ✅ 2 académies | ✅ | ✅ SQL direct | ✅ | ✅ capture |
| Messages longs non coupés | ✅ 14 tests | ✅ | — | ✅ 6300/6300 car. | ✅ 1011/1011 | ✅ capture |
| Isolation + anti-IDOR | ✅ | ✅ | ✅ | ✅ | — | ✅ preuve |
| Stockage privé | ✅ | ✅ | — | ✅ | — | — |
| Contrôle des secrets | ✅ garde-fou | ✅ ZIP analysé | — | — | — | — |

---

## E-mails : ce qui s'est réellement passé

Le brief demande de distinguer cinq états. Voici lequel s'applique.

| État | S'applique ? | Détail |
|---|:-:|---|
| Capturé par un backend local | **OUI** | `django.core.mail.backends.console.EmailBackend` |
| Mis en file | non | Aucune file n'a été employée |
| Simulé | non | Les messages sont réellement composés et remis au backend |
| Accepté par un fournisseur externe | **NON** | Aucun fournisseur configuré |
| Réellement distribué | **NON** | Impossible à affirmer sans fournisseur |

Le journal `EmailDelivery` porte `status = sent` et
`backend = console.EmailBackend`. Le drapeau `used_real_provider` vaut
**faux**, et l'interface affiche « Sans fournisseur » — jamais « Envoyé ».
`manage.py email_check` sort en erreur dans cet état, exprès.

Un fichier HTML a bien été produit pour chaque message. **Cela ne vaut pas
envoi**, et rien dans cette livraison ne le présente comme tel.

---

## Les cinq défauts trouvés en validant l'archive

Aucun n'était visible depuis le dépôt source.

**1. La livraison partait avec les rapports de l'itération précédente.**
La liste était figée sur V8. L'archive V9 ne contenait aucun des douze
rapports écrits pour elle. Corrigé par une liste vérifiée : un rapport
annoncé mais absent interrompt la construction.

**2. La règle d'académie ne tenait que dans la vue HTTP.** Produire un
diplôme au fond FEBA pour un élève de l'académie en ligne était refusé par
l'API et **accepté par le service**. Une commande, un script d'import ou un
test produisait donc un document au nom d'une académie et à l'effigie
d'une autre. Une règle posée à la porte d'entrée HTTP n'est pas une règle.

**3. L'adresse imprimée se répétait.** `Akpakpa, Cotonou, Bénin, Cotonou,
Bénin` en tête de chaque reçu — et, pour l'académie en ligne, une ville qui
n'est pas la sienne affichée deux fois sur ses propres documents.

**4. Deux caractères disparaissaient de chaque message long.** DRF retire
les blancs de fin par défaut. Un message de 7 014 caractères arrivait à
7 012. Deux caractères — mais c'est la même mécanique qui modifie ce que le
visiteur a écrit, pendant que l'application affirme ne rien tronquer.

**5. Un fichier d'environnement réel partait dans chaque archive.**
`.env.dev` contenait une `SECRET_KEY` et un `JITSI_APP_SECRET`. Des secrets
faibles restent des secrets : livrés, ils deviennent les secrets par défaut
de toute installation qui recopie le fichier sans le lire.

Chacun a reçu un test de non-régression. L'archive a été régénérée et
réinstallée depuis zéro après chaque correction — **quatre tours de
boucle**.

---

## Non validé faute d'identifiants externes

| Sujet | Ce qui manque | Ce qui a été fait malgré tout |
|---|---|---|
| Envoi d'e-mail réel | Un fournisseur SMTP et ses identifiants | Composition, formats, langues, pièces jointes, journal, états d'échec, relance — et un refus explicite de présenter un envoi comme réel |
| Paiement par carte | Des clés Stripe valides | 54 tests couvrant tentative, webhook, idempotence, ordre, remboursement, reçu, permissions ; signature vérifiée par la bibliothèque officielle, sans réseau |

---

## Limitations réelles restantes

**Aucune signature officielle n'est fournie.** Les zones
`director_signature` restent vides. Le moteur ne dessine, ne reconstitue et
n'approche jamais une signature : une signature inventée sur un diplôme
n'est pas une approximation graphique, c'est un faux.

**L'académie en ligne n'a pas de fond de diplôme ni de certificat.** Les
deux gabarits sont réservés à FEBA et l'interface le dit, avec sa raison.
Le jour où le fond est fourni, il fera l'objet d'un gabarit distinct.

**Ni téléphone ni e-mail ne sont renseignés pour les deux académies.** Les
documents ne les affichent donc pas. C'est une donnée que l'établissement
doit saisir, pas un défaut de code — et les inventer serait pire.

**Les fonds installés ne sont pas les PNG d'origine** : variantes
transcodées, acceptées nommément et tracées. Géométrie exacte, calibrage
valide.

**Les libellés d'état des dossiers FHA restent en français** sur une
session anglaise. Défaut d'affichage seulement : l'état stocké et transmis
est le code interne.

**L'interface charge une police depuis `fonts.googleapis.com`.** Injoignable
derrière le proxy de ce conteneur, elle retombe sur la police système sans
rien casser. À signaler pour un déploiement hors ligne, et parce que chaque
visiteur est alors vu par un tiers.

**Redis doit tourner.** `django-ratelimit` et l'authentification passent par
le cache ; sans lui, le formulaire public et la connexion renvoient 500.
Documenté dans `INSTALLATION_GUIDE.md` et démarré par `make dev`.

---

## Détail par priorité

| | Sujet | État |
|---|---|---|
| P0 | Source unique d'identité par académie | Corrigé et vérifié |
| P1 | Inscription FEBA FHA de bout en bout | Corrigé et vérifié |
| P2 | Audit de la chaîne des champs | Corrigé et vérifié |
| P3 | Fiche PDF + téléchargement sécurisé | Corrigé et vérifié |
| P4 | Vue détail complète + export | Corrigé et vérifié |
| P5 | Formulaires de contact | Corrigé et vérifié |
| P6 | Messages longs jamais tronqués | Corrigé et vérifié |
| P7 | Diplôme disponible dès l'installation | Corrigé et vérifié |
| P8 | Documents filtrés par académie | Corrigé et vérifié |
| P9 | Tests automatisés | 806 backend, 123 frontend |
| P10 | Vérification navigateur | 34 vérifications, depuis l'archive |
| P11 | Audit global | 5 défauts trouvés et corrigés |

« Corrigé et vérifié » signifie : exécuté sur cette instance, depuis
l'archive extraite, avec la sortie reproduite dans `TEST_REPORT.md`.
