# Audit de sécurité — livraison FEBA

Portée : les correctifs de cette livraison et l'audit transversal demandé.
Les limites de profondeur sont énoncées en section 6 — un audit qui tait
ce qu'il n'a pas regardé n'est pas un audit.

---

## 1. Constats corrigés dans cette livraison

### 1.1 `CSRF_TRUSTED_ORIGINS` absent — **bloquant en production**

| | |
|---|---|
| **Gravité** | Élevée (indisponibilité, pas fuite) |
| **Où** | `backend/feba_project/settings/prod.py` |
| **Statut** | **Corrigé** |

Depuis Django 4, un POST portant un en-tête `Origin` est refusé si cette
origine n'est pas déclarée. Le réglage était **absent**.

Ce qui rendait le défaut invisible : l'API s'authentifie par jeton JWT,
sans cookie de session — elle n'est donc pas concernée. Tout fonctionnait.
Le seul symptôme apparaissait au moment le plus gênant : un administrateur
tentant de se connecter à `/django-admin/`, exposé par
`nginx/nginx.prod.conf`, était rejeté avec un message parlant d'« origin
checking », qui ne désigne pas sa cause.

**Correction.** Le réglage est lu depuis l'environnement et, à défaut,
dérivé d'`ALLOWED_HOSTS` en `https://` — pour qu'une installation
existante qui met simplement le code à jour ne se retrouve pas avec un
back-office inaccessible. `SESSION_COOKIE_SAMESITE` et
`CSRF_COOKIE_SAMESITE` sont fixés à `Lax`.

**Preuve.** `backend/tests/test_production_settings.py` charge le vrai
module de production. Retirer le correctif fait échouer 5 tests.

### 1.2 Un fichier statique absent répondait `HTTP 200`

| | |
|---|---|
| **Gravité** | Moyenne (intégrité de la livraison) |
| **Où** | `frontend/nginx.prod.conf`, `nginx/nginx.prod.conf` |
| **Statut** | **Corrigé pour le flyer** |

Constaté **sur le site en ligne** :

```
curl -sSI https://globalfeba.com/images/feba-fha/definitely-not-here.pdf
→ HTTP/2 200 ; content-type: text/html
```

La règle `try_files $uri $uri/ /index.html` du SPA renvoie la page de
l'application pour **toute** URL inconnue, y compris un fichier. Un
document manquant passe donc pour un document servi : un lien de
téléchargement cassé ne se signale jamais, ni au visiteur, ni à la
supervision, ni à un test qui se contenterait du code HTTP.

**Correction.** Le flyer est servi par une `location` exacte avec
`try_files $uri =404`, un `Content-Type: application/pdf` explicite et un
`Content-Disposition: attachment`. Vérifié : présent → `200 application/pdf` ;
retiré → `404`.

**Reste à faire.** Les autres chemins statiques conservent le
comportement d'origine. Une règle générale (`location /images/`,
`location /assets/`) serait souhaitable ; elle n'a pas été posée dans
cette livraison pour ne pas modifier le service de fichiers qui
fonctionne aujourd'hui. Consigné en limitation.

### 1.3 Instances de visioconférence publiques proposées par défaut

| | |
|---|---|
| **Gravité** | Élevée — protection des mineurs |
| **Où** | `.env.example`, `.env.dev.example`, `.env.prod.example` |
| **Statut** | **Corrigé** |

Le code refusait déjà `meet.jit.si` (`JITSI_FORBIDDEN_DOMAINS`). Les trois
modèles de configuration livrés le proposaient pourtant comme valeur par
défaut — **`.env.prod.example` compris**. Une installation faite en
copiant le modèle, comme la documentation l'indique, produisait une
configuration que le backend rejette, et dirigeait la personne qui
l'exploite vers une instance publique.

Sur une instance publique, les cours de mineurs transitent chez un tiers
et **toute personne connaissant le nom d'une salle y entre** — sans
compte, sans invitation, sans trace.

**Correction.** Les modèles visent `meet.globalfeba.com`. Le modèle de
développement est **vide** : il n'existe aucun repli, y compris en
développement. Les mentions restantes sont des commentaires qui expliquent
l'interdiction.

**Preuve.** `test_jitsi_production_domain.py` analyse les affectations des
fichiers livrés (commentaires exclus) ; `scripts/jitsi_config_check.sh`
refait le contrôle avant chaque démarrage de production.

---

## 2. Cloisonnement entre académies — vérifié

Testé **en navigateur réel**, contre backend Django et PostgreSQL
(parcours 5) :

