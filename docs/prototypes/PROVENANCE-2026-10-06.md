# Provenance — the two overlay prototypes, copied 2026-10-06

| File | size | md5 | sha256 |
|---|---|---|---|
| `2026-10-01-opas-overlay.html` | 93177 | `a52a1e95153bd5c686b88d0acffc31e6` | `c377f366b8fa63bee27d3307e3a1fba78533859d196f8da7a875e52992c4836e` |
| `2026-10-03-product-pane.html` | 81464 | `d6ca8a967a615d53fbd24b5610290528` | `91d9c38cca9f3a078797bde0eeae5a9b119f11478328517c9ec96dd705620ac7` |

Sources: `claude.ai/code/artifact/5ac52e5a-682e-4a29-9ed6-51f95f68e711` ("Opas Overlay",
updated 2026-10-01) and `.../702f2f18-6b30-43f1-a91c-14557217d62e` ("Product Pane",
updated 2026-10-03). Both owned by James; the Product Pane is link-shared.

⚠️ **THESE DIGESTS COVER THE ARTIFACT AS SERVED, NOT THE AUTHORED SOURCE.** 39,424 bytes
of each file — **42%** of the overlay and **48%** of the product pane — is the
`<!-- frame-runtime -->` block that claude.ai injects at serve time. It is byte-identical
in both. So the authored HTML is roughly 54KB and 42KB respectively, and a re-fetch after
a platform runtime update will produce a DIFFERENT digest for an UNCHANGED prototype.

**What that means for citing them:** the digest proves which bytes a finding was taken
from, which is its job. It does not prove the design is unchanged, and it must not be
read as a version identifier for the prototype itself. If the authored content needs a
stable digest, strip the runtime block first and digest the remainder — not done here,
because stripping is an edit and an edited copy is no longer the thing that was served.

⚠️ **AND THE FETCH IS NOT A BROWSER.** These were retrieved by WebFetch, which saved the
full response body. The prototypes load IBM Plex from `fonts.googleapis.com`, so neither
file is self-contained: opening the local copy offline renders in a fallback face.
