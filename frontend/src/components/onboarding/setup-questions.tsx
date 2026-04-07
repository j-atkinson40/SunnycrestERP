/**
 * Setup Questions — shown on first visit to onboarding for manufacturing tenants.
 * Asks about spring burials and saves settings before showing the main checklist.
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Snowflake, Sun, ChevronRight } from "lucide-react";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";

interface SetupQuestionsProps {
  vertical: string;
  onComplete: () => void;
}

export function SetupQuestions({ vertical, onComplete }: SetupQuestionsProps) {
  const [springBurials, setSpringBurials] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  if (vertical !== "manufacturing") {
    // Only manufacturing has setup questions for now
    onComplete();
    return null;
  }

  async function handleContinue() {
    setSaving(true);
    try {
      await apiClient.post("/companies/tenant-settings/bulk", {
        spring_burials_enabled: springBurials === true,
        onboarding_questions_completed: true,
      });
      onComplete();
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold">A few quick questions</h1>
        <p className="mt-2 text-muted-foreground">
          Help us configure your workspace. This takes about 30 seconds.
        </p>
      </div>

      {/* Spring Burial Question */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">
          Do you manage spring burials?
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Some cemeteries close in winter — vault orders are held until spring.
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <Card
            className={`cursor-pointer transition-all hover:shadow-md ${
              springBurials === true
                ? "ring-2 ring-blue-500 bg-blue-50"
                : "hover:border-gray-300"
            }`}
            onClick={() => setSpringBurials(true)}
          >
            <CardContent className="flex flex-col items-center gap-3 pt-6 pb-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                <Snowflake className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="font-semibold">Yes, we have spring burials</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Some of our cemeteries close in winter — we hold vaults for
                  spring delivery
                </p>
              </div>
            </CardContent>
          </Card>

          <Card
            className={`cursor-pointer transition-all hover:shadow-md ${
              springBurials === false
                ? "ring-2 ring-green-500 bg-green-50"
                : "hover:border-gray-300"
            }`}
            onClick={() => setSpringBurials(false)}
          >
            <CardContent className="flex flex-col items-center gap-3 pt-6 pb-4 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                <Sun className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="font-semibold">No spring burials</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Our cemeteries stay open year-round
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Continue button */}
      <div className="flex justify-end">
        <div className="relative group">
          <Button
            disabled={springBurials === null || saving}
            onClick={handleContinue}
            className="gap-2 transition-opacity"
          >
            {saving ? "Saving..." : "Continue to Setup Checklist"}
            <ChevronRight className="h-4 w-4" />
          </Button>
          {springBurials === null && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs text-white bg-gray-900 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              Select an option to continue
              <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-gray-900" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
