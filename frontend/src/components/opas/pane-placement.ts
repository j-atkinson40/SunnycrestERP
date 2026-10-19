/**
 * Where an anchored pane sits. First free space, not on top of another.
 *
 * ⚠️ JAMES'S SECOND MULTI-PANE RULE (2026-10-19): "A new pane is placed in the first free
 * space, not on top of another."
 *
 * ⚠️ WHAT IT REPLACES, AND WHY IT WAS WRONG. `OpasHost` positioned anchored panes at
 * `right: 24 + i * 18, top: 72 + i * 22` — an index cascade, so a second pane sat 18px
 * left and 22px down from the first and covered almost all of it. With two 430px panes on
 * a 1440px screen there was room for both side by side and they overlapped anyway.
 *
 * ⚠️ MEASURED FROM THE PROTOTYPE'S `place()`, quoted:
 *
 *     function place(p){
 *       const r=stage.getBoundingClientRect(),W=p.el.offsetWidth||430,H=…,pad=16,…;
 *       const taken=panes.filter(w=>w!==p&&w.x!=null).map(w=>({l:w.x,t:w.y,
 *                     r:w.x+w.el.offsetWidth,b:w.y+w.el.offsetHeight}));
 *       const x0=Math.max(pad,Math.min(r.width*.06,r.width-W-pad));
 *       for(let x=x0;x+W<=r.width-pad;x+=24)
 *         if(!taken.some(t=>x<t.r+pad&&x+W>t.l-pad)){p.x=x;p.y=pad;setXY(p);return}
 *       const n=panes.length;p.x=clamp(x0+n*28,pad,r.width-W-pad);p.y=pad+n*22;setXY(p);
 *     }
 *
 * So: a HORIZONTAL-ONLY overlap test (the prototype always lands at `y = pad`), a 24px
 * scan step, a `pad` gap enforced on both sides, and an index cascade as the fallback
 * when no gap fits.
 *
 * ⚠️ ONE DEVIATION, STATED: THE SCAN RUNS RIGHT TO LEFT. The prototype scans from
 * `x0 = 6%` of the stage rightward. This app's info panes already anchor to `right: 24`
 * and James has walked that position for three rounds; scanning from the left would move
 * the FIRST pane to the other side of the screen, which is a redesign nobody asked for
 * inside a rule about the second pane. Right-to-left puts the first pane exactly where it
 * is today and the second one beside it instead of on top of it.
 *
 * ⚠️ AND THE PAD IS 16 LIKE THE PROTOTYPE'S, NOT 24 LIKE THE ANCHOR. `right: 24` is where
 * the first pane sits (it lines up with the command bar's own offset); 16 is the GAP
 * enforced between two panes. Two different measurements that happen to be adjacent.
 */

/** The prototype's `pad` — the gap kept between panes and at the stage edge. */
export const PANE_GAP = 16

/** The prototype's scan step. */
export const SCAN_STEP = 24

/** This app's right-edge anchor for the first info pane, matching the command bar. */
export const RIGHT_ANCHOR = 24

/** The top of the anchored band. Clears the sphere and the top chrome. */
export const TOP_ANCHOR = 72

/** An occupied horizontal span.
 *
 * ⚠️ NO `top` OR `height`, DELIBERATELY. The overlap test below is horizontal only — the
 * prototype's is too, because every anchored pane lands in the same top band. Carrying a
 * height here would be a field nothing reads, and the first person to add a vertical test
 * would find it already populated with a value nobody had checked. */
export interface Rect {
  readonly left: number
  readonly width: number
}

export interface Placement {
  readonly left: number
  readonly top: number
}

/**
 * The first free slot for a pane of `width`, scanning right to left.
 *
 * `taken` is every rect already occupied — dragged panes and slots assigned earlier in
 * the same pass. `index` is only used by the fallback cascade.
 */
export function firstFreeSlot(
  { stageWidth, width, taken, index }: {
    stageWidth: number
    width: number
    taken: readonly Rect[]
    index: number
  },
): Placement {
  // The rightmost left-edge a pane can have and still keep its anchor gap.
  const start = stageWidth - RIGHT_ANCHOR - width
  for (let left = start; left >= PANE_GAP; left -= SCAN_STEP) {
    // ⚠️ HORIZONTAL ONLY, LIKE THE PROTOTYPE. Every anchored pane lands in the same
    // top band, so two panes overlap exactly when their x ranges do. Testing vertical
    // overlap as well would let a pane be placed "free" underneath a taller one.
    const clashes = taken.some(
      (t) => left < t.left + t.width + PANE_GAP && left + width > t.left - PANE_GAP,
    )
    if (!clashes) return { left, top: TOP_ANCHOR }
  }
  // ⚠️ THE PROTOTYPE'S OWN FALLBACK, in this app's direction: when nothing fits, cascade
  // rather than refuse. An overlapping pane the director can drag beats a pane that
  // never appeared.
  return {
    left: clamp(start - index * 28, PANE_GAP, Math.max(PANE_GAP, start)),
    top: TOP_ANCHOR + index * 22,
  }
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

/**
 * Slots for every anchored pane, in pane order, so each one sees the ones before it.
 *
 * ⚠️ THE ASSIGNED SLOTS JOIN `taken` AS THEY ARE DECIDED. Computing all of them against
 * only the dragged panes would place every new pane in the SAME first free slot — which
 * is the overlap this module exists to remove, reintroduced one level up.
 */
export function anchoredSlots(
  panes: readonly { id: string; width: number }[],
  dragged: readonly Rect[],
  stageWidth: number,
): Record<string, Placement> {
  const taken: Rect[] = [...dragged]
  const out: Record<string, Placement> = {}
  panes.forEach((pane, index) => {
    const slot = firstFreeSlot({ stageWidth, width: pane.width, taken, index })
    out[pane.id] = slot
    taken.push({ left: slot.left, width: pane.width })
  })
  return out
}
