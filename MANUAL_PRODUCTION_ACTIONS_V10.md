# FEBA — Actions humaines requises (V10)

Ce que le code ne peut pas faire seul. Aucune de ces actions n'a été
exécutée : conformément aux consignes, **rien n'a été déployé**.

---

## 1. Avant tout déploiement

### 1.1 Sauvegarder la base de production

La livraison contient **trois migrations** :

| Migration | Effet | Réversible |
|---|---|---|
| `schools.0016_activate_orphan_school_years` | active l'année la plus récente des académies qui en ont une sans qu'aucune soit active | oui (aucune donnée supprimée) |
| `classes.0003_class_language_track` | ajoute `language_track`, défaut `BILINGUAL` | oui |
| `virtualclass.0003_virtualroom_target_roles` | ajoute `target_roles`, défaut `[]` | oui |

Aucune ne supprime ni ne réécrit de donnée existante.
`schools.0016` **ne touche pas** aux académies qui ont déjà une année
active.

**Action :** `scripts/backup_database.sh` avant `migrate`.

### 1.2 Vérifier l'effet de `schools.0016` en pré-production

Cette migration change l'année de travail d'une académie mal configurée.
C'est l'effet voulu — mais c'est un changement visible pour les
utilisateurs.

**Action :** exécuter la migration sur une copie de la base de
production, et vérifier quelle académie est modifiée et vers quelle année.

---

## 2. Visioconférence

### 2.1 Secrets Jitsi

`JITSI_APP_ID` et `JITSI_APP_SECRET` doivent exister côté serveur, et
**uniquement là**. Sans eux, le backend répond 503 et refuse de servir une
salle non protégée — c'est le comportement voulu, pas une panne à
contourner.

**Action :** confirmer que les secrets de production sont posés dans
l'environnement du backend **et** dans celui de la pile Jitsi, avec la
**même** valeur.

> Aucun secret réel n'est présent dans le dépôt. Le `.env` de
> développement est ignoré par git (vérifié).

### 2.2 Vérifier que l'adhésion anonyme est refusée

**Action :** ouvrir `https://meet.globalfeba.com/salle-test-xyz` dans un
navigateur, sans passer par FEBA. L'accès doit être **refusé**.

Si une salle s'ouvre, l'authentification JWT n'est pas active sur
l'instance en service, et **n'importe qui sur Internet peut créer des
salles sur votre serveur**.

### 2.3 Identifier le proxy en service

Les en-têtes de `meet.globalfeba.com` ne correspondent pas au fichier
nginx du dépôt (voir `KNOWN_LIMITATIONS_V10.md` §3).

**Action :** déterminer quelle configuration sert réellement le domaine,
et décider si elle doit être alignée.

### 2.4 Renouvellement du certificat

Le certificat expire le **2026-12-02**.

**Action :** confirmer que le renouvellement ACME est en place.

### 2.5 Ports Jitsi

**Action :** vérifier que `10000/udp` (JVB) est ouvert et joignable depuis
l'extérieur. Sans lui, les participants entrent dans la salle et ne se
voient pas.

---

## 3. Après déploiement — vérifications à faire soi-même

| # | Vérification | Attendu |
|---|---|---|
| 1 | Connexion administrateur FEBA FHA | tableau de bord |
| 2 | Salles virtuelles → Nouvelle salle | le menu « Classe » propose les classes FHA |
| 3 | Enseignants → Nouvel enseignant | « Classes assignées » propose des classes |
| 4 | Paramètres | « Salles physiques de l'école » > 0 |
| 5 | Classes → Nouvelle classe | « Parcours linguistique » présent |
| 6 | Classe francophone → Matières | aucun reproche sur les matières anglaises |
| 7 | Bulletin d'une classe francophone | aucune partie anglaise vide |
| 8 | Salles virtuelles → Rejoindre | **un nouvel onglet** s'ouvre, plein écran |
| 9 | Réunion à 2 participants | les deux se voient et s'entendent |
| 10 | Réunion de 30 minutes | aucune reconnexion spontanée |
| 11 | **FEBA** : classes, notes, bulletins | inchangés |

Les points 9 et 10 sont ceux que l'environnement de développement **ne
peut pas** trancher.

---

## 4. Ce qui n'a pas été fait, volontairement

- aucun push vers une branche autre que la branche de développement
  désignée ;
- aucun merge vers `main` ;
- aucun déploiement Hetzner ;
- aucune migration sur la base de production ;
- aucune modification DNS ;
- aucune ouverture de pare-feu ;
- aucun démarrage de l'instance Jitsi de production ;
- aucun secret réel ajouté au dépôt.
