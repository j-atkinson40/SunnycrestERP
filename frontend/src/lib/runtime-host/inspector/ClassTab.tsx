/**
 * Phase R-1 — Inspector Class tab.
 *
 * For the selected widget, look up its effective component classes
 * via `getEffectiveComponentClasses(entry)` (v1: each component
 * belongs to exactly one class — its ComponentKind). Resolve
 * `componentClassConfigurationsService.resolve(component_class)` for
 * the active class default, fetch the class registration's
 * `configurableProps` from `class-registrations.ts`, and render auto-
 * generated controls.
 *
 * Edits stage to EditModeProvider's `draftOverrides` keyed by
 * `component_class:{className}:{prop}`.
 *
 * Source badge per prop: registration-default vs. class-default vs.
 * draft. Reset-to-inherited per prop clears the staged override.
 */
import { useEffect, useMemo, useState } from "react"

import { CompactPropControl } from "@/bridgeable-admin/components/visual-editor/CompactPropControl"
import {
  componentClassConfigurationsService,
  type ResolvedClassConfiguration,
} from "@/bridgeable-admin/services/component-class-configurations-service"
import {
  getClassRegistration,
  type ClassRegistration,
} from "@/lib/visual-editor/registry/class-registrations"
import {
  getEffectiveComponentClasses,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry/types"

import { useEditMode } from "../edit-mode-context"


type SourceBadge =
  | "registration-default"
  | "class-default"
  | "draft"


export function ClassTab({ selectedEntry }: { selectedEntry: RegistryEntry }) {
  const editMode = useEditMode()
  const classes = getEffectiveComponentClasses(selectedEntry)

  // V1 invariant: exactly one class per component (the kind). Future
  // multi-class support would render a class picker here.
  const className = classes[0]
  const classRegistration: ClassRegistration | undefined = className
    ? getClassRegistration(className)
    : undefined

  const [resolved, setResolved] = useState<ResolvedClassConfiguration | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!className) return
    let cancelled = false
    setIsLoading(true)
    componentClassConfigurationsService
      .resolve(className)
      .then((res) => {
        if (!cancelled) setResolved(res)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] resolve class config failed", err)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [className])

  const target = className ?? ""
  const propsSchema: Record<string, ConfigPropSchema> =
    classRegistration?.configurableProps ?? {}

  // Collect staged drafts for this class.
  const draftMap = useMemo(() => {
    const map: Record<string, unknown> = {}
    for (const o of editMode.draftOverrides.values()) {
      if (
        o.type === "component_class" &&
        o.target === target &&
        o.value !== undefined
      ) {
        map[o.prop] = o.value
      }
    }
    return map
  }, [editMode.draftOverrides, target])

  const classDefaults = resolved?.props ?? {}

  // Effective = registration default → class default → draft (top wins).
  const effective = useMemo(() => {
    const eff: Record<string, unknown> = {}
    for (const [propName, schema] of Object.entries(propsSchema)) {
      if (propName in draftMap) {
        eff[propName] = draftMap[propName]
      } else if (propName in classDefaults) {
        eff[propName] = classDefaults[propName]
      } else {
        eff[propName] = schema.default
      }
    }
    return eff
  }, [propsSchema, classDefaults, draftMap])

  if (!className) {
    return (
      <div className="px-3 py-4 text-caption text-content-muted">
        This widget has no component class membership.
      </div>
    )
  }

  if (Object.keys(propsSchema).length === 0) {
    return (
      <div className="px-3 py-4 text-caption text-content-muted">
        Class <code>{className}</code> declares no class-level
        configurable props.
      </div>
    )
  }

  function badgeForProp(propName: string): SourceBadge {
    if (propName in draftMap) return "draft"
    if (propName in classDefaults) return "class-default"
    return "registration-default"
  }

  return (
    <div className="px-1 py-2" data-testid="runtime-inspector-class-tab">
      <div className="px-3 pb-2 text-caption text-content-muted">
        Editing class <code className="text-content-strong">{className}</code>
        {classRegistration ? ` — ${classRegistration.displayName}` : null}
        . Changes apply to every component in this class.
      </div>
      {isLoading && (
        <div className="px-3 py-1 text-caption text-content-muted">
          Loading…
        </div>
      )}
      {Object.entries(propsSchema).map(([propName, schema]) => {
        const value = effective[propName]
        const source = badgeForProp(propName)
        const draftKey = `component_class::${target}::${propName}`
        const isOverridden = editMode.draftOverrides.has(draftKey)
        return (
          <div
            key={propName}
            className="border-b border-border-subtle px-2 py-1.5"
            data-testid={`runtime-inspector-class-prop-${propName}`}
          >
            <CompactPropControl
              name={propName}
              schema={schema}
              value={value}
              source={source}
              onChange={(next) =>
                editMode.stageOverride({
                  type: "component_class",
                  target,
                  prop: propName,
                  value: next,
                })
              }
              isOverriddenAtCurrentScope={isOverridden}
              onReset={() => {
                editMode.clearStaged("component_class", target)
              }}
            />
          </div>
        )
      })}
    </div>
  )
}
