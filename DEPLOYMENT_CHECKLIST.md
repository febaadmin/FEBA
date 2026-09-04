# FEBA — Liste de contrôle de déploiement

À dérouler dans l'ordre. Chaque case demande une **vérification**, pas une
supposition.

---

## 1. Avant

- [ ] Sauvegarder la base : `scripts/backup_database.sh`
- [ ] Vérifier l'espace disque et l'état des services
- [ ] `git log --oneline -5` — confirmer le commit déployé

### Migrations de cette livraison

| Migration | Effet | Réversible |
|---|---|---|
| `classes.0003_class_language_track` | ajoute `language_track`, défaut `BILINGUAL` | oui |
| `classes.0004_audit_language_tracks` | aligne les classes FHA sur leurs matières réelles | oui |
| `schools.0016_activate_orphan_school_years` | active l'année la plus récente des académies sans année active | oui |
| `virtualclass.0003_virtualroom_target_roles` | ajoute `target_roles`, défaut `[]` | oui |

Aucune ne supprime ni ne réécrit de donnée existante.

- [ ] **Exécuter `classes.0004` d'abord sur une copie de la base de
      production** et lire son rapport : elle imprime les classes dont le
      parcours a été déduit, et celles laissées à valider.

---

## 2. Déploiement

- [ ] `python manage.py migrate`
- [ ] Lire la sortie de `classes.0004` — noter les classes « à valider »
- [ ] `python manage.py collectstatic --noinput`
- [ ] `npm run build`
- [ ] Redémarrer backend, Celery, Celery Beat
- [ ] `python manage.py check --deploy`

---

## 3. Visioconférence

- [ ] `JITSI_APP_ID` et `JITSI_APP_SECRET` présents côté backend **et**
      côté pile Jitsi, avec la **même** valeur
- [ ] `make jitsi-health JITSI_TARGET=meet.globalfeba.com` → **OPÉRATIONNEL**,
      les 9 contrôles au vert
- [ ] **Adhésion anonyme refusée** : ouvrir
      `https://meet.globalfeba.com/salle-test-xyz` sans passer par FEBA.
      L'accès doit être **refusé**
- [ ] `nc -vzu 89.167.63.1 10000` depuis un réseau externe
- [ ] Certificat TLS : renouvellement ACME en place

---

## 4. Vérifications fonctionnelles

### FEBA FHA

- [ ] Classe **francophone** → Matières → 4 FR, 0 EN → **s'enregistre**
- [ ] Aucun message réclamant une matière anglaise
- [ ] Colonne anglaise grisée et non cochable
- [ ] Recharger la page : les matières sont toujours là
- [ ] Classe **anglophone** → symétrique
- [ ] Classe **bilingue** → exige les deux langues
- [ ] Bulletin francophone : **aucune** partie anglaise
- [ ] Bulletin anglophone : **aucune** partie française
- [ ] Bulletin bilingue : les deux parties et la moyenne bilingue
- [ ] Salles virtuelles : le menu « Classe » propose les classes FHA
- [ ] « Rejoindre » ouvre un **nouvel onglet**, plein écran, sans layout FEBA
- [ ] Un élève d'une autre classe reçoit un refus **expliqué**

### FEBA — non-régression

- [ ] Connexion administrateur
- [ ] Classes, notes, bulletins **inchangés**
- [ ] Une classe FEBA exige toujours français **et** anglais
- [ ] Aucune classe FEBA n'a changé de parcours

---

## 5. Après

- [ ] Surveiller les journaux 30 minutes
- [ ] Vérifier les incidents techniques dans l'administration
- [ ] **Réunion réelle à deux participants** (§32)
- [ ] **Session de 30 minutes** (§33)

Les deux derniers points sont ceux que l'environnement de développement ne
peut pas trancher — voir `KNOWN_LIMITATIONS.md`.

---

## 6. En cas de retour arrière

```bash
python manage.py migrate classes 0002
python manage.py migrate schools 0015
python manage.py migrate virtualclass 0002
```

Puis restaurer la sauvegarde si des données ont été modifiées entre-temps.
