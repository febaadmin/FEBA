/** Mentions légales, politique de confidentialité et 404 publique. */
import Seo from "../components/Seo";
import { Section, PageBanner } from "../components/SiteSection";
import { useSiteSettings } from "../SiteLayout";

export function LegalPage() {
  const settings = useSiteSettings();
  return (
    <>
      <Seo title="Mentions légales" description="Mentions légales du site de Faith Excellence Bilingual Academy." />
      <PageBanner title="Mentions légales" />
      <Section tone="white">
        <div className="max-w-3xl mx-auto space-y-6 text-sm leading-relaxed">
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">Éditeur du site</h2>
            <p>
              {settings.school_name || "Faith Excellence Bilingual Academy"} (FEBA),
              établissement scolaire bilingue situé à {settings.address || "Akpakpa, Cotonou, Bénin"}.
              {settings.email && <> Contact : <a className="text-feba-navy font-semibold hover:text-feba-gold" href={`mailto:${settings.email}`}>{settings.email}</a>.</>}
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">Contenus</h2>
            <p>
              L'ensemble des textes, photographies et vidéos de ce site est la
              propriété de FEBA. Toute reproduction sans autorisation préalable
              est interdite. Les informations complémentaires (immatriculation,
              hébergeur) sont renseignées par l'administration de l'école dans
              cette page dès qu'elles sont disponibles.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}

export function PrivacyPage() {
  return (
    <>
      <Seo title="Politique de confidentialité"
        description="Politique de confidentialité du site de Faith Excellence Bilingual Academy." />
      <PageBanner title="Politique de confidentialité" />
      <Section tone="white">
        <div className="max-w-3xl mx-auto space-y-6 text-sm leading-relaxed">
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">Données collectées</h2>
            <p>
              Les formulaires de contact et de préinscription collectent
              uniquement les informations nécessaires au traitement de votre
              demande (identité, coordonnées, informations sur l'enfant pour la
              préinscription). Aucune donnée n'est vendue ni transmise à des tiers.
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">Utilisation</h2>
            <p>
              Ces informations sont accessibles uniquement à l'administration de
              l'école, pour répondre à votre demande et assurer le suivi des
              admissions. Vous pouvez demander leur consultation, leur
              rectification ou leur suppression en contactant l'école.
            </p>
          </div>
          <div>
            <h2 className="font-bold text-feba-navy text-lg mb-2">Cookies</h2>
            <p>
              Le site public n'utilise pas de cookies de suivi publicitaire.
              Seuls des stockages techniques (préférences d'affichage,
              session de l'espace utilisateurs) sont utilisés.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
