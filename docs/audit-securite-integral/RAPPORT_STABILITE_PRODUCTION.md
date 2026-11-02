# Stabilité

**Cause de la coupure :** un seul conteneur backend. `compose up -d` le remplace ; pendant son démarrage, nginx répond 502, environ 5 secondes. Mesure du 02/11 : 4 réponses 502 à 16:12.

**Atténuation livrée :** le navigateur rejoue les lectures sur 502 et 504, 4 fois au plus, toutes les 2 s.

**Ce qui n'est pas résolu :** les écritures reçoivent toujours le 502. Elles ne peuvent pas être rejouées sans risque de doublon.

**Solution complète, non appliquée :** deux backends et bascule nginx. Elle touche l'exploitation et demande une fenêtre et un retour arrière.
- Démarrer le nouveau conteneur à côté de l'ancien.
- Attendre le contrôle de santé.
- Basculer, puis arrêter l'ancien.
- Retour arrière : revenir à l'étape unique actuelle.

Attention : le déploiement relance aussi nginx. L'effet réel de la reprise n'a pas encore été observé pendant un vrai déploiement avec un utilisateur connecté.
