# FEBA — Plan de test réel de la classe virtuelle

Ces tests **ne peuvent pas** être exécutés depuis l'environnement de
développement : il n'a aucun accès sortant depuis un navigateur, et son
mandataire ne relaie aucune mise à niveau WebSocket. Ils sont donc à
réaliser depuis vos machines.

Statut de tout ce document : **À TESTER EN ENVIRONNEMENT RÉEL.**

---

## Préparation

| Élément | Valeur |
|---|---|
| Participant A | enseignant ou super-administrateur FEBA FHA |
| Participant B | élève **inscrit dans la classe de la salle** |
| Machines | deux, sur des **réseaux différents** de préférence |
| Navigateur | Chrome ou Firefox à jour |
| Durée à prévoir | 45 min (10 min de mise en place, 30 min de test, 5 min de relevé) |

Avant de commencer, sur une machine disposant du dépôt :

```bash
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

**Ne pas commencer** si `dns`, `tls`, `http`, `external_api` ou
`signalisation` sont en échec — le test mesurerait autre chose que ce
qu'on cherche.

---

## Test 1 — Deux participants (§10)

### Déroulé

1. **A** ouvre FEBA, se connecte, va dans *Salles virtuelles*, clique
   **Rejoindre**.
2. Vérifier : un **nouvel onglet** s'ouvre, Jitsi occupe tout l'écran,
   aucune barre latérale ni en-tête FEBA n'est visible.
3. **A** autorise caméra et micro.
4. **B** fait de même, sur l'autre machine, sur la **même** salle.

### À vérifier

| # | Point | Attendu |
|---|---|---|
| 1.1 | Liste des participants | **exactement 2** noms |
| 1.2 | Doublons | aucun participant n'apparaît deux fois |
| 1.3 | Audio | chacun entend l'autre |
| 1.4 | Vidéo | chacun voit l'autre |
| 1.5 | Modération | **A** dispose des contrôles de modérateur, **B** non |
| 1.6 | Console navigateur (F12) | aucune erreur `Content Security Policy`, aucune erreur WebSocket |

### Si la liste montre 3 participants pour 2 personnes

C'est le défaut historique — une identité résiduelle. Relever
immédiatement, dans la console de l'onglet :

```js
document.querySelectorAll('iframe[src*="meet.globalfeba.com"]').length
```

**Attendu : 1.** Une valeur supérieure signifie que plusieurs instances
Jitsi coexistent, et le rapport doit le mentionner.

---

## Test 2 — Rafraîchissement de FEBA pendant la conférence (§12)

Conférence en cours dans l'onglet Jitsi. Dans l'onglet **FEBA** :

1. recharger le tableau de bord (Ctrl/Cmd + R) ;
2. naviguer vers *Élèves*, puis *Notes*, puis revenir à *Salles virtuelles* ;
3. attendre au moins 60 secondes (deux cycles du rafraîchissement
   automatique de la liste).

**Attendu :** la conférence de l'autre onglet **n'est pas interrompue**.
Aucune reconnexion, aucun retour à l'écran « Rejoindre ».

> C'était le défaut d'origine : la conférence vivait dans la page qui se
> rafraîchissait, et disparaissait avec elle. C'est ce test qui vérifie
> que l'architecture en onglet séparé tient.

---

## Test 3 — Fermeture et retour (§13)

| # | Action | Attendu |
|---|---|---|
| 3.1 | **A** raccroche via le bouton Jitsi | l'onglet affiche « Vous avez quitté la réunion » |
| 3.2 | Retour à FEBA, liste des salles | le compteur de participants décroît |
| 3.3 | **A** rejoint à nouveau | une seule identité, pas deux |
| 3.4 | **B** ferme l'onglet sans raccrocher | sa participation est close côté FEBA |
| 3.5 | **B** recharge l'onglet de conférence | il revient dans la salle, **une seule fois** |

Contrôle côté serveur, après le test :

```bash
# Aucune participation ne doit rester ouverte alors que la salle est vide
docker compose exec backend python manage.py shell -c "
from apps.virtualclass.models import VirtualRoomAttendance
ouvertes = VirtualRoomAttendance.objects.filter(left_at__isnull=True)
print('participations encore ouvertes :', ouvertes.count())
for a in ouvertes[:10]: print(' ', a.user, a.room, a.joined_at)
"
```

**Attendu :** 0, une fois tout le monde parti.

---

## Test 4 — Stabilité 30 minutes (§11)

Reprendre le test 1, et **laisser tourner 30 minutes** en parlant
régulièrement (une conférence silencieuse ne sollicite pas le média).

### Pendant le test, sur le serveur

```bash
# Fenêtre 1 — ressources
docker stats --no-stream jvb prosody jitsi-web jicofo

