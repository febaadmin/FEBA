# Classe virtuelle plugNmeet — test navigateur à deux participants

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
