# SECURITY_NOTES.md — Missions V4 → V8
## V9-bis

### Une fuite d'information corrigée

Un identifiant de gabarit inconnu renvoyait au navigateur
« Gabarit « None » introuvable (/home/…/backend/document_templates/
None_template.json) ». Cette erreur est une erreur de SAISIE (400), donc
transmise telle quelle au client par le gestionnaire d'exceptions : elle
offrait l'arborescence du serveur à qui poste un identifiant au hasard.

Le chemin ne sort plus. La liste des gabarits disponibles reste — elle
est déjà publiée par `/api/documents/templates/`.

Trouvé en produisant un document depuis le navigateur, pas en lisant le
code.

### Anti-IDOR, vérifié dans un navigateur réel

Six sondes, avec les identifiants de session de chaque administrateur :

| Sonde | Attendu | Obtenu |
|---|---|---|
| Fiche d'un document d'une autre académie | 404 | 404 |
| PDF d'un document d'une autre académie | 404 | 404 |
| Liste d'élèves d'une autre académie demandée explicitement | portée inchangée | portée inchangée |

**404 et non 403** : répondre « interdit » confirmerait que le dossier
existe.

### Une orientation corrigée, qui n'était pas une faille

`RoleRedirect` déposait dans l'espace élève un utilisateur dont le rôle
n'était pas encore chargé. Le serveur continuait de refuser tout ce que
ce compte n'avait pas le droit de lire, et l'espace élève s'affichait
vide — aucune donnée n'a pu fuir. Mais un écran qui dit à un
administrateur qu'il est un élève est un écran auquel on ne peut plus se
fier pour juger de ses droits.

### Le limiteur de débit tombé : 503, plus 500

Le limiteur de `/api/auth/login/` compte dans le cache Redis. Redis
indisponible, l'exception remontait au gestionnaire d'exceptions et
devenait un **500 « Une erreur interne est survenue »**.

Refuser était la bonne décision — c'est le message qui était faux. Un 500
dit « l'application a un défaut », alors que l'application va bien et
qu'une dépendance d'infrastructure est absente. L'utilisateur rappelle
son école, l'école appelle l'éditeur, l'éditeur cherche un bug qui
n'existe pas, et personne ne redémarre Redis.

**On reste fermé.** La tentation, quand le compteur ne répond plus, est
de laisser passer : le service reste debout et personne ne se plaint.
C'est exactement ce qu'il ne faut pas faire. Ce limiteur est ce qui
sépare une base de comptes d'une attaque par force brute ; le désactiver
parce qu'un cache est tombé revient à ouvrir la porte au moment précis où
l'on ne peut plus compter les visiteurs.

La réponse est désormais :

| Élément | Valeur |
|---|---|
| Statut | **503 Service Unavailable** |
| `Retry-After` | 30 s, en en-tête et dans le corps |
| Message | clair, dans la langue négociée (FR/EN) |
| `service` | `cache` — nommé, sans adresse ni version |
| `incident_reference` | référence de l'incident ouvert |
| Jeton délivré | **aucun** |

Vérifié en conditions réelles, Redis réellement arrêté :

```
HTTP/1.1 503 Service Unavailable
Retry-After: 30
{"detail":"Le service d'authentification est temporairement
indisponible. …","service":"cache","retry_after":30,
"incident_reference":"ERR-4C707E"}
```

L'incident est enregistré avec `module=ratelimit`, `status_code=503`,
`severity=high` et le chemin tenté ; il apparaît dans l'écran des
incidents techniques du super administrateur. Redis relancé, la connexion
repasse à 200 sans intervention.

**Seul l'appel au compteur est protégé.** La vue s'exécute sans filet :
un défaut dans la connexion elle-même continue de sortir en 500 avec son
incident. Entourer la vue entière transformerait n'importe quel bug en
« service temporairement indisponible » — le genre de message rassurant
derrière lequel un défaut réel vit très longtemps.

Treize tests (`tests/test_ratelimit_degrade.py`) tiennent les deux
situations ; les treize échouent contre l'ancien code.

Ils ont aussi révélé que `RATELIMIT_ENABLE = False` dans les réglages de
test : le limiteur n'était éprouvé par **aucun** test, ni son comptage ni
son comportement en panne. Ces tests le rallument, et eux seuls.

---

## V8 (26/07/2026)

### Faille corrigée : cloisonnement multi-établissement inopérant

Le filtrage par établissement des champs DRF `many=True` ne s'appliquait pas :

```python
self.fields["subject_ids"].queryset = Subject.objects.filter(school=school)  # sans effet
```

Pour un `PrimaryKeyRelatedField(many=True)`, DRF enveloppe le champ dans un
`ManyRelatedField` : la validation lit **`child_relation.queryset`**, jamais
celui de l'enveloppe. Un administrateur pouvait donc rattacher à un enseignant
des **matières et classes d'un AUTRE établissement**. Corrigé et couvert par un
test dédié. À auditer partout où ce motif est utilisé.

### Incidents techniques : aucune donnée sensible enregistrée

Sanitisation centrale (`sanitize_text` / `sanitize_data`), appliquée
**récursivement** : mots de passe, jetons, `Authorization: Bearer <jwt>`, JWT
nus, cookies, clés d'API, secrets, numéros de carte → `[expurgé]`.
Vérifié en conditions réelles (4 secrets injectés, 4 expurgés).
Aucun **traceback** ni détail interne n'est renvoyé au client : seule une
référence `ERR-XXXXXX` non devinable est communiquée.

Accès aux incidents : **super administrateur uniquement** (admin → 403,
enseignant/parent/élève → 403, anonyme → 401). Les données techniques sont
**immuables** ; seuls statut, gravité, assignation et notes sont modifiables ;
la création manuelle est refusée.

### Intégrité des données

Création de profil **atomique** (`transaction.atomic`) : aucun profil partiel,
aucune relation orpheline après échec. Les erreurs d'intégrité sont traduites
en **400 exploitables** — plus de 500 exposant l'état interne.


## V7 (25/07/2026)
- Précision des notes : la valeur saisie n'est jamais transformée en silence ; aucune règle
  cachée (`if score==10`), aucun arrondi d'affichage masquant la base. Backend = source de vérité
  (DecimalField, validation 0..20). Permissions de saisie inchangées (enseignant→ses matières,
  anti-IDOR de V6 conservé).
- Cachet : fichier statique packagé, apposé côté serveur sur les PDF ; aucune donnée sensible
  exposée. Noms officiels centralisés (branding.py).


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
