import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useBranding } from "../hooks/useBranding";
import toast from "react-hot-toast";
import logoFeba from "../assets/logo_feba.jpeg";

const schema = z.object({
  email: z.string().email("Email invalide"),
  password: z.string().min(4, "Mot de passe requis"),
});

export default function LoginPage() {
  const [showPwd, setShowPwd] = useState(false);
  const { login } = useAuth();
  const { logoSrc } = useBranding();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data) => {
    try {
      await login(data.email, data.password);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.response?.data?.[0] || "Identifiants incorrects.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-950 via-blue-900 to-blue-800 flex items-center justify-center p-4">
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-10" style={{
        backgroundImage: "repeating-linear-gradient(45deg, rgba(201,162,39,0.3) 0, rgba(201,162,39,0.3) 1px, transparent 0, transparent 50%)",
        backgroundSize: "20px 20px"
      }} />

      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10">

        {/* Logo + School Name */}
        <div className="text-center mb-8">
          <div className="inline-block mb-4">
            <div className="w-24 h-24 rounded-full overflow-hidden border-4 border-yellow-400 shadow-2xl mx-auto">
              <img src={logoSrc} alt="FEBA Logo" className="w-full h-full object-contain bg-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white mb-1">
            Faith & Excellence Bilingual Academy
          </h1>
          <p className="text-yellow-300 text-sm italic">
            L'école autrement avec vous.
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-bold text-gray-800 mb-1 text-center">Connexion</h2>
          <p className="text-gray-500 text-sm text-center mb-6">Système de Gestion Scolaire</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                {...register("email")}
                type="email"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                placeholder="votre@email.com"
              />
              {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mot de passe</label>
              <div className="relative">
                <input
                  {...register("password")}
                  type={showPwd ? "text" : "password"}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition pr-10"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>}
            </div>

            <button type="submit" disabled={isSubmitting}
              className="w-full bg-blue-800 hover:bg-blue-900 text-white font-semibold py-2.5 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-60">
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {isSubmitting ? "Connexion…" : "Se connecter"}
            </button>
          </form>
        </div>

        <p className="text-center text-blue-300 text-xs mt-6 opacity-70">
          © {new Date().getFullYear()} Faith & Excellence Bilingual Academy — Cotonou, Bénin
        </p>
      </motion.div>
    </div>
  );
}
