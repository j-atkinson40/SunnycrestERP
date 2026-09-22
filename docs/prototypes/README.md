# Prototypes

Clickable prototypes, saved here so the DECISIONS entries they produced can cite
their source. CLAUDE.md's *Prototype before dispatch* rules that new surfaces are
prototyped and reviewed before dispatch, and that rulings made while prototyping go
to DECISIONS — because the prototype file will be superseded and its reasons should
not go with it.

Naming: `YYYY-MM-<surface>.html`.

| File | Title | Entries it produced |
|---|---|---|
| `2026-09-call-to-print.html` | Bridgeable — From Call to Print | The sixteen `2026-09-22` entries, from the note's register through legacy approval |
| `2026-09-capture-schema.html` | Capture schema — prototype | The seven `2026-09-22` capture-schema entries (`c54d3e93`, corrected by `d44cc958` and `19844464`) |

Both files are saved byte-identical to the reviewed artifact, verified with `cmp`.
They are records, not living documents — a prototype is superseded by the thing it
was used to decide, and editing one after the fact would break the correspondence
the entries rest on.

## Rendering

`2026-09-call-to-print.html` is fully self-contained: 6 embedded data URIs, no
external references.

`2026-09-capture-schema.html` loads IBM Plex Sans and Mono from Google Fonts —
three `<link>` references, the only external requests it makes. Offline it falls
back to system fonts; nothing structural depends on them. The refs were left in
place rather than inlined, to keep the file identical to what was reviewed.

## Citation status

The seven capture-schema entries in DECISIONS **do not yet cite this prototype**.
They landed on 2026-09-22 at a point when the file was not available, and the
dispatch's own fallback was to land without the path and record its absence. The
file arrived later the same day. Amending the seven entries to carry the path is a
canon edit and has not been made.
