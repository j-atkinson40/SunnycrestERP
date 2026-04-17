import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { installCmdDigitShortcuts } from "./lib/cmd-digit-shortcuts";

// Install Cmd+1..5 capture-phase listener BEFORE React mounts.
// Attaches to window + document once for the entire session — no race
// window with the browser's native Cmd+N tab-switch shortcut.
installCmdDigitShortcuts();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
