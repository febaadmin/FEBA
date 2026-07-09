import { FileText, X, Calendar, User } from "lucide-react";

/**
 * Reusable modal to display an announcement detail with attachment.
 * Usage: <AnnouncementModal announcement={obj} onClose={() => setSelected(null)} />
 */
export default function AnnouncementModal({ announcement, onClose }) {
  if (!announcement) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-100">
          <div className="flex-1 min-w-0 pr-4">
            <h2 className="font-bold text-slate-800 text-lg leading-snug">{announcement.title}</h2>
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Calendar className="w-3 h-3" />
                {announcement.created_at?.slice(0,10)}
              </span>
              {(announcement.author?.first_name || announcement.author_name) && (
                <span className="flex items-center gap-1 text-xs text-slate-400">
                  <User className="w-3 h-3" />
                  {announcement.author?.first_name} {announcement.author?.last_name}
                </span>
              )}
              {(announcement.target_roles || []).map(r => (
                <span key={r} className="text-xs px-2 py-0.5 rounded-full bg-primary-50 text-primary font-medium">{r}</span>
              ))}
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 shrink-0 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">
            {announcement.content}
          </div>
        </div>

        {/* Attachment */}
        {announcement.has_attachment && announcement.attachment && (
          <div className="p-5 border-t border-slate-100">
            <a
              href={announcement.attachment}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 bg-primary-50 text-primary px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-primary-100 transition-colors"
            >
              <FileText className="w-4 h-4" />
              {announcement.attachment_name || "Télécharger la pièce jointe"}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
