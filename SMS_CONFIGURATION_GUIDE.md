# FEBA — SMS : copie des e-mails et des relances de paiement

**État au 25/10/2026.** Le mécanisme est écrit et couvert par des tests
automatisés (fournisseur simulé au niveau HTTP). **Aucun SMS réel n'a été
envoyé** : aucun compte Twilio ni jeton n'était disponible, et le numéro
**+1 (215) 715-5406** n'a pas pu être vérifié auprès d'un fournisseur.
Tant que `manage.py sms_check` n'a pas réussi sur le serveur, ce numéro
n'est PAS un expéditeur opérationnel.

---

## 1. Ce qui déclenche un SMS

Chaque e-mail enregistré par FEBA (un envoi = un destinataire) met en file
la copie SMS de son texte, depuis la couche centrale
(`apps/notifications/mailer.create_delivery`). Aucun module ne peut
l'oublier. Chemins couverts :

| Chemin | SMS | Destinataire |
|---|---|---|
| E-mails groupés (campagnes) | oui | compte du destinataire de la campagne |
| Relances de paiement (e-mail **et/ou** notification interne) | **un** par événement de relance | responsable financier (même règle que la relance) |
| Accusé de réception FHA au parent | oui | compte FEBA du parent s'il existe, sinon le numéro saisi dans la fiche |
| Alerte FHA aux administrateurs, notifications FHA | oui | compte retrouvé par l'adresse, dans l'académie |
| Rapports mensuels | oui | compte du parent |
| Envoi direct d'un autre module (`send_mail`) | oui (sauf lien de sécurité) | compte retrouvé par l'adresse |
| Test SMTP, `email_check` | **non** (diagnostics) | — |
| Alertes d'erreur de Django (`mail_admins`, objet « [Django] ») | **non** (traces techniques) | — |
| Renvoi manuel d'un e-mail (boîte d'envoi) | **non** : le SMS de l'événement existe déjà | — |

## 2. Contenu

- Le SMS reprend le **texte de l'e-mail tel quel** : paragraphes, ponctuation,
  accents, montants, dates, références, liens. Pour un e-mail uniquement
  HTML, une version texte complète est produite (paragraphes, listes « - »,
  adresse des liens).
- Encodage : GSM-7 si possible, sinon UCS-2 (accents comme « ê », « ç »,
  tirets « — ») ; le nombre de segments facturés est enregistré.
- **Aucune troncature** : jusqu'à 1 600 caractères, un seul SMS concaténé
  (recomposé par le téléphone). Au-delà, plusieurs SMS numérotés « (1/3) »
  dont la concaténation redonne le texte exact ; au-delà de
  `SMS_MAX_MESSAGES_PER_NOTIFICATION` (5 par défaut), l'envoi **échoue**
  explicitement, sans rien envoyer de partiel. L'ordre d'arrivée de SMS
  distincts n'est pas garanti par les opérateurs : d'où la numérotation.
