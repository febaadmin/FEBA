# plugNmeet et CSP

**État : non testé avec une vraie salle.** Il faut des comptes de production et une salle réelle, ou un plugNmeet de test, que je n'ai pas.

**Analyse du code :** FEBA ouvre la salle par `window.location.replace(join_url)`, une navigation complète vers le domaine plugNmeet (`VirtualRoomSession.jsx`, ligne 139). La salle s'exécute donc hors de la page FEBA : la CSP de FEBA ne s'applique pas à la réunion et ne peut pas en bloquer l'audio, la vidéo ou le partage d'écran.

**Ce que la CSP peut toucher :** la page FEBA avant la redirection (appel API, `connect-src 'self'`) et le bandeau d'état. La navigation de la page était sans erreur en CI (navigation et sélecteur).

**Scénario de validation, avec comptes de test :**
1. Enseignant : Salles virtuelles, ouvrir une salle, vérifier l'entrée, le micro, la caméra et le partage.
2. Élève de la classe : entrer, voir et entendre l'enseignant.
3. Élève d'une autre classe : refusé.
4. Couper le réseau 10 s : reconnexion.
5. Fin de réunion par l'enseignant : les élèves sortent.

Scripts existants : `e2e/plugnmeet/recette-salle.mjs`, `parcours-feba.mjs`.
