import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CommandBar } from "@/components/core/CommandBar";

interface CommandBarContextValue {
  open: () => void;
  openVoice: () => void;
  close: () => void;
  isOpen: boolean;
}

const CommandBarContext = createContext<CommandBarContextValue>({
  open: () => {},
  openVoice: () => {},
  close: () => {},
  isOpen: false,
});

export function useCommandBar() {
  return useContext(CommandBarContext);
}

export function CommandBarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const prevFocusRef = useRef<Element | null>(null);

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
    // Restore focus
    if (prevFocusRef.current instanceof HTMLElement) {
      prevFocusRef.current.focus();
    }
  }, []);

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

  return (
    <CommandBarContext.Provider value={{ open, openVoice, close, isOpen }}>
      {children}
      <CommandBar isOpen={isOpen} onClose={close} voiceMode={voiceMode} />
    </CommandBarContext.Provider>
  );
}
