/**
 * Spring Burial dashboard widget for manufacturing dashboard.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Snowflake } from "lucide-react";
import * as springBurialService from "@/services/spring-burial-service";
import type { SpringBurialStats } from "@/types/spring-burial";

export function SpringBurialWidget() {
  const [stats, setStats] = useState<SpringBurialStats | null>(null);

  useEffect(() => {
    springBurialService
      .getStats()
      .then(setStats)
      .catch(() => {
        // Silently fail — feature may not be enabled
      });
  }, []);

  if (!stats || stats.total_count === 0) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">
          <Snowflake className="mr-1.5 inline h-4 w-4 text-blue-500" />
          Spring Burials
        </CardTitle>
        <Link
          to="/spring-burials"
          className="text-xs text-blue-600 hover:underline"
        >
          View All →
        </Link>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold">{stats.total_count}</p>
        <p className="text-xs text-muted-foreground">
          across {stats.funeral_home_count} funeral home
          {stats.funeral_home_count !== 1 ? "s" : ""}
        </p>
        {stats.soonest_cemetery && (
          <p className="mt-2 text-xs text-muted-foreground">
            Opening soonest:{" "}
            <span className="font-medium text-foreground">
              {stats.soonest_cemetery}
            </span>
            {stats.days_until_soonest != null && (
              <> — ~{stats.days_until_soonest} days</>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
