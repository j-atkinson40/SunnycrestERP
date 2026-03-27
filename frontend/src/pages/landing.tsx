import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

const appName = import.meta.env.VITE_APP_NAME || "Bridgeable";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <h1 className="text-xl font-bold">{appName}</h1>
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
          The platform built for the Wilbert licensee network.
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
        {appName}
      </footer>
    </div>
  );
}
