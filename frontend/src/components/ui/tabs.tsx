import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Bridgeable Tabs — Aesthetic Arc Session 3 refresh.
 *
 * Two variants:
 *   - default — recessed surface-sunken background with rounded-md
 *     pill; active tab sits on bg-surface-raised (lifts out of track)
 *     with text-content-strong.
 *   - line    — line indicator (accent, bottom-border) under active
 *     tab; transparent track. Used for hub sub-nav (CRMHub, Vault).
 *
 * Inactive: text-content-muted with hover→text-content-strong.
 * Focus: accent focus ring via focus-ring-accent utility.
 * Disabled: opacity-50 + pointer-events-none.
 * Motion: transition-colors duration-quick ease-settle.
 */

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: TabsPrimitive.Root.Props) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn(
        "group/tabs flex gap-2 font-plex-sans data-horizontal:flex-col",
        className
      )}
      {...props}
    />
  )
}

const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center rounded-md p-[3px] text-content-muted group-data-horizontal/tabs:h-8 group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col data-[variant=line]:rounded-none",
  {
    variants: {
      variant: {
        default: "bg-surface-sunken",
        line: "gap-1 bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function TabsList({
  className,
  variant = "default",
  ...props
}: TabsPrimitive.List.Props & VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        "relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded px-3 py-1 text-body-sm font-medium whitespace-nowrap text-content-muted outline-none transition-colors duration-quick ease-settle focus-ring-accent group-data-vertical/tabs:w-full group-data-vertical/tabs:justify-start hover:text-content-strong disabled:pointer-events-none disabled:opacity-50 has-data-[icon=inline-end]:pr-1 has-data-[icon=inline-start]:pl-1 aria-disabled:pointer-events-none aria-disabled:opacity-50 group-data-[variant=default]/tabs-list:data-active:shadow-level-1 group-data-[variant=line]/tabs-list:data-active:shadow-none",
        // Default variant: active tab lifts onto surface-raised.
        "group-data-[variant=default]/tabs-list:data-active:bg-surface-raised group-data-[variant=default]/tabs-list:data-active:text-content-strong",
        // Line variant: transparent + accent underline on active.
        "group-data-[variant=line]/tabs-list:bg-transparent group-data-[variant=line]/tabs-list:data-active:bg-transparent group-data-[variant=line]/tabs-list:data-active:text-content-strong",
        "after:absolute after:bg-accent after:opacity-0 after:transition-opacity after:duration-quick after:ease-settle group-data-horizontal/tabs:after:inset-x-0 group-data-horizontal/tabs:after:bottom-[-5px] group-data-horizontal/tabs:after:h-0.5 group-data-vertical/tabs:after:inset-y-0 group-data-vertical/tabs:after:-right-1 group-data-vertical/tabs:after:w-0.5 group-data-[variant=line]/tabs-list:data-active:after:opacity-100",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn(
        "flex-1 text-body-sm text-content-base outline-none",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants }
