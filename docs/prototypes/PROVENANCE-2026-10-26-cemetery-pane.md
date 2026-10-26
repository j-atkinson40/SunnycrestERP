# Provenance — the Contact / Cemetery / Invoice Panes prototype, copied 2026-10-26

| File | size | md5 | sha256 |
|---|---|---|---|
| `2026-10-03-contact-cemetery-invoice-panes.html` | 93927 | `44063e83a50a1260e42a30a4d7e975e2` | `33eed8d5793ca36998b104abc93177f132c1eeb4874c9d419ac68818fd8c418b` |

Source: `claude.ai/code/artifact/0f3ee586-8baf-4b5e-b058-a9848aabc3ce` ("Contact,
Cemetery, Invoice Panes", updated **2026-10-03**). Owned by James. Retrieved by WebFetch,
which saves the full response body. Of the 93,927 bytes, **52,899 chars after
`<!-- /frame-runtime -->` are the author's own source**; the rest is the artifact
runtime wrapper, which is why the md5 above is of the page as served rather than of the
hand-written document.

⚠️ **THE DISPATCH'S SHORT URL IS NOT A FETCHABLE SHAPE; THE UUID IS, AND THE DISPATCH
GAVE IT TRUNCATED.** The 2026-10-26 dispatch cites
`https://claude.ai/artifact/2tC5PifJ1YWHeYvvAbMMBT` plus "artifact 0f3ee586-…". Only
`claude.ai/code/artifact/{uuid}` resolves, and the truncated id had to be completed from
the artifact listing — where exactly one entry starts `0f3ee586`. This is the second
slice running where the short URL did not resolve and the id did (see
`PROVENANCE-2026-10-19-sales-order-pane.md`), which is the argument for always citing
the full uuid. Resolved without guessing: one listing, one match.

⚠️ **THE TITLE IN THE LISTING IS "Contact, Cemetery, Invoice Panes" — NO "Statement".**
The dispatch says "Notion: Contact, Cemetery, Invoice and Statement Panes". The artifact
does define a `stmtPane()`, reached by `a==='stmt'`, so the Notion page is plausibly
named for a superset. Recorded because a title mismatch is how the wrong document gets
built from, and here the document is right.

**Verified to be the right document.** The dispatch names six things to leave out of
slice 1, and a superset should contain all six. Measured in this file: `cemPane` 3 hits,
`Right now` present (`c.alert`), `Sections` present (`c.secs`, three per cemetery),
`Driver notes` present (`c.notes`), `People` present (`c.people`), and a `Call the
<role>` action alongside `Directions`. Two cemeteries are defined, both named
"St. Mary's Cemetery" — `skan` (Skaneateles) and `auburn` — which is the shared-name
case the dispatch's opening rule is about.

## The lines slice 1 follows, quoted

```
.ttl      `<div class="ttl">${c.n}</div>`
.meta     `<div class="meta">${c.town}, NY · <button type="button" class="lnk"
           data-a="cem:${c.other}">${c.not}</button></div>`
           with  not:"not the St. Mary's in Auburn",  other:'auburn'
action    `<button class="btn${R==='driver'?' primary':''}"
           data-a="chip:Directions to the ${esc(c.gate.toLowerCase())}">Directions</button>`
essentials `<div class="sech"><span>The essentials</span></div><div class="kv">`
           `<div><span>Address</span><span>${esc(c.addr)}</span></div>`
           `<div><span>Gate</span><span>${esc(c.gate)}</span></div>`
           `<div><span>Getting in</span><span>${esc(c.approach)}</span></div>`
           `<div><span>Hours</span><span>${esc(c.hours)}</span></div>`
           `<div><span>${c.people[0][1]}</span><span>${esc(c.people[0][0])} · …</span></div>`
           `<div><span>Vault</span><span>${c.vault}</span></div>`
           `<div><span>Equipment</span>…` `<div><span>Tents</span>…`
coming up `<div class="sech"><span>Coming up here</span><span>${c.up.length}</span></div>`
           `<button type="button" class="row" data-a="chip:Opens ${u[5]}">
             <span class="a">${u[0]}</span>
             <span class="b">${esc(u[1])} · ${esc(u[2])} · Section ${u[3]}, ${u[4]}</span>
             <span class="c">›</span></button>`
tabs      `S.push(['people','People',c.people.length, …])`
           `S.push(['knows','What Opas knows','', …])`
knows     `<div><span>Deliveries this year</span><span>${c.year}</span></div>`
           `<div><span>Next delivery</span><span>${next?`${next[0]} · … · Section ${next[3]}`
             :'None scheduled'}</span></div>`
           `<div><span>Same name elsewhere</span><span><button type="button" class="lnk"
             data-a="cem:${c.other}">${CEMS[c.other].n}, ${CEMS[c.other].town}</button></span></div>`
```

⚠️ **WHAT THE PROTOTYPE SHOWS THAT BRIDGEABLE DOES NOT RECORD** is the whole reason the
dispatch scopes this slice the way it does: `gate`, `approach`, `hours`, `vault`,
`equip`, `tents`, `fee`, `secs`, `notes`, `also` and `alert` are all hand-written
fixture strings in `CEMS` above. Which of them the schema actually holds is measured
separately and is not inferred from this file.
