// call-intelligence-settings.tsx — Call Intelligence settings page.
// Provider-agnostic call feature config. RingCentral is one provider option.

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
  const { preferences, updatePreferences, connected } = useCall();

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

          {/* Connection status */}
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              {connected ? (
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
            {connected ? (
              <Button variant="outline" size="sm">
                Disconnect
              </Button>
            ) : (
              <Button size="sm">
                <Phone className="h-4 w-4 mr-1" />
                Connect RingCentral
              </Button>
            )}
          </div>
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
