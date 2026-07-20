/** Contact — coordonnées administrables + formulaire public. */
import { Mail, MapPin, MessageCircle, Phone, Clock } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section, PageBanner } from "../components/SiteSection";
import { ContactForm } from "../components/PublicForms";
import { useSiteSettings } from "../SiteLayout";

export default function ContactPage() {
  const settings = useSiteSettings();
  const hasCoords = settings.phone || settings.email || settings.address || settings.opening_hours;

  return (
    <>
      <Seo title="Contact"
        description="Contactez FEBA à Akpakpa, Cotonou : demande d'informations, rendez-vous ou visite de l'école." />
      <PageBanner title="Contactez-nous"
        intro="Une question, une visite, une inscription : notre équipe vous répond."
        image="/site/img/contact-administration-1600.webp" />

      <Section tone="white">
        <div className="grid lg:grid-cols-5 gap-10 items-start">
          <div className="lg:col-span-2 space-y-6">
            <SiteImage src="/site/img/contact-accueil-1600.webp" alt="L'accueil de FEBA"
              sizes="(min-width:1024px) 40vw, 100vw" className="rounded-2xl shadow-lg object-cover w-full h-64" />
            {hasCoords ? (
              <ul className="space-y-4 text-sm">
                {settings.address && (
                  <li className="flex gap-3">
                    <MapPin className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">Adresse</strong>{settings.address}</span>
                  </li>
                )}
                {settings.phone && (
                  <li className="flex gap-3">
                    <Phone className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">Téléphone</strong>
                      <a href={`tel:${settings.phone.replace(/\s/g, "")}`} className="hover:text-feba-gold">{settings.phone}</a>
                    </span>
                  </li>
                )}
                {settings.email && (
                  <li className="flex gap-3">
                    <Mail className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">Email</strong>
                      <a href={`mailto:${settings.email}`} className="hover:text-feba-gold">{settings.email}</a>
                    </span>
                  </li>
                )}
                {settings.opening_hours && (
                  <li className="flex gap-3">
                    <Clock className="w-5 h-5 text-feba-gold shrink-0" aria-hidden="true" />
                    <span><strong className="text-feba-navy block">Horaires</strong>{settings.opening_hours}</span>
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-sm text-feba-gray">
                Les coordonnées détaillées seront publiées prochainement.
                En attendant, utilisez le formulaire ci-contre.
              </p>
            )}
            {settings.whatsapp && (
              <a href={`https://wa.me/${settings.whatsapp.replace(/[^0-9]/g, "")}`}
                target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-feba-green text-white font-bold text-sm hover:bg-feba-green2 transition-colors">
                <MessageCircle className="w-4 h-4" aria-hidden="true" /> Écrire sur WhatsApp
              </a>
            )}
          </div>
          <div className="lg:col-span-3 rounded-3xl bg-feba-cream shadow-xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-feba-navy mb-1">Envoyez-nous un message</h2>
            <p className="text-sm text-feba-gray mb-6">
              Les champs marqués d'un astérisque (*) sont obligatoires.
            </p>
            <ContactForm />
          </div>
        </div>
      </Section>
    </>
  );
}
