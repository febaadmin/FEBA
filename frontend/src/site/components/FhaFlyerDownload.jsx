/**
 * FhaFlyerDownload — lien « Voir le détail des formules ».
 *
 * CE QU'IL CORRIGE
 * ----------------
 * Sur le formulaire d'inscription FEBA FHA, ce libellé était un
 * `<Link to="/feba-fha">` : un clic quittait le formulaire pour la page
 * de présentation. Deux conséquences, la seconde plus grave que la
 * première :
 *
 *   1. l'utilisateur n'obtenait pas le détail des formules, mais une page
 *      entière à parcourir pour le retrouver ;
 *   2. il PERDAIT sa saisie en cours — le formulaire d'inscription est
 *      long (identité, parents, consentements) et n'est pas remonté au
 *      retour. Un parent à mi-parcours qui vérifie un tarif recommence
 *      tout.
 *
 * Le détail des formules existe déjà, complet et officiel : la section 6
 * du flyer (« Nos formules annuelles » — Standard, Premium, Excellence).
 * Le lien la DONNE au lieu d'y renvoyer.
 *
 * POURQUOI UN `<a download>` ET PAS UN `<Link>`
 * ---------------------------------------------
 * Le fichier est servi statiquement depuis `public/`. Un `<Link>` du
 * routeur intercepterait la navigation et laisserait le SPA répondre
 * « route inconnue » au lieu de laisser le navigateur télécharger.
 *
 * `download` porte le nom de fichier voulu. Les navigateurs qui l'ignorent
 * (certains mobiles) reçoivent malgré tout un `Content-Disposition:
 * attachment` posé par Nginx sur ce chemin (voir nginx/nginx.prod.conf) :
 * le téléchargement a donc deux garanties indépendantes, l'une côté
 * client, l'autre côté serveur.
 */
import { FHA_FLYER_DOWNLOAD_NAME, FHA_FLYER_PDF_PATH } from "../fhaPlans";

export default function FhaFlyerDownload({ lang = "fr", className = "", children }) {
  const label =
    children ??
    (lang === "fr" ? "Voir le détail des formules" : "See full plan details");

  return (
    <a
      href={FHA_FLYER_PDF_PATH}
      download={FHA_FLYER_DOWNLOAD_NAME}
      className={className}
      data-testid="fha-flyer-download"
      // `rel` sans `target` : le téléchargement se fait dans l'onglet
      // courant, donc sans perdre la saisie du formulaire en cours.
      rel="noopener"
    >
      {label}
    </a>
  );
}
