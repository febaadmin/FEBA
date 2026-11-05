# Phase 6 : performances et sécurité

## Performances

Temps de réponse sur la base locale (données de démonstration : 30 élèves notés, 600 notes, 104 appels), trois mesures successives :

| Point d'API | Temps |
|---|---|
| `/students/?school_year=` (liste, classe corrigée) | 91–98 ms |
| `/analytics/vue-ensemble/` (4 analyses agrégées) | 190–212 ms |
| `/analytics/resultats/` | 89–98 ms |
| `/analytics/classes/` | 83–99 ms |
| `/analytics/matieres/detail/` | 82–84 ms |
| `/analytics/enseignants/profils/` | 82–85 ms |
| `/payments/situation/` | 43–47 ms |
| `/payments/tableau-de-bord/?periode=12m` | 65–67 ms |
| `/payments/tableau-de-bord/detail/` | 67–81 ms |

**Requêtes SQL** :
- les analyses agrègent en base ;
- `test_requetes_en_nombre_constant` vérifie que le nombre de requêtes ne dépend pas du nombre d'élèves ;
- les plafonds existants (`test_requetes_sql`) restent verts ;
- la correction de la colonne « Classe » utilise les inscriptions déjà préchargées par la vue : aucune requête par élève.

**Frontend** : pdf.js (≈ 1,4 Mo, worker compris) n'est chargé qu'à l'ouverture d'un aperçu PDF ; il n'est pas dans le paquet principal.

**Mesure manquante** : aucune mesure n'a été faite en production, faute de compte utilisable. Les routes y répondent 401 sans connexion, aucune erreur 500 n'a été relevée.

## Sécurité

- **CSP** :
  - non affaiblie. L'élargissement de `frame-src` à `blob:` a été envisagé, puis écarté.
  - l'aperçu PDF est dessiné sans cadre, par pdf.js : code et worker servis par notre origine, `isEvalSupported: false` (CVE-2024-4367), PDF passé en mémoire.
- **CSP éprouvée** : chaque page E2E reçoit désormais la CSP de `nginx/nginx.prod.conf`. Sur 310 contrôles, aucune violation.
- **Dépendance ajoutée** : `pdfjs-dist` 4.10.38 (version exacte). `npm audit --omit=dev` : 0 vulnérabilité.
- **Droits** :
  - centre d'analyse : 403 pour parent et élève sur toutes les analyses d'établissement ;
  - enseignant : 403 hors de ses classes, sur un autre enseignant, sur les finances ;
  - administrateur d'une autre académie : 404 ;
  - sélections multiples validées identifiant par identifiant ;
  - balayage de l'API (6 800 requêtes, 5 profils) : 0 erreur 500, aucune fuite.
- **Données** : les deux commandes de correction simulent par défaut, journalisent et savent revenir en arrière. Aucune n'a été exécutée en production.

## Exploitation

| Contrôle (05/11) | Résultat |
|---|---|
| Conteneurs | sains |
| Journaux du backend, 24 h | une seule trace : un robot qui appelle l'IP (400) |
| Celery et planificateur | 0 erreur |
| Incidents | 0 ouvert (5 corrigés, 4 résolus) |
| Sauvegarde `feba-backup.timer` | dernière exécution le 05/11 à 02:32 UTC, `Result=success`, code 0 |
| Restauration de la sauvegarde FEBA | non éprouvée : accès root nécessaire (action humaine, déjà listée) |
| Disque | 31 % |
| Projet OKX | non touché |
