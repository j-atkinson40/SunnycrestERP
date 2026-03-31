// voice-input-button.tsx
// Self-contained voice capture button for the mobile Operations Board.
// Wraps the voiceInput singleton and interpretVoice function.

import { useState } from 'react'
import { Mic, MicOff, Loader2, AlertCircle, Keyboard } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import voiceInput from '@/services/voice-input'
import { interpretVoice } from '@/services/voice-interpreter'

export interface VoiceInputButtonProps {
  context: string
  onResult: (interpreted: Record<string, unknown>) => void
  onTranscript?: (text: string) => void
  availableProducts?: { id: string; name: string }[]
  availableEmployees?: { id: string; name: string }[]
  className?: string
  label?: string
}

type ButtonState = 'idle' | 'listening' | 'processing' | 'error'

export default function VoiceInputButton({
  context,
  onResult,
  onTranscript,
  availableProducts,
  availableEmployees,
  className,
  label = 'Tap to speak',
}: VoiceInputButtonProps) {
  const [state, setState] = useState<ButtonState>('idle')
  const [liveTranscript, setLiveTranscript] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  // Voice not supported — show informational fallback instead of the button
  if (!voiceInput.isSupported) {
    return (
      <div className={cn('flex flex-col items-center gap-2 text-center', className)}>
        <Keyboard className="h-8 w-8 text-gray-400" />
        <p className="text-sm text-gray-500">Voice not available — type below</p>
      </div>
    )
  }

  function handleTap() {
    if (state === 'listening') {
      // User taps again while listening — stop early
      voiceInput.stopListening()
      return
    }

    if (state === 'processing') return // ignore taps while processing

    // Reset any previous error, then start
    setErrorMessage('')
    setLiveTranscript('')
    setState('listening')

    voiceInput.startListening(
      // onInterim
      (text: string) => {
        setLiveTranscript(text)
      },
      // onFinal
      async (text: string) => {
        if (text.startsWith('ERROR:')) {
          const msg = text.replace(/^ERROR:\s*/, '')
          setErrorMessage(msg)
          setState('error')
          toast.error(`Voice error: ${msg}`)
          return
        }

        // Empty transcript (user said nothing before stopping)
        if (!text.trim()) {
          setState('idle')
          setLiveTranscript('')
          return
        }

        setState('processing')
        setLiveTranscript('')

        try {
          const result = await interpretVoice(
            context,
            text,
            availableProducts,
            availableEmployees,
          )
          onResult(result)
          onTranscript?.(text)
          setState('idle')
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Interpretation failed'
          setErrorMessage(msg)
          setState('error')
          toast.error(msg)
        }
      },
    )
  }

  // Derived display values
  const buttonLabel =
    state === 'listening'
      ? 'Listening...'
      : state === 'processing'
        ? 'Understanding...'
        : state === 'error'
          ? 'Try again'
          : label

  const circleBase =
    'w-20 h-20 rounded-full flex items-center justify-center transition-all duration-200 select-none'

  const circleStyle =
    state === 'idle'
      ? 'bg-blue-600 shadow-lg active:scale-95'
      : state === 'listening'
        ? 'bg-red-500 shadow-lg voice-btn-listening'
        : state === 'processing'
          ? 'bg-gray-400'
          : /* error */ 'bg-red-100 border-2 border-red-400'

  return (
    <div className={cn('flex flex-col items-center gap-3', className)}>
      {/* Live transcript — only visible while listening */}
      {state === 'listening' && (
        <p
          className="min-h-[2rem] max-w-xs text-center text-lg italic text-gray-700 leading-snug"
          aria-live="polite"
        >
          {liveTranscript || '\u00A0'}
        </p>
      )}

      {/* The button itself */}
      <button
        type="button"
        onClick={handleTap}
        disabled={state === 'processing'}
        aria-label={buttonLabel}
        className={cn(circleBase, circleStyle, 'cursor-pointer disabled:cursor-not-allowed')}
      >
        {state === 'idle' && <Mic className="h-8 w-8 text-white" />}
        {state === 'listening' && <MicOff className="h-8 w-8 text-white" />}
        {state === 'processing' && (
          <Loader2 className="h-8 w-8 text-white animate-spin" />
        )}
        {state === 'error' && <AlertCircle className="h-8 w-8 text-red-500" />}
      </button>

      {/* Label */}
      <span
        className={cn(
          'text-sm font-medium',
          state === 'error' ? 'text-red-600' : 'text-gray-600',
        )}
      >
        {buttonLabel}
      </span>

      {/* Tap-to-stop hint while listening */}
      {state === 'listening' && (
        <span className="text-xs text-gray-400">tap to stop</span>
      )}

      {/* Error message */}
      {state === 'error' && errorMessage && (
        <p className="max-w-[240px] text-center text-xs text-red-500">{errorMessage}</p>
      )}
    </div>
  )
}
