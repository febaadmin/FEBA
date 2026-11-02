/**
 * Une écriture identique déjà en cours n'est pas renvoyée : le second appel reçoit la même réponse.
 * Un double clic sur un réseau lent créait sinon deux paiements, deux classes ou deux annonces.
 */
function empreinte(config) {
  const { data } = config;
  const corps = typeof FormData !== "undefined" && data instanceof FormData
    ? JSON.stringify([...data.entries()].map(([cle, valeur]) => [cle, valeur instanceof Blob ? `${valeur.name}:${valeur.size}` : valeur]))
    : String(data ?? "");
  return `${config.method} ${config.baseURL || ""}${config.url} ${corps}`;
}

export function sansDoublon(envoi) {
  const enCours = new Map();
  return (config) => {
    if ((config.method || "get").toLowerCase() === "get") return envoi(config);
    const cle = empreinte(config);
    if (enCours.has(cle)) return enCours.get(cle);
    const reponse = Promise.resolve().then(() => envoi(config)).finally(() => enCours.delete(cle));
    enCours.set(cle, reponse);
    return reponse;
  };
}
