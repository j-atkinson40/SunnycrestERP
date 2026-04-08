import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import {
  BookOpen,
  GraduationCap,
  ShieldCheck,
  ClipboardList,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";

interface TrainingTile {
  title: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  permission?: string;
  requiresModule?: string;
}

const TILES: TrainingTile[] = [
  {
    title: "Vault Order Lifecycle",
    description:
      "Interactive walkthrough of the 7-stage vault order process from entry to delivery.",
    href: "/training/vault-order-lifecycle",
    icon: GraduationCap,
    color: "bg-blue-50 text-blue-600",
  },
  {
    title: "Procedure Library",
    description:
      "Standard operating procedures and reference documents for daily operations.",
    href: "/training/procedures",
    icon: BookOpen,
    color: "bg-purple-50 text-purple-600",
  },
  {
    title: "Safety & OSHA",
    description:
      "Safety training calendar, inspections, toolbox talks, OSHA 300 log, and compliance programs.",
    href: "/safety",
    icon: ShieldCheck,
    color: "bg-green-50 text-green-600",
    permission: "safety.view",
    requiresModule: "safety_management",
  },
  {
    title: "Training Records",
    description:
      "Track employee training completions, certifications, and upcoming renewals.",
    href: "/safety/training/calendar",
    icon: ClipboardList,
    color: "bg-amber-50 text-amber-600",
    requiresModule: "safety_management",
  },
];

export default function TrainingHubPage() {
  const { hasPermission, hasModule, isAdmin } = useAuth();

  const visibleTiles = TILES.filter((tile) => {
    if (tile.requiresModule && !hasModule(tile.requiresModule)) return false;
    if (tile.permission && !isAdmin && !hasPermission(tile.permission))
      return false;
    return true;
  });

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Training</h1>
        <p className="text-muted-foreground">
          Training resources, safety programs, and procedure documentation
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2">
        {visibleTiles.map((tile) => {
          const Icon = tile.icon;
          return (
            <Link key={tile.href} to={tile.href} className="group">
              <Card className="h-full transition-all hover:shadow-md hover:border-primary/30">
                <CardContent className="flex gap-4 p-5">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${tile.color}`}
                  >
                    <Icon className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="font-semibold group-hover:text-primary transition-colors">
                      {tile.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {tile.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
