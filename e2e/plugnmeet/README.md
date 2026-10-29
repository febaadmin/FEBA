# Classes virtuelles plugNmeet — tests navigateur

Deux scénarios :

| Scénario | Ce qu'il vérifie |
|---|---|
| `parcours-feba.mjs` | **Parcours complet depuis FEBA** : connexion réelle, règles d'accès (404 hors de la classe, modérateur pour l'enseignant), salle d'attente et admission, audio/vidéo dans les deux sens en UDP, présence enregistrée par les webhooks, partage d'écran, refus dans le navigateur d'un compte hors de la classe, coupure réseau de 12 s et reprise, fin de réunion par l'enseignant, retour vers `/virtual-room/<id>/ended`, réunion inactive et présences closes dans FEBA (26 critères). |
| `deux-participants.mjs` | La salle plugNmeet seule, jetons produits par le code FEBA sans passer par l'interface (15 critères). |

`parcours-feba.mjs` : `FEBA_URL` (frontend), `FEBA_API` (défaut `FEBA_URL/api`),
`ROOM_ID`, `TEACHER`, `STUDENT`, `OUTSIDER` (comptes de `DEMO_ACCOUNTS.md`,
ou `ACCOUNTS_FILE`), `OUT`, `CHROMIUM_PATH`. FEBA doit avoir
`VIDEO_PROVIDER=plugnmeet` et un `PLUGNMEET_WEBHOOK_URL` joignable par
plugNmeet. Les libellés du client sont reconnus en français et en anglais
(la langue de la réunion suit celle de l'interface FEBA).

## deux-participants.mjs

Vérifie une vraie session : une salle et deux jetons (enseignant modérateur,
élève) produits par le code FEBA (`apps.virtualclass.plugnmeet`), puis deux
navigateurs Chrome sans interface, caméra et micro simulés.

Critères (code de sortie 1 si l'un échoue), mesurés par `getStats()` :

- micro et caméra publiés par les deux participants ; chacun voit les deux vidéos ;
- audio et vidéo reçus dans les deux sens (au-delà de 20 000 octets) ;
- transport UDP (ports multiplexés LiveKit) ;
- partage d'écran de l'enseignant reçu par l'élève ; aucun bouton de partage chez l'élève ;
- fin de réunion par FEBA (`end_room`) et retour vers `/virtual-room/<id>/ended`.

FEBA impose `mute_on_start` : le micro arrive coupé, le test le réactive comme
le ferait un utilisateur.

## Lancer

```bash
# 1. Salle et jetons (usage unique : relancer à chaque essai), depuis backend/
PLUGNMEET_TEST_URL=http://localhost:18080 PLUGNMEET_TEST_KEY=… PLUGNMEET_TEST_SECRET=… \
  DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  python ../e2e/plugnmeet/salle_et_jetons.py > /tmp/urls.json

# 2. Navigateurs (playwright-core de frontend/node_modules)
PNM_URLS=/tmp/urls.json OUT=/tmp/captures \
  FIN_CMD="python ../e2e/plugnmeet/salle_et_jetons.py --fin" \
  node ../e2e/plugnmeet/deux-participants.mjs
```

Variables : `PLUGNMEET_PUBLIC_URL` (URL du client vue du navigateur, si elle
diffère de l'API), `FEBA_PUBLIC_URL` (base du retour de fin), `CHROMIUM_PATH`,
`DUREE_MS`. Les jetons sont masqués dans toutes les sorties.

Limite : caméra et micro sont simulés. Ce test prouve la signalisation, le
transport et le routage des flux, pas la qualité perçue sur un vrai poste.
