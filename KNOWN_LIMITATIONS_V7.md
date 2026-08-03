# Limites connues — après l'itération V7

Ce document ne sert pas à requalifier du travail inachevé. Les quatre
priorités de l'itération (P0 à P3) sont **terminées et vérifiées** ; voir
`RAPPORT_V7.md` et `VERIFICATION_V7.md`.

Ce qui suit décrit des comportements **volontaires** et des sujets hors
périmètre, avec la raison de chaque choix.

---

## Écarts assumés dans le mode « Toutes les Académies »

Sur dix-sept endpoints mesurés, quinze satisfont exactement
« total consolidé = somme des académies ». Les deux écarts sont corrects :

**Le Super Administrateur n'appartient à aucune académie.** C'est un rôle
plateforme. Il apparaît donc dans la liste consolidée des utilisateurs avec
le badge « Sans académie », mais dans aucune des deux listes par académie.
Le masquer serait pire : un compte qui existe et n'apparaît nulle part est
plus dangereux qu'un compte visible et correctement étiqueté.

**Les salles virtuelles n'existent pas pour une académie présentielle.**
L'endpoint répond 403 pour FEBA (matrice de fonctionnalités). Le total
consolidé vaut donc celui de la seule académie en ligne. Ce n'est pas une
perte de données : il n'y a rien à additionner.

---

## Traductions du contenu administré

Les champs `_en` de `HeroSlide`, `NewsPost`, `GalleryAlbum`, `GalleryItem`
et `SiteSettings` sont **facultatifs**. Le jeu de démonstration les
remplit ; une actualité saisie par l'administration sans traduction
anglaise s'affichera en français, y compris en mode EN.

C'est délibéré. L'alternative — masquer le contenu non traduit — ferait
disparaître des actualités réelles d'une page anglaise. Traduire un article
reste une décision éditoriale ; l'outil ne peut pas la prendre à la place
de l'école.

---

## Ce qui reste en attente de la direction de FEBA FHA

Aucune donnée commerciale n'a été inventée. Les champs suivants restent
`null` dans `School.settings.pending_direction_validation`, et l'interface
ne les affiche pas tant qu'ils ne sont pas renseignés :

tarif annuel, paiement en plusieurs fois, date de rentrée, horaires
définitifs des groupes, réduction fratrie, réduction anticipée, politique
de remboursement, noms des enseignants, prestataire de paiement, politique
d'enregistrement des visioconférences.

Les horaires des séances du jeu de démonstration sont des **exemples
techniques** (mardi, jeudi et samedi en UTC), pas un calendrier validé.

---

## Environnement de test

**Un test de concurrence est ignoré sur SQLite** (`test_parent_student.py`,
assignation simultanée). SQLite en mémoire verrouille la table entière : le
test ne mesurerait rien. Il s'exécute sur PostgreSQL, qui est le moteur de
production.

**82 avertissements ESLint subsistent.** Aucune erreur. Ce sont des
avertissements historiques (`react-hooks/set-state-in-effect`, variables
inutilisées préfixées) hérités des itérations précédentes, sans rapport
avec cette livraison. Les corriger demanderait de restructurer des écrans
qui fonctionnent, ce qui n'était pas demandé.

**La visioconférence exige une instance Jitsi auto-hébergée.** Il n'existe
aucun repli vers une instance publique : c'était le correctif de
l'itération précédente. Sans `JITSI_DOMAIN`, `JITSI_APP_ID` et
`JITSI_APP_SECRET`, l'application affiche une erreur d'infrastructure
explicite plutôt que de basculer des cours de mineurs sur un serveur tiers.
`make jitsi-up` monte l'instance ; `make jitsi-health` la contrôle.

---

## Portée des tests end-to-end

Les trois scénarios de `e2e/` couvrent les parcours de cette itération :
bascule d'académie, identification des données, séparation des emplois du
temps, bilinguisme des cinq profils et des treize pages publiques.

Ils **ne remplacent pas** une campagne de tests fonctionnels complète sur
l'ensemble de l'application. Les autres fonctionnalités restent couvertes
par les 562 tests backend et les 98 tests frontend.
