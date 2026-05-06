/**
 * HierarchicalEditorBrowser — shared two-level browser for editor
 * surfaces with categorized content (Focus Editor, Workflows,
 * potentially future editors).
 *
 * Pattern: top-level categories with child templates underneath.
 * Operator clicks a category → category-level editing surface;
 * clicks a template → template-specific editing surface.
 *
 * The component is purely presentational — the consuming editor
 * manages state (selectedCategoryId, selectedTemplateId, search) and
 * passes it in as props. Lifts decisions about category/template
 * activation up to the page (which knows the editor surface to
 * dispatch to).
 *
 * Used by:
 *   • Focus Editor at /visual-editor/focuses — categories are 5 Focus
 *     types; templates are concrete Focus instances (funeral-scheduling
 *     under Decision Focus, etc.)
 *   • Workflows refactor at /visual-editor/workflows — categories are
 *     workflow types (funeral_cascade, quote_to_pour); templates are
 *     specific workflow_template records per type.
 *
 * Empty categories (no templates yet — e.g. Generation Focus with
 * arrangement_scribe + triage_decision before they're built as
 * production primitives) render with an empty-state caption underneath
 * rather than a misleading collapse. Operators see "what's possible
 * here" even when nothing is authored yet.
 */
import { useMemo } from "react"
import { ChevronDown, ChevronRight, Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"


export interface HierarchicalCategory {
  /** Stable id used as selection key + React key. */
  id: string
  /** Operator-facing label. */
  label: string
  /** Optional one-line description shown under the label. */
  description?: string
  /** Optional badge text (e.g. "5 templates", "platform-shipped"). */
  badge?: string
  /** Optional icon component. Renders 14px to the left of the label. */
  icon?: React.ComponentType<{ size?: number; className?: string }>
}


export interface HierarchicalTemplate {
  /** Stable id used as selection key + React key. */
  id: string
  /** Operator-facing label. */
  label: string
  /** Optional one-line description shown under the label. */
  description?: string
  /** Optional badge text. */
  badge?: string
  /** Category id this template belongs to. */
  categoryId: string
}


export interface HierarchicalEditorBrowserProps {
  categories: HierarchicalCategory[]
  templates: HierarchicalTemplate[]
  /** Currently-selected category (when no template is selected). */
  selectedCategoryId: string | null
  /** Currently-selected template (overrides category-only selection). */
  selectedTemplateId: string | null
  /** Search query. Filtering matches against category + template
   *  labels + descriptions case-insensitively. */
  search: string
  onSearchChange: (next: string) => void
  /** Fired when the operator clicks a category row (selects the
   *  category for category-level editing, deselects template). */
  onSelectCategory: (categoryId: string) => void
  /** Fired when the operator clicks a template row. */
  onSelectTemplate: (templateId: string) => void
  /** Optional rendering override for category-level empty state
   *  (when no templates exist for that category). Default is a
   *  subtle "No templates yet" caption. */
  emptyStateForCategory?: (category: HierarchicalCategory) => React.ReactNode
  /** Optional override for the search-placeholder copy. */
  searchPlaceholder?: string
}


export function HierarchicalEditorBrowser({
  categories,
  templates,
  selectedCategoryId,
  selectedTemplateId,
  search,
  onSearchChange,
  onSelectCategory,
  onSelectTemplate,
  emptyStateForCategory,
  searchPlaceholder = "Filter categories + templates",
}: HierarchicalEditorBrowserProps) {
  // Group templates by their category id for fast lookup.
  const templatesByCategory = useMemo(() => {
    const map = new Map<string, HierarchicalTemplate[]>()
    for (const t of templates) {
      const list = map.get(t.categoryId) ?? []
      list.push(t)
      map.set(t.categoryId, list)
    }
    return map
  }, [templates])

  // Filter categories + templates by search. A category matches
  // either directly (its own label/description matches) OR
  // transitively (any of its templates matches). Matched-only
  // rendering keeps the browser scannable when the operator is
  // hunting for a specific item.
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) {
      return {
        categories,
        // Deduplicated map matching templatesByCategory.
        templatesByCategory,
      }
    }
    const matches = (s: string | undefined): boolean =>
      typeof s === "string" && s.toLowerCase().includes(term)

    const matchedTemplatesByCategory = new Map<string, HierarchicalTemplate[]>()
    for (const c of categories) {
      const list = templatesByCategory.get(c.id) ?? []
      const matchingTemplates = list.filter(
        (t) => matches(t.label) || matches(t.description),
      )
      const categorySelfMatches =
        matches(c.label) || matches(c.description)
      if (categorySelfMatches) {
        // Category matches → include all its templates.
        matchedTemplatesByCategory.set(c.id, list)
      } else if (matchingTemplates.length > 0) {
        // Some templates match → include those + the category
        // (so the operator can navigate into the match's parent).
        matchedTemplatesByCategory.set(c.id, matchingTemplates)
      }
    }
    const visibleCategories = categories.filter((c) =>
      matchedTemplatesByCategory.has(c.id),
    )
    return {
      categories: visibleCategories,
      templatesByCategory: matchedTemplatesByCategory,
    }
  }, [categories, templatesByCategory, search])

  return (
    <div
      className="flex h-full flex-col"
      data-testid="hierarchical-editor-browser"
    >
      {/* Search */}
      <div className="border-b border-border-subtle px-2 py-1.5">
        <div className="relative">
          <Search
            size={11}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
          />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-7 pl-7 text-caption"
            data-testid="hierarchical-browser-search"
          />
        </div>
      </div>

      {/* Categories + templates */}
      <div className="flex-1 overflow-y-auto" data-testid="hierarchical-browser-list">
        {filtered.categories.length === 0 && (
          <div className="px-3 py-6 text-center text-caption text-content-muted">
            No categories match.
          </div>
        )}
        {filtered.categories.map((category) => {
          const categoryTemplates =
            filtered.templatesByCategory.get(category.id) ?? []
          const isCategorySelected =
            selectedCategoryId === category.id && selectedTemplateId === null
          const Icon = category.icon
          return (
            <div
              key={category.id}
              data-testid={`hierarchical-category-${category.id}`}
            >
              {/* Category row */}
              <button
                type="button"
                onClick={() => onSelectCategory(category.id)}
                className={cn(
                  "flex w-full items-start gap-2 px-3 py-2 text-left transition-colors hover:bg-accent-subtle/40",
                  isCategorySelected && "bg-accent-subtle/60",
                )}
                data-testid={`hierarchical-category-row-${category.id}`}
                data-selected={isCategorySelected ? "true" : "false"}
              >
                <ChevronDown
                  size={11}
                  className="mt-1 flex-shrink-0 text-content-muted"
                />
                {Icon && (
                  <Icon size={14} className="mt-0.5 flex-shrink-0 text-content-muted" />
                )}
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="truncate text-body-sm font-medium text-content-strong">
                      {category.label}
                    </span>
                    {category.badge && (
                      <span className="flex-shrink-0 rounded-sm bg-surface-sunken px-1.5 py-0.5 text-[10px] font-plex-mono text-content-muted">
                        {category.badge}
                      </span>
                    )}
                  </div>
                  {category.description && (
                    <span className="truncate text-caption text-content-muted">
                      {category.description}
                    </span>
                  )}
                </div>
              </button>

              {/* Templates under this category */}
              <div data-testid={`hierarchical-templates-${category.id}`}>
                {categoryTemplates.length === 0 ? (
                  <div className="ml-7 mr-3 mb-1 rounded-sm border border-dashed border-border-subtle px-2 py-1.5 text-caption text-content-subtle">
                    {emptyStateForCategory
                      ? emptyStateForCategory(category)
                      : "No templates yet."}
                  </div>
                ) : (
                  categoryTemplates.map((template) => {
                    const isTemplateSelected =
                      selectedTemplateId === template.id
                    return (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => onSelectTemplate(template.id)}
                        className={cn(
                          "flex w-full items-start gap-2 pl-9 pr-3 py-1.5 text-left transition-colors hover:bg-accent-subtle/40",
                          isTemplateSelected && "bg-accent-subtle/60",
                        )}
                        data-testid={`hierarchical-template-row-${template.id}`}
                        data-selected={isTemplateSelected ? "true" : "false"}
                      >
                        <ChevronRight
                          size={10}
                          className="mt-1 flex-shrink-0 text-content-muted"
                        />
                        <div className="flex min-w-0 flex-1 flex-col">
                          <div className="flex items-center justify-between gap-1.5">
                            <span className="truncate text-caption font-medium text-content-strong">
                              {template.label}
                            </span>
                            {template.badge && (
                              <span className="flex-shrink-0 rounded-sm bg-surface-sunken px-1.5 py-0.5 text-[10px] font-plex-mono text-content-muted">
                                {template.badge}
                              </span>
                            )}
                          </div>
                          {template.description && (
                            <span className="truncate text-[11px] text-content-muted">
                              {template.description}
                            </span>
                          )}
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
