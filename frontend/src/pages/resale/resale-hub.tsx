import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Store, Package, ShoppingBag, Boxes, ArrowRight } from "lucide-react";

const TILES = [
  {
    label: "Urn Catalog",
    description: "Browse and manage cremation urns, mementos, and jewelry",
    href: "/resale/catalog",
    icon: Package,
    color: "bg-blue-50 text-blue-600",
  },
  {
    label: "Orders",
    description: "Track and manage resale orders",
    href: "/resale/orders",
    icon: ShoppingBag,
    color: "bg-purple-50 text-purple-600",
  },
  {
    label: "Inventory",
    description: "Monitor resale product stock levels",
    href: "/resale/inventory",
    icon: Boxes,
    color: "bg-amber-50 text-amber-600",
  },
];

export default function ResaleHub() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
          <Store className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Resale</h1>
          <p className="text-sm text-muted-foreground">
            Products you source and resell — urns, cremation accessories, and
            supplies.
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TILES.map((tile) => {
          const Icon = tile.icon;
          return (
            <Link key={tile.href} to={tile.href}>
              <Card className="group h-full cursor-pointer transition-all hover:border-primary/30 hover:bg-accent/30">
                <CardContent className="flex items-center gap-4 p-5">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${tile.color}`}
                  >
                    <Icon className="h-6 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold group-hover:text-primary transition-colors">
                      {tile.label}
                    </h3>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {tile.description}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
