# SECURITY_NOTES.md — Missions V4 + V6

## Saisie groupée de notes (V6, P7)

- **Autorisation décidée côté serveur uniquement.** `POST
  /api/grades/bulk-create/` est protégé par `IsAdminOrTeacher` (parent/élève →
  `403`, anonyme → `401`). Pour chaque ligne, `_validate_teacher_permission`
  vérifie que l'enseignant enseigne **cette matière** et que l'élève est dans
  **une de ses classes**. L'interface ne fait que présenter les matières
  transmises ; elle n'accorde aucun droit.
- **Anti-IDOR.** `student` et `school_year` sont résolus **filtrés par
  l'établissement** de la requête (`get_request_school`). Cibler un élève d'une
  autre école renvoie « Élève introuvable » (jamais la note). Test dédié
  `test_teacher_cannot_target_other_school_student_idor`.
- **Atomicité.** Écriture dans `transaction.atomic()` seulement si **aucune**
  ligne n'est en erreur → pas d'écriture partielle silencieuse exploitable.
- **Pas de fuite d'appréciation/logique.** L'appréciation est calculée par le
  backend ; l'aperçu client est purement cosmétique.
- **Journalisation.** Chaque note créée passe par `_log_grade` (traçabilité,
  comme la saisie simple).

## Réinitialisation de mot de passe par administrateur (P2)

- **Contrôle d'accès côté backend uniquement décisif** :
  `CustomUser.can_reset_password_of()` est évalué dans la vue pour CHAQUE
  appel — l'interface ne fait que masquer les actions non autorisées.
  - Admin → enseignant / parent / élève **de son établissement** ;
  - Superadmin → admin / enseignant / parent / élève ;
  - Personne ne réinitialise un superadmin ni son propre compte via cet
    endpoint (parcours « changer mon mot de passe » distinct, avec ancien
    mot de passe exigé).
  - Contournement par ID direct (ex. admin qui poste l'ID d'un superadmin
    ou d'un utilisateur d'un autre établissement) → **403**, vérifié par
    tests et en conditions réelles.
- **Aucun secret ne circule ni ne persiste en clair** : hachage par
  `set_password` (PBKDF2 Django en production), le mot de passe n'apparaît
  ni dans les réponses API, ni dans les logs, ni dans `PasswordResetLog`.
- **Journal d'audit** (`PasswordResetLog`) : auteur (FK + copie e-mail),
  cible, rôle, établissement, horodatage. Créé uniquement en cas de
  succès ; les tentatives refusées sont tracées dans le log applicatif.
- **Sessions** : tous les refresh tokens de la cible sont blacklistés
  (`rest_framework_simplejwt.token_blacklist`). L'ancien mot de passe est
  refusé immédiatement au login ; un access token déjà émis expire sous
  60 min max (configurable). L'administrateur auteur n'est pas déconnecté.
- **Anti-abus** : rate-limit 10 requêtes/min par utilisateur sur
  l'endpoint ; le login public reste limité à 20/min par IP.
- **Mot de passe temporaire** (solution A du cahier des charges) : saisi
  par l'administrateur, soumis aux validateurs Django standard appliqués
  au **profil de la cible** (longueur, similarité avec ses informations,
  mots de passe courants, non-numérique). `must_change_password` force la
  cible à choisir son propre mot de passe à la connexion suivante — le
  routeur frontend bloque tous les espaces tant que le drapeau est levé.

## Site vitrine public (P4)

- **Cloisonnement** : le site public utilise une instance HTTP dédiée sans
  jeton (`src/site/siteApi.js`) — aucune fuite d'en-tête d'authentification
  vers les endpoints publics, aucun intercepteur ERP déclenché pour un
  visiteur anonyme.
- **Lecture publique minimale** : seuls paramètres d'affichage, slides,
  actualités publiées, galerie. Les soumissions (messages, préinscriptions)
  ne sont **jamais** exposées par l'API publique (lecture réservée
  admin/superadmin, testée anonyme → 401 et parent → 403).
- **Formulaires** : validation backend systématique (champs obligatoires,
  format e-mail, âge 1–18, niveau dans la liste), honeypot invisible
  (champ `website` rempli → 400), rate-limit 5/min/IP par formulaire.
  Côté admin, les champs saisis par les familles sont en lecture seule
  (seuls `is_read`/`status` sont modifiables) — pas de falsification des
  demandes.
- **CSRF** : API DRF authentifiée par JWT (pas de cookie de session) ; les
  deux POST publics sont sans état, sans cookie et protégés par
  rate-limit + honeypot. L'admin Django classique conserve la protection
  CSRF de Django.
- **Uploads CMS** : `ImageField` (validation d'image Pillow) stocké sous
  `MEDIA_ROOT/website/` ; les médias packagés du site sont des fichiers
  statiques versionnés, sans métadonnées sensibles (conversion Pillow).
- **SEO/robots** : les espaces privés (`/login`, `/admin/`, `/parent/`,
  etc.) sont exclus de l'indexation via `robots.txt`.

## Divers

- Les identifiants de démonstration (`seed_demo_data`) sont réservés aux
  environnements de dev/démo — ne jamais exécuter ce seed en production.
- `.env.example` ne contient aucun secret réel ; `SECRET_KEY`, base de
  données et identifiants Jitsi doivent être fournis par environnement.
- Migrations V4 non destructives : `accounts/0005` (ajout de champ +
  table d'audit), `grades/0010` (choices), `website/0001` (nouvelles
  tables), `bulletins/0005` (donnée recalculée, réversible, la moyenne
  source est préservée).
