// voice-input.ts
// Wraps Web Speech API for iOS Safari voice input.

export type VoiceState = 'idle' | 'listening' | 'processing' | 'error'

export interface VoiceInputService {
  isSupported: boolean
  state: VoiceState
  startListening(onInterim: (text: string) => void, onFinal: (text: string) => void): void
  stopListening(): void
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySpeechRecognition = any

const SpeechRecognitionAPI: AnySpeechRecognition =
  typeof window !== 'undefined'
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : undefined

function createVoiceInputService(): VoiceInputService {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let recognition: any = null
  let currentState: VoiceState = 'idle'
  let finalTranscript = ''

  const service: VoiceInputService = {
    isSupported: !!SpeechRecognitionAPI,
    get state() {
      return currentState
    },

    startListening(
      onInterim: (text: string) => void,
      onFinal: (text: string) => void
    ): void {
      if (!SpeechRecognitionAPI) {
        currentState = 'error'
        onFinal('ERROR: Speech recognition is not supported in this browser.')
        return
      }

      // iOS requires a new instance per call
      recognition = new SpeechRecognitionAPI()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'
      recognition.maxAlternatives = 1

      finalTranscript = ''
      currentState = 'listening'

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (event: any) => {
        let interimText = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]
          if (result.isFinal) {
            finalTranscript += result[0].transcript
          } else {
            interimText += result[0].transcript
          }
        }

        if (interimText) {
          onInterim(interimText)
        }
      }

      recognition.onend = () => {
        currentState = 'processing'
        onFinal(finalTranscript)
        currentState = 'idle'
        recognition = null
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (event: any) => {
        currentState = 'error'
        const message = event.error ? `ERROR: ${event.error}` : 'ERROR: Speech recognition failed.'
        onFinal(message)
        recognition = null
      }

      try {
        recognition.start()
      } catch (err) {
        currentState = 'error'
        const message = err instanceof Error ? err.message : 'Failed to start recognition'
        onFinal(`ERROR: ${message}`)
        recognition = null
      }
    },

    stopListening(): void {
      if (recognition) {
        try {
          recognition.stop()
        } catch {
          // Ignore errors when stopping (already stopped or not started)
        }
      }
    },
  }

  return service
}

const voiceInput = createVoiceInputService()

export default voiceInput
