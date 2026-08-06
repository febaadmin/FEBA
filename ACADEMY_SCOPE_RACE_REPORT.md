# ACADEMY_SCOPE_RACE_REPORT — tableau de bord Super Admin à zéro après actualisation

**Priorité absolue n°1.** Statut : **corrigé, prouvé par test automatisé.**

## 1. Symptôme rapporté

Sur `/superadmin/dashboard`, le premier chargement affichait les bons
chiffres. Après `Cmd+R`, tous les compteurs tombaient à `0` — Total
utilisateurs, Administrateurs, Enseignants, Parents, Élèves, Comptes actifs —
et la répartition des rôles se vidait. Les données ne revenaient qu'après
sélection manuelle d'une académie ou de « Toutes les Académies ». Le sélecteur
pouvait afficher « Toutes les Académies » alors que la portée effective
n'était pas initialisée.

## 2. Reproduction — VÉRIFIÉ PAR TEST AUTOMATISÉ

Le scénario est reproduit dans `frontend/src/context/academyBoot.test.jsx`.
Exécutés contre le code d'origine, quatre tests échouent :

```
× n'appelle pas /auth/users/ tant que /auth/entity-context/ n'a pas répondu
× applique la portée AVANT d'autoriser la requête métier
× reste en attente — sans afficher 0 — quand la requête est annulée
× affiche une attente explicite tant que la portée n'est pas prête
```

Contre le code corrigé, les 10 tests du module passent. La correction est donc
établie par différence observable, pas par relecture.

## 3. Cause racine

Un enchaînement de cinq maillons, dont aucun n'est fautif isolément.

1. **Aucun garde de démarrage.** `AcademyScopedOutlet` rendait `<Outlet/>`
   immédiatement. Les écrans métier se montaient donc pendant que
   `/auth/entity-context/` était encore en vol.
2. **Requêtes émises sous portée indéterminée.** L'intercepteur axios
   annonçait `X-Academy-Scope: UNKNOWN` et enregistrait un `AbortController`
   dans le registre des requêtes en vol.
3. **La résolution du contexte avortait ces requêtes.** À l'arrivée du
   contexte, `setAcademyScope("ALL")` détectait un changement
   `UNKNOWN → ALL` et appelait `abortInflightRequests()` — qui annulait
   précisément la requête `/auth/users/` du tableau de bord.
4. **Aucune reprise.** `main.jsx` fixe `retry: false` pour `ERR_CANCELED`
   (choix délibéré et correct). La requête annulée ne repartait donc jamais.
5. **`undefined` replié sur `[]`.** Le tableau de bord faisait
   `data?.data?.results || data?.data || []`. Une donnée absente devenait un
   tableau vide, et six compteurs à `0` — crédibles, et faux.

### Pourquoi le remontage ne rattrapait rien

`AcademyScopedOutlet` remonte le sous-arbre via `key={academyKey}`. On
pourrait croire que le passage `academy:UNKNOWN → academy:ALL` relance la
requête. Il n'en est rien, à cause de l'ordre React :

```
rendu (nouvelle clé) → démontage/remontage des écrans → effets → abort
```

Le remontage a lieu AVANT l'annulation. Le nouvel observateur s'attache à une
requête encore en vol, qui est ensuite annulée : `retryOnMount` ne peut plus
jouer, aucun nouveau montage ne survient. L'écran reste à zéro.

### Pourquoi le premier chargement fonctionnait

Après un login, la navigation vers le tableau de bord intervient une fois le
contexte déjà résolu : la portée est posée, aucune annulation. Le `Cmd+R`
monte tout simultanément et ouvre la fenêtre de course. D'où un bug qui ne se
manifeste qu'au rechargement — exactement ce qui était décrit.

### Pourquoi une sélection manuelle réparait l'écran

`switchAcademy` appelle `queryClient.removeQueries()`. L'entrée en erreur est
supprimée, la requête repart avec une portée définie, les chiffres reviennent.

## 4. Correction

### 4.1 Cycle de démarrage explicite

`AcademyContext.jsx` expose une machine d'états
(`APP_BOOTING → AUTH_HYDRATING → … → BUSINESS_DATA_ENABLED`) et trois
drapeaux : `authReady`, `scopeReady`, `businessDataEnabled`.

L'hydratation de `zustand-persist` est désormais attendue (`_hasHydrated`) :
interroger le contexte pendant le tick où `accessToken` est encore `null`
produisait un 401 puis une portée durablement fausse.

### 4.2 Synchronisation pendant le rendu, pas dans un effet

