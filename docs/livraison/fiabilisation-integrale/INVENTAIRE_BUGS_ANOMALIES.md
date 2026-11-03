# Bugs et anomalies de cette mission

| ID | Gravité | Anomalie | Cause | Correction | Preuve | État |
|---|---|---|---|---|---|---|
| F1 | **Élevée** | Double clic : 2 requêtes, donc 2 paiements, classes ou annonces possibles | Aucun verrou d'envoi | `useFormulaire` et `sansDoublon` | `dbl.mjs` : 2 requêtes puis 1 ; `sansDoublon.test.js` | Déployé. Production : 0 doublon existant |
| F2 | Élevée | Coupure de 16 à 20 s à chaque déploiement | Un seul backend remplacé directement | Relais, arrêt progressif | Banc : 260 puis 0 | Production |
| F3 | Moyenne | 2 requêtes SQL par note listée | Relations non préchargées | `select_related` | `VolumeTests` | Déployé |
| F4 | Faible | 1 requête par compte listé | Idem | Idem | `VolumeTests` | Déployé |
| F5 | Moyenne | Compte désactivé annoncé « identifiants incorrects » | `authenticate` l'écarte avant le message prévu | Message si le mot de passe est correct | `SessionsTests` | PR de livraison |
| F6 | Faible | Auteur d'un bulletin non conservé | Aucune trace | Écrit au journal | Revue | Déployé, sans historique |
| F7 | Information | Crochet WebSocket mort et `/ws/` en 404 | Production en WSGI, aucun appelant | Crochet retiré | 0 requête en 3 h, 404 | Déployé |
| F8 | Moyenne | CSP non bloquante | Observation | Appliquée | 132 pages | Déployé. **plugNmeet à vérifier** |
| F9 | Moyenne | React Router vulnérable | Version 6 | 7.18.5 | `npm audit` : 0 | Déployé |

## Corrections de mes rapports précédents

- Le « jeton WebSocket dans l'URL » n'était pas exploitable : aucun appelant.
- La coupure n'était pas de 5 s.
- L'échec d'isolation A1 reste une forte présomption de faux positif.

## Vérifiés sans défaut

- Le signal « portée désynchronisée » vient des compteurs d'en-tête avant la résolution.
- Mes scripts ont produit des faux KO : message enseignant vers élève interdit par conception, justification de suppression exigée, `password2` exigé.

## Laissé en l'état

- `/grades/student-summary/` : environ 5 requêtes par camarade. Touche le calcul officiel.
- `POST /auth/users/` ne renvoie pas l'identifiant créé. Sans effet sur l'interface actuelle.
- 4 copies identiques de `Messages.jsx`.
