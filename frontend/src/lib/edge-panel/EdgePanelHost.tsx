/**
 * R-5.0 — EdgePanelHost.
 *
 * Renders both the always-visible handle + the slide-in panel at the
 * tenant route root. Wires the keyboard + gesture hooks so they fire
 * once globally rather than per-consumer.
 */
import { EdgePanel } from "./EdgePanel"
import { EdgePanelHandle } from "./EdgePanelHandle"
import { useEdgePanelGesture } from "./useEdgePanelGesture"
import { useEdgePanelKeyboard } from "./useEdgePanelKeyboard"


export function EdgePanelHost() {
  useEdgePanelKeyboard()
  useEdgePanelGesture()
  return (
    <>
      <EdgePanelHandle />
      <EdgePanel />
    </>
  )
}
