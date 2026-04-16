import { useCallback, useEffect, useRef, useState } from "react";

interface UseVoiceInputOptions {
  onResult?: (transcript: string) => void;
  onInterim?: (transcript: string) => void;
  onEnd?: () => void;
  onError?: (error: string) => void;
  silenceTimeout?: number;
}

// Get the SpeechRecognition constructor
const SpeechRecognition =
  typeof window !== "undefined"
    ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : null;

export function useVoiceInput(options: UseVoiceInputOptions = {}) {
  const {
    onResult,
    onInterim,
    onEnd,
    onError,
    silenceTimeout = 3000,
  } = options;

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);
  const [audioLevels, setAudioLevels] = useState<number[]>(new Array(16).fill(0));

  const isSupported = !!SpeechRecognition;

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
    if (audioContextRef.current?.state !== "closed") {
      audioContextRef.current?.close().catch(() => {});
    }
    setIsListening(false);
    setInterimTranscript("");
    onEnd?.();
  }, [onEnd]);

  const startListening = useCallback(async () => {
    if (!SpeechRecognition) {
      onError?.("Speech recognition not supported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      // Reset silence timer
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = setTimeout(stopListening, silenceTimeout);

      let interim = "";
      let final = "";
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      if (final) {
        setTranscript(final);
        onResult?.(final);
        stopListening();
      } else {
        setInterimTranscript(interim);
        onInterim?.(interim);
      }
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onerror = (event: any) => {
      if (event.error !== "aborted") {
        onError?.(event.error);
      }
      stopListening();
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    // Start audio visualization
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      audioContextRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateLevels = () => {
        analyser.getByteFrequencyData(dataArray);
        const levels = Array.from(dataArray.slice(0, 16)).map((v) => v / 255);
        setAudioLevels(levels);
        animFrameRef.current = requestAnimationFrame(updateLevels);
      };
      updateLevels();
    } catch {
      // visualization not available, continue anyway
    }

    // Start silence timer
    silenceTimerRef.current = setTimeout(stopListening, silenceTimeout);

    setIsListening(true);
    setTranscript("");
    setInterimTranscript("");
    recognition.start();
  }, [onResult, onInterim, onError, silenceTimeout, stopListening]);

  useEffect(() => {
    return () => {
      stopListening();
    };
  }, [stopListening]);

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    audioLevels,
    startListening,
    stopListening,
  };
}
