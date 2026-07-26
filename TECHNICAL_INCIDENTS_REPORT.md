# TECHNICAL_INCIDENTS_REPORT.md — Remontée des erreurs techniques (V8-P3)

## 1. Le problème : une promesse creuse

L'interface affichait, sur toute erreur serveur :

> « Erreur interne du serveur. **L'équipe technique a été notifiée.** »

Or **aucune** notification n'était créée, **aucune** trace n'était consultable
et **aucun** super administrateur ne recevait quoi que ce soit. L'affirmation
était trompeuse — elle a été supprimée.

## 2. Ce qui a été construit

Nouvelle application `apps/incidents`.

### Modèle `TechnicalIncident`

| Catégorie | Champs |
|---|---|
| Identification | `reference` (**ERR-XXXXXX**, unique), `created_at`, `environment` |
| Classement | `severity` (Faible/Moyenne/Élevée/Critique), `status` (Nouveau/En cours/Résolu/Ignoré/Réouvert) |
| Localisation | `module`, `frontend_route`, `endpoint`, `http_method`, `status_code`, `exception_type`, `location` (fichier:ligne (fonction)) |
| Contexte | `message` (nettoyé), `user`, `user_role`, `school`, `attempted_action`, `context_data`, `user_agent`, `app_version`, `release` |
| Dédoublonnage | `fingerprint`, `occurrences`, `first_seen_at`, `last_seen_at` |
| Traitement | `assigned_to`, `resolution_notes`, `resolved_at` |

### Capture

Gestionnaire d'exceptions DRF (`EXCEPTION_HANDLER`) :

- **erreurs 500 / exceptions non gérées** → incident créé ;
- **erreurs métier (400/403/404…)** → **aucun** incident (la table ne doit pas
  être noyée sous les erreurs de saisie) ;
- **aucun traceback** ni détail interne renvoyé au client.

### Dédoublonnage

Empreinte = `type d'exception + endpoint + module + ligne + message normalisé`
(les nombres variables sont neutralisés : « id 42 » ≡ « id 77 »).

Une erreur qui se répète **incrémente `occurrences`** et met à jour
`last_seen_at` au lieu de créer un nouvel incident. Renotification uniquement
aux paliers **1, 5, 25, 100, 500** — la cloche des super administrateurs n'est
jamais saturée.

## 3. Sanitisation (données interdites)

Fonction centrale `sanitize_text` / `sanitize_data` :

| Type | Traitement |
|---|---|
| `password`, `token`, `access`, `refresh`, `cookie`, `session`, `secret`, `api_key`, `card`, `cvv`, `iban`… | valeur remplacée par `[expurgé]` |
| En-tête `Authorization: Bearer <jwt>` | jeton expurgé |
| JWT nu (`eyJ….….…`) | expurgé |
| Numéro type carte bancaire (13–19 chiffres) | expurgé |
| Structures imbriquées (dict/list) | nettoyage **récursif** |

> **Gap corrigé pendant les tests** : l'ordre des motifs laissait le JWT en
> clair après `Authorization: Bearer` (le motif générique « clé=valeur »
> consommait seulement le mot « Bearer »). Les motifs spécifiques passent
> désormais **avant** le motif générique.

## 4. Notification réelle des super administrateurs

Chaque incident nouveau (ou atteignant un palier) crée une `Notification`
interne pour **chaque** super administrateur actif, avec :

```
titre       : « Incident technique ERR-XXXXXX »
related_url : /superadmin/incidents/<id>     ← ouvre l'INCIDENT, pas les Annonces
```

`notify_superadmins()` renvoie le nombre de notifications **réellement**
créées (0 s'il n'existe aucun super administrateur).

## 5. Message utilisateur honnête

| Situation | Message |
|---|---|
| Incident enregistré | « Une erreur interne est survenue. L'incident a été transmis à l'équipe technique sous la référence **ERR-XXXXXX**. » |
| Enregistrement impossible | « Une erreur interne est survenue. Veuillez réessayer ou contacter l'assistance. » |

Le frontend n'affiche la référence que si le backend l'a **réellement**
renvoyée (`incident_reference`) — plus aucune promesse non vérifiable.

## 6. Interface super administrateur

Page **« Incidents techniques »** (`/superadmin/incidents`) : compteurs
(nouveaux / en cours / résolus / total), filtres statut et gravité, recherche
(référence, message, endpoint), liste paginée, détail complet (contexte
expurgé), assignation, note interne, changement de statut, **résolution** et
**réouverture**.

### Permissions

| Rôle | Accès |
|---|---|
| Super administrateur | complet |
| Administrateur | **aucun** (403) |
| Enseignant / Parent / Élève | **aucun** (403) |
| Anonyme | 401 |

Les données techniques sont **immuables** (seuls statut, gravité, assignation
et notes sont modifiables) ; la création manuelle d'un incident est refusée
(405) — un incident se constate, il ne se saisit pas.

## 7. Preuves (`tests/test_technical_incidents.py`, 18 cas)

| Test | Vérifie |
|---|---|
| Erreur 500 **réelle** (vue de test qui lève une exception) | incident créé, référence `ERR-…` renvoyée, notification super admin, `related_url` vers l'incident, **aucun traceback exposé** |
| Erreur métier | **aucun** incident créé |
| Répétition ×3 | 1 seul incident, `occurrences = 3`, **1 seule** notification |
| Sanitisation | mot de passe, JWT, Bearer, carte bancaire, clés imbriquées → `[expurgé]` |
| Empreinte | insensible aux nombres variables |
| 0 / 1 / N super admins | incident créé même sans super admin ; tous notifiés sinon |
| Permissions | admin, enseignant → 403 ; anonyme → 401 |
| Traitement | statut, note, assignation, résolution, réouverture, champs techniques non modifiables |

## 8. Système externe

Aucun service externe (type Sentry) n'est configuré dans ce projet : le
système interne fonctionne **seul**. S'il en était ajouté un, il s'intégrerait
dans `report_incident()` sans remplacer l'interface interne.