- **Pièces jointes** : jamais envoyées par SMS ; une ligne finale indique
  « [Pièce(s) jointe(s) : consultez l'e-mail correspondant.] ».
- **Messages de sécurité** (réinitialisation de mot de passe, liens signés,
  codes) : **jamais copiés**. Un SMS s'affiche sur l'écran verrouillé et
  survit à un vol de carte SIM ; dupliquer ces liens affaiblirait
  l'authentification. Statut « Non envoyé — Message de sécurité ».

## 3. Destinataire, numéro, consentement

- Le numéro est celui du **compte** du destinataire (`Mon profil` →
  téléphone). Jamais un autre numéro choisi à sa place.
- Normalisation E.164 (bibliothèque `phonenumbers` 9.0.40, numérotation
  béninoise à 10 chiffres incluse). Un numéro sans « + » n'est accepté que
  pour une académie listée dans `SMS_DEFAULT_REGIONS` (`FEBA:BJ` par
  défaut) ; ailleurs il est refusé plutôt que deviné. Une ligne fixe est
  refusée.
- **Consentement** : chaque personne choisit dans `Mon profil` →
  « Notifications par SMS » (horodaté par le serveur). Par défaut
  (`SMS_REQUIRE_EXPLICIT_CONSENT=True`), seules les personnes ayant
  **accepté** reçoivent des SMS. Un refus est toujours respecté ; une
  réponse « STOP » à Twilio (erreur 21610) enregistre le refus.
  `SMS_REQUIRE_EXPLICIT_CONSENT=False` (tous sauf refus) n'est à activer
  qu'après validation juridique (clause du contrat de scolarité).
- Chaque SMS non envoyé porte sa raison, visible dans la boîte d'envoi :
  aucun compte, aucun numéro, numéro invalide, ligne fixe, consentement
  non recueilli, refus, message de sécurité, relance devenue sans objet,
  SMS désactivés.

## 4. Relances de paiement

- Un événement de relance (un responsable, une exécution) = **un** SMS, même
  s'il est publié par e-mail ET en notification interne, même si l'envoi
  est repris après une panne (clé d'événement unique).
- Une relance publiée **sans** e-mail (pas d'adresse, ou e-mail désactivé
  dans la politique) produit quand même son SMS, avec le texte complet de
  la relance.
- **Au moment de l'envoi**, le SMS est revérifié ; il n'est PAS envoyé si
  l'échéance a été supprimée, si le montant restant dû a changé (paiement
  reçu entre-temps), si le destinataire n'est plus responsable de l'élève,
  ou si les relances ont été suspendues. Raison enregistrée.
- Historique : chaque relance (`PaymentReminder`) pointe vers son SMS
  (statut, numéro masqué, texte, erreurs).

## 5. Fiabilité

- File Celery (`notifications.send_sms`) ; l'envoi de l'e-mail n'attend
  jamais le SMS.
- Statuts : en file, envoi en cours, **accepté par le fournisseur**, **remis**
  (accusé Twilio), nouvel essai programmé, échec définitif, non envoyé,
  capturé (test). « Accepté » n'est pas « reçu ».
- Reprises : 1, 5, 30 puis 120 minutes (5 tentatives), tâche périodique
  `notifications.retry_due_sms` toutes les 5 min ; reprise des SMS restés
  en file (worker arrêté) ou interrompus.
- Erreurs définitives (numéro invalide 21211, non mobile 21614, STOP 21610,
  expéditeur non autorisé 21606/21659, pays non autorisé 21408) : pas de
  nouvel essai. Authentification refusée (20003) : nouvel essai, pour
  partir une fois la configuration corrigée.
- Un texte en plusieurs parties : chaque partie acceptée est enregistrée
  aussitôt ; une reprise n'envoie que les parties manquantes.
- Un SMS en échec ne déclenche JAMAIS le renvoi de l'e-mail, et
  inversement.
- Limite connue : si le serveur s'arrête entre l'acceptation d'une partie
  par Twilio et son enregistrement (quelques millisecondes), cette partie
  peut être renvoyée — Twilio n'offre pas de clé d'idempotence.

## 6. Configuration Twilio (production)

1. Compte Twilio de l'établissement ; le numéro **+1 215 715 5406** doit
   figurer dans *Phone Numbers > Active numbers* **de ce compte**, avec la
   capacité SMS.
2. *Messaging > Settings > Geo permissions* : autoriser le **Bénin** (et
   les pays des familles FHA). Envoyer depuis un numéro américain vers
   l'étranger est possible chez Twilio, mais certains opérateurs béninois
   filtrent les numéros internationaux : à vérifier par le test réel (§7).
3. Envoi **vers des numéros américains** depuis un numéro +1 « 10DLC » :
   enregistrement A2P 10DLC (marque + campagne) obligatoire aux États-Unis.
4. `.env.prod` :
   ```
   SMS_ENABLED=False            # True seulement après le §7
   SMS_PROVIDER=twilio
   SMS_FROM_NUMBER=+12157155406
   TWILIO_ACCOUNT_SID=AC…
   TWILIO_AUTH_TOKEN=…
   SMS_STATUS_CALLBACK_URL=https://globalfeba.com/api/notifications/sms/status/
   ```

## 7. Vérification réelle (à exécuter, non faite ici)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py sms_check </dev/null
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py sms_check --to +229XXXXXXXXXX </dev/null
```

Le premier contrôle (sans envoi) vérifie que le numéro appartient au compte
et peut envoyer des SMS. Le second envoie UN SMS au numéro indiqué (un
numéro autorisé, le vôtre). Codes de sortie : 0 vérifié/accepté, 1 échec,
2 transport de test. Réception : sur le téléphone et dans la console
Twilio (*Monitor > Logs > Messaging*). Puis `SMS_ENABLED=True`.

## 8. Variables

| Variable | Défaut | Rôle |
|---|---|---|
| `SMS_ENABLED` | False | interrupteur général |
| `SMS_PROVIDER` | capture | `twilio`, `capture` (enregistré, jamais envoyé), `console` |
| `SMS_FROM_NUMBER` | — | expéditeur E.164 |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | — | secrets, environnement uniquement |
| `SMS_STATUS_CALLBACK_URL` | — | accusés de remise (signature vérifiée) |
| `SMS_REQUIRE_EXPLICIT_CONSENT` | True | voir §3 |
| `SMS_DEFAULT_REGIONS` | FEBA:BJ | indicatif des numéros saisis sans « + » |
| `SMS_MAX_MESSAGES_PER_NOTIFICATION` | 5 | au-delà : échec explicite |
| `SMS_TIMEOUT` | 15 | secondes |
