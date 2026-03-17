import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { FHPortalData } from "@/types/funeral-home";
import { funeralHomeService } from "@/services/funeral-home-service";

const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "");
const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

export default function FamilyPortalPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<FHPortalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [message, setMessage] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const [approvalNotes, setApprovalNotes] = useState("");
  const [changeNotes, setChangeNotes] = useState("");
  const [showChanges, setShowChanges] = useState(false);

  useEffect(() => {
    if (!token) return;
    funeralHomeService
      .getPortalData(token)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [token]);

  const handleApprove = async () => {
    if (!token) return;
    try {
      await funeralHomeService.approveObituary(token, approvalNotes || undefined);
      // Reload
      const updated = await funeralHomeService.getPortalData(token);
      setData(updated);
    } catch {
      alert("Failed to approve obituary. Please try again.");
    }
  };

  const handleRequestChanges = async () => {
    if (!token || !changeNotes.trim()) return;
    try {
      await funeralHomeService.requestObituaryChanges(token, changeNotes);
      setShowChanges(false);
      setChangeNotes("");
      const updated = await funeralHomeService.getPortalData(token);
      setData(updated);
    } catch {
      alert("Failed to submit changes. Please try again.");
    }
  };

  const handleSendMessage = async () => {
    if (!token || !message.trim()) return;
    setSendingMessage(true);
    try {
      await funeralHomeService.sendDirectorMessage(token, message);
      setMessage("");
      alert("Message sent to your funeral director.");
    } catch {
      alert("Failed to send message. Please try again.");
    } finally {
      setSendingMessage(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <p className="text-stone-500">Loading...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="text-center max-w-md px-6">
          <h1 className="text-xl font-semibold text-stone-800">Unable to Load</h1>
          <p className="mt-2 text-stone-500">
            This link may have expired or is invalid. Please contact your funeral director for a new link.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="mx-auto max-w-2xl px-6 py-6 text-center">
          <h1 className="text-lg font-semibold text-stone-800">
            {data.funeral_home.name}
          </h1>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-8 space-y-8">
        {/* Deceased */}
        <section className="text-center">
          <h2 className="text-2xl font-semibold text-stone-900">
            {data.deceased.first_name} {data.deceased.last_name}
          </h2>
          <p className="mt-1 text-stone-500">
            {fmtDate(data.deceased.date_of_death)}
          </p>
        </section>

        {/* Service */}
        {data.service && (data.service.date || data.service.location) && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Service Details
            </h3>
            <div className="space-y-2 text-stone-700">
              {data.service.type && (
                <p className="capitalize">{data.service.type.replace(/_/g, " ")}</p>
              )}
              {data.service.date && (
                <p>
                  <span className="font-medium">Date:</span> {fmtDate(data.service.date)}
                  {data.service.time && ` at ${data.service.time}`}
                </p>
              )}
              {data.service.location && (
                <p>
                  <span className="font-medium">Location:</span> {data.service.location}
                </p>
              )}
            </div>
          </section>
        )}

        {/* Visitation */}
        {data.visitation && (data.visitation.date || data.visitation.location) && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Visitation
            </h3>
            <div className="space-y-2 text-stone-700">
              {data.visitation.date && (
                <p>
                  <span className="font-medium">Date:</span> {fmtDate(data.visitation.date)}
                </p>
              )}
              {data.visitation.start_time && (
                <p>
                  <span className="font-medium">Time:</span> {data.visitation.start_time}
                  {data.visitation.end_time && ` - ${data.visitation.end_time}`}
                </p>
              )}
              {data.visitation.location && (
                <p>
                  <span className="font-medium">Location:</span> {data.visitation.location}
                </p>
              )}
            </div>
          </section>
        )}

        {/* Obituary */}
        {data.obituary && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Obituary
            </h3>
            {data.obituary.content && (
              <div className="text-stone-700 leading-relaxed whitespace-pre-line mb-4">
                {data.obituary.content}
              </div>
            )}
            {data.obituary.can_approve && data.obituary.status === "pending_family_approval" && (
              <div className="space-y-4 border-t pt-4">
                <p className="text-sm text-stone-600">
                  Please review the obituary above and approve or request changes.
                </p>
                <div className="space-y-2">
                  <textarea
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Optional notes..."
                    rows={2}
                    className="w-full rounded-lg border border-stone-300 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-stone-400"
                  />
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <button
                    onClick={handleApprove}
                    className="flex-1 rounded-lg bg-green-700 px-6 py-3 text-white font-medium hover:bg-green-800 transition-colors"
                  >
                    Approve Obituary
                  </button>
                  <button
                    onClick={() => setShowChanges(!showChanges)}
                    className="flex-1 rounded-lg border border-stone-300 px-6 py-3 font-medium text-stone-700 hover:bg-stone-50 transition-colors"
                  >
                    Request Changes
                  </button>
                </div>
                {showChanges && (
                  <div className="space-y-3">
                    <textarea
                      value={changeNotes}
                      onChange={(e) => setChangeNotes(e.target.value)}
                      placeholder="Please describe the changes you would like..."
                      rows={3}
                      className="w-full rounded-lg border border-stone-300 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-stone-400"
                    />
                    <button
                      onClick={handleRequestChanges}
                      disabled={!changeNotes.trim()}
                      className="rounded-lg bg-stone-700 px-6 py-2 text-white text-sm font-medium hover:bg-stone-800 disabled:opacity-50 transition-colors"
                    >
                      Submit Changes
                    </button>
                  </div>
                )}
              </div>
            )}
            {data.obituary.status === "approved" && (
              <p className="text-sm text-green-700 border-t pt-3">
                Obituary has been approved. Thank you.
              </p>
            )}
          </section>
        )}

        {/* Vault Status */}
        {data.vault_status && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Vault Status
            </h3>
            <p className="text-stone-700">
              <span className="font-medium">Status:</span> {data.vault_status.label}
            </p>
          </section>
        )}

        {/* Invoice */}
        {data.invoice && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Invoice Summary
            </h3>
            <div className="space-y-2">
              <div className="flex justify-between text-stone-700">
                <span>Total</span>
                <span className="font-medium">{currency(data.invoice.total_amount)}</span>
              </div>
              <div className="flex justify-between text-stone-700">
                <span>Paid</span>
                <span className="font-medium">{currency(data.invoice.amount_paid)}</span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="font-semibold text-stone-900">Balance Due</span>
                <span className="font-semibold text-stone-900">
                  {currency(data.invoice.balance_due)}
                </span>
              </div>
            </div>
          </section>
        )}

        {/* Documents */}
        {data.documents.length > 0 && (
          <section className="rounded-xl bg-white border border-stone-200 p-6">
            <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
              Documents
            </h3>
            <div className="space-y-2">
              {data.documents.map((doc) => (
                <a
                  key={doc.id}
                  href={doc.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between rounded-lg border border-stone-200 px-4 py-3 hover:bg-stone-50 transition-colors"
                >
                  <span className="text-sm font-medium text-stone-700">{doc.document_name}</span>
                  <span className="text-xs text-stone-500">Download</span>
                </a>
              ))}
            </div>
          </section>
        )}

        {/* Message Director */}
        <section className="rounded-xl bg-white border border-stone-200 p-6">
          <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wider mb-4">
            Contact Your Director
          </h3>
          <div className="space-y-3">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type your message here..."
              rows={3}
              className="w-full rounded-lg border border-stone-300 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-stone-400"
            />
            <button
              onClick={handleSendMessage}
              disabled={!message.trim() || sendingMessage}
              className="w-full rounded-lg bg-stone-800 px-6 py-3 text-white font-medium hover:bg-stone-900 disabled:opacity-50 transition-colors"
            >
              {sendingMessage ? "Sending..." : "Send Message"}
            </button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="mx-auto max-w-2xl px-6 py-6 text-center">
          <p className="text-xs text-stone-400">
            {data.funeral_home.name}
          </p>
        </div>
      </footer>
    </div>
  );
}
