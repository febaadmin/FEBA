# Sécurité

**FEBA n'est pas déclaré sûr à 100 %.** Inventaire détaillé : `../../audit-securite-integral/INVENTAIRE_VULNERABILITES.md`.

| Sujet | État réel au 02/11 |
|---|---|
| Avatars HTML, SVG | Corrigé, testé, déployé |
| Formules CSV | Corrigé, testé, déployé |
| Jeton WebSocket | Masqué des journaux. 0 occurrence dans le journal nginx actuel. **Reste dans l'URL** |
| CSP | **En observation seulement** |
| Pièces jointes | Contrôlées |
| Limites | `/django-admin/` et connexion par adresse. **Pas par compte** : votre accord est requis |
| React Router | **2 vulnérabilités modérées restantes**, correctif en version 7 |
| Conteneur en root | **Non corrigé** |
| Jetons en `localStorage` | **Non corrigé** |
| Test d'intrusion externe | **Non fait** |
| Isolation | Tests PostgreSQL verts, faux positif A1 expliqué |

Pour la connexion : aucune protection retirée. Le contrôle de portée reste actif sur les lectures métier, avec un test témoin.
