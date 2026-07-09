import { motion } from "framer-motion";

export default function PageHeader({ title, subtitle, action }) {
  return (
    <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }}
      className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="text-slate-500 text-sm mt-1">{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </motion.div>
  );
}