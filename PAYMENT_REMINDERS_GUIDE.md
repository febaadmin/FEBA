# FEBA — Guide des relances automatiques de paiement

Écran : **Relances de paiement** (administrateur de l'académie, ou
super-administrateur sur l'académie active). Moteur :
`backend/apps/payments/reminders.py`.

---

## 1. Point de départ (constat d'audit)

Avant cette version, FEBA ne connaissait **aucune échéance** : la grille
tarifaire (`FeeSchedule`) disait « combien », jamais « quand ». Il n'existait
ni abonnement aux services optionnels (cantine, transport, garderie), ni
exonération, ni réduction. Il était donc impossible de déterminer un retard
sans inventer une règle.

Les modalités par tranche sont désormais des **données saisies par
l'académie**, jamais des montants écrits dans le code.

## 2. Ce qu'il faut configurer

### 2.1 Échéanciers (onglet « Échéanciers »)

Un tarif = type de frais (inscription, mensualité/scolarité, cantine,
transport, garderie, autre) + année + niveau (facultatif) + montant total
+ **échéances** (libellé, date limite, montant).

- **Obligatoire** : dû par tous les élèves du périmètre (scolarité,
  inscription). **Non obligatoire** : dû uniquement par les élèves
  **abonnés** (cantine, transport, garderie). Les tarifs optionnels déjà
  existants ont été marqués non obligatoires par la migration
  `payments.0013` — aucun parent non abonné ne peut être relancé.
- Mode **Tranches** : la somme des échéances doit égaler le montant total.
  Sinon, anomalie affichée et **aucune relance** pour ce tarif.
- Mode **Récurrent** : chaque échéance est un montant dû (ex. mensuel).

### 2.2 Grille FEBA 2026-2027 (affiche fournie)

Le fichier `backend/apps/payments/fee_plans/feba_2026_2027.json` reprend
l'affiche : inscription 10 000 FCFA ; scolarité Maternelle 1&2 325 900,
CI&CP 315 500, CE1&CE2 329 800, CM1&CM2 349 500 (tranches septembre /
novembre / janvier) ; garderie 41 900 FCFA/mois (abonnés).

**À confirmer par l'administration avant activation** (l'affiche ne le dit
pas) : le **jour** de chaque échéance (le fichier retient le dernier jour du
mois), la date limite de l'inscription (30/09/2026 retenu), et les mois de
garderie (septembre à juin retenus).

Chargement — simulation d'abord, rien n'est écrit :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py load_fee_plan apps/payments/fee_plans/feba_2026_2027.json </dev/null
```

Puis écriture (les tarifs existants ne sont jamais modifiés sans `--update`) :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend-prod python manage.py load_fee_plan apps/payments/fee_plans/feba_2026_2027.json --apply </dev/null
```

La commande liste les niveaux reconnus et ceux qui restent sans tarif : les
noms de niveaux de la base doivent correspondre à ceux du fichier
(« CE1 », « Maternelle 1 »…).

### 2.3 Dispositions par élève (bouton « Élèves » d'un tarif)

- **Abonnement** au service (avec dates de début/fin facultatives) ;
- **Exonération totale** ;
- **Réduction / bourse** d'un montant fixe, imputée sur les **dernières**
  échéances (elle allège le solde, elle ne retarde pas la 1re tranche).

### 2.4 Règles de relance (onglet « État et règles »)

| Réglage | Défaut | Effet |
|---|---|---|
| Délai de grâce | 7 j | 1re relance au plus tôt 7 jours après la date limite |
| Intervalle | 14 j | 2e relance à J+21, 3e à J+35… |
| Maximum | 3 | relances par échéance et par responsable |
| Solde minimum | 1 | pas de relance pour un solde inférieur |
| E-mail / notification interne | oui / oui | canaux utilisés |
| Modalités de paiement, contact | — | repris dans le message |

## 3. Calcul des montants dus

Pour chaque élève actif et chaque échéance :

