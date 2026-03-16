import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <h1 className="text-xl font-bold">ERP Platform</h1>
          <Link
            to="/register-company"
            className={buttonVariants({ variant: "default" })}
          >
            Get Started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Business management,
          <br />
          <span className="text-primary">simplified.</span>
        </h2>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Manage users, track work, and stay organized — all in one place.
          Each company gets its own secure workspace.
        </p>
        <div className="mt-8 flex gap-4">
          <Link
            to="/register-company"
            className={buttonVariants({ size: "lg" })}
          >
            Register Your Company
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        ERP Platform
      </footer>
    </div>
  );
}
