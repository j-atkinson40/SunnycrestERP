// LegacyCompositorMobile.tsx — Mobile-optimised legacy proof compositor.
// Full-screen canvas with floating bottom toolbar. Same data model as desktop.

import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  X, Check, RotateCcw, Type, Move, Maximize, Trash2,
  Image as ImageIcon, ChevronLeft, ZoomIn, Sun,
} from "lucide-react"
import type { LegacyPhotoLayer, LegacyTextLayer, LegacyLayout, GenerateResult } from "./LegacyCompositor"

// ── Helpers ─────────────────────────────────────────────────────────────────

function uid(): string {
  return Math.random().toString(36).slice(2, 10)
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

// ── Props (same as desktop) ─────────────────────────────────────────────────

interface LegacyCompositorMobileProps {
  backgroundUrl: string
  mode: "manufacturer" | "funeral_home"
  initialLayout?: LegacyLayout
  name: string
  dates: string
  additionalText: string
  defaultTextColor: "white" | "black"
  onGenerate: (layout: LegacyLayout) => Promise<GenerateResult>
  onApprove: (layout: LegacyLayout, proofUrl: string, tifUrl: string) => void
  onCancel?: () => void
  isGenerating?: boolean
  generatedProofUrl?: string
}

type SelectedLayer = { type: "photo"; id: string } | { type: "text" } | null
type BottomPanel = "photo-controls" | "text-controls" | null

// ── Component ───────────────────────────────────────────────────────────────

export default function LegacyCompositorMobile({
  backgroundUrl,
  mode: _mode,
  initialLayout,
  name,
  dates,
  additionalText,
  defaultTextColor,
  onGenerate,
  onApprove,
  onCancel,
  isGenerating,
  generatedProofUrl: initialProofUrl,
}: LegacyCompositorMobileProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const bgImageRef = useRef<HTMLImageElement | null>(null)
  const photoImagesRef = useRef<Map<string, HTMLImageElement>>(new Map())

  const [photos, setPhotos] = useState<LegacyPhotoLayer[]>(initialLayout?.photos || [])
  const [textLayer, setTextLayer] = useState<LegacyTextLayer>(
    initialLayout?.text || {
      x: 0.75,
      y: 0.5,
      fontSize: 0.07,
      color: defaultTextColor,
      shadow: true,
    },
  )
  const [generating, setGenerating] = useState(false)
  const [proofUrl, setProofUrl] = useState<string | null>(initialProofUrl || null)
  const [tifUrl, setTifUrl] = useState<string | null>(null)
  const [showProof, setShowProof] = useState(!!initialProofUrl)
  const [dragging, setDragging] = useState<{ type: "photo" | "text"; id?: string } | null>(null)
  const [bgLoaded, setBgLoaded] = useState(false)

  // Mobile-specific state
  const [selected, setSelected] = useState<SelectedLayer>(null)
  const [bottomPanel, setBottomPanel] = useState<BottomPanel>(null)

  // Load background image
  useEffect(() => {
    const img = new Image()
    img.crossOrigin = "anonymous"
    img.onload = () => {
      bgImageRef.current = img
      setBgLoaded(true)
    }
    img.src = backgroundUrl
  }, [backgroundUrl])

  // Load photo images
  useEffect(() => {
    for (const photo of photos) {
      if (!photoImagesRef.current.has(photo.id)) {
        const img = new Image()
        img.crossOrigin = "anonymous"
        img.onload = () => {
          photoImagesRef.current.set(photo.id, img)
          renderCanvas()
        }
        img.src = photo.url
      }
    }
  }, [photos])

  // ── Canvas rendering ────────────────────────────────────────────────────

  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const bg = bgImageRef.current
    if (!canvas || !bg) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const cw = canvas.width
    const ch = canvas.height

    ctx.clearRect(0, 0, cw, ch)
    ctx.drawImage(bg, 0, 0, cw, ch)

    // Photos
    for (const photo of photos) {
      const img = photoImagesRef.current.get(photo.id)
      if (!img) continue

      const pw = cw * photo.scale
      const ratio = img.naturalHeight / img.naturalWidth
      const ph = pw * ratio
      const px = cw * photo.x - pw / 2
      const py = ch * photo.y - ph / 2

      ctx.save()
      ctx.globalAlpha = photo.opacity

      if (photo.style === "soft_fade") {
        ctx.beginPath()
        ctx.ellipse(cw * photo.x, ch * photo.y, pw / 2 * 0.85, ph / 2 * 0.85, 0, 0, Math.PI * 2)
        ctx.clip()
      }

      ctx.drawImage(img, px, py, pw, ph)
      ctx.restore()

      // Selection indicator
      if (selected?.type === "photo" && selected.id === photo.id) {
        ctx.save()
        ctx.strokeStyle = "#3b82f6"
        ctx.lineWidth = 2
        ctx.setLineDash([6, 4])
        ctx.strokeRect(px, py, pw, ph)
        ctx.restore()
      }
    }

    // Text
    const lines: string[] = []
    if (name) lines.push(name)
    if (dates) lines.push(dates)
    if (additionalText) lines.push(additionalText)

    if (lines.length > 0) {
      const fsPx = ch * textLayer.fontSize
      const mainFont = `bold italic ${fsPx}px 'Liberation Sans', 'Arial', sans-serif`
      const smallFont = `bold italic ${fsPx * 0.85}px 'Liberation Sans', 'Arial', sans-serif`

      const centerX = cw * textLayer.x
      const lineSpacing = fsPx * 0.35
      const totalH = lines.length * fsPx + (lines.length - 1) * lineSpacing
      let y = ch * textLayer.y - totalH / 2 + fsPx / 2

      for (let i = 0; i < lines.length; i++) {
        const font = i >= 2 ? smallFont : mainFont
        ctx.font = font
        ctx.textAlign = "center"

        if (textLayer.shadow) {
          ctx.shadowBlur = 4
          ctx.shadowColor = "rgba(0,0,0,0.6)"
          ctx.shadowOffsetX = 2
          ctx.shadowOffsetY = 2
        }

        ctx.fillStyle = textLayer.color === "white" ? "#FFFFFF" : "#000000"
        ctx.fillText(lines[i], centerX, y)

        ctx.shadowBlur = 0
        ctx.shadowOffsetX = 0
        ctx.shadowOffsetY = 0

        y += fsPx + lineSpacing
      }

      // Selection indicator for text
      if (selected?.type === "text") {
        const textW = cw * 0.3
        const textH = totalH + fsPx * 0.5
        ctx.save()
        ctx.strokeStyle = "#3b82f6"
        ctx.lineWidth = 2
        ctx.setLineDash([6, 4])
        ctx.strokeRect(centerX - textW / 2, ch * textLayer.y - textH / 2, textW, textH)
        ctx.restore()
      }
    }
  }, [photos, textLayer, name, dates, additionalText, selected])

  useEffect(() => {
    if (bgLoaded && !showProof) {
      requestAnimationFrame(renderCanvas)
    }
  }, [bgLoaded, renderCanvas, showProof])

  // ── Touch / pointer handling ──────────────────────────────────────────

  function getEventCoords(
    e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>,
    canvas: HTMLCanvasElement,
  ): { x: number; y: number } {
    const rect = canvas.getBoundingClientRect()
    const clientX = "touches" in e ? e.touches[0]?.clientX ?? 0 : e.clientX
    const clientY = "touches" in e ? e.touches[0]?.clientY ?? 0 : e.clientY
    return {
      x: (clientX - rect.left) / rect.width,
      y: (clientY - rect.top) / rect.height,
    }
  }

  const pinchRef = useRef<{
    initialDist: number
    layerType: "photo" | "text"
    id?: string
    initialScale: number
  } | null>(null)

  function hitTest(mx: number, my: number): { type: "photo" | "text"; id?: string } | null {
    if (Math.abs(mx - textLayer.x) < 0.15 && Math.abs(my - textLayer.y) < 0.1) {
      return { type: "text" }
    }
    for (let i = photos.length - 1; i >= 0; i--) {
      const p = photos[i]
      if (Math.abs(mx - p.x) < p.scale / 2 && Math.abs(my - p.y) < p.scale / 2) {
        return { type: "photo", id: p.id }
      }
    }
    return null
  }

  function handlePointerDown(e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current
    if (!canvas) return

    // Pinch start
    if ("touches" in e && e.touches.length === 2) {
      e.preventDefault()
      const t = e.touches
      const dist = Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)
      const rect = canvas.getBoundingClientRect()
      const midX = ((t[0].clientX + t[1].clientX) / 2 - rect.left) / rect.width
      const midY = ((t[0].clientY + t[1].clientY) / 2 - rect.top) / rect.height
      const hit = hitTest(midX, midY)
      if (hit) {
        const scale =
          hit.type === "text"
            ? textLayer.fontSize
            : (photos.find((p) => p.id === hit.id)?.scale ?? 0.4)
        pinchRef.current = { initialDist: dist, layerType: hit.type, id: hit.id, initialScale: scale }
      }
      return
    }

    if ("touches" in e) e.preventDefault()

    const { x, y } = getEventCoords(e, canvas)
    const hit = hitTest(x, y)

    if (hit) {
      // Select the layer
      if (hit.type === "text") {
        setSelected({ type: "text" })
      } else if (hit.id) {
        setSelected({ type: "photo", id: hit.id })
      }
      setDragging(hit)
    } else {
      // Tap on empty area deselects
      setSelected(null)
      setBottomPanel(null)
    }
  }

  function handlePointerMove(e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current
    if (!canvas) return

    // Pinch move
    if ("touches" in e && e.touches.length === 2 && pinchRef.current) {
      e.preventDefault()
      const t = e.touches
      const dist = Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY)
      const factor = dist / pinchRef.current.initialDist
      const newScale = pinchRef.current.initialScale * factor

      if (pinchRef.current.layerType === "text") {
        setTextLayer((prev) => ({ ...prev, fontSize: clamp(newScale, 0.03, 0.12) }))
      } else if (pinchRef.current.id) {
        const id = pinchRef.current.id
        setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, scale: clamp(newScale, 0.05, 1.0) } : p)))
      }
      return
    }

    if (!dragging) return
    if ("touches" in e) e.preventDefault()

    const { x, y } = getEventCoords(e, canvas)
    const mx = clamp(x, 0, 1)
    const my = clamp(y, 0, 1)

    if (dragging.type === "text") {
      setTextLayer((t) => ({ ...t, x: mx, y: my }))
    } else if (dragging.type === "photo" && dragging.id) {
      setPhotos((prev) => prev.map((p) => (p.id === dragging.id ? { ...p, x: mx, y: my } : p)))
    }
  }

  function handlePointerUp() {
    setDragging(null)
    pinchRef.current = null
  }

  // ── Layer actions ─────────────────────────────────────────────────────

  function handleAddPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    for (const file of Array.from(files)) {
      const url = URL.createObjectURL(file)
      const newId = uid()
      setPhotos((prev) => [
        ...prev,
        { id: newId, url, file, x: 0.35, y: 0.4, scale: 0.4, opacity: 1, style: "soft_fade" },
      ])
      setSelected({ type: "photo", id: newId })
    }
    e.target.value = ""
  }

  function removeSelected() {
    if (!selected) return
    if (selected.type === "photo") {
      setPhotos((prev) => prev.filter((p) => p.id !== selected.id))
      photoImagesRef.current.delete(selected.id)
    }
    setSelected(null)
    setBottomPanel(null)
  }

  function updateSelectedPhoto(updates: Partial<LegacyPhotoLayer>) {
    if (selected?.type !== "photo") return
    setPhotos((prev) => prev.map((p) => (p.id === selected.id ? { ...p, ...updates } : p)))
  }

  // ── Generate / Approve ────────────────────────────────────────────────

  function buildLayout(): LegacyLayout {
    return {
      photos,
      text: {
        ...textLayer,
        name,
        dates,
        additional: additionalText,
        font_size: textLayer.fontSize,
      },
    }
  }

  async function handleGenerate() {
    setGenerating(true)
    try {
      const result = await onGenerate(buildLayout())
      setProofUrl(result.proof_url)
      setTifUrl(result.tif_url)
      setShowProof(true)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || "Failed to generate proof")
    } finally {
      setGenerating(false)
    }
  }

  function handleApprove() {
    if (proofUrl && tifUrl) {
      onApprove(buildLayout(), proofUrl, tifUrl)
    }
  }

  // Canvas dimensions — fit viewport width
  const canvasWidth = 600
  const bg = bgImageRef.current
  const canvasHeight = bg ? Math.round(canvasWidth * (bg.naturalHeight / bg.naturalWidth)) : 300

  const selectedPhoto = selected?.type === "photo" ? photos.find((p) => p.id === selected.id) : null
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Proof preview (full-screen modal) ─────────────────────────────────

  if (showProof && proofUrl) {
    return (
      <div className="fixed inset-0 z-50 bg-black flex flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-black/80">
          <button
            onClick={() => setShowProof(false)}
            className="flex items-center gap-1 text-white text-sm"
          >
            <RotateCcw className="h-4 w-4" /> Edit
          </button>
          <span className="text-white text-sm font-medium">Preview</span>
          <div className="w-16" />
        </div>

        {/* Proof image — pinch-to-zoom via overflow scroll */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-4">
          <img
            src={proofUrl}
            alt="Legacy proof"
            className="max-w-none w-full"
            style={{ touchAction: "pinch-zoom" }}
          />
        </div>

        {/* Bottom actions */}
        <div className="px-4 py-4 bg-black/80 space-y-2 safe-bottom">
          <Button
            onClick={handleApprove}
            className="w-full bg-green-600 hover:bg-green-700 text-white"
          >
            <Check className="h-4 w-4 mr-1" /> Approve & finish
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowProof(false)}
            className="w-full border-white/30 text-white hover:bg-white/10"
          >
            <RotateCcw className="h-4 w-4 mr-1" /> Adjust & regenerate
          </Button>
        </div>
      </div>
    )
  }

  // ── Main compositor layout ────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-40 bg-gray-950 flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-3 py-2.5 bg-gray-900 border-b border-gray-800">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 text-gray-300 text-sm"
        >
          <ChevronLeft className="h-4 w-4" /> Back
        </button>
        <span className="text-white text-sm font-medium truncate max-w-[50%]">
          {name || "Compositor"}
        </span>
        <Button
          size="sm"
          onClick={handleGenerate}
          loading={generating || isGenerating}
          className="text-xs px-3 h-8"
        >
          Submit
        </Button>
      </div>

      {/* Canvas area — takes remaining space */}
      <div className="flex-1 overflow-hidden flex items-center justify-center bg-gray-950 px-2">
        <canvas
          ref={canvasRef}
          width={canvasWidth}
          height={canvasHeight}
          className="w-full max-h-full rounded-lg cursor-move touch-none"
          style={{ objectFit: "contain" }}
          onMouseDown={handlePointerDown}
          onMouseMove={handlePointerMove}
          onMouseUp={handlePointerUp}
          onMouseLeave={handlePointerUp}
          onTouchStart={handlePointerDown}
          onTouchMove={handlePointerMove}
          onTouchEnd={handlePointerUp}
        />
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleAddPhoto}
      />

      {/* Bottom panel — context-sensitive controls */}
      {bottomPanel === "photo-controls" && selectedPhoto && (
        <div className="bg-gray-900 border-t border-gray-800 px-4 py-3 space-y-3 animate-in slide-in-from-bottom-4 duration-200">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Photo settings</span>
            <button onClick={() => setBottomPanel(null)} className="text-gray-400">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="flex gap-4">
            <label className="text-[11px] text-gray-400 flex-1">
              Size
              <input
                type="range"
                min="0.1"
                max="0.8"
                step="0.02"
                value={selectedPhoto.scale}
                onChange={(e) => updateSelectedPhoto({ scale: parseFloat(e.target.value) })}
                className="w-full accent-blue-500"
              />
            </label>
            <label className="text-[11px] text-gray-400 flex-1">
              Opacity
              <input
                type="range"
                min="0.2"
                max="1"
                step="0.05"
                value={selectedPhoto.opacity}
                onChange={(e) => updateSelectedPhoto({ opacity: parseFloat(e.target.value) })}
                className="w-full accent-blue-500"
              />
            </label>
          </div>
          <div className="flex gap-3 text-[11px] text-gray-300">
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={selectedPhoto.style === "soft_fade"}
                onChange={() => updateSelectedPhoto({ style: "soft_fade" })}
                className="accent-blue-500"
              />
              Soft fade
            </label>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={selectedPhoto.style === "hard_edge"}
                onChange={() => updateSelectedPhoto({ style: "hard_edge" })}
                className="accent-blue-500"
              />
              Hard edge
            </label>
          </div>
        </div>
      )}

      {bottomPanel === "text-controls" && (
        <div className="bg-gray-900 border-t border-gray-800 px-4 py-3 space-y-3 animate-in slide-in-from-bottom-4 duration-200">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Text settings</span>
            <button onClick={() => setBottomPanel(null)} className="text-gray-400">
              <X className="h-4 w-4" />
            </button>
          </div>
          <label className="text-[11px] text-gray-400 block">
            Size
            <input
              type="range"
              min="0.03"
              max="0.12"
              step="0.005"
              value={textLayer.fontSize}
              onChange={(e) => setTextLayer((t) => ({ ...t, fontSize: parseFloat(e.target.value) }))}
              className="w-full accent-blue-500"
            />
          </label>
          <div className="flex gap-3 text-[11px] text-gray-300">
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={textLayer.color === "white"}
                onChange={() => setTextLayer((t) => ({ ...t, color: "white" }))}
                className="accent-blue-500"
              />
              White
            </label>
            <label className="flex items-center gap-1">
              <input
                type="radio"
                checked={textLayer.color === "black"}
                onChange={() => setTextLayer((t) => ({ ...t, color: "black" }))}
                className="accent-blue-500"
              />
              Black
            </label>
            <label className="flex items-center gap-1 ml-auto">
              <input
                type="checkbox"
                checked={textLayer.shadow}
                onChange={(e) => setTextLayer((t) => ({ ...t, shadow: e.target.checked }))}
                className="accent-blue-500"
              />
              Shadow
            </label>
          </div>
        </div>
      )}

      {/* Bottom toolbar */}
      <div className="bg-gray-900 border-t border-gray-800 px-2 py-2 safe-bottom">
        {!selected ? (
          // No selection — general tools
          <div className="flex items-center justify-around">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
            >
              <ImageIcon className="h-5 w-5" />
              <span className="text-[10px]">Add photo</span>
            </button>
            <button
              onClick={() => {
                setSelected({ type: "text" })
                setBottomPanel("text-controls")
              }}
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
            >
              <Type className="h-5 w-5" />
              <span className="text-[10px]">Edit text</span>
            </button>
          </div>
        ) : selected.type === "photo" ? (
          // Photo selected — layer-specific tools
          <div className="flex items-center justify-around">
            <button
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
              onClick={() => toast.info("Drag photo on canvas to move")}
            >
              <Move className="h-5 w-5" />
              <span className="text-[10px]">Move</span>
            </button>
            <button
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
              onClick={() => setBottomPanel(bottomPanel === "photo-controls" ? null : "photo-controls")}
            >
              <ZoomIn className="h-5 w-5" />
              <span className="text-[10px]">Style</span>
            </button>
            <button
              className="flex flex-col items-center gap-0.5 text-red-400 active:text-red-300 p-2"
              onClick={removeSelected}
            >
              <Trash2 className="h-5 w-5" />
              <span className="text-[10px]">Delete</span>
            </button>
          </div>
        ) : (
          // Text selected — text tools
          <div className="flex items-center justify-around">
            <button
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
              onClick={() => toast.info("Drag text on canvas to move")}
            >
              <Move className="h-5 w-5" />
              <span className="text-[10px]">Move</span>
            </button>
            <button
              className="flex flex-col items-center gap-0.5 text-gray-300 active:text-blue-400 p-2"
              onClick={() => setBottomPanel(bottomPanel === "text-controls" ? null : "text-controls")}
            >
              <Maximize className="h-5 w-5" />
              <span className="text-[10px]">Size</span>
            </button>
            <button
              className={`flex flex-col items-center gap-0.5 p-2 ${
                textLayer.color === "white" ? "text-white" : "text-gray-600"
              }`}
              onClick={() =>
                setTextLayer((t) => ({ ...t, color: t.color === "white" ? "black" : "white" }))
              }
            >
              <Sun className="h-5 w-5" />
              <span className="text-[10px]">Color</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
