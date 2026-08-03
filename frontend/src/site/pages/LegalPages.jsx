/** Mentions légales, politique de confidentialité et 404 publique. */
import Seo from "../components/Seo";
import { Section, PageBanner } from "../components/SiteSection";
import { useSiteSettings } from "../SiteLayout";
import { useSiteLang } from "../useSiteLang";

export function LegalPage() {
  const { t } = useSiteLang();
  const settings = useSiteSettings();
  return (
    <>
      <Seo title={t("Mentions légales", "Legal notice")}
        description={t(
          "Mentions légales du site de Faith & Excellence Bilingual Academy.",
          "Legal notice for the Faith & Excellence Bilingual Academy website.",
        )} />
      <PageBanner title={t("Mentions légales", "Legal notice")} />
      <Section tone="white">
        <div className="max-w-3xl mx-auto space-y-6 text-sm leading-relaxed">
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">{t("Éditeur du site", "Website publisher")}</h2>
            <p>
              {settings.school_name || "Faith & Excellence Bilingual Academy"} (FEBA),{" "}
              {t("établissement scolaire bilingue situé à", "a bilingual school located in")}{" "}
              {settings.address || "Akpakpa, Cotonou, Bénin"}.
              {settings.email && <> {t("Contact :", "Contact:")} <a className="text-feba-navy font-semibold hover:text-feba-gold" href={`mailto:${settings.email}`}>{settings.email}</a>.</>}
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">{t("Contenus", "Content")}</h2>
            <p>
              {t(
                "L'ensemble des textes, photographies et vidéos de ce site est la propriété de FEBA. Toute reproduction sans autorisation préalable est interdite. Les informations complémentaires (immatriculation, hébergeur) sont renseignées par l'administration de l'école dans cette page dès qu'elles sont disponibles.",
                "All texts, photographs and videos on this site are the property of FEBA. Any reproduction without prior authorisation is prohibited. Additional information (registration number, hosting provider) is added to this page by the school administration as soon as it becomes available.",
              )}
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}

export function PrivacyPage() {
  const { t } = useSiteLang();
  return (
    <>
      <Seo title={t("Politique de confidentialité", "Privacy policy")}
        description={t(
          "Politique de confidentialité du site de Faith & Excellence Bilingual Academy.",
          "Privacy policy for the Faith & Excellence Bilingual Academy website.",
        )} />
      <PageBanner title={t("Politique de confidentialité", "Privacy policy")} />
      <Section tone="white">
        <div className="max-w-3xl mx-auto space-y-6 text-sm leading-relaxed">
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">{t("Données collectées", "Data collected")}</h2>
            <p>
              {t(
                "Les formulaires de contact et de préinscription collectent uniquement les informations nécessaires au traitement de votre demande (identité, coordonnées, informations sur l'enfant pour la préinscription). Aucune donnée n'est vendue ni transmise à des tiers.",
                "The contact and pre-registration forms collect only the information needed to handle your request (identity, contact details, information about the child for pre-registration). No data is sold or passed on to third parties.",
              )}
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">{t("Utilisation", "Use")}</h2>
            <p>
              {t(
                "Ces informations sont accessibles uniquement à l'administration de l'école, pour répondre à votre demande et assurer le suivi des admissions. Vous pouvez demander leur consultation, leur rectification ou leur suppression en contactant l'école.",
                "This information is accessible only to the school administration, in order to answer your request and follow up admissions. You may ask to view, correct or delete it by contacting the school.",
              )}
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">{t("Cookies", "Cookies")}</h2>
            <p>
              {t(
                "Le site public n'utilise pas de cookies de suivi publicitaire. Seuls des stockages techniques (préférences d'affichage, session de l'espace utilisateurs) sont utilisés.",
                "The public website does not use advertising tracking cookies. Only technical storage is used (display preferences, user-area session).",
              )}
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
