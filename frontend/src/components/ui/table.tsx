"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Table — Aesthetic Arc Session 3 refresh.
 *
 * Tokens per DESIGN_LANGUAGE.md §3 + §5 + §6:
 *   - Header: border-b border-border-subtle; cells text-content-strong
 *     font-medium uppercase tracking-wider at text-caption — matches
 *     the sidebar section-eyebrow pattern for tabular heading voice.
 *   - Row: border-b border-border-subtle; hover bg-accent-subtle/60;
 *     selected bg-accent-muted — consistent with dropdown-item hover
 *     pattern from Session 2.
 *   - Cell padding: p-3 (12px) default matching §5 "table cell py-3 px-4"
 *     generous-default; pages can override with className.
 *   - Footer (tfoot): bg-surface-base + border-t border-border-subtle
 *     (sinking feel matching Card + Dialog footer).
 *   - Transitions: duration-quick ease-settle on hover/selected.
 *
 * Numeric tabular alignment: opt-in via className (`tabular-nums`) on
 * cells that render numbers in columns. See DESIGN_LANGUAGE §4 Numerals.
 */

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn(
          "w-full caption-bottom font-plex-sans text-body-sm text-content-base",
          className
        )}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-b [&_tr]:border-border-subtle", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t border-border-subtle bg-surface-base font-medium text-content-strong [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b border-border-subtle transition-colors duration-quick ease-settle hover:bg-accent-subtle/60 data-[state=selected]:bg-accent-muted",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-3 text-left align-middle whitespace-nowrap font-medium text-micro uppercase tracking-wider text-content-muted [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-3 align-middle whitespace-nowrap text-content-base [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-caption text-content-muted", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