```js
const scopeResolved = hasHydrated && isAuthenticated && isSuccess;
if (scopeResolved) setAcademyScope(academyScope);
const scopeReady = scopeResolved && getAcademyScope() === academyScope;
```

Un effet s'exécute après le commit : il subsisterait un rendu où le contexte
est connu mais la portée pas encore appliquée — la fenêtre même du bug. Le
corps d'un composant parent s'exécutant toujours avant celui de ses enfants,
la portée est posée avant le premier rendu d'un écran métier.
`setAcademyScope` est idempotent, ce qui rend l'opération sûre sous
StrictMode.

### 4.3 Garde de portée

`AcademyScopedOutlet` ne monte plus aucun écran métier tant que
`scopeReady !== true`. Il affiche un état d'attente explicite, et un message
d'erreur si la portée est introuvable — jamais des zéros. **Aucune requête
métier ne peut plus partir sous une portée indéterminée**, ce qui supprime la
cause plutôt que ses effets.

### 4.4 Le tableau de bord ne fabrique plus de zéro

```js
const loaded  = Boolean(data);
const users   = loaded ? data?.data?.results || data?.data || [] : null;
const canceled = isCanceledError(error);
```

Trois états distincts : en attente, en erreur, chargé. Une requête annulée
(`ERR_CANCELED`, `CanceledError`, `AbortError`, réponse périmée) conserve
l'état d'attente et **ne vide jamais l'écran**. La clé de requête inclut la
portée (`["all-users", academyKey]`), et `enabled: businessDataEnabled` ajoute
une seconde barrière indépendante du garde amont.

### 4.5 Génération de portée

`academyScope.js` expose `getScopeGeneration()`, incrémenté à chaque
changement de portée, pour permettre à tout appelant asynchrone de rejeter une
réponse périmée sans dépendre de l'annulation ni d'un en-tête serveur.

### 4.6 Déduplication de `entity-context`

`fetchEntityContext()` partage une promesse unique : n appels concurrents ne
produisent qu'une requête réseau. Complète la déduplication par clé de React
Query, qui ne couvre pas les appels hors React Query.

### 4.7 Nettoyage à la déconnexion

`logout` purge le cache React Query, avorte les requêtes en vol et remet la
portée à `UNKNOWN`. `login` remet également la portée à zéro : aucune donnée
de la session précédente ne peut survivre.

## 5. Interdictions respectées

| Interdiction | Respect |
|---|---|
| `setTimeout` arbitraire | aucun — la correction est un ordre garanti |
| Retry silencieux | aucun ajout ; `retry: false` sur annulation conservé |
| `ALL` forcé pour tous les rôles | non — la portée vient toujours du serveur |
| Suppression de contrôles backend | aucune modification du backend |
| Tableau vidé sur annulation | supprimé, et verrouillé par test |
| Faux zéro en attente | supprimé, et verrouillé par test |

## 6. Tests

`frontend/src/context/academyBoot.test.jsx` — 10 tests, tous passants :

| # | Test | Couvre |
|---|---|---|
| 1 | pas de `/auth/users/` avant `entity-context` | ordre de démarrage |
| 2 | portée appliquée avant la requête métier | jamais de requête sous UNKNOWN |
| 3 | chiffres réels en portée `ALL` | actualisation ALL |
| 4 | chiffres réels en portée `FEBA` | actualisation FEBA |
| 5 | chiffres réels en portée `FEBA_FHA` | actualisation FEBA_FHA |
| 6 | requête annulée → pas de zéro | rétention sur annulation |
| 7 | dix actualisations consécutives | stabilité |
| 8 | attente explicite tant que la portée n'est pas prête | garde |
| 9 | appels concurrents → une seule requête | déduplication |
| 10 | requête relancée après résolution | pas de blocage du verrou |

Suite frontend complète : **179 tests passants** (163 d'origine + 16 ajoutés).

## 7. Ce qui n'a pas été vérifié

- **VALIDATION DOCKER LOCALE REQUISE** : le scénario n'a pas été rejoué dans
  un navigateur réel contre la pile Docker. Les statuts Nginx `499`
  mentionnés dans la demande sont la trace réseau des annulations décrites
  ci-dessus ; ils doivent disparaître puisque les requêtes annulées au
  démarrage ne sont plus émises, mais cela reste à confirmer par observation.
- Les rôles Admin, Enseignant, Parent et Élève bénéficient du même garde
  (il est appliqué au niveau du sous-arbre routé, pas du tableau de bord),
  mais leur non-régression est couverte par les tests d'isolation backend
  existants, pas par de nouveaux tests frontend dédiés.
