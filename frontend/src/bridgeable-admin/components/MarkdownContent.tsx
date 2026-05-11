/**
 * R-8.y.d — minimal markdown renderer for PLUGIN_CONTRACTS.md
 * subsection content.
 *
 * Custom (no react-markdown dep) — handles the canonical subset
 * PLUGIN_CONTRACTS.md uses across all 24 categories:
 *   - paragraphs (separated by blank lines)
 *   - bullet lists (- or *)
 *   - inline `code spans`
 *   - bold via **text**
 *   - markdown links [label](url) — rendered as anchor tags
 *   - inline §N cross-references — rendered as clickable chips
 *
 * Not a general markdown engine. The PLUGIN_CONTRACTS.md prose
 * sticks to this subset deliberately so the snapshot's rich
 * subsections render coherently inside the browser without
 * pulling in a heavy parser.
 */

import { Fragment } from "react"
import type { JSX } from "react"


interface MarkdownContentProps {
  content: string
  onCrossReferenceClick?: (sectionNumber: number) => void
  className?: string
}


export function MarkdownContent({
  content,
  onCrossReferenceClick,
  className,
}: MarkdownContentProps) {
  if (!content || !content.trim()) {
    return null
  }

  // Split into paragraphs on blank-line boundaries. Preserve list
  // blocks (sequence of lines all starting with `-` or `*`).
  const paragraphs = splitParagraphs(content)

  return (
    <div
      className={className ?? "flex flex-col gap-3 text-body-sm text-content-base"}
    >
      {paragraphs.map((para, idx) => renderParagraph(para, idx, onCrossReferenceClick))}
    </div>
  )
}


function splitParagraphs(content: string): string[] {
  const lines = content.split("\n")
  const paragraphs: string[] = []
  let buf: string[] = []
  for (const line of lines) {
    if (!line.trim()) {
      if (buf.length > 0) {
        paragraphs.push(buf.join("\n"))
        buf = []
      }
    } else {
      buf.push(line)
    }
  }
  if (buf.length > 0) paragraphs.push(buf.join("\n"))
  return paragraphs
}


function renderParagraph(
  para: string,
  key: number,
  onCrossReferenceClick?: (sectionNumber: number) => void,
): JSX.Element {
  const lines = para.split("\n")
  const isList = lines.every((l) => /^\s*[-*]\s+/.test(l))

  if (isList) {
    return (
      <ul key={key} className="flex flex-col gap-1 pl-4 list-disc">
        {lines.map((line, i) => {
          const text = line.replace(/^\s*[-*]\s+/, "")
          return (
            <li key={i} className="leading-relaxed">
              {renderInline(text, onCrossReferenceClick)}
            </li>
          )
        })}
      </ul>
    )
  }

  // Plain paragraph — collapse single newlines into spaces.
  return (
    <p key={key} className="leading-relaxed">
      {renderInline(para.replace(/\n/g, " "), onCrossReferenceClick)}
    </p>
  )
}


function renderInline(
  text: string,
  onCrossReferenceClick?: (sectionNumber: number) => void,
): JSX.Element[] {
  // Tokenize for: **bold**, `code`, [text](url), §N cross-references.
  // Process in one pass — order matters: code spans before bold to
  // avoid conflicts.
  const parts: JSX.Element[] = []
  let remaining = text
  let key = 0

  // Greedy left-to-right tokenizer.
  while (remaining.length > 0) {
    const codeMatch = remaining.match(/^`([^`]+)`/)
    const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/)
    const linkMatch = remaining.match(/^\[([^\]]+)\]\(([^)]+)\)/)
    const xrefMatch = remaining.match(/^§(\d+)/)

    if (codeMatch) {
      parts.push(
        <code
          key={key++}
          className="rounded-sm bg-surface-sunken px-1 py-0.5 font-plex-mono text-caption text-content-strong"
        >
          {codeMatch[1]}
        </code>,
      )
      remaining = remaining.slice(codeMatch[0].length)
      continue
    }

    if (boldMatch) {
      parts.push(
        <strong key={key++} className="font-medium text-content-strong">
          {boldMatch[1]}
        </strong>,
      )
      remaining = remaining.slice(boldMatch[0].length)
      continue
    }

    if (linkMatch) {
      const [, label, url] = linkMatch
      parts.push(
        <a
          key={key++}
          href={url}
          target={url.startsWith("http") ? "_blank" : undefined}
          rel={url.startsWith("http") ? "noreferrer" : undefined}
          className="text-accent underline hover:text-accent-hover"
        >
          {label}
        </a>,
      )
      remaining = remaining.slice(linkMatch[0].length)
      continue
    }

    if (xrefMatch) {
      const sectionNumber = parseInt(xrefMatch[1], 10)
      if (
        sectionNumber >= 1 &&
        sectionNumber <= 24 &&
        onCrossReferenceClick
      ) {
        parts.push(
          <button
            key={key++}
            type="button"
            onClick={() => onCrossReferenceClick(sectionNumber)}
            className="inline-flex items-center rounded-sm border border-border-base bg-surface-raised px-1.5 py-0 font-plex-mono text-caption text-accent hover:bg-accent-subtle"
            data-testid={`plugin-registry-xref-section-${sectionNumber}`}
          >
            §{sectionNumber}
          </button>,
        )
      } else {
        parts.push(<Fragment key={key++}>§{sectionNumber}</Fragment>)
      }
      remaining = remaining.slice(xrefMatch[0].length)
      continue
    }

    // Plain text — consume up to the next markdown boundary.
    const nextMarker = findNextMarker(remaining)
    parts.push(<Fragment key={key++}>{remaining.slice(0, nextMarker)}</Fragment>)
    remaining = remaining.slice(nextMarker)
  }

  return parts
}


function findNextMarker(text: string): number {
  // Find smallest index of any markdown marker. If none, return
  // full length.
  const markers = [
    text.indexOf("`"),
    text.indexOf("**"),
    text.indexOf("["),
    text.indexOf("§"),
  ].filter((i) => i >= 0)
  if (markers.length === 0) return text.length
  // If a marker is at index 0 we're stuck — emit at least one char.
  const next = Math.min(...markers)
  return next === 0 ? 1 : next
}
