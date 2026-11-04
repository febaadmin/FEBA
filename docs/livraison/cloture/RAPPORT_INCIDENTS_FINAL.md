# Incidents techniques — état final

Date : 04/11/2026. Source : table `TechnicalIncident` de la production, lue sans modification (`docker exec feba_backend_prod python manage.py shell`, requêtes `SELECT` uniquement). Aucun statut n'a été changé par l'assistant ; les changements de statut restent humains (§ 4).

## 1. Inventaire complet (9 incidents en base)

| Référence | Statut | Gravité | Occur. | Première → dernière (UTC) | Erreur | Emplacement |
|---|---|---|---|---|---|---|
| ERR-310AC0 | nouveau | critique | 19 | 03/11 05:00 → 03/11 09:30 | AnomaliePlateforme « Sauvegarde plugNmeet : aucune réussite depuis plus de 26 h. » | surveillance |
| ERR-72B72D | résolu | élevée | 2 | 31/10 05:20 | AttributeError `'dict' object has no attribute 'strip'` | `DELETE /api/grades/742/`, `grades/views.py:274` |
| ERR-FF13EF | résolu | élevée | 4 | 31/10 05:18 | idem | `DELETE /api/grades/934/` |
| ERR-291699 | résolu | élevée | 6 | 31/10 05:16 → 05:17 | idem | `DELETE /api/grades/936/` |
| ERR-CBAA57 | résolu | élevée | 2 | 31/10 05:17 | idem | `DELETE /api/grades/931/` |
| ERR-A036A8 | corrigé, à valider | élevée | 4 | 24/10 18:47 | idem | `DELETE /api/grades/476/`, `grades/views.py:262` |
| ERR-5D12BE | corrigé, à valider | élevée | 4 | 24/10 11:16 → 11:20 | RelatedObjectDoesNotExist `CustomUser has no teacher_profile.` | `GET /api/auth/recipients/` |
| ERR-FC6DC7 | corrigé, à valider | élevée | 4 | 23/10 14:36 | AttributeError `'dict'…strip` | `DELETE /api/grades/192/` |
| ERR-4744E2 | corrigé, à valider | élevée | 6 | 23/10 13:28 | idem | `DELETE /api/grades/133/` |

Les captures montrent ERR-291699 comme « RelatedObjectDoesNotExist ou AttributeError ». La base indique AttributeError.

## 2. Analyse par famille

### 2.1 Suppression de note : sept incidents, une seule cause, défaut répété

- **Cause** : `mutationFn: gradesAPI.delete`. React Query appelle la fonction avec `(variables, contexte)`. Le contexte, un objet, arrivait comme 2ᵉ argument (`justification`), et le serveur appelait `.strip()` sur un dictionnaire.
- **Nature** : défaut systématique pour les suppressions faites depuis l'écran enseignant, et non ponctuel.
- **Correctif** : commit `400dd0d` du 31/10 à 18:01 UTC.
  - `mutationFn: ({ id, justification }) => gradesAPI.delete(id, justification)` ;
  - côté serveur, `text_field` renvoie 400 « Ce champ doit être un texte » au lieu d'une erreur 500.
- **Composants susceptibles du même défaut** : toutes les méthodes d'API à plusieurs paramètres passées directement à `mutationFn`. Un test de contrat (`frontend/src/api/mutationFnContract.test.js`) les recherche dans tout `src/` et échoue s'il en trouve une.
- **Tests de non-régression** :
  - `backend/tests/test_incidents_notes_destinataires.py` : suppression par un enseignant, justification non texte ;
  - le test de contrat ci-dessus.
- **Preuve en production** (lecture seule) :
  - **10 suppressions de notes par un enseignant ont réussi le 01/11**, après le correctif (`GradeHistory`, action `delete`) ;
  - aucune occurrence nouvelle depuis le 31/10 à 05:20.
- **Historique et conservation** : la suppression reste logique (`is_deleted`), avec un historique `GradeHistory` (ancienne valeur, auteur, justification). Aucune note n'a été modifiée par l'assistant.
- Les quatre incidents du 23 et 24/10 étaient déjà « corrigés » avant le 31/10, mais le défaut est réapparu (incidents du 31/10, ligne 274) : le premier correctif ne couvrait pas tous les écrans. Le correctif du 31/10 traite la cause commune.

