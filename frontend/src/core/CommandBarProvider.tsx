import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CommandBar } from "@/components/core/CommandBar";
import type { CommandAction } from "@/core/actionRegistry";

interface CommandBarContextValue {
  open: () => void;
  openVoice: () => void;
  close: () => void;
  isOpen: boolean;
  // Wired by CommandBar.tsx — lets the provider-level Cmd+N listener
  // reach the current results + executor without re-rendering.
  setShortcutRefs: (refs: {
    results: CommandAction[];
    execute: (action: CommandAction) => void;
  }) => void;
}

const CommandBarContext = createContext<CommandBarContextValue>({
  open: () => {},
  openVoice: () => {},
  close: () => {},
  isOpen: false,
  setShortcutRefs: () => {},
});

export function useCommandBar() {
  return useContext(CommandBarContext);
}

export function CommandBarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const prevFocusRef = useRef<Element | null>(null);

  // Refs the inner CommandBar component populates — so the outer listener
  // always sees current values without re-registering on every render.
  const isOpenRef = useRef(false);
  const resultsRef = useRef<CommandAction[]>([]);
  const executeRef = useRef<((action: CommandAction) => void) | null>(null);

  useEffect(() => {
    isOpenRef.current = isOpen;
  }, [isOpen]);

  const setShortcutRefs = useCallback(
    (refs: { results: CommandAction[]; execute: (action: CommandAction) => void }) => {
      resultsRef.current = refs.results;
      executeRef.current = refs.execute;
    },
    [],
  );

  const open = useCallback(() => {
    prevFocusRef.current = document.activeElement;
    setVoiceMode(false);
    setIsOpen(true);
  }, []);

  const openVoice = useCallback(() => {
    prevFocusRef.current = document.activeElement;
    setVoiceMode(true);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setVoiceMode(false);
    if (prevFocusRef.current instanceof HTMLElement) {
      prevFocusRef.current.focus();
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────
  // Cmd+K open/close + Escape — bubble phase is fine
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key === "k") {
        e.preventDefault();
        if (e.shiftKey) {
          openVoice();
        } else {
          if (isOpen) close();
          else open();
        }
      }
      if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        close();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, open, openVoice, close]);

  // ─────────────────────────────────────────────────────────────────
  // Cmd+1..5 quick-pick — MUST be capture phase on window, attached ONCE
  // for the provider's lifetime. Moving it here (rather than inside
  // CommandBar which unmounts when closed) eliminates the re-register
  // race where the browser wins the tab-switch shortcut during the
  // brief window between effect cleanup and re-attach.
  //
  // The listener reads bar state via refs, so it never needs to re-run.
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const handleShortcut = (e: KeyboardEvent) => {
      // Only intercept when the command bar is open.
      if (!isOpenRef.current) return;
      if (!(e.metaKey || e.ctrlKey)) return;

      const fromKey = parseInt(e.key, 10);
      const fromCode = e.code && e.code.startsWith("Digit") ? parseInt(e.code.slice(5), 10) : NaN;
      const num = !Number.isNaN(fromKey) && fromKey >= 1 && fromKey <= 5
        ? fromKey
        : (!Number.isNaN(fromCode) && fromCode >= 1 && fromCode <= 5 ? fromCode : null);
      if (!num) return;

      // CRITICAL: preventDefault BEFORE any other check. If we skip it
      // (e.g. because results haven't loaded yet), the browser wins the
      // race to the Cmd+N tab-switch shortcut.
      e.preventDefault();
      e.stopPropagation();
      const maybeStopImmediate = (e as KeyboardEvent & { stopImmediatePropagation?: () => void }).stopImmediatePropagation;
      if (typeof maybeStopImmediate === "function") {
        maybeStopImmediate.call(e);
      }

      const target = resultsRef.current[num - 1];
      const exec = executeRef.current;
      if (target && exec) exec(target);
    };

    const opts: AddEventListenerOptions = { capture: true };
    window.addEventListener("keydown", handleShortcut, opts);
    document.addEventListener("keydown", handleShortcut, opts);
    return () => {
      window.removeEventListener("keydown", handleShortcut, opts);
      document.removeEventListener("keydown", handleShortcut, opts);
    };
  }, []); // no deps — attach ONCE for the lifetime of the provider

  return (
    <CommandBarContext.Provider value={{ open, openVoice, close, isOpen, setShortcutRefs }}>
      {children}
      <CommandBar isOpen={isOpen} onClose={close} voiceMode={voiceMode} />
    </CommandBarContext.Provider>
  );
}
