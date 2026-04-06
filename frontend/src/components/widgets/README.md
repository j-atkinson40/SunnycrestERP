# Widget Dashboard Framework

Shared infrastructure for configurable widget dashboards across Bridgeable.

## Adding a new dashboard page

1. Choose a `page_context` slug (e.g. `'home'`, `'company_detail'`).

2. Add widget definitions to `backend/app/services/widgets/widget_registry.py` with the new page_context in their `page_contexts` array.

3. In the new page component:

```tsx
import { useDashboard } from '@/components/widgets/useDashboard'
import WidgetGrid from '@/components/widgets/WidgetGrid'
import { MY_PAGE_WIDGETS } from '@/components/widgets/my-page'

export default function MyDashboardPage() {
  const dashboard = useDashboard('my_page_context')

  return (
    <WidgetGrid
      widgets={dashboard.layout}
      componentMap={MY_PAGE_WIDGETS}
      editMode={dashboard.editMode}
      onReorder={dashboard.reorderWidgets}
      onRemove={dashboard.removeWidget}
      onSizeChange={dashboard.resizeWidget}
    />
  )
}
```

4. Create widget components in `frontend/src/components/widgets/{page-context}/`.

5. Create a component map (see `ops-board/index.ts` for the pattern).

## Adding a new widget

1. Add the definition to `WIDGET_DEFINITIONS` in `widget_registry.py` with the correct `page_contexts`.

2. Create a component in the appropriate `widgets/{page-context}/` directory following the `WidgetWrapper` pattern.

3. Register it in the page's component map:

```ts
export const MY_PAGE_WIDGETS: WidgetComponentMap = {
  existing_widget: ExistingWidget,
  your_new_widget: YourNewWidget,
}
```

4. Restart the backend (seeder runs on startup) or run the seeder manually.

The widget automatically appears in the WidgetPicker for users on that page.

## Key files

| File | Purpose |
|------|---------|
| `types.ts` | Shared TypeScript interfaces |
| `useDashboard.ts` | Hook managing layout state, edit mode, save |
| `useWidgetData.ts` | Data fetching hook with auto-refresh |
| `WidgetGrid.tsx` | Drag-and-drop grid container |
| `WidgetWrapper.tsx` | Standard widget chrome (header, refresh, menu) |
| `WidgetPicker.tsx` | Slide-in panel for adding widgets |
| `WidgetErrorBoundary.tsx` | Per-widget error isolation |
| `WidgetSkeleton.tsx` | Loading placeholder |

## Backend

| File | Purpose |
|------|---------|
| `models/widget_definition.py` | Widget catalog table |
| `models/user_widget_layout.py` | Per-user layout persistence |
| `models/extension_widget.py` | Extension widget tracking |
| `services/widgets/widget_service.py` | Layout CRUD, availability checks |
| `services/widgets/widget_registry.py` | Seed data + startup seeder |
| `api/routes/widgets.py` | Layout API endpoints |
| `api/routes/widget_data.py` | Widget data summary endpoints |
