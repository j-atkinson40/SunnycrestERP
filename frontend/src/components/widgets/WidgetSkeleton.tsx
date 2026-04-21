// WidgetSkeleton — loading placeholder matching widget content shape.
// Phase II Batch 1a — `bg-gray-200` → `bg-surface-sunken` for mode-aware
// recessed shimmer that matches DL dark-mode cocktail-lounge mood.

export default function WidgetSkeleton() {
  return (
    <div className="animate-pulse space-y-3 p-1">
      <div className="h-3 w-2/3 rounded-sm bg-surface-sunken" />
      <div className="h-3 w-full rounded-sm bg-surface-sunken" />
      <div className="h-3 w-5/6 rounded-sm bg-surface-sunken" />
      <div className="h-3 w-1/2 rounded-sm bg-surface-sunken" />
    </div>
  )
}
