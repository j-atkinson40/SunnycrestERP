// LegacyCompositor.tsx — Canvas-based legacy print proof compositor.
// Shared by manufacturer proof review and funeral home order station.

import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Plus, X, Check, RotateCcw } from "lucide-react"

// ── Types ────────────────────────────────────────────────────────────────────

export interface LegacyPhotoLayer {
  id: string
  url: string
  file?: File
  x: number
  y: number
  scale: number
  opacity: number
  style: "soft_fade" | "hard_edge"
}

export interface LegacyTextLayer {
  x: number
  y: number
  fontSize: number
  color: "white" | "black"
  shadow: boolean
}

export interface LegacyLayout {
  photos: LegacyPhotoLayer[]
  text: LegacyTextLayer
}

export interface GenerateResult {
  proof_url: string
  tif_url: string
}

interface LegacyCompositorProps {
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

// ── Helpers ──────────────────────────────────────────────────────────────────

function uid(): string {
  return Math.random().toString(36).slice(2, 10)
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

// ── Component ────────────────────────────────────────────────────────────────

export default function LegacyCompositor({
  backgroundUrl,
  mode,
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
}: LegacyCompositorProps) {
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
    }
  )
  const [generating, setGenerating] = useState(false)
  const [proofUrl, setProofUrl] = useState<string | null>(initialProofUrl || null)
  const [tifUrl, setTifUrl] = useState<string | null>(null)
  const [showProof, setShowProof] = useState(!!initialProofUrl)
  const [dragging, setDragging] = useState<{ type: "photo" | "text"; id?: string } | null>(null)
  const [bgLoaded, setBgLoaded] = useState(false)

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

  // Canvas rendering
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const bg = bgImageRef.current
    if (!canvas || !bg) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const cw = canvas.width
    const ch = canvas.height

    // Clear
    ctx.clearRect(0, 0, cw, ch)

