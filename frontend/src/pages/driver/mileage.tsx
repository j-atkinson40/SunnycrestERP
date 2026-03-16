import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { driverService } from "@/services/driver-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function MileagePage() {
  const navigate = useNavigate();
  const [mileage, setMileage] = useState("");
  const [completing, setCompleting] = useState(false);

  const handleComplete = async () => {
    try {
      setCompleting(true);
      const totalMileage = mileage ? parseFloat(mileage) : undefined;
      await driverService.completeRoute(totalMileage);
      toast.success("Route completed!");
      navigate("/driver");
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Complete Route</h1>

      <Card className="space-y-4 p-4">
        <div className="space-y-2">
          <Label htmlFor="mileage">Ending Odometer / Total Mileage</Label>
          <Input
            id="mileage"
            type="number"
            step="0.1"
            min="0"
            value={mileage}
            onChange={(e) => setMileage(e.target.value)}
            placeholder="Enter mileage (optional)"
            className="text-lg"
          />
          <p className="text-xs text-muted-foreground">
            Enter total miles driven for this route, or leave blank to skip.
          </p>
        </div>
      </Card>

      <Button
        className="w-full py-6 text-lg bg-green-600 hover:bg-green-700"
        onClick={handleComplete}
        disabled={completing}
      >
        {completing ? "Completing..." : "Finish Route"}
      </Button>

      <Button
        variant="outline"
        className="w-full"
        onClick={() => navigate("/driver/route")}
      >
        Back to Route
      </Button>
    </div>
  );
}
