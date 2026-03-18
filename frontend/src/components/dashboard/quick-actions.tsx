import {
  ClipboardList,
  ShoppingCart,
  Truck,
  AlertTriangle,
  Phone,
  Package,
  DollarSign,
  Send,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";

interface QuickActionsProps {
  onAction?: (prompt: string) => void;
}

interface ActionDef {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  prompt: string;
  color: string;
}

const MANUFACTURING_ACTIONS: ActionDef[] = [
  {
    icon: ClipboardList,
    label: "Log Production",
    prompt: "we made ",
    color: "text-green-600 bg-green-50 hover:bg-green-100",
  },
  {
    icon: ShoppingCart,
    label: "New Order",
    prompt: "",
    color: "text-blue-600 bg-blue-50 hover:bg-blue-100",
  },
  {
    icon: Truck,
    label: "Schedule Delivery",
    prompt: "schedule delivery for ",
    color: "text-purple-600 bg-purple-50 hover:bg-purple-100",
  },
  {
    icon: AlertTriangle,
    label: "Log Incident",
    prompt: "incident report: ",
    color: "text-red-600 bg-red-50 hover:bg-red-100",
  },
];

const FUNERAL_HOME_ACTIONS: ActionDef[] = [
  {
    icon: Phone,
    label: "First Call",
    prompt: "first call from ",
    color: "text-stone-600 bg-stone-50 hover:bg-stone-100",
  },
  {
    icon: Package,
    label: "Order Vault",
    prompt: "order vault for ",
    color: "text-blue-600 bg-blue-50 hover:bg-blue-100",
  },
  {
    icon: DollarSign,
    label: "Record Payment",
    prompt: "received payment from ",
    color: "text-green-600 bg-green-50 hover:bg-green-100",
  },
  {
    icon: Send,
    label: "Send Portal",
    prompt: "send portal to ",
    color: "text-purple-600 bg-purple-50 hover:bg-purple-100",
  },
];

export function QuickActions({ onAction }: QuickActionsProps) {
  const { company } = useAuth();

  const actions =
    company?.vertical === "funeral_home"
      ? FUNERAL_HOME_ACTIONS
      : MANUFACTURING_ACTIONS;

  return (
    <div className="flex gap-3">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => onAction?.(action.prompt)}
          className={`flex flex-col items-center gap-1.5 rounded-lg border px-4 py-3 transition-colors ${action.color}`}
        >
          <action.icon className="h-5 w-5" />
          <span className="text-xs font-medium">{action.label}</span>
        </button>
      ))}
    </div>
  );
}
