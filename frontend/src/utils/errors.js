/**
 * utils/errors.js — FEBA v29.2
 *
 * Normalise les réponses d'erreur DRF en un message lisible.
 *
 * DRF peut renvoyer :
 *   - { "email": ["Cette adresse email est déjà utilisée."] }
 *   - { "non_field_errors": ["Les mots de passe ne correspondent pas."] }
 *   - { "detail": "Identifiants incorrects." }
 *   - { "password": ["Ce mot de passe est trop court."] }
 *   - "Une erreur s'est produite."   ← string brute
 *
 * extractApiError(axiosError) → string toujours non vide et lisible.
 *
 * UTILISATION :
 *   import { extractApiError } from "../../utils/errors";
 *   onError: (e) => toast.error(extractApiError(e))
 */

const FIELD_LABELS = {
  email:      "Email",
  password:   "Mot de passe",
  password2:  "Confirmation du mot de passe",
  username:   "Nom d'utilisateur",
  first_name: "Prénom",
  last_name:  "Nom",
  role:       "Rôle",
  school:     "Établissement",
  phone:      "Téléphone",
  amount:     "Montant",
  student:    "Élève",
  school_year:"Année scolaire",
  class_obj:  "Classe",
};

/**
 * Extrait le premier message d'erreur compréhensible.
 * @param {Error|AxiosError} axiosError
 * @param {string} [fallback="Une erreur inattendue s'est produite."]
 * @returns {string}
 */
export function extractApiError(axiosError, fallback = "Une erreur inattendue s'est produite.") {
  if (!axiosError) return fallback;

  // Erreur réseau (pas de réponse HTTP)
  if (!axiosError.response) {
    if (axiosError.message?.includes("Network Error"))
      return "Impossible de joindre le serveur. Vérifiez votre connexion réseau.";
    if (axiosError.message?.includes("timeout"))
      return "La requête a expiré. Réessayez dans quelques instants.";
    return axiosError.message || fallback;
  }

  const status = axiosError.response.status;
  const data   = axiosError.response.data;

  // Erreurs HTTP communes
  if (status === 401) return "Votre session a expiré. Reconnectez-vous.";
  if (status === 403) return "Vous n'avez pas la permission d'effectuer cette action.";
  if (status === 404) return "La ressource demandée est introuvable.";
  if (status === 429) return "Trop de tentatives. Attendez quelques secondes avant de réessayer.";
  if (status >= 500)  return "Erreur interne du serveur. L'équipe technique a été notifiée.";

  if (!data) return fallback;

  // String brute
  if (typeof data === "string") return data || fallback;

  // { detail: "..." }
  if (typeof data.detail === "string") return data.detail;

  // { non_field_errors: ["..."] }
  if (Array.isArray(data.non_field_errors) && data.non_field_errors.length > 0) {
    return String(data.non_field_errors[0]);
  }

  // { error: "..." }  ← format FEBA views
  if (typeof data.error === "string") return data.error;

  // { email: ["..."], password: ["..."], ... }  ← format DRF field errors
  if (typeof data === "object") {
    for (const [field, messages] of Object.entries(data)) {
      const msg  = Array.isArray(messages) ? messages[0] : messages;
      const label = FIELD_LABELS[field];
      if (msg && typeof msg === "string") {
        return label ? `${label} : ${msg}` : String(msg);
      }
    }
  }

  return fallback;
}

/**
 * Extrait TOUS les messages d'erreur sous forme de tableau.
 * Utile pour afficher une liste d'erreurs sous un formulaire.
 * @param {Error|AxiosError} axiosError
 * @returns {string[]}
 */
export function extractApiErrors(axiosError) {
  if (!axiosError?.response?.data) return [extractApiError(axiosError)];
  const data = axiosError.response.data;
  const errors = [];

  if (typeof data === "string") return [data];
  if (typeof data.detail === "string") return [data.detail];
  if (Array.isArray(data.non_field_errors))
    return data.non_field_errors.map(String);

  if (typeof data === "object") {
    for (const [field, messages] of Object.entries(data)) {
      const msgs = Array.isArray(messages) ? messages : [messages];
      const label = FIELD_LABELS[field];
      for (const msg of msgs) {
        if (msg && typeof msg === "string") {
          errors.push(label ? `${label} : ${msg}` : String(msg));
        }
      }
    }
  }
  return errors.length > 0 ? errors : [extractApiError(axiosError)];
}
