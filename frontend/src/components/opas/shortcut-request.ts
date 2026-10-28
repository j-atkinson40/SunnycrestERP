/**
 * "set my shortcut to control" — the bar phrase that sets the pill-pick modifier.
 *
 * James's ruling of 2026-10-28, clause 4: *"Where the setting lives: whatever
 * user-preferences surface exists. If none, a stored preference and 'set my shortcut
 * to control' in the bar."*
 *
 * ⚠️ WHY THE BAR AND NOT A SETTINGS PAGE, REPORTED RATHER THAN ASSUMED. Measured: a
 * per-user preference PATTERN exists — several routers own a `GET`/`PATCH
 * /preferences` pair writing into `User.preferences`, `edge_panel` being the cleanest
 * — but the ~40 pages under `/settings/*` are each owned by one feature and none is a
 * home for an Opas interaction setting. A page for one three-way choice would also
 * need an Opas entrance anyway, per CLAUDE.md §1a ("a feature is INCOMPLETE if it can
 * only be accessed by navigating to a page"), so the phrase is required either way.
 *
 * ⚠️ RECOGNISED CLIENT-SIDE, BEFORE THE TEXT IS SENT. The capture bar has no general
 * command path — "always" is a scope choice on the `why` flow, not parsed from bar
 * text — and adding one to `set_text` would put a command parser on the path every
 * keystroke takes. This is a sibling of `isCloseRequest`, which is handled the same
 * way and for the same reason.
 *
 * ⚠️ AND IT IS DELIBERATELY NARROW. It matches a near-exact sentence rather than
 * anything containing "control", because the bar's whole job is orders: a vault called
 * "Control Series" or a note reading "set my shortcut to the usual" must reach the
 * extractor untouched. A phrase that nearly matches is better refused than guessed —
 * the office retypes it; a guess silently changes a keyboard under them.
 */

/** The modifier names the phrase may end with, and what each stores. */
const NAMES: Record<string, "option" | "control" | "command"> = {
  option: "option",
  opt: "option",
  alt: "option",
  control: "control",
  ctrl: "control",
  command: "command",
  cmd: "command",
  meta: "command",
}

/**
 * ⚠️ THE LEADING FORMS ARE ENUMERATED, NOT PATTERN-MATCHED ON "shortcut". "what is my
 * shortcut" is a question, not an instruction, and a loose match would answer it by
 * changing the setting.
 */
const PREFIXES = [
  "set my shortcut to",
  "set my pick shortcut to",
  "set shortcut to",
  "my shortcut is",
  "use",
] as const

function cleaned(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[.!]+$/g, "")
    .replace(/\s+/g, " ")
}

/**
 * The modifier a shortcut-setting phrase names, or null if this is not one.
 *
 * ⚠️ `"use"` IS THE ONE LOOSE PREFIX AND IT IS FENCED. It only matches
 * `use <name> for pills` / `use <name> to pick` — never a bare `use control` — because
 * "use monticello" is a thing somebody types into this bar.
 */
export function shortcutRequest(text: string): "option" | "control" | "command" | null {
  const phrase = cleaned(text)
  if (phrase === "") return null

  for (const prefix of PREFIXES) {
    if (!phrase.startsWith(`${prefix} `)) continue
    let rest = phrase.slice(prefix.length + 1).trim()
    if (prefix === "use") {
      // the fenced form only
      const fenced = /^(.+?) (?:for pills|to pick|for picking|for the pills)$/.exec(rest)
      if (fenced === null) return null
      rest = fenced[1].trim()
    }
    // ⚠️ A TRAILING "KEY" OR "INSTEAD" IS TOLERATED because people say it: "set my
    // shortcut to the control key". Anything else is refused.
    rest = rest
      .replace(/^the /, "")
      .replace(/ key$/, "")
      .replace(/ instead$/, "")
      .trim()
    const named = NAMES[rest]
    return named ?? null
  }
  return null
}