| Contrôle | Résultat |
|---|---|
| Chaque académie voit ses élèves | FEBA 30 · FHA 3 |
| Un élève visible des deux | **aucun** |
| **IDOR** : un admin FEBA demande un élève FHA par son identifiant | **HTTP 404** |
| Salles virtuelles partagées | **aucune** |

Le `404` (plutôt qu'un `403`) est le bon choix : un `403` confirmerait
l'existence de la ressource.

Contrôles d'accès aux salles (`assert_can_join`) : académie de la salle,
fonctionnalité activée, compte actif, salle active, appartenance à la
classe pour élèves et parents. Un superadmin ne franchit pas la frontière
non plus — son académie active est comparée à celle de la salle.

---

## 3. Jetons de visioconférence

| Propriété | État |
|---|---|
| Signature | HS256, secret connu du seul backend |
| Durée de vie | 900 s (15 min) — vérifié |
| Jeton expiré rejeté | vérifié (`ExpiredSignatureError`) |
| Salle nommée dans le jeton (`room`) | vérifié — non rejouable ailleurs |
| Émission sans configuration complète | **refusée** (`JitsiNotConfigured`) |
| Repli vers une instance publique | **aucun** — HTTP 503 explicite |
| `JWT_ALLOW_EMPTY=0` côté Prosody | imposé par la surcouche de production |

Un jeton intercepté n'ouvre ni une autre salle, ni un accès durable.

---

## 4. Identité institutionnelle

Le numéro imprimé sur les documents ne provient plus d'une colonne
administrable par entité (`School.phone`) mais d'une source unique
(`apps/schools/institution.py`). Conséquences de sécurité :

- une saisie erronée — ou malveillante — dans l'écran « Paramètres » ne
  peut plus modifier ce qui figure sur une pièce officielle ;
- un numéro retiré du service ne peut pas être remis en circulation, même
  par variable d'environnement : `official_phone()` le refuse ;
- la détection est insensible à la mise en forme : `01 96 69 73 63`,
  `01.96.69.73.63` et `+229 0196697363` sont reconnus comme le même
  abonné. Un audit qui ne chercherait que la forme compacte déclarerait
  propre un document où le numéro est simplement espacé.

---

## 5. Contrôles transverses

| Point | État |
|---|---|
| Secrets dans le dépôt | **aucun** — seuls des modèles `.env.*.example` |
| `.env`, `.env.prod`, `.env.jitsi` ignorés par Git | oui |
| `DEBUG` en production | `False`, imposé par le module |
| `ALLOWED_HOSTS` | sans `*` ; vérifié par test |
| HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` | présents (Django + Nginx) |
| Cookies `Secure` + `SameSite=Lax` | oui |
| `SECURE_PROXY_SSL_HEADER` | présent — sans lui, boucle de redirection |
| Limitation de débit sur la connexion | 20/min par IP (observée à l'usage) |
| Téléversements | type MIME **réel** vérifié, pas l'extension |
| Fichiers privés | servis par une vue authentifiée, jamais par URL publique |
| Documents d'une académie émis sous l'identité d'une autre | refusé (`BrandingUnavailable`) |

---

## 6. Ce que cet audit n'a PAS couvert

À lire comme faisant partie du résultat :

- **Pas de test d'intrusion.** Aucune tentative d'exploitation active
  (injection, élévation de privilèges, désérialisation).
- **Pas de revue endpoint par endpoint** des permissions objet. Le
  cloisonnement a été vérifié sur les élèves et les salles ; les autres
  ressources reposent sur le même mécanisme (`academy_scope`) sans avoir
  été exercées une à une.
- **Pas d'analyse des dépendances.** Ni `pip-audit`, ni `npm audit` : sans
  accès aux bases de vulnérabilités, un résultat partiel serait trompeur.
- **Pas d'audit des flux de paiement par carte.** Stripe est intégré et
  couvert par des tests fonctionnels ; la conformité PCI et la gestion des
  remboursements n'ont pas été revues.
- **Pas de vérification d'un appel Jitsi réel.** L'infrastructure n'existe
  pas encore (voir `MANUAL_PRODUCTION_ACTIONS.md`). Le chiffrement de bout
  en bout des médias et la configuration TURN restent à valider sur le
  serveur.
- **Pas d'inspection des fonds d'image** des certificats et diplômes. Un
  numéro incrusté en pixels échapperait à tout test textuel — c'est
  exactement ainsi que trois fuites d'identité ont échappé aux contrôles
  lors de livraisons précédentes.
