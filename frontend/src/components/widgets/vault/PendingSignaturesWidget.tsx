/**
 * PendingSignaturesWidget — V-1b Vault Overview widget.
 *
 * Shows envelopes in `out_for_signature` status (signers still have
 * action to take). Uses the existing `signingService.listEnvelopes()`
 * endpoint — no new backend work.
 */

import { useEffect, useState } from "react";
import { FileCheck, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import {
  signingService,
  type EnvelopeListItem,
} from "@/services/signing-service";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

export default function PendingSignaturesWidget(props: WidgetProps) {
  const [items, setItems] = useState<EnvelopeListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const rows = await signingService.listEnvelopes({
        status: "out_for_signature",
        limit: 10,
      });
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const isLoading = items === null && !error;

  return (
    <WidgetWrapper
      widgetId="vault_pending_signatures"
      title="Pending signatures"
      icon={<FileCheck className="h-4 w-4" />}
      size={(props._size as string) || "2x1"}
      editMode={(props._editMode as boolean) || false}
      dragHandleProps={props._dragHandleProps as Record<string, unknown>}
      onRemove={props._onRemove as () => void}
      onSizeChange={props._onSizeChange as (s: string) => void}
      supportedSizes={props._supportedSizes as string[]}
      isLoading={isLoading}
      error={error}
      onRefresh={load}
    >
      {items && items.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 py-6 text-center text-sm text-gray-500">
          <p>No envelopes awaiting signature.</p>
          <Link
            to="/vault/documents/signing/new"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Create envelope
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((env) => (
              <li key={env.id}>
                <Link
                  to={`/vault/documents/signing/${env.id}`}
                  className="flex items-center justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-gray-800">
                      {env.subject}
                    </div>
                    <div className="truncate text-xs text-gray-500">
                      {env.routing_type}
                      {env.expires_at
                        ? ` · expires ${formatRelativeAge(env.expires_at)}`
                        : ""}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(env.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/documents/signing"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
