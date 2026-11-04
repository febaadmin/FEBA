# Suivi et point de reprise (04/11/2026)

Ce fichier dit exactement où en est le travail, pour une reprise sans perte.

## PR de la phase 3

| PR | Objet | État au moment de l'écriture |
|---|---|---|
| #69 | Sauvegarde plugNmeet : restauration d'essai fiable (ERR-310AC0) | fusionnée ; script installé sur le serveur vidéo le 04/11 à 02:03 UTC |
| #70 | Réinitialisation du mot de passe superadmin ; logo de /login | fusionnée, déployée (`f3e30de`) |
| #71 | Identifiant d'image déterministe (nginx conservé) | fusionnée |
| #72 | Centre d'aide (52 articles, bilingue, par profil) | fusionnée |
| #73 | Cloche superadmin ; e-mail des incidents critiques | fusionnée |
| #74 | Dossiers FHA simultanés ; surveillance testée ; `server_tokens off` | fusionnée |
| #75 | Écritures refusées : motif toujours affiché | fusionnée, déployée (`48a9377`) |
| #76 | URGENT : Celery en panne (kombu 5.7.0) | fusionnée, déployée (`48a9377`) ; Celery vérifié en production |
| #77 | Une seule coupure nginx quand sa configuration change | fusionnée (`935b1ca`) |
| #78 | Dossier de clôture | fusionnée |
| #79 | Rapport de l'archive finale | fusionnée |
| #80 à #85 | Phase 4 : graphique des paiements, aide, notifications, API sans erreur 500, N+1, E2E | fusionnées, déployées (`4b8b165`) ; voir `RAPPORT_PHASE4.md` |

Vérifier l'état réel avec `gh pr list --state all -L 12` : ce tableau peut être en retard.

## Actions qui nécessitent un humain

1. **Root sur le serveur FEBA** : surveiller la sauvegarde Restic de FEBA. Aujourd'hui, aucune alerte n'existe en cas d'échec. Proposition : ajouter à la fin de `/opt/feba/scripts/backup-local-restic.sh`, en cas de réussite :

   ```bash
   install -d -m 755 /opt/feba/etat && date -u +%FT%TZ > /opt/feba/etat/sauvegarde_feba.txt
   ```

   Puis monter `/opt/feba/etat` en lecture seule dans le backend et ajouter le contrôle à `apps/incidents/tasks.py`, comme pour plugNmeet. La partie dépôt peut être préparée sur demande.
2. **Copie hors site** des sauvegardes plugNmeet et FEBA : choix du stockage et du coût.
3. **Restriction par IP** de `/django-admin/` : décision.
4. **Validation humaine** des incidents « corrigés, à valider » : scénarios dans `RAPPORT_INCIDENTS_FINAL.md`, § 4.
5. Décisions déjà listées en phase 2 et toujours ouvertes :
   - compte 208 ;
   - profil parent du superadmin 191 ;
   - les 4 superadmins ;
   - parents manquants de l'académie 2 ;
   - limite de connexions par compte ;
   - les 10 notes supprimées ;
   - les 147 affectations ;
   - PDF historiques ;
   - comptes de test en production ;
   - test Restic root.

## Prochaines étapes techniques possibles

- Tableau de bord parent (132 requêtes) et liste du suivi (123) : regrouper les calculs de moyennes et de progression.
- Échéanciers à saisir dans « Relances de paiement » pour que le graphique affiche l'attendu et le reste à payer (décision métier).

- Expiration d'une requête par déploiement lors du remplacement du backend : éprouver `proxy_connect_timeout` court et `proxy_next_upstream` sur la mini-pile (voir `RAPPORT_DEPLOIEMENT_FINAL.md`).

- Fichier de verrouillage complet des dépendances Python (`pip-compile`) : seules celles de Celery sont épinglées.
- Monter le dossier `nginx/` au lieu du fichier, pour un rechargement sans coupure.
- Migration HttpOnly (plan en phase 2).
