import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ConsoleSelectPage() {
  const { consoleAccess, functionalAreas } = useAuth();

  const consoles = [
    {
      key: "delivery_console",
      title: "Delivery Console",
      description: "View routes, confirm deliveries, and log mileage",
      icon: "🚚",
      href: "/console/delivery",
    },
    {
      key: "production_console",
      title: "Production Console",
      description: "Log production, view work orders, and track quality",
      icon: "🏭",
      href: "/console/production",
    },
    {
      key: "operations_board",
      title: "Operations Board",
      description: "Unified production dashboard — briefings, quick actions, daily log",
      icon: "📋",
      href: "/console/operations",
    },
  ];

  const available = consoles.filter((c) => {
    if (c.key === "operations_board") {
      return functionalAreas.has("production_log") || functionalAreas.has("full_admin");
    }
    return consoleAccess.has(c.key);
  });

  return (
    <div className="flex flex-col items-center gap-6 py-12">
      <h1 className="text-2xl font-bold">Select Console</h1>
      <div className="grid w-full max-w-md gap-4">
        {available.map((c) => (
          <Link key={c.key} to={c.href}>
            <Card className="cursor-pointer transition-shadow hover:shadow-md">
              <CardHeader className="flex flex-row items-center gap-4">
                <div className="text-3xl">{c.icon}</div>
                <div>
                  <CardTitle className="text-lg">{c.title}</CardTitle>
                  <CardDescription>{c.description}</CardDescription>
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
