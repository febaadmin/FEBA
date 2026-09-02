# KNOWN_LIMITATIONS — ce qui n'a pas été vérifié

Ce document est délibérément explicite. Un rapport qui tait ses angles
morts est plus dangereux qu'un rapport incomplet.

---

## 1. Ce qui n'a pas pu être fait depuis le dépôt

La visioconférence de production **n'est pas en service**, et rien dans
cette livraison ne peut la mettre en service.

Vérifié au moment de la livraison :

```
getent hosts globalfeba.com        → 62.238.38.111        ✅
getent hosts meet.globalfeba.com   → aucun enregistrement ❌
```

Le code, la configuration, la surcouche Docker de production, les scripts
d'exploitation et les contrôles de santé sont livrés et testés. Ce qui
manque relève de **Hetzner** (créer le serveur, ouvrir `10000/udp`) et de
**Hostinger** (créer l'enregistrement `A meet`). Ces actions sont
détaillées, avec leurs commandes de vérification, dans
[`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md).

**Aucune de ces actions n'a été effectuée, et aucune n'est présentée comme
faite.** Tant qu'elles ne le sont pas, l'application affiche le bandeau
« Visioconférence indisponible — instance FEBA non configurée ». C'est le
comportement voulu : aucune session n'est basculée vers un service public.

## 2. Cachet officiel de FEBA French Heritage Academy

**Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet d'une autre
académie n'est réutilisé.**

Les documents de l'académie en ligne — reçus, certificats, fiches —
sortent donc **sans cachet**. Ce n'est pas un oubli et ce n'est pas
réparable en écrivant du code : le visuel n'existe pas dans les éléments
transmis.

Apposer `cachet_feba.png` à la place serait pire que l'absence : cette
image porte en couronne « COMPLEXE SCOLAIRE FAITH & EXCELLENCE BILINGUAL
ACADEMY ». Sur un certificat de l'académie en ligne, elle y estampille le
nom d'une autre personne morale — sur la pièce qui fait foi. Un document
sans cachet se voit et se corrige ; un document au cachet d'un autre
établissement circule et fait autorité.

**Pour lever cette limitation :** déposer le cachet officiel FHA dans
`backend/feba_project/static_files/` et renseigner son nom dans
`ACADEMY_DEFAULTS["FEBA_FHA"]["stamp"]`
(`backend/apps/schools/branding.py`). Rien d'autre n'est à modifier.

## 3. Nom d'établissement sur deux lignes — limitation levée

Cette limitation figurait dans les livraisons précédentes. Elle **est
levée** : un nom d'établissement de **79 caractères est composé sur deux
lignes** sans chevauchement ni troncature, l'interligne étant calculé à
partir de la taille de police au lieu d'être laissé à sa valeur par défaut
(`backend/apps/payments/pdf_generator.py`).

Elle est maintenue dans ce document uniquement pour dire qu'elle n'a plus
lieu d'être : la laisser inscrite ferait renoncer quelqu'un à un service
qui fonctionne.

## 4. Portée des vérifications de cette livraison

### Ce qui a été réellement exécuté

| Vérification | Résultat |
|---|---|
| Suite backend PostgreSQL 16 | 1 164 passés, 0 échec |
| Suite backend SQLite | 1 163 passés, 1 ignoré, 0 échec |
| Suite frontend (Vitest) | 185 passés (179 dans la source + 6 ajoutés) |
| ESLint | 0 erreur, 81 avertissements préexistants |
| Build frontend de production | PASS |
| Parcours navigateur 1 à 5 (Chromium réel) | PASS |
| `nginx -t` sur les deux configurations | PASS |
| Migrations + `seed_demo_data` sur PostgreSQL vierge | PASS |

### Ce qui n'a PAS été exécuté

- **Docker Compose.** Aucun démon Docker n'était disponible dans
  l'environnement de travail. `make install`, `make jitsi-up`,
  `make jitsi-prod-up`, `docker compose up` n'ont donc pas été lancés. Les
  fichiers Compose ont été validés syntaxiquement (analyse YAML) et les
  configurations Nginx par `nginx -t` sur un binaire réel, mais **la pile
  n'a jamais démarré en conteneurs**.
- **Un appel Jitsi réel.** Il faut l'infrastructure de la section 1. Le
  jeton, les permissions, le refus des instances publiques et le rapport
  de santé sont testés ; **le passage effectif de l'audio et de la vidéo ne
  l'est pas** et ne peut l'être sans serveur.
- **Un envoi d'e-mail réel.** Les tests utilisent le backend en mémoire.
  Aucun message n'est parti vers une boîte réelle : la configuration SMTP
  de production reste à valider sur le serveur.
- **Les 13 fichiers de tests e2e existants** (`e2e/*.mjs`) : ils supposent
  la pile Docker complète. Les cinq parcours de cette livraison ont été
  écrits et exécutés séparément, contre le build de production servi par
  Nginx et un backend Django réel sur PostgreSQL.

## 5. Ce que le correctif du numéro institutionnel ne couvre pas

Le numéro `0160011717` est imposé à **tous les documents générés**, via
`apps/schools/institution.py`. Deux réserves :

- **Les documents déjà émis ne sont pas modifiés.** Un reçu remis à une
  famille avant cette livraison porte toujours l'ancien numéro. Les
  régénérer est possible (bouton « générer le reçu ») mais n'a pas été
  fait en masse : cela changerait la date de génération inscrite sur des
  pièces déjà en circulation.
- **Les fonds d'image des certificats et diplômes ne sont pas analysés.**
  Ces documents sont composés sur un visuel fourni par l'établissement. Si
  un numéro y est incrusté en pixels, aucun test textuel ne peut le voir —
  c'est précisément ainsi que trois fuites d'identité ont échappé aux
  contrôles lors de livraisons précédentes. Les gabarits actuels n'ont
  **aucun champ téléphone**, et les tests vérifient l'absence de l'ancien
  numéro dans leur texte ; l'inspection visuelle des fonds reste à faire.
- **Le flyer FEBA FHA n'a pas été retouché.** Il porte le contact WhatsApp
  `+1 (215) 715-5406` et `www.globalfeba.com` — les coordonnées voulues
  pour la diaspora. Ce n'est pas un document généré par l'application mais
  une pièce marketing fournie ; son contenu n'a pas été modifié.

## 6. Avertissements de lint non traités

81 avertissements ESLint préexistants subsistent (0 erreur). Ils n'ont pas
été traités : ce sont des `no-unused-vars` et des règles React Hooks sur
du code qui n'entre pas dans le périmètre de cette mission. Un seul a été
corrigé, dans un fichier déjà modifié pour le flyer (`FhaPage.jsx`).

## 7. Audit de sécurité — profondeur réelle

L'audit a porté sur : cloisonnement inter-académies (vérifié en navigateur,
y compris par manipulation directe d'identifiants), réglages de production
(`CSRF_TRUSTED_ORIGINS` manquant — corrigé), contrôle d'accès aux salles
virtuelles, absence de valeurs institutionnelles en dur, et secrets absents
du dépôt.

**N'ont pas été menés :** revue ligne à ligne des permissions objet de
chaque endpoint, test d'intrusion, analyse des dépendances
(`pip-audit` / `npm audit`), revue des téléversements de fichiers au-delà
de la vérification de type MIME déjà en place.

## 8. Nommage de l'archive

L'archive source s'appelle `feba.zip` et son dossier racine
`feba_v6_version_finale_corrigee`, alors que le dépôt contient des rapports
`KNOWN_LIMITATIONS_V4` à `V9`. Le versionnage interne du projet a dépassé
« V6 ». Le nom du dossier source a été conservé sans modification pour
éviter toute ambiguïté sur ce qui a été livré.