### 2.2 ERR-5D12BE : destinataires de message d'un enseignant sans profil

- **Cause** : un compte de rôle enseignant sans fiche `Teacher` (création générique). `user.teacher_profile` levait `RelatedObjectDoesNotExist`.
- **Correctif** : `400dd0d`. Le profil absent donne une liste vide de parents ; les administrateurs restent joignables.
- **Test** : `test_incidents_notes_destinataires.py`, qui crée un compte enseignant et un compte parent sans profil.
- **Production** : aucun enseignant sans profil aujourd'hui (0, requête en lecture seule) ; aucune occurrence depuis le 24/10.

### 2.3 ERR-310AC0 : sauvegarde plugNmeet

Voir `RAPPORT_SAUVEGARDES_PLUGNMEET.md`.

- Cause : course au démarrage du conteneur MariaDB d'essai.
- Corrigé, puis vérifié par une sauvegarde réelle et une restauration isolée identique à la source.
- La surveillance ne voit plus d'anomalie.

## 3. Défauts trouvés par l'audit, sans incident enregistré

| Défaut | Pourquoi aucun incident | Correctif |
|---|---|---|
| **Celery en panne depuis le 03/11 vers 09:40 UTC** (worker 792 redémarrages, planificateur 1 444) | La surveillance elle-même tourne dans Celery. | PR #76 : kombu épinglé, contrôle en CI et au déploiement |
| Notifications des superadmins invisibles (87 non lues) | Il n'y avait pas de cloche dans l'interface superadmin. | PR #73 : cloche, et e-mail pour les incidents critiques |
| Deux dépôts FHA simultanés provoquent une erreur 500 | Défaut rare, jamais encore survenu | PR #74 : nouvelle tentative sur collision de référence |
| 63 écritures refusées sans message | Refus 4xx, non enregistrés comme incidents | PR #75 : gestionnaire d'erreur par défaut |

Impact vérifié de la panne Celery (lecture seule) :
- 0 opération de bulletins, 0 campagne, 0 relance bloquée ;
- 0 tentative d'examen échue non remise ;
- l'unique e-mail de la période est parti.

Les tâches planifiées de maintenance et de surveillance n'ont pas tourné pendant la panne.

Retour à la normale vérifié en production après le déploiement de `48a9377`, le 04/11 à 03:16 UTC :
- `kombu 5.6.2` installé ;
- worker et planificateur à 0 redémarrage ;
- `inspect ping` renvoie « 1 node online » ;
- les tâches planifiées s'exécutent (`evaluations.cloturer_echues succeeded`, `incidents.surveillance_plateforme` reçue) ;
- le contrôle Celery du déploiement est passé.

## 4. Statuts : décisions et validations humaines

Aucun statut n'a été modifié automatiquement. Proposition :

| Incident | Statut proposé | Niveaux de validation documentables | Reste à faire par un humain |
|---|---|---|---|
| ERR-310AC0 | Corrigé, à valider | développé (PR #69) ; testé automatiquement (`test_surveillance_sauvegarde.py`) ; testé localement (3/3) ; testé en production (sauvegarde et restauration isolée du 04/11) | Contrôler le lendemain qu'il n'y a pas de nouvelle occurrence (scénario du rapport de sauvegarde, § 7) |
| ERR-A036A8, ERR-FC6DC7, ERR-4744E2 | Corrigé, à valider (inchangé) | développé (`400dd0d`) ; tests ; production : 10 suppressions réussies le 01/11 | Un enseignant supprime une note avec justification depuis « Notes », puis la restaure : aucun message d'erreur, et une ligne dans « Historique » |
| ERR-5D12BE | Corrigé, à valider (inchangé) | idem (`400dd0d`) | Un enseignant ouvre « Messages », puis « Nouveau message » : la liste des destinataires s'affiche |
| ERR-72B72D, FF13EF, 291699, CBAA57 | Résolu (inchangé) | — | — |

Le passage à « Résolu » exige le niveau « Parcours réel validé par l'utilisateur concerné », que seul l'utilisateur peut fournir.
