# Archive

Voir le compte rendu final pour le nom, le commit et le SHA-256.

**Séparation**
- Code de production : `backend/`, `frontend/`, `nginx/`.
- Fixtures de test : `backend/tests/`, `e2e/ci/`.
- Démonstration : `seed_demo_data`, avec des mots de passe lus dans l'environnement ou générés.
- Configuration : `.env*.example`, sans secret.
- Exclus de l'archive (`.gitattributes`) : anciens rapports et anciens scénarios qui citaient des mots de passe.

**Reste dans l'archive, volontairement :**
- `check_demo_passwords.py` contient la liste des anciens mots de passe de démonstration : c'est le contrôle qui vérifie qu'aucun compte de production ne les utilise.
- `test_securite_fenetre_alertes.py` vérifie que l'un d'eux n'apparaît pas dans une sortie.
