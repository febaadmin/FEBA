/** 404 publique du site vitrine. */
import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import Seo from "../components/Seo";

export default function SiteNotFound() {
  return (
    <>
      <Seo title="Page introuvable" description="La page demandée n'existe pas ou a été déplacée." />
      <div className="min-h-[55vh] flex items-center justify-center px-4 py-20">
        <div className="text-center max-w-md">
          <Compass className="w-14 h-14 text-feba-gold mx-auto mb-5" aria-hidden="true" />
          <p className="text-feba-gold font-bold text-5xl">404</p>
          <h1 className="text-xl font-bold text-feba-navy mt-3">Page introuvable</h1>
          <p className="text-sm text-feba-gray mt-3">
            La page que vous cherchez n'existe pas ou a été déplacée.
          </p>
          <div className="flex flex-wrap gap-3 justify-center mt-7">
            <Link to="/" className="px-5 py-2.5 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors">
              Retour à l'accueil
            </Link>
            <Link to="/contact" className="px-5 py-2.5 rounded-xl border border-feba-navy/30 text-feba-navy font-bold text-sm hover:bg-feba-navy/5 transition-colors">
              Contacter FEBA
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
