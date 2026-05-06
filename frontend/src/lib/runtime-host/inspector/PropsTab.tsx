/**
 * Phase R-1 — Inspector Props tab.
 *
 * For the selected widget, look up registry entry's
 * `configurableProps` and render auto-generated controls via
 * `PropControlDispatcher`. Edits stage to EditModeProvider's
 * `draftOverrides` keyed by `componentConfig:{kind}:{name}:{prop}`.
 *
 * Source badge per prop walks the resolution chain
 * (registration default → class default → platform → vertical →
 * tenant → draft) and shows where the visible value came from.
 *
 * Reset-to-inherited per prop clears the staged override.
 */
import { useEffect, useMemo, useState } from "react"

import { CompactPropControl } from "@/bridgeable-admin/components/visual-editor/CompactPropControl"
import {
  componentConfigurationsService,
  type ResolvedConfiguration,
} from "@/bridgeable-admin/services/component-configurations-service"
import {
  composeEffectiveProps,
  emptyConfigStack,
  resolvePropSource,
  stackFromResolvedConfig,
  type ConfigStack,
  type PropOverrideMap,
} from "@/lib/visual-editor/components/config-resolver"
import type {
  ComponentKind,
  RegistryEntry,
} from "@/lib/visual-editor/registry"

import { useEditMode } from "../edit-mode-context"


export function PropsTab({
  selectedEntry,
  vertical,
}: {
  selectedEntry: RegistryEntry
  vertical: string | null
}) {
  const editMode = useEditMode()
  const [resolved, setResolved] = useState<ResolvedConfiguration | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const kind = selectedEntry.metadata.type as ComponentKind
  const name = selectedEntry.metadata.name

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    const params: Parameters<typeof componentConfigurationsService.resolve>[0] = {
      component_kind: kind,
      component_name: name,
    }
    if (vertical) params.vertical = vertical
    componentConfigurationsService
      .resolve(params)
      .then((res) => {
        if (!cancelled) setResolved(res)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] resolve config failed", err)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [kind, name, vertical])

  const target = `${kind}:${name}`
  const propsSchema = selectedEntry.metadata.configurableProps ?? {}

  // Build the config stack for source-resolution + effective values.
  const stack: ConfigStack = useMemo(() => {
    const base = resolved
      ? stackFromResolvedConfig(resolved)
      : emptyConfigStack()
    // Layer staged drafts as the top tier.
    const draftMap: PropOverrideMap = {}
    for (const o of editMode.draftOverrides.values()) {
      if (
        o.type === "component_prop" &&
        o.target === target &&
        o.value !== undefined
      ) {
        draftMap[o.prop] = o.value
      }
    }
    return { ...base, draft: draftMap }
  }, [resolved, editMode.draftOverrides, target])

  const effective = useMemo(
    () => composeEffectiveProps(kind, name, stack),
    [kind, name, stack],
  )

  if (Object.keys(propsSchema).length === 0) {
    return (
      <div className="px-3 py-4 text-caption text-content-muted">
        This widget declares no configurable props. Theme + class
        edits still apply via their tabs.
      </div>
    )
  }

  return (
    <div className="px-1 py-2" data-testid="runtime-inspector-props-tab">
      {isLoading && (
        <div className="px-3 py-1 text-caption text-content-muted">
          Loading…
        </div>
      )}
      {Object.entries(propsSchema).map(([propName, schema]) => {
        const value = effective[propName]
        const source = resolvePropSource(propName, stack)
        const draftKey = `component_prop::${target}::${propName}`
        const isOverridden = editMode.draftOverrides.has(draftKey)
        return (
          <div
            key={propName}
            className="border-b border-border-subtle px-2 py-1.5"
            data-testid={`runtime-inspector-prop-${propName}`}
          >
            <CompactPropControl
              name={propName}
              schema={schema}
              value={value}
              source={source}
              onChange={(next) =>
                editMode.stageOverride({
                  type: "component_prop",
                  target,
                  prop: propName,
                  value: next,
                })
              }
              isOverriddenAtCurrentScope={isOverridden}
              onReset={() => {
                // Clear just this one staged prop.
                editMode.clearStaged("component_prop", target)
              }}
            />
          </div>
        )
      })}
    </div>
  )
}
