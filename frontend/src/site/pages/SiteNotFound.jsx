/** 404 publique du site vitrine. */
import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import Seo from "../components/Seo";
import { useSiteLang } from "../useSiteLang";

export default function SiteNotFound() {
  const { t } = useSiteLang();
  return (
    <>
      <Seo title={t("Page introuvable", "Page not found")}
        description={t("La page demandée n'existe pas ou a été déplacée.", "The page you requested does not exist or has been moved.")} />
      <div className="min-h-[55vh] flex items-center justify-center px-4 py-20">
        <div className="text-center max-w-md">
          <Compass className="w-14 h-14 text-feba-gold mx-auto mb-5" aria-hidden="true" />
          <p className="text-feba-gold font-bold text-5xl">404</p>
          <h1 className="text-xl font-bold text-feba-navy mt-3">{t("Page introuvable", "Page not found")}</h1>
          <p className="text-sm text-feba-gray mt-3">
            {t(
              "La page que vous cherchez n'existe pas ou a été déplacée.",
              "The page you are looking for does not exist or has been moved.",
            )}
          </p>
          <div className="flex flex-wrap gap-3 justify-center mt-7">
            <Link to="/" className="px-5 py-2.5 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors">
              {t("Retour à l'accueil", "Back to home")}
            </Link>
            <Link to="/contact" className="px-5 py-2.5 rounded-xl border border-feba-navy/30 text-feba-navy font-bold text-sm hover:bg-feba-navy/5 transition-colors">
              {t("Contacter FEBA", "Contact FEBA")}
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
