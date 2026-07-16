/**
 * Messages page — v7
 *
 * Uses the new ConversationViewSet API:
 *   GET  /api/messages/conversations/          → list
 *   GET  /api/messages/conversations/{id}/     → thread detail
 *   POST /api/messages/conversations/          → compose
 *   POST /api/messages/conversations/{id}/reply/ → reply
 *   PUT  /api/messages/conversations/{id}/mark_read/ → mark read
 *
 * UX: single panel — list on left, thread on right.
 */
import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Send, Inbox, MessageSquare, ArrowLeft, Paperclip, X, FileText,
  Download, Plus, CheckCheck,
} from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { conversationsAPI, authAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useAuthStore } from "../../store/authStore";
import { extractApiError } from "../../utils/errors";
import { t, dateLocale } from "../../i18n";

export default function MessagesPage() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  // FIX (redirections notifications) : une notification de message pointe
  // vers "messages?conversation=<id>" — on ouvre directement ce fil au
  // chargement de la page, au lieu de forcer l'utilisateur à le retrouver
  // manuellement dans la liste.
  const [searchParams] = useSearchParams();
  const conversationParam = searchParams.get("conversation");
  const [selectedId, setSelectedId] = useState(conversationParam ? Number(conversationParam) : null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeFile, setComposeFile] = useState(null);
  const [replyFile, setReplyFile] = useState(null);
  const activeThread = !!selectedId; // mobile: true when a conversation is open
  const composeFileRef = useRef();
  const replyFileRef = useRef();
  const messagesEndRef = useRef();

  const composeForm = useForm();
  const replyForm = useForm();

  // List of conversations (polling for near-realtime)
  const { data: convListData, isLoading: listLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: conversationsAPI.list,
    refetchInterval: 8000,
    refetchOnWindowFocus: true,
  });

  // Single conversation (thread detail)
  const { data: threadData } = useQuery({
    queryKey: ["conversation", selectedId],
    queryFn: () => conversationsAPI.get(selectedId),
    enabled: !!selectedId,
    refetchInterval: 5000,
  });

  // Recipients list
  const { data: recipientsData } = useQuery({
    queryKey: ["recipients"],
    queryFn: authAPI.recipients,
  });

  const conversations = convListData?.data?.results || convListData?.data || [];
  const thread = threadData?.data;
  const recipients = recipientsData?.data || [];
  const recipientOpts = recipients.map(r => ({
    value: r.id,
    label: `${r.full_name} (${r.role})`,
  }));

  const totalUnread = conversations.reduce(
    (sum, c) => sum + (c.unread_count || 0), 0
  );

  // Scroll to bottom when thread updates
  useEffect(() => {
    if (thread && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [thread?.messages?.length]);

  // Mark as read when opening a conversation
  const markReadMut = useMutation({
    mutationFn: (id) => conversationsAPI.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const openThread = (conv) => {
    setSelectedId(conv.id);
    if (conv.unread_count > 0) {
      markReadMut.mutate(conv.id);
    }
    replyForm.reset();
    setReplyFile(null);
  };

  // Send new message (compose)
  const composeMut = useMutation({
    mutationFn: (d) => {
      const fd = new FormData();
      fd.append("recipient_id", d.recipient);
      fd.append("subject", d.subject);
      fd.append("body", d.body);
      if (composeFile) fd.append("attachment", composeFile);
      return conversationsAPI.create(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      toast.success(t("Message envoyé !"));
      setComposeOpen(false);
      setComposeFile(null);
      composeForm.reset();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  // Reply in thread
  const replyMut = useMutation({
    mutationFn: (d) => {
      const fd = new FormData();
      fd.append("body", d.body);
      if (replyFile) fd.append("attachment", replyFile);
      return conversationsAPI.reply(selectedId, fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", selectedId] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
      toast.success(t("Réponse envoyée !"));
      replyForm.reset();
      setReplyFile(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const isMe = (msg) =>
    msg.sender?.id === user?.id || msg.sender?.email === user?.email;

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("Messages")}
        subtitle={totalUnread > 0 ? `${totalUnread} non lu(s)` : "Messagerie"}
        action={
          <button
            onClick={() => setComposeOpen(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> {t("Nouveau message")}</button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-14rem)]">
        {/* ── Conversation list — hidden on mobile when a thread is open ── */}
        <div className={`card p-0 overflow-hidden flex flex-col ${activeThread ? "hidden lg:flex" : "flex"}`}>
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
            <Inbox className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-semibold text-slate-700">
              Conversations ({conversations.length})
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
            {listLoading && (
              <div className="py-12 text-center text-slate-400 text-sm">{t("Chargement…")}</div>
            )}
            {!listLoading && conversations.length === 0 && (
              <div className="py-12 text-center text-slate-400">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">{t("Aucune conversation")}</p>
              </div>
            )}
            {conversations.map((conv) => {
              const latest = conv.latest_message;
              const unread = conv.unread_count > 0;
              const active = selectedId === conv.id;
              const other = conv.other_participant;
              return (
                <button
                  key={conv.id}
                  onClick={() => openThread(conv)}
                  className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors flex items-start gap-3 ${
                    active ? "bg-primary-50 border-l-2 border-primary" : ""
                  }`}
                >
                  {/* Avatar */}
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white text-xs font-bold shrink-0">
                    {(other?.first_name || conv.subject || "?")[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <p className={`text-sm truncate ${unread ? "font-bold text-slate-900" : "font-medium text-slate-700"}`}>
                        {other ? `${other.first_name} ${other.last_name}` : conv.subject}
                      </p>
                      {latest && (
                        <span className="text-xs text-slate-400 shrink-0">
                          {new Date(latest.sent_at).toLocaleDateString(dateLocale(), { day:"2-digit", month:"2-digit" })}
                        </span>
                      )}
                    </div>
                    <p className={`text-xs truncate ${unread ? "font-semibold text-slate-700" : "text-slate-500"}`}>
                      {conv.subject}
                    </p>
                    {latest && (
                      <p className="text-xs text-slate-400 truncate">
                        {latest.sender_name}: {latest.body}
                      </p>
                    )}
                  </div>
                  {unread && (
                    <span className="w-5 h-5 bg-primary rounded-full text-white text-xs flex items-center justify-center shrink-0">
                      {conv.unread_count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Thread / Message detail — full screen on mobile when selected ── */}
        <div className={`lg:col-span-2 card p-0 overflow-hidden flex flex-col ${activeThread ? "flex" : "hidden lg:flex"}`}>
          {!selectedId ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3">
              <MessageSquare className="w-12 h-12 opacity-20" />
              <p className="text-sm">{t("Sélectionnez une conversation")}</p>
            </div>
          ) : !thread ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="animate-pulse text-slate-400 text-sm">{t("Chargement…")}</div>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 flex items-center gap-3">
                <button
                  onClick={() => setSelectedId(null)}
                  className="lg:hidden p-1.5 rounded-lg hover:bg-slate-200"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900 truncate">
                    {thread.subject}
                  </p>
                  <p className="text-xs text-slate-500">
                    {thread.participants?.map(p => p.full_name).join(", ")}
                    {" · "}
                    {thread.messages?.length} message(s)
                  </p>
                </div>
                {thread.messages?.some(m => !m.is_read && m.recipient?.id === user?.id) && (
                  <button
                    onClick={() => markReadMut.mutate(thread.id)}
                    className="p-1.5 text-primary hover:bg-primary-50 rounded-lg"
                    title={t("Tout marquer comme lu")}
                  >
                    <CheckCheck className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
                {thread.messages?.map((msg) => {
                  const mine = isMe(msg);
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${mine ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                          mine
                            ? "bg-primary text-white"
                            : "bg-white border border-slate-200 text-slate-800"
                        }`}
                      >
                        {/* Sender info */}
                        <div className="flex items-center gap-2 mb-1.5">
                          <div
                            className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                              mine ? "bg-white/20 text-white" : "bg-primary-100 text-primary"
                            }`}
                          >
                            {(msg.sender?.first_name || "?")[0]}
                          </div>
                          <span className={`text-xs font-medium ${mine ? "text-white/80" : "text-slate-500"}`}>
                            {mine ? "Moi" : `${msg.sender?.first_name} ${msg.sender?.last_name}`}
                          </span>
                          <span className={`text-xs ml-auto ${mine ? "text-white/60" : "text-slate-400"}`}>
                            {new Date(msg.sent_at).toLocaleString(dateLocale(), {
                              day: "2-digit", month: "2-digit",
                              hour: "2-digit", minute: "2-digit",
                            })}
                          </span>
                        </div>
                        {/* Body */}
                        <p className={`text-sm whitespace-pre-wrap leading-relaxed break-words overflow-wrap-anywhere ${mine ? "text-white" : "text-slate-700"}`}>
                          {msg.body}
                        </p>
                        {/* Attachment */}
                        {msg.has_attachment && msg.attachment && (
                          <a
                            href={msg.attachment}
                            target="_blank"
                            rel="noreferrer"
                            className={`flex items-center gap-1.5 mt-2 text-xs ${
                              mine ? "text-white/80 hover:text-white" : "text-primary hover:underline"
                            }`}
                          >
                            <Download className="w-3.5 h-3.5" />
                            {msg.attachment_name || "Pièce jointe"}
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply box */}
              <div className="border-t border-slate-100 px-5 py-3">
                <form
                  onSubmit={replyForm.handleSubmit((d) => replyMut.mutate(d))}
                  className="flex items-end gap-2"
                >
                  <div className="flex-1">
                    <textarea
                      {...replyForm.register("body", { required: true })}
                      placeholder={t("Écrire une réponse…")}
                      className="input w-full resize-none"
                      rows={2}
                    />
                    {replyFile && (
                      <span className="flex items-center gap-1 text-xs text-primary mt-1">
                        <FileText className="w-3 h-3" />
                        {replyFile.name}
                        <button
                          type="button"
                          onClick={() => setReplyFile(null)}
                          className="ml-1 text-slate-400 hover:text-danger"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <input
                      ref={replyFileRef}
                      type="file"
                      className="hidden"
                      onChange={(e) => setReplyFile(e.target.files[0] || null)}
                    />
                    <button
                      type="button"
                      onClick={() => replyFileRef.current?.click()}
                      className="p-2 rounded-lg hover:bg-slate-100 text-slate-400"
                      title={t("Joindre un fichier")}
                    >
                      <Paperclip className="w-4 h-4" />
                    </button>
                    <button
                      type="submit"
                      disabled={replyMut.isPending}
                      className="btn-primary p-2"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </form>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Compose modal ──────────────────────────────────── */}
      <Modal
        open={composeOpen}
        onClose={() => { setComposeOpen(false); setComposeFile(null); composeForm.reset(); }}
        title={t("Nouveau message")}
        size="md"
      >
        <form
          onSubmit={composeForm.handleSubmit((d) => composeMut.mutate(d))}
          className="space-y-4"
        >
          <div>
            <label className="label">{t("Destinataire *")}</label>
            <Controller
              name="recipient"
              control={composeForm.control}
              rules={{ required: true }}
              render={({ field }) => (
                <SearchableSelect
                  options={recipientOpts}
                  value={field.value}
                  onChange={field.onChange}
                  placeholder={
                    recipients.length === 0 ? t("Chargement…") : t("Rechercher…")
                  }
                />
              )}
            />
          </div>
          <div>
            <label className="label">{t("Sujet *")}</label>
            <input
              {...composeForm.register("subject", { required: true })}
              className="input"
              placeholder={t("Objet du message")}
            />
          </div>
          <div>
            <label className="label">{t("Message *")}</label>
            <textarea
              {...composeForm.register("body", { required: true })}
              className="input"
              rows={6}
              placeholder={t("Votre message…")} style={{resize:"vertical",minHeight:"120px"}}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={composeFileRef}
              type="file"
              className="hidden"
              onChange={(e) => setComposeFile(e.target.files[0] || null)}
            />
            <button
              type="button"
              onClick={() => composeFileRef.current?.click()}
              className="btn-secondary flex items-center gap-1.5 text-sm"
            >
              <Paperclip className="w-4 h-4" />
              {composeFile ? composeFile.name : "Joindre un fichier"}
            </button>
            {composeFile && (
              <button
                type="button"
                onClick={() => setComposeFile(null)}
                className="text-slate-400 hover:text-danger"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={() => { setComposeOpen(false); composeForm.reset(); }}
              className="btn-secondary"
            >{t("Annuler")}</button>
            <button
              type="submit"
              disabled={composeMut.isPending}
              className="btn-primary flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              {composeMut.isPending ? t("Envoi…") : t("Envoyer")}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
