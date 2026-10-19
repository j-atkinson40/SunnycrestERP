# Provenance — the Sales Order Pane prototype, copied 2026-10-19

| File | size | md5 | sha256 |
|---|---|---|---|
| `2026-10-04-sales-order-pane.html` | 81544 | `1fe0b3083812cb92ed0975f8c17c5926` | `2d306e724ec4ae0112e0010ff16392435196385383485c46c853af32be674fdc` |

Source: `claude.ai/code/artifact/115f1411-7c22-4983-91e4-6dca3d99fcc4` ("Sales Order
Pane", updated **2026-10-04**). Owned by James. Retrieved by WebFetch, which saves the
full response body; the file is byte-identical to what was served (`cmp`).

⚠️ **THE DISPATCH CITED A DIFFERENT URL AND THAT URL RESOLVES TO NOTHING.** The
2026-10-19 dispatch cites `https://claude.ai/artifact/39R6gdLS6PrrAPWr4GmjBh`. That
path shape is not fetchable (only `claude.ai/code/artifact/{uuid}` is), and the short
id `39R6gdLS6PrrAPWr4GmjBh` does not appear in James's artifact listing — 30 artifacts
enumerated, no match. The file here is the only "Sales Order Pane" in that listing.

**How it was verified to be the right document, since the cited id could not confirm
it.** The dispatch names five things to leave OUT of slice 1. All five are present in
this file, which is what a superset of slice 1 should look like: `proof` 37 hits,
`Driver` 36, `Office` 21, `contact` 12, `Scheduling` 5, `Accounting` 4, `"Right now"` 1.

⚠️ **TWO THINGS THE DISPATCH SPECIFIES ARE NOT IN THIS PROTOTYPE, AND FOR THOSE THE
DISPATCH WINS.** `Confirmed` — 0 hits; the prototype's progress steps are
**Proof → Scheduled → Delivered → Invoiced**, while the dispatch specifies
**Confirmed → Delivered → Invoiced**. `Undo confirm` — 0 hits. Both are consistent with
the artifact predating the confirm step: it was last updated 2026-10-04, and Approve
began confirming orders on 2026-10-16. The prototype is the reference for look and
layout, not for the state vocabulary.

## The runtime block, and a confirmed instance of the 2026-10-06 caveat

`PROVENANCE-2026-10-06.md` warned that the digests cover the artifact **as served**, so
a platform runtime update would change the digest of an unchanged prototype. That has
now happened, measured across the three files:

| File | runtime block | runtime md5 | authored remainder |
|---|---|---|---|
| `2026-10-01-opas-overlay.html` | 39424 | `dccdb66cc5ae…` | 53695 |
| `2026-10-03-product-pane.html` | 39424 | `dccdb66cc5ae…` | 41996 |
| `2026-10-04-sales-order-pane.html` | **40448** | **`a94d15f95b3e…`** | 41096 |

The injected `<!-- frame-runtime -->` block grew by 1024 bytes and is no longer
byte-identical to the one in the October 6 pair. So the whole-file digest above proves
which bytes this finding was taken from and **cannot** be read as a version identifier
for the design.

For that, here is the authored remainder — the file with the `<!-- frame-runtime -->`
… `<!-- /frame-runtime -->` span removed, computed over bytes, the stripped copy not
written to disk:

| | bytes | md5 | sha256 |
|---|---|---|---|
| authored remainder | 41096 | `b49d38c664f9d4e253485be7c549a395` | `97cdb2e30944d2cd3bfd5f8129c27b47e8911dfcdddc578ed5922d914ff96ca9` |

⚠️ **AND THE FETCH IS NOT A BROWSER.** Same as the October 6 pair: the prototype loads
IBM Plex from `fonts.googleapis.com`, so the local copy is not self-contained and
renders in a fallback face offline.
