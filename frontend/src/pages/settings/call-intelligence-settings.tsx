// call-intelligence-settings.tsx — Call Intelligence settings page.
// Provider-agnostic call feature config. RingCentral is one provider option.

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { useCall } from "@/contexts/call-context";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Phone,
  PhoneCall,
  Plug,
  CheckCircle2,
  XCircle,
} from "lucide-react";

const PROVIDERS = [
  { value: "ringcentral", label: "RingCentral", available: true },
  { value: "dialpad", label: "Dialpad", available: false },
  { value: "8x8", label: "8x8", available: false },
  { value: "vonage", label: "Vonage", available: false },
];

export default function CallIntelligenceSettings() {
  // ⚠️ `connected` from useCall() is the SSE STREAM's state (call-context.tsx),
  // NOT the phone system's. This page previously reported "Phone system
  // connected" from it, so a tenant with no RingCentral connection at all read
  // as connected whenever the browser's event stream was open — a check with no
  // contact with what it names, on the exact page someone visits to find out
  // whether the thing works. Renamed at the point of use so the confusion
  // cannot be re-made silently.
  const { preferences, updatePreferences, connected: sseConnected } = useCall();

  // RingCentral connection is derived from RC facts. `ringcentral_connected` is
  // set only by the OAuth callback (backend ringcentral.py) after a successful
  // token exchange. Deliberately NOT derived from token presence: the settings
  // payload carries encrypted token material and this page should not depend on
  // credential fields at all.
  // null = not yet known; render neither claim until it resolves.
  const [rcConnected, setRcConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    apiClient
      .get<Record<string, unknown>>("/companies/tenant-settings")
      .then((r) => {
        if (alive) setRcConnected(r.data?.ringcentral_connected === true);
      })
      .catch(() => {
        // Unknown is not "connected". Fail toward the honest claim.
        if (alive) setRcConnected(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Call Intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Capture order details from phone calls automatically.
        </p>
      </div>

      {/* Phone System Provider */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-1">
          <Plug className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Phone System Provider</h2>
        </div>
        <Separator className="my-4" />

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Provider</Label>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              defaultValue="ringcentral"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value} disabled={!p.available}>
                  {p.label}
                  {!p.available ? " (coming soon)" : ""}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              More phone systems coming soon.
            </p>
          </div>

          {/* Connection status — RingCentral, not the SSE stream. */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              {rcConnected === null ? (
                <span className="text-sm text-muted-foreground">
                  Checking connection…
                </span>
              ) : rcConnected ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium text-green-800">
                    Phone system connected
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    via RingCentral
                  </Badge>
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    No phone system connected
                  </span>
                </>
              )}
            </div>
            {/* The connection flow does not exist yet: the backend has an OAuth
                CALLBACK but no authorize endpoint, and nothing in the app can
                start the flow. This button previously rendered as actionable
                with no onClick and no href, which meant a page already claiming
                "connected" sat above a button that did nothing — so the gap was
                undiscoverable from here. Disabled and labelled until the
                provisioning arc lands. */}
            <Button size="sm" disabled title="Not yet available">
              <Phone className="h-4 w-4 mr-1" />
              Connect RingCentral
            </Button>
          </div>
          {rcConnected === false && (
            <p className="text-xs text-muted-foreground">
              Connecting a phone system is not available yet. Call features can
              be demonstrated, but no phone system can be attached to this
              tenant.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Live event stream: {sseConnected ? "connected" : "disconnected"}.
            This is the browser&rsquo;s connection to Bridgeable, not to your
            phone system.
          </p>
        </div>
      </Card>

      {/* Call Overlay Settings */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-1">
          <PhoneCall className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Call Overlay</h2>
        </div>
        <Separator className="my-4" />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>Enable call overlay</Label>
              <p className="text-xs text-muted-foreground">
                Show incoming call popup and live extraction panel
              </p>
            </div>
            <Switch
              checked={preferences.rc_overlay_enabled}
              onCheckedChange={(v) =>
                updatePreferences({ rc_overlay_enabled: v })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label>Sound on incoming call</Label>
              <p className="text-xs text-muted-foreground">
                Play a ring tone for incoming calls
              </p>
            </div>
            <Switch
              checked={preferences.rc_sound_enabled}
              onCheckedChange={(v) =>
                updatePreferences({ rc_sound_enabled: v })
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <Label>Auto-open order form</Label>
              <p className="text-xs text-muted-foreground">
                Automatically open Order Station when a call ends
              </p>
            </div>
            <Switch
              checked={preferences.rc_auto_open_order}
              onCheckedChange={(v) =>
                updatePreferences({ rc_auto_open_order: v })
              }
            />
          </div>
        </div>
      </Card>

      {/* Phone Extensions */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Phone Extensions</h2>
        <Separator className="my-4" />
        <p className="text-sm text-muted-foreground">
          Map phone extensions to team members so calls are routed to the right
          person. Extension mapping will be available once a phone system is
          connected.
        </p>
        {/* Placeholder table — will be wired when backend extension mapping is built */}
        <div className="mt-4 rounded-lg border">
          <div className="grid grid-cols-3 gap-3 px-4 py-2 bg-muted/50 text-xs font-medium text-muted-foreground">
            <span>Extension</span>
            <span>Name</span>
            <span>Team Member</span>
          </div>
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No extensions configured yet
          </div>
        </div>
      </Card>
    </div>
  );
}