1. **Tarif applicable** : le plus spécifique (niveau + année > année >
   niveau > permanent), selon le niveau de la classe de l'élève **pour cette
   année**.
2. **Payé** : paiements **confirmés et non supprimés**, de ce type et de
   cette année scolaire, **nets des remboursements carte**. Annulés,
   supprimés et transactions carte non abouties ne comptent pas.
3. **Imputation** : un paiement qui précise son « mois concerné » est imputé
   à l'échéance de ce mois ; le reste va à l'échéance la plus ancienne non
   soldée (règle des tranches : en novembre, le cumul septembre + novembre
   est exigible). Aucun montant n'est compté deux fois.
4. **Statut** : à venir (date limite non dépassée), réglée, échue — impayée,
   échue — partiellement payée (seul le **solde** est réclamé), exonérée.

**Abstention plutôt qu'erreur** — pas de relance, anomalie affichée :
échéancier incohérent, paiement sans année scolaire, devise incohérente,
responsable rattaché à une autre académie, paiement carte en cours.

## 4. Destinataires et messages

- Responsables marqués « responsable financier » de l'élève ; à défaut, les
  tuteurs légaux. Comptes actifs, **de la même académie** uniquement.
- **Un message par responsable**, regroupant ses enfants : chaque ligne
  indique l'enfant, le frais, l'échéance, la date limite, le montant prévu,
  le montant réglé et le **reste à payer**, puis les modalités et le contact
  de l'académie. Langue : préférence du responsable (fr/en).
- **Notification interne** dans l'espace parent (lien vers « Paiements »)
  ET e-mail. Statuts enregistrés tels que constatés : notification créée,
  e-mail remis au serveur, nouvel essai, échec, pas d'adresse.

## 5. Automatisation et sûreté

- Tâche **Celery Beat** `payments.run_payment_reminders`, chaque jour à
  `PAYMENT_REMINDERS_HOUR:PAYMENT_REMINDERS_MINUTE` (défaut 08:30).
- **Double interrupteur** : `PAYMENT_REMINDERS_ENABLED=True` dans
  l'environnement du serveur **et** relances activées pour l'académie.
  Faux par défaut ; faux en développement et en test. Quand la tâche ne
  s'exécute pas, elle journalise pourquoi (« Non exécutée (désactivée) ») :
  l'écran sait que Beat tourne.
- **Idempotence** : clé unique (échéance × élève × responsable × niveau de
  rappel). Rejouer la tâche, ou deux exécutions simultanées, ne produisent
  aucun doublon (vérifié sur PostgreSQL avec deux exécutions parallèles).
- Verrou par académie (cache Redis) contre les exécutions concurrentes.
- Worker arrêté entre l'enregistrement et l'envoi : la relance est reprise
  à l'exécution suivante. E-mail en échec temporaire : relancé par
  `notifications.retry_due_deliveries`.
- Paiement reçu après une 1re relance : plus de relance (solde nul).
- Échéancier modifié après une relance : l'historique conserve l'instantané
  des montants envoyés.

## 6. Mise en service recommandée

1. Configurer et vérifier le SMTP (voir `EMAIL_CONFIGURATION_GUIDE.md`).
2. Charger ou saisir les échéanciers ; confirmer les dates.
3. Déclarer les abonnements (cantine, transport, garderie) et les
   exonérations/réductions.
4. Onglet **Retards** : simulation à la date du jour ; vérifier montants,
   destinataires et anomalies. **Rien n'est envoyé.**
5. Mettre `PAYMENT_REMINDERS_ENABLED=True` dans `.env.prod`, redémarrer
   `celery-prod` et `celery-beat`.
6. Activer les relances de l'académie (onglet « État et règles »).
7. Surveiller l'onglet « Historique » et l'état du service (healthchecks
   Docker de `celery-prod` et `celery-beat`).

Suspension immédiate : bouton « Suspendre les envois automatiques ».
