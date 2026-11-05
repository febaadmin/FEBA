# Point de reprise — phase 8 (05-06/11/2026)

## Production
- `7e9bf59` déployé et vérifié (06/11, 00 h 05 UTC) : #102 messagerie, #105 boîte contact, #104 rapports, #103 paiement carte FedaPay (désactivé : webhook → 503 « non configuré », tant que `CARD_PAYMENTS_ENABLED` et les clés ne sont pas définis). 0 migration en attente, 0 erreur dans les journaux, synchronisation périodique de la boîte réussie (Celery).
- Migrations appliquées : `messaging.0005_phase7_messagerie`, `boite_mail.0001_initial` (ajouts uniquement).
- Boîte contact : première synchronisation réelle réussie — réception 44 messages (40 non lus, comme chez Hostinger), Envoyés 1 + 53 envois FEBA importés ; second passage : 0 nouveau (aucun doublon). Tâche Celery `boite_mail.synchroniser` toutes les 3 min.
- Messagerie : cas exact de la capture rejoué en production sur les vrais comptes, dans une transaction annulée — 201, reçu par le destinataire, présent dans « Envoyés », compteur à jour, 154/154 destinataires proposés acceptés ; aucune donnée conservée, aucun e-mail ni notification émis.

## PR
| PR | Objet | État |
|---|---|---|
| #102 | Messagerie (correctif d'envoi + refonte) | fusionnée, déployée |
| #105 | Boîte contact@globalfeba.com + Espace d'envoi d'e-mails | fusionnée, déployée |
| #104 | Rapports phase 7 + 8 | fusionnée, déployée |
| #103 | Paiement carte FedaPay | fusionnée, déployée (désactivé) |
| #106 | Délais CI (+ ce point de reprise) | ouverte, à fusionner |

## Incident d'exploitation
Le déploiement de #102 est resté bloqué > 35 min sur l'installation apt de LibreOffice (job sans délai : jusqu'à 6 h, file de déploiement bloquée). Exécution annulée avec l'accord de l'utilisateur ; le déploiement suivant (même `main`) a réussi. #106 ajoute des délais (15 min pour ce pas, 60 min pour le job).

## Tests exécutés
Backend complet (branche boîte contact) : 2186 tests, 1 échec trouvé (502 au lieu de 503 sur fournisseur indisponible) puis corrigé ; suites ciblées 48 à 111 OK après fusions ; frontend 599 à 603 OK, 0 erreur de lint ; E2E messagerie 21/21 (Chrome) ; CI 12/12 sur chaque PR.

## Bloqué / actions humaines
1. Fusionner #106.
2. Vérification visuelle connectée en production (messagerie, boîte contact) : connexion dans le navigateur.
3. Accorder éventuellement l'accès à la boîte contact à des administrateurs (« Gérer les accès »).
4. DMARC : passer de `p=none` à `p=quarantine` après lecture des rapports (DNS).
5. Phase 7 : compte marchand FedaPay, tarifs et échéances ; phase 6 : points ouverts.

## Prochaine action exacte
Après fusion de #106 : vérifier qu'un déploiement complet passe sous les nouveaux délais ; ouvrir « Boîte mail contact » avec un compte super administrateur et contrôler l'affichage d'un message réel.
