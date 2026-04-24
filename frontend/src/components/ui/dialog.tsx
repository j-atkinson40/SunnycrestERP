"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { XIcon } from "lucide-react"

/**
 * Bridgeable Dialog — Aesthetic Arc Session 2 refresh.
 *
 * Modal composition per DESIGN_LANGUAGE.md §6:
 *   - Overlay: bg-black/40 scrim (canonical form §9), duration-arrive
 *     ease-settle for enter / duration-settle ease-gentle for exit.
 *   - Content: bg-surface-raised (level-2 raised — one step above
 *     surrounding page / card content), rounded-lg (12px per Q2 —
 *     modals + signature surfaces), shadow-level-2, p-6 (§5 generous
 *     default — 24px).
 *   - Default size: max-w-sm preserved per Q3 (per-page sizing via
 *     className override across 58 existing call sites).
 *   - Close button: Ghost variant inherits the refreshed brass focus
 *     treatment.
 *
 * Motion:
 *   - Enter: duration-arrive (400ms) ease-settle — opacity + zoom-in
 *     from 95% (slight scale-in, "arriving" per §6 motion pattern).
 *   - Exit: duration-settle (300ms) ease-gentle — opacity fade only.
 *
 * Footer: bg-surface-base + border-t border-border-subtle — sinking
 * feel against elevated modal body, identical logic to CardFooter.
 */

function Dialog({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({ ...props }: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      // Phase A Session 4.2.6 — z-index routed through --z-modal
      // (token, value 105) instead of literal z-50. Dialogs opened
      // from inside a Focus (which sits at --z-focus: 100) must
      // render above the Focus Popup; the prior z-50 put them
      // behind it — QuickEditDialog mounted correctly but was
      // invisible. See DESIGN_LANGUAGE.md §9 Layering tokens.
      className={cn(
        "fixed inset-0 isolate bg-black/40 transition-opacity duration-arrive ease-settle supports-backdrop-filter:backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 data-closed:duration-settle data-closed:ease-gentle",
        className
      )}
      style={{ zIndex: "var(--z-modal)" }}
      {...props}
    />
  )
}

function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: DialogPrimitive.Popup.Props & {
  showCloseButton?: boolean
}) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Popup
        data-slot="dialog-content"
        // Phase A Session 4.2.6 — z-index routed through --z-modal
        // (105, above --z-focus: 100) so nested Dialogs inside a
        // Focus render above the Focus Popup. Prior literal z-50
        // put the Popup behind Focus → QuickEditDialog mounted
        // correctly but was invisible to the user.
        className={cn(
          "fixed top-1/2 left-1/2 grid w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-lg border border-border-subtle bg-surface-raised p-6 font-plex-sans text-body-sm text-content-base shadow-level-2 outline-none duration-arrive ease-settle sm:max-w-sm data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95 data-closed:duration-settle data-closed:ease-gentle",
          className
        )}
        style={{ zIndex: "var(--z-modal)" }}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            render={
              <Button
                variant="ghost"
                className="absolute top-2 right-2"
                size="icon-sm"
              />
            }
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Popup>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "-mx-6 -mb-6 flex flex-col-reverse gap-2 rounded-b-lg border-t border-border-subtle bg-surface-base p-4 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close render={<Button variant="outline" />}>
          Close
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "text-h3 font-medium leading-snug text-content-strong",
        className
      )}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn(
        "text-body-sm text-content-muted *:[a]:underline *:[a]:underline-offset-3 *:[a]:text-brass *:[a]:hover:text-brass-hover",
        className
      )}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