    // Background
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
        // Elliptical clip with feathered edge approximation
        ctx.beginPath()
        ctx.ellipse(cw * photo.x, ch * photo.y, pw / 2 * 0.85, ph / 2 * 0.85, 0, 0, Math.PI * 2)
        ctx.clip()
      }

      ctx.drawImage(img, px, py, pw, ph)
      ctx.restore()
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
    }
  }, [photos, textLayer, name, dates, additionalText])

  useEffect(() => {
    if (bgLoaded && !showProof) {
      requestAnimationFrame(renderCanvas)
    }
  }, [bgLoaded, renderCanvas, showProof])

  // Canvas mouse interaction
  function handleCanvasMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = (e.clientX - rect.left) / rect.width
    const my = (e.clientY - rect.top) / rect.height

    // Check text hit
    if (Math.abs(mx - textLayer.x) < 0.15 && Math.abs(my - textLayer.y) < 0.1) {
      setDragging({ type: "text" })
      return
    }
    // Check photo hits (reverse order — top first)
    for (let i = photos.length - 1; i >= 0; i--) {
      const p = photos[i]
      if (Math.abs(mx - p.x) < p.scale / 2 && Math.abs(my - p.y) < p.scale / 2) {
        setDragging({ type: "photo", id: p.id })
        return
      }
    }
  }

  function handleCanvasMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!dragging || !canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = clamp((e.clientX - rect.left) / rect.width, 0, 1)
    const my = clamp((e.clientY - rect.top) / rect.height, 0, 1)

    if (dragging.type === "text") {
      setTextLayer((t) => ({ ...t, x: mx, y: my }))
    } else if (dragging.type === "photo" && dragging.id) {
      setPhotos((prev) =>
        prev.map((p) => (p.id === dragging.id ? { ...p, x: mx, y: my } : p))
      )
    }
  }

  function handleCanvasMouseUp() {
    setDragging(null)
  }

  // Photo management
  function handleAddPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files) return
    for (const file of Array.from(files)) {
      const url = URL.createObjectURL(file)
      setPhotos((prev) => [
        ...prev,
        { id: uid(), url, file, x: 0.35, y: 0.4, scale: 0.4, opacity: 1, style: "soft_fade" },
      ])
    }
    e.target.value = ""
  }

  function removePhoto(id: string) {
    setPhotos((prev) => prev.filter((p) => p.id !== id))
    photoImagesRef.current.delete(id)
  }

  function updatePhoto(id: string, updates: Partial<LegacyPhotoLayer>) {
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, ...updates } : p)))
  }

  // Generate
  async function handleGenerate() {
    setGenerating(true)
    try {
      const layout: LegacyLayout = { photos, text: textLayer }
      const result = await onGenerate(layout)
      setProofUrl(result.proof_url)
      setTifUrl(result.tif_url)
      setShowProof(true)
    } catch {
      // Error handling in parent
    } finally {
      setGenerating(false)
    }
  }

  function handleApprove() {
    if (proofUrl && tifUrl) {
      onApprove({ photos, text: textLayer }, proofUrl, tifUrl)
    }
  }

  // Compute canvas dimensions
  const canvasWidth = 800
  const bg = bgImageRef.current
  const canvasHeight = bg ? Math.round(canvasWidth * (bg.naturalHeight / bg.naturalWidth)) : 400

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* LEFT — Canvas / Proof */}
      <div className="flex-1 min-w-0">
        {showProof && proofUrl ? (
          <div>
            <img src={proofUrl} alt="Legacy proof" className="w-full rounded-lg border" />
            <p className="text-xs text-gray-500 text-center mt-2">Print-ready proof</p>
            <button
              onClick={() => setShowProof(false)}
              className="text-sm text-blue-600 mt-2 flex items-center gap-1 mx-auto"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Edit layout
            </button>
          </div>
        ) : (
          <div>
            <canvas
              ref={canvasRef}
              width={canvasWidth}
              height={canvasHeight}
              className="w-full rounded-lg border cursor-move bg-gray-100"
              onMouseDown={handleCanvasMouseDown}
              onMouseMove={handleCanvasMouseMove}
              onMouseUp={handleCanvasMouseUp}
              onMouseLeave={handleCanvasMouseUp}
            />
            <p className="text-xs text-gray-400 text-center mt-1">
              Drag photos and text to reposition
            </p>
          </div>
        )}
      </div>

      {/* RIGHT — Controls */}
      <div className="w-full lg:w-80 space-y-5 flex-shrink-0">
        {/* Photos */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Photos</Label>
            <label className="cursor-pointer">
              <input type="file" accept="image/*" multiple className="hidden" onChange={handleAddPhoto} />
              <span className="flex items-center gap-1 text-xs text-blue-600 font-medium">
                <Plus className="h-3.5 w-3.5" /> Add photo
              </span>
            </label>
          </div>
          {photos.length === 0 && (
            <p className="text-xs text-gray-400">No photos added. Text-only proof will be generated.</p>
          )}
          {photos.map((p) => (
            <div key={p.id} className="bg-gray-50 rounded-lg p-3 mb-2 space-y-2">
              <div className="flex items-center justify-between">
                <img src={p.url} alt="" className="w-12 h-12 rounded object-cover" />
                <button onClick={() => removePhoto(p.id)} className="text-gray-400 hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="flex gap-2">
                <label className="text-[11px] text-gray-500 flex-1">
                  Size
                  <input
                    type="range" min="0.1" max="0.8" step="0.02"
                    value={p.scale}
                    onChange={(e) => updatePhoto(p.id, { scale: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                </label>
                <label className="text-[11px] text-gray-500 flex-1">
                  Opacity
                  <input
                    type="range" min="0.2" max="1" step="0.05"
                    value={p.opacity}
                    onChange={(e) => updatePhoto(p.id, { opacity: parseFloat(e.target.value) })}
                    className="w-full"
                  />
                </label>
              </div>
              <div className="flex gap-2 text-[11px]">
                <label className="flex items-center gap-1">
                  <input type="radio" name={`style-${p.id}`} checked={p.style === "soft_fade"} onChange={() => updatePhoto(p.id, { style: "soft_fade" })} className="accent-blue-600" />
                  Soft fade
                </label>
                <label className="flex items-center gap-1">
                  <input type="radio" name={`style-${p.id}`} checked={p.style === "hard_edge"} onChange={() => updatePhoto(p.id, { style: "hard_edge" })} className="accent-blue-600" />
                  Hard edge
                </label>
              </div>
            </div>
          ))}
        </div>

        {/* Text controls */}
        <div>
          <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-2 block">Text</Label>
          <div className="space-y-2">
            <label className="text-[11px] text-gray-500 block">
              Size
              <input
                type="range" min="0.03" max="0.12" step="0.005"
                value={textLayer.fontSize}
                onChange={(e) => setTextLayer((t) => ({ ...t, fontSize: parseFloat(e.target.value) }))}
                className="w-full"
              />
            </label>
            <div className="flex gap-3 text-[11px]">
              <label className="flex items-center gap-1">
                <input type="radio" name="textColor" checked={textLayer.color === "white"} onChange={() => setTextLayer((t) => ({ ...t, color: "white" }))} className="accent-blue-600" />
                White
              </label>
              <label className="flex items-center gap-1">
                <input type="radio" name="textColor" checked={textLayer.color === "black"} onChange={() => setTextLayer((t) => ({ ...t, color: "black" }))} className="accent-blue-600" />
                Black
              </label>
              <label className="flex items-center gap-1 ml-auto">
                <input type="checkbox" checked={textLayer.shadow} onChange={(e) => setTextLayer((t) => ({ ...t, shadow: e.target.checked }))} className="accent-blue-600" />
                Shadow
              </label>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-2 pt-3 border-t border-gray-200">
          {!showProof && (
            <Button
              onClick={handleGenerate}
              loading={generating || isGenerating}
              className="w-full"
            >
              Preview legacy
            </Button>
          )}

          {showProof && proofUrl && (
            <>
              {mode === "manufacturer" && (
                <Button onClick={handleApprove} className="w-full bg-green-600 hover:bg-green-700">
                  <Check className="h-4 w-4 mr-1" /> Approve & send to print
                </Button>
              )}
              {mode === "funeral_home" && (
                <Button onClick={handleApprove} className="w-full">
                  <Check className="h-4 w-4 mr-1" /> Submit legacy order
                </Button>
              )}
              <Button variant="outline" onClick={() => setShowProof(false)} className="w-full">
                <RotateCcw className="h-4 w-4 mr-1" /> Regenerate
              </Button>
            </>
          )}

          {onCancel && (
            <Button variant="ghost" onClick={onCancel} className="w-full">
              Cancel
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
