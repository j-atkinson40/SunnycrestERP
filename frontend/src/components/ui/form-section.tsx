/**
 * Bridgeable FormSection — Aesthetic Arc Session 3.
 *
 * Lightweight form section wrapper — title + description + children.
 * Net-new primitive. Complements, doesn't replace, Card. Use Card for
 * elevated surfaces; use FormSection for in-form grouping without
 * elevation.
 *
 * Tokens per DESIGN_LANGUAGE.md §4 (heading pairings) + §5 (vertical
 * rhythm):
 *   - Title: text-h4 font-medium text-content-strong
 *   - Description: text-body-sm text-content-muted
 *   - Section-to-content gap: space-3 (§5 "subsection heading to body
 *     content: space-3 tight")
 *   - Content-to-next-section gap: space-6 generous (applied via
 *     FormStack helper, below)
 *
 * Usage:
 *
 *     <FormSection title="Contact" description="How we reach this person.">
 *       <Input ... />
 *       <Input ... />
 *     </FormSection>
 *
 * For grouped sections, compose inside a FormStack:
 *
 *     <FormStack>
 *       <FormSection title="Basics">...</FormSection>
 *       <FormSection title="Contact">...</FormSection>
 *     </FormStack>
 *
 * FormFooter: sticky or in-flow form footer with action buttons
 * (Cancel, Save). Pairs with FormSection for multi-section forms.
 */

import * as React from "react";
import { cn } from "@/lib/utils";

export interface FormSectionProps
  extends React.HTMLAttributes<HTMLElement> {
  title?: string;
  description?: React.ReactNode;
  /** Mark the section as containing an error — tinted left border. */
  error?: boolean;
}

function FormSection({
  title,
  description,
  error,
  className,
  children,
  ...props
}: FormSectionProps) {
  return (
    <section
      data-slot="form-section"
      data-error={error ? "true" : undefined}
      className={cn(
        "flex flex-col gap-3 font-plex-sans",
        error && "border-l-2 border-status-error pl-4",
        className,
      )}
      {...props}
    >
      {title || description ? (
        <div className="flex flex-col gap-1">
          {title ? (
            <h3 className="text-h4 font-medium leading-snug text-content-strong">
              {title}
            </h3>
          ) : null}
          {description ? (
            <p className="text-body-sm text-content-muted">{description}</p>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

/** Vertical stack of form sections with generous between-section
 * spacing per DESIGN_LANGUAGE.md §5 vertical-rhythm rules. */
function FormStack({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="form-stack"
      className={cn("flex flex-col gap-8", className)}
      {...props}
    />
  );
}

/** Form footer: sticky or in-flow. Pairs Cancel + primary action in a
 * row with generous spacing. Matches DialogFooter convention
 * (bg-surface-base + border-t) for visual consistency. */
function FormFooter({
  className,
  sticky = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { sticky?: boolean }) {
  return (
    <div
      data-slot="form-footer"
      data-sticky={sticky ? "true" : undefined}
      className={cn(
        "flex items-center justify-end gap-3 border-t border-border-subtle bg-surface-base px-6 py-4 rounded-b-md",
        sticky && "sticky bottom-0 z-10",
        className,
      )}
      {...props}
    />
  );
}

export { FormSection, FormStack, FormFooter };
