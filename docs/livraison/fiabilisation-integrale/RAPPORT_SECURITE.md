> État à jour : `RAPPORT_SECURITE_FINAL.md`.

# Sécurité

| Point | État réel | Niveau |
|---|---|---|
| Jetons en `localStorage` | **Non corrigé**, atténué par la CSP. Passer aux cookies HttpOnly touche toute l'authentification | Risque documenté |
| Jeton WebSocket dans l'URL | Sans objet : code retiré, `/ws/` en 404. Le code serveur dormant lit encore `?token=` | Déployé |
| Backend en root | **Non corrigé** : droits des volumes de production à migrer | Plan |
| React Router | 0 vulnérabilité npm en production | Déployé |
| CSP | **Appliquée**. Retour à Jitsi : autoriser son domaine | Déployé |
| Test d'intrusion externe | **Non fait** : prestataire requis | Décision humaine |
| Audit des API | **Incomplet** : balayage automatique et tests ciblés, pas de revue ligne à ligne | Partiel |
| `/django-admin/` | Limite configurée. **Non éprouvée**, je ne fais pas de test agressif en production | Déployé |
| Fichiers, avatars | Contenu contrôlé, media sandboxé | Déployé |
| Anciens jetons au journal | 0 dans le journal nginx actuel. Autres copies du serveur non vérifiées | Partiel |
| Secrets | Gitleaks sur le dépôt : 0 | Local |

**Scénarios testés sous PostgreSQL :** élévation, mass assignment, compte désactivé, révocation, IDOR entre académies et entre personnes, injection dans la recherche, lien falsifié.

**Image Docker :** non analysée par un scanner. **Redis :** réseau interne, mot de passe non vérifié.
