import { Store } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function ResaleInventory() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Resale Inventory
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Track stock levels for products you source and resell.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
            <Store className="h-8 w-8 text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold mb-2">
            Resale Inventory — Coming Soon
          </h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            Resale inventory tracking will appear here. Urn stock levels are
            currently managed within the Urn Catalog.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
