import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CommandBar } from "@/components/core/CommandBar";
import type { CommandAction } from "@/services/actions";
import { setCmdShortcutState } from "@/lib/cmd-digit-shortcuts";

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
    // Tell the module-scope Cmd+N listener (installed in main.tsx) about
    // the current bar state.
    setCmdShortcutState({ isOpen });
  }, [isOpen]);

  const setShortcutRefs = useCallback(
    (refs: { results: CommandAction[]; execute: (action: CommandAction) => void }) => {
      resultsRef.current = refs.results;
      executeRef.current = refs.execute;
      // Mirror into the module-scope state so the pre-React listener can act.
      setCmdShortcutState({ results: refs.results, execute: refs.execute });
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

  // Cmd+1..5 is handled by the listener installed in main.tsx
  // (see @/lib/cmd-digit-shortcuts). Provider just keeps its state
  // in sync via setCmdShortcutState above.

  return (
    <CommandBarContext.Provider value={{ open, openVoice, close, isOpen, setShortcutRefs }}>
      {children}
      <CommandBar isOpen={isOpen} onClose={close} voiceMode={voiceMode} />
    </CommandBarContext.Provider>
  );
}
