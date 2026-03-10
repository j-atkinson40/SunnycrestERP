import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export default function Unauthorized() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-bold">403</h1>
      <p className="text-muted-foreground">
        You don't have permission to access this page.
      </p>
      <Link to="/" className={buttonVariants()}>
        Go Home
      </Link>
    </div>
  );
}