# Fenêtre 2 — le pont vidéo
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  logs -f jvb | grep -iE "expire|restart|error|ice|failed"

# Fenêtre 3 — la signalisation
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml \
  logs -f prosody | grep -iE "disconnect|error|timeout"
```

### Critères — tous obligatoires

| Critère | Attendu |
|---|---|
| Déconnexions spontanées | **0** |
| Participants fantômes | **0** |
| Identités en double | **0** |
| Redémarrages de conteneur | **0** |
| Nouvelles instances Jitsi dans l'onglet | **0** (voir la commande du test 1) |
| Mémoire de `jvb` | stable, sans croissance continue |

### Relevé final

```bash
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml ps
# la colonne STATUS doit indiquer « Up 30 minutes » ou plus,
# JAMAIS « Restarting » ni un uptime plus court que le test.
```

---

## Test 5 — Accès anonyme refusé (§9)

Le plus important pour la sécurité. **Sans passer par FEBA :**

1. ouvrir un navigateur en **navigation privée** ;
2. aller directement sur `https://meet.globalfeba.com/une-salle-quelconque`.

| Observation | Conclusion |
|---|---|
| une salle s'ouvre et la caméra démarre | **FAIL — critique.** N'importe qui sur Internet peut créer des salles sur votre serveur. Vérifier `ENABLE_AUTH=1`, `ENABLE_GUESTS=0`, `AUTH_TYPE=jwt`, `JWT_ALLOW_EMPTY=0` |
| authentification demandée, ou accès refusé | **PASS** |

La page d'accueil peut rester visible : ce qui compte est qu'elle ne
permette ni de **rejoindre** ni de **créer** une salle.

### Variantes à vérifier depuis FEBA

| Cas | Attendu |
|---|---|
| Élève d'une **autre classe** clique Rejoindre | refus expliqué : « Vous n'êtes pas inscrit dans le groupe de cette salle. » |
| Utilisateur d'une **autre académie** | salle introuvable |
| Jeton expiré (laisser l'onglet ouvert > 15 min avant de rejoindre) | Jitsi refuse, message explicite |

---

## Test 6 — Redémarrage (§14)

```bash
cd /opt/feba
docker compose -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml restart
sleep 30
make jitsi-health JITSI_TARGET=meet.globalfeba.com
```

Puis un redémarrage machine complet, et le même contrôle.

| Point | Attendu |
|---|---|
| `meet.globalfeba.com` répond | oui, sans intervention |
| HTTPS | certificat toujours valide |
| Réseau `feba_jitsi_shared` | présent, sans création manuelle |
| Une conférence FEBA s'ouvre | oui |

---

## Fiche de relevé

À remplir et à me renvoyer — c'est ce qui permettra de passer les statuts
« À TESTER EN ENVIRONNEMENT RÉEL » en « PASS VÉRIFIÉ ».

```
Date :                        Réseaux utilisés (A / B) :
Version jitsi/web :           docker compose images jitsi-web

Test 1  deux participants      [ ] PASS   [ ] FAIL  →
Test 2  refresh FEBA           [ ] PASS   [ ] FAIL  →
Test 3  fermeture / retour     [ ] PASS   [ ] FAIL  →
Test 4  stabilité 30 min       [ ] PASS   [ ] FAIL  →
Test 5  accès anonyme refusé   [ ] PASS   [ ] FAIL  →
Test 6  redémarrage            [ ] PASS   [ ] FAIL  →

WebSocket (§9 de JITSI_PRODUCTION_ACTIONS.md) : code obtenu =
UDP 10000 depuis l'extérieur (nc -vzu)        : 
Candidats ICE observés                        : 
Anomalies :
```
