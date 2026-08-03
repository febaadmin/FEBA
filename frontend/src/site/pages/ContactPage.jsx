/** Contact — coordonnées administrables + formulaire public. */
import { Mail, MapPin, MessageCircle, Phone, Clock } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section, PageBanner } from "../components/SiteSection";
import { ContactForm } from "../components/PublicForms";
import { useSiteSettings } from "../SiteLayout";
import { useSiteLang } from "../useSiteLang";

export default function ContactPage() {
  const { t } = useSiteLang();
  const settings = useSiteSettings();
  const hasCoords = settings.phone || settings.email || settings.address || settings.opening_hours;

  return (
    <>
      <Seo title={t("Contact", "Contact")}
        description={t(
          "Contactez FEBA à Akpakpa, Cotonou : demande d'informations, rendez-vous ou visite de l'école.",
          "Contact FEBA in Akpakpa, Cotonou: information requests, appointments or a school visit.",
        )} />
      <PageBanner title={t("Contactez-nous", "Contact us")}
        intro={t(
          "Une question, une visite, une inscription : notre équipe vous répond.",
          "A question, a visit, an enrolment: our team will get back to you.",
        )}
        image="/site/img/contact-administration-1600.webp" />

      <Section tone="white">
        <div className="grid lg:grid-cols-5 gap-10 items-start">
          <div className="lg:col-span-2 space-y-6">
            <SiteImage src="/site/img/contact-accueil-1600.webp" alt={t("L'accueil de FEBA", "The FEBA reception")}
              sizes="(min-width:1024px) 40vw, 100vw" className="rounded-2xl shadow-lg object-cover w-full h-64" />
            {hasCoords ? (
              <ul className="space-y-4 text-sm">
                {settings.address && (
                  <li className="flex gap-3">
                    <MapPin className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">{t("Adresse", "Address")}</strong>{settings.address}</span>
                  </li>
                )}
                {settings.phone && (
                  <li className="flex gap-3">
                    <Phone className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">{t("Téléphone", "Phone")}</strong>
                      <a href={`tel:${settings.phone.replace(/\s/g, "")}`} className="hover:text-feba-gold">{settings.phone}</a>
                    </span>
                  </li>
                )}
                {settings.email && (
                  <li className="flex gap-3">
                    <Mail className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">{t("Email", "Email")}</strong>
                      <a href={`mailto:${settings.email}`} className="hover:text-feba-gold">{settings.email}</a>
                    </span>
                  </li>
                )}
                {settings.opening_hours && (
                  <li className="flex gap-3">
                    <Clock className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">{t("Horaires", "Opening hours")}</strong>{settings.opening_hours}</span>
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-sm text-feba-gray">
                {t(
                  "Les coordonnées détaillées seront publiées prochainement. En attendant, utilisez le formulaire ci-contre.",
                  "Full contact details will be published shortly. In the meantime, please use the form opposite.",
                )}
              </p>
            )}
            {settings.whatsapp && (
              <a href={`https://wa.me/${settings.whatsapp.replace(/[^0-9]/g, "")}`}
                target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-feba-green text-white font-bold text-sm hover:bg-feba-green2 transition-colors">
                <MessageCircle className="w-4 h-4" aria-hidden="true" /> {t("Écrire sur WhatsApp", "Message us on WhatsApp")}
              </a>
            )}
          </div>
          <div className="lg:col-span-3 rounded-3xl bg-feba-cream shadow-xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-feba-navy mb-1">
              {t("Envoyez-nous un message", "Send us a message")}
            </h2>
            <p className="text-sm text-feba-gray mb-6">
              {t(
                "Les champs marqués d'un astérisque (*) sont obligatoires.",
                "Fields marked with an asterisk (*) are required.",
              )}
            </p>
            <ContactForm />
          </div>
        </div>
      </Section>
    </>
  );
}
