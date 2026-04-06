// WidgetSkeleton — loading placeholder matching widget content shape

export default function WidgetSkeleton() {
  return (
    <div className="animate-pulse space-y-3 p-1">
      <div className="h-3 w-2/3 rounded bg-gray-200" />
      <div className="h-3 w-full rounded bg-gray-200" />
      <div className="h-3 w-5/6 rounded bg-gray-200" />
      <div className="h-3 w-1/2 rounded bg-gray-200" />
    </div>
  )
}
