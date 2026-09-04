# FEBA — Classes virtuelles (V10)

---

## 1. Ce qui a changé dans l'architecture

| Avant | Après |
|---|---|
| Modale posée sur le tableau de bord | Onglet dédié, route `/virtual-room/:id/join` |
| Conférence dans l'arbre React de la page | Route montée à la **racine** du routeur |
| Détruite par le `refetchInterval` du parent | Hors de portée des rendus du tableau de bord |
| Jeton obtenu par la page puis transmis | Jeton demandé **par l'onglet lui-même** |

La raison est simple : tant que la conférence vit dans l'arbre React du
tableau de bord, elle reste à la merci de tout ce qui s'y passe — un
poll, une invalidation de cache, une navigation. Corriger le composant
n'aurait traité que le symptôme du jour.

---

## 2. Ciblage d'une salle (§1)

Une salle peut désormais viser :

| Cible | Champ | Effet |
|---|---|---|
| Une classe | `class_obj` | seuls les membres du groupe entrent |
| Toute l'académie | `class_obj = null` | aucune restriction de groupe |
| Des profils | `target_roles` | admin / enseignant / élève / parent |

`target_roles` est une liste. Vide = aucun filtre, **comportement
historique préservé**.

### Appliqué par le backend, pas seulement masqué

`assert_can_join()` vérifie le ciblage côté serveur. Un identifiant posté
directement, sans passer par l'interface, est refusé — couvert par
`IdorParLApiTests`.

Détail d'implémentation qui vaut d'être noté : un groupe de cases à
cocher renvoie `false` quand rien n'est coché, et une chaîne quand une
seule l'est. Sans normalisation, le backend recevait `false` et refusait
la création. Un test le tient (`test_envoie_target_roles_en_LISTE`).

---

## 3. Un enseignant n'est plus automatiquement chez lui

Le contrôle d'appartenance au groupe ne portait que sur les **élèves** et
les **parents**. Conséquence : tout enseignant de l'académie pouvait
entrer dans le cours d'une classe qui ne lui est pas confiée.

Désormais, un enseignant doit être **affecté** à la classe de la salle —
sauf s'il en est le créateur : il l'a ouverte pour une classe qu'il
encadre ponctuellement (remplacement, soutien) sans en être titulaire.

**Statut : CORRIGÉ ET VÉRIFIÉ.**

---

## 4. Cycle de vie d'une participation (§14)

| Événement | Effet |
|---|---|
| Ouverture de l'onglet | **une** adhésion, même sous React StrictMode |
| `videoConferenceLeft` puis `readyToClose` | **un seul** départ |
| Fermeture / rechargement de l'onglet (`pagehide`) | départ signalé |
| Panne de la conférence | départ signalé automatiquement |
| Départ refusé par le backend | l'écran ne casse pas — c'est une trace, pas un blocage |

Sans ces gardes : deux participations pour une seule personne, et des
participations « en cours » indéfiniment qui faussaient les durées.

---

## 5. États de l'onglet

Aucun n'est un écran noir muet.

| État | Écran |
|---|---|
| Portée d'académie en cours | « Ouverture de la salle… » |
| Portée introuvable | « Impossible de rejoindre la salle » + quoi faire |
| Accès refusé (403) | le motif exact du backend |
| Visio non configurée (503) | « L'instance FEBA n'est pas joignable » |
| Jitsi injoignable | « Impossible de charger l'interface Jitsi depuis … » |
| Réunion quittée | « Vous avez quitté la réunion » + fermer l'onglet |

Les trois derniers ont été **observés en navigateur**, pas seulement en
test unitaire.

---

## 6. Sécurité du jeton

- Le secret reste backend : **0 occurrence** dans `src/` et dans `dist/`
  après build.
- Le JWT ne transite **pas** par l'URL : l'onglet est ouvert en
  same-origin, la session FEBA y est déjà valide, et il appelle
  `virtualAPI.join(id)` lui-même.
- Le JWT est lié à **une** salle par la revendication `room`.
- Sans secret, le backend répond 503 plutôt que de servir une salle non
  protégée.

Détail : `window.open(..., "noopener")` — l'onglet ouvert ne garde aucune
référence vers la page appelante.

---

## 7. Bloqueur de fenêtres surgissantes (§13)

`window.open` part **synchronement** dans le gestionnaire de clic, avant
tout appel réseau. Ouvrir après un `await` fait bloquer l'onglet,
silencieusement.

Quand le navigateur bloque tout de même, le message donne la cause **et**
le remède : « Votre navigateur a bloqué l'ouverture de la salle. Autorisez
les fenêtres surgissantes pour ce site, puis réessayez. » C'est le cas le
plus fréquent sur un poste d'école.

---

## 8. Reste à vérifier en environnement réel

Réunion à 2 participants, stabilité sur 30 minutes, poignée de main
WebSocket, refus effectif de l'adhésion anonyme.
Voir `KNOWN_LIMITATIONS_V10.md`.
