# Provenance — `2026-10-27-guided-order-capture.html`

James's dispatch of 2026-10-27 cites
`https://claude.ai/artifact/S5F1YvGR49ew7wa7ev9mcr` (Notion: Bridgeable Modules →
Guided Capture).

⚠️ **THAT URL IS NOT FETCHABLE AND THE ID IN IT RESOLVES TO NOTHING.** The
fetchable form is `claude.ai/code/artifact/{uuid}`, and `S5F1YvGR49ew7wa7ev9mcr`
is not a uuid. Same shape as the 2026-10-26 cemetery dispatch, which cited an id
that did not appear in the artifact listing at all. Per CLAUDE.md §11 — *a
dispatch may only cite sources the executor can reach* — the bytes are in the
repository rather than described, and the digests below are part of the citation
rather than a courtesy.

## What was fetched, and how it was identified

`Artifact action:"list" scope:"all"` returned twelve artifacts. Exactly one was
updated 2026-10-27 and exactly one had a title matching the dispatch:

| Field | Value |
|---|---|
| Title | **Guided Order Capture** (the dispatch says "Guided Capture") |
| URL | `https://claude.ai/code/artifact/cb0c1342-8272-4455-b474-4bae79d1a1ff` |
| Updated | 2026-10-27 |
| Owner | the user ("mine") |

⚠️ **THE TITLE IS NOT AN EXACT MATCH** — "Guided Order Capture" vs the dispatch's
"Guided Capture". It is recorded here rather than smoothed over, because a
one-candidate match on a near-name is still an inference. Nothing else in the
listing is close, and the file's content is the guided-capture surface the
dispatch describes (pills, the Opas pane left of the bar, vault-dependent
follow-ups, the cremation chip), which is the real confirmation.

## Digests

```
file   docs/prototypes/2026-10-27-guided-order-capture.html
bytes  92138
sha256 34b3938d9a2dcedca7fce8f15f14c7ba62fc37a80da86d4b2ba6b58bcacd09f3
```

The first line (50,633 bytes of it) is claude.ai's `frame-runtime` preamble, not
James's work. The prototype's own source is lines 2–817.

```
prototype source only (lines 2-817)
bytes  50633
lines  816
```

## What this slice follows, quoted

Layout, `.dock`, line 44 — and note the narrow order matches the dispatch's
"pane, Opas pane, pills, bar, stacked" exactly:

```css
.dock{...display:grid;
  grid-template-columns:300px minmax(0,600px);
  grid-template-areas:"side pane" "side chips" "side bar";
  gap:12px 16px;justify-content:end;align-items:end;...}
@media (max-width:960px){.dock{grid-template-columns:minmax(0,600px);
  grid-template-areas:"pane" "side" "chips" "bar"}}
```

Applicability — the engine's own rule for which question comes next (lines
251-258):

```js
function applicable(f){
  const v=S.f.vault&&VAULT[S.f.vault.id],p=S.f.pers;
  if(f==='pers')return !!(v&&v.pers.length);
  if(f==='print')return !!(p&&p.id==='legacy');
  if(f==='dates')return !!(p&&p.id!=='none');
  return true;
}
const nextField=()=>ORDER.find(f=>applicable(f)&&!S.f[f])||null;
```

Clearing what no longer fits, and saying why in one line (lines 274-285):

```js
if(old&&old.kind!==nv.kind&&S.f.equip){delete S.f.equip;
  S.note=nv.kind==='urn'?'Equipment cleared: an urn vault means a cremation setup.'
                        :'Equipment cleared: a burial vault needs burial equipment.'}
if(S.f.pers&&S.f.pers.id!=='none'&&!nv.pers.includes(S.f.pers.id)){
  S.note=`${S.f.pers.label} cleared: the ${nv.short} doesn't offer it.`;...}
```

The deceased label and question (lines 237, 552):

```js
const LABEL={fh:'Funeral home',decedent:'Deceased',...}
case 'decedent':return {ask:'What is the name of the deceased?',...,free:true};
```

The cremation chip and the relabelled equipment row (lines 598, 609):

```js
if(k)h+=`<span class="chip kind${k!==lastKind?' pop':''}">${k==='urn'?'Cremation':'Burial'}</span>`;
const lab=f==='equip'&&k==='urn'?'Cremation setup':LABEL[f];
```

Usual-first ordering, and the pill subtitle carrying only an answer-side
annotation — town on homes and cemeteries, date on days, "cremation" on urn
vaults (lines 553-568):

```js
const ids=fh&&fh.usual?fh.usual.vault:POPULAR.vault;
options:ids.map(id=>opt('vault',id,VAULT[id].label,VAULT[id].kind==='urn'?'cremation':''))
options:POPULAR.fh.map(id=>opt('fh',id,FH[id].label,FH[id].sub))
options:ids.map(id=>opt('cemetery',id,CEM[id].label,CEM[id].sub))
options:nextDays(3).map(({d,tomorrow})=>opt('day',d.iso,tomorrow?'Tomorrow':d.weekday,d.short,d))
```

## ⚠️ Where this slice DEPARTS from the prototype, and why

**The pill key is ⌥, not ⌘.** James ruled it: *"Chrome keeps ⌘1–8 for switching
tabs, so ⌘ would only ever work in a desktop app."* The prototype renders
`⌘` — line 172, `const MOD=MAC?'⌘':'Ctrl+'`, printed into each pill's `<kbd>`.

⚠️ **AND THE PROTOTYPE'S HANDLER ALREADY ACCEPTS OPTION, so only the LABEL was
ever wrong** (line 705):

```js
const mod=e.metaKey||e.ctrlKey||e.altKey;   // altKey — ⌥ already works
```

So the ruling does not change the prototype's behaviour at all; it corrects what
the prototype advertises. Recorded because "the prototype uses ⌘" is true of its
display and false of its code, and a reader checking one of those will reach the
opposite conclusion from a reader checking the other.

**The bare-digit rule is followed exactly as written** (lines 706-708) — the
dispatch's "not while the question takes numbers: day, time, dates" is the
prototype's own list:

```js
const typingNumber=['time','dates','day'].includes(...currentField()...);
const bareOK=document.activeElement!==inp||(!inp.value.trim()&&!typingNumber);
```

**"Watch it work" is left out** per clause 5. In the prototype it is the
`.proto` strip (lines 26-31) plus its driver; none of it ships.

## ⚠️ What the prototype does NOT settle, and is therefore not a ruling

Per CLAUDE.md — *a prototype's omissions are not rulings*:

- Its catalogue is **eight hard-coded vaults, five cemeteries, four funeral
  homes** with `usual` lists written by hand (`FH.hopkins.usual`). The dispatch
  requires these counted from real orders, so the data path is new work and the
  prototype cannot be quoted for it.
- `vnote` — *"Hopkins usually orders the Monticello: 7 of their last 12"* — is a
  hand-written string. The dispatch's rule (≥2 orders and ≥25%, max 3, the
  Customer Pane's rule) is what decides it, not this sentence.
- Prices appear in its data (`price:1405`) and the dispatch says pills carry
  **no prices**. The prototype shows them only in the pane total, never on a
  pill, so the two agree — stated because the price field's presence invites the
  opposite reading.
