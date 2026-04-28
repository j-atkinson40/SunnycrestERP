# Bridgeable Design Language

**Status:** In authoring. Sections 0 and 1 drafted; remaining sections to follow.

**Purpose:** This document defines the visual and sensory design language for the Bridgeable platform. It is the source of truth for how Bridgeable looks and feels across all verticals and all components. Component patterns (layouts, interaction flows, specific component behavior) live in `COMPONENT_PATTERNS.md`. This document changes slowly; that one changes as patterns evolve.

**Audience:**
- **Primary:** Sonnet, executing build prompts. Needs unambiguous, implementable rules.
- **Secondary:** James, reviewing shipped UI against intent.
- **Tertiary:** Future contributors who need to understand aesthetic intent without re-deriving it.

**Format:** Each rule appears in three layers — **rule**, **rationale**, **implementation**. Sonnet can skip to implementation; humans read rationale to understand why the rule exists.

**Reading order:** Section 0 articulates the emotional register that ties the platform's identity to its reference family — the *character of the tool itself*. Section 1 articulates the moods — the *settings the tool exists within*. The two layer: the moods are where the tool is observed; the register is what the tool is. Both must hold simultaneously for a Bridgeable surface to feel right.

---

## Section 0 — The Object's Character

> **This section is Layer 1 of the three-layer design thesis.** Layer 2 (interaction model) lives in [`PLATFORM_INTERACTION_MODEL.md`](PLATFORM_INTERACTION_MODEL.md). Layer 3 (execution standard) lives in [`PLATFORM_QUALITY_BAR.md`](PLATFORM_QUALITY_BAR.md). The synthesis is in [`PLATFORM_DESIGN_THESIS.md`](PLATFORM_DESIGN_THESIS.md): *Bridgeable looks like a Range Rover, behaves like Tony Stark's workshop, and is built like an Apple Pro app.* Read the thesis doc first if this is your first encounter with the platform's design canon.

> **Bridgeable's design philosophy mirrors Land Rover's: restrained, materially honest, architecturally proportioned, quietly confident, made to last. Applied natively to digital surfaces, not borrowed from automotive vocabulary.**

That thesis is the platform's North Star *for visual values* (Layer 1). It governs every visual decision — color, type, surface, motion, spacing, iconography, density, all of it. When Sections 1–10 specify values and Sections 2–9 lock the tokens, this thesis is what they're all working toward.

Bridgeable is an instrument. Sections 1 and onward define the moods (light = Mediterranean garden morning; dark = cocktail lounge evening) — the atmospheres the tool is observed within. This section defines what the tool itself **is**, independent of where it's seen. The same Leica camera body is the same instrument under garden sun or lamplight; the light on it changes, the object does not. Section 0 articulates that object.

This section is opinionated, long, and load-bearing. Every visual decision in the platform answers to it. Read it once carefully; refer back when in doubt.

### Design DNA, not vehicle vocabulary

The Land Rover frame is the most important single statement in this document, and it is the most easily misread. Read carefully.

**What the thesis means:** Imagine Land Rover's design team was given a brief to create operational software for the physical economy. They wouldn't put steering wheels and tachometers in it. They'd make something that *feels like their work, expressed in pixels*. Same instincts about restraint. Same approach to materials. Same proportions. Same quiet confidence. Same time-resistance. The result is software that **shares the design DNA of the vehicle without any of the literal vehicle vocabulary**.

**What the thesis does NOT mean:**
- NOT heads-up display chrome (transparent overlays, projection effects, vehicle-dashboard simulations)
- NOT vehicle-specific iconography (steering wheels, speedometers, tachometers, fuel gauges)
- NOT automotive color palettes (carbon fiber black, race red, racing stripes, hi-vis safety yellow)
- NOT skeuomorphic dashboard chrome (gauges rendered in pixels, instrument-cluster compositions, dial-textured surfaces)
- NOT any literal vehicle imagery, vocabulary, or styling

The "would this look at home as a screen inside a Range Rover" test — when invoked — is a **coherence check**, not a style mandate. It asks: does this share the design DNA of the vehicle, such that if it were embedded in a Range Rover dashboard, it would look like the same team made both? It does NOT ask: does this look like a HUD or vehicle UI element.

The check is on **shared design instincts**, not shared visual elements.

### The reference family

Bridgeable's identity sits in a specific lineage of considered, restrained, time-resistant tools and instruments. The full reference family:

- **Leica M-series camera body.** Brass, leather, restraint. Honest materials. Mechanical precision presented without ornament. Looked right in 1954, looks right now, will look right in 2046.
- **Teenage Engineering OP-1.** Restraint at scale. Calm expensiveness. The simplicity is the flex.
- **Old Land Rover Defender interior.** Functional honesty. Materials at their full strength. Tools belong where you can reach them.
- **Filson briefcase, well-worn.** Heirloom-grade. Worth maintaining. Time-resistant, not time-frozen — patina without decay.
- **Rotring 600 mechanical pencil.** Knurled metal, precise weight, no decoration. Doesn't ask for attention.
- **Hans Wegner / Borge Mogensen furniture.** Architectural confidence. Joinery exposed, not hidden. Proportions earn the form.
- **Linear app.** Information density without ornament. Keyboard-grade. Workshop-tool digital register.
- **Bloomberg Terminal.** Density permitted. Functional color. Tool-grade — not decorative software.
- **Industrial HMI panels.** Honest about being functional. No skeuomorphism, no ornament, no apology.
- **Workshop with tools in their place.** Things have weight. Things have positions. Things are accessible because they need to be.
- **Range Rover exterior architecture (NOT interior HUD).** Architectural proportions, restrained metalwork, surfaces that read as material rather than ornament. The vehicle's outside, not its dashboard.

These eleven references share an emotional register that Bridgeable adopts as its own. They are NOT what Bridgeable looks like — Bridgeable is digital software and looks like digital software. They are what Bridgeable **feels like** to use.

### Critical framing — what the reference family means

The reference family is an **imaginative brief**, not a literal style spec. Bridgeable is not a HUD, not a dashboard cluster, not a vehicle interior, not a leather portfolio app, not a accent-finished skeuomorphic surface. It is digital software for the physical economy. The references articulate the *emotional register* — they are the answer to "what does this product feel like to use?", not "what does this product look like?".

**DO translate the reference family into:**
- Restraint at scale (simplicity that signals resources)
- Architectural proportions (buildings, not vehicles — proportional discipline at the scale of the surface, not at the scale of literal vehicle parts)
- Honest materials at full strength (real type, real shadow, no fake glass, no fake metal, no fake leather)
- Quietness (calm presence, not engaging)
- Density permitted (information-dense without clutter)
- Functional color (accent for action; status colors for communication, not decoration)
- Time-resistance (avoid current-decade visual trends — neumorphism in 2020, glassmorphism in 2022, AI gradients in 2024)
- Heirloom commitment (worth maintaining, not disposable)

**DO NOT translate the reference family into:**
- Heads-up display chrome (transparent overlays, projection effects, vehicle dashboards)
- Vehicle iconography (steering wheels, speedometers, gauges, dashboards)
- Automotive color palettes (carbon fiber black, race red, racing green)
- Camera-body skeuomorphism (knurled metal textures, brass fittings as decoration, leather grain as background pattern)
- Workshop skeuomorphism (wood-grain surfaces, blueprint backgrounds, ruler tick marks)
- Bloomberg Terminal literalism (green-on-black monospace prose, oppressive density)
- Leica-camera-body literalism (silver-and-black photography UI)

The references inform character. The character is then expressed in the canonical visual language of digital software — type, color, surface, motion, spacing — not in references to physical objects.

### The eight emotional qualities

The reference family converges on eight qualities. A Bridgeable surface that achieves all eight evokes the right register. A surface missing any one drifts.

**1. Warm restraint.** Not cold lab. Not playful consumer. Warmth without softness; restraint without coldness. The platform is approachable but serious — adults working with adults, not customers being entertained.

**2. Considered materiality.** Real type, real shadow, real elevation. Surfaces feel like material the way Wegner's chairs feel like wood — not because they show grain, but because their proportions and joinery are honest about what they are. UI surfaces feel like material via elevation, light direction, and shadow character. Never via skeuomorphic textures.

**3. Architectural confidence.** Proportions matter more than decoration. Spacing, hierarchy, alignment, and type cadence carry the visual weight. When in doubt, make the proportions right rather than adding chrome. A well-proportioned plain surface beats a poorly-proportioned ornamented one every time.

**4. Calm expensiveness.** The simplicity is the flex. The reference family signals expense not through gold and glass but through *what was deliberately left out*. Bridgeable should feel expensive the way a Leica feels expensive — through restraint and resolution, not through ornament. If it looks like a SaaS template with accent buttons, the restraint failed.

**5. Time-resistance.** The platform must look right in 2026 AND in 2036. Avoid visual conventions tied to specific years — gradient meshes (2020s AI), glassmorphism (early 2020s), neumorphism (2020), Material Design soft drop shadows (2010s), iOS 7 thin-everything (2013). The reference family is time-resistant by construction — Leica looked right in 1954, Wegner chairs look right today, Filson briefcases look right after 50 years. Bridgeable inherits that property by referring to that family.

**6. Quietness as a design value.** The platform is *available*, not *engaging*. It does not demand attention through animation, color, or chrome. It earns attention through density and clarity at the moment the user needs it. Quietness is positive, not absence — a quiet workshop is intentional, not empty.

**7. Workshop-tool-grade seriousness.** The platform is for operators doing real work. It is not entertainment software. It does not gamify, celebrate, or anthropomorphize. It signals that the work being done is consequential and that the tool respects the work.

**8. Heirloom commitment.** The platform is worth maintaining. It is not disposable. Its visual language reads as something a serious operation invests in for years, not as something that will be replaced when the next design trend arrives. This is partly a result of (5) time-resistance and partly an attitude of design — every detail considered enough that it would not embarrass the team in five years.

### The ten translation principles

The eight qualities answer "what character does Bridgeable have?" These ten principles answer "how does that character translate into actual design decisions?" Each principle takes a Land-Rover-design instinct and articulates how to apply it natively to digital surfaces.

**1. Materials translate as digital materials.** Real wood becomes warm-grained dark surfaces with subtle elevation. Real metal becomes deepened terracotta accents with appropriate sheen. Real leather becomes warm-tinted neutral surfaces with hint of grain (where grain is *implied* by warmth and texture in the color, not depicted). The principle is "honest digital materials at full strength" — not skeuomorphic textures, but the **digital equivalent of how the vehicle treats real material**. Surfaces that feel substantial and warm, not flat and cheap. Surfaces that have presence without pretending to be physical.

Implementation: `bg-surface-elevated` carries lifted lightness + warmer hue (Section 3). `shadow-level-1` carries warm-tinted soft shadow (Section 6). The accent token retains a single fixed hue across modes (Section 2 cross-mode rule). Together: cards feel material because they elevate with warmth, not because they show fake wood grain.

**2. Proportions translate directly.** Range Rover proportions are tall, square, generous, settled. Digital surfaces have the same relationships. Generous spacing. Square-shouldered cards. Flat-roofed elements that don't taper into curved corners. Vertical sides meeting horizontal tops cleanly. A Bridgeable card has the same proportional relationship to its surface that a Range Rover door has to its window — solid, considered, with breathing room. This principle is mostly about spacing and aspect ratios, which are completely medium-independent.

Implementation: Section 5 spacing scale defaults generous (`p-6` cards, `space-10` region gaps). Section 6 radii: `radius-md` (8px) at card scale, NOT `radius-xl` (16px) — square-shouldered, not pillowy. Aspect ratios on hero surfaces favor 16:9 / 4:3 / 3:2 (architectural) over 1:1 / 9:16 (consumer photo).

**3. Restraint translates literally.** Reduce until removing one more element breaks it, then stop. A Range Rover door has a handle, a window, a mirror, a body line, and almost nothing else. A Bridgeable card has a title, the data that matters, and almost nothing else. No badges. No tags. No metadata clutter. No decorative accents. **The discipline of what to leave out is the most direct translation of the design instinct.**

Implementation: every element on a card must justify its presence in operational terms. "It looks nice" is not a justification. If you can remove an element and the user doesn't notice, the element was decorative — remove it. If you can remove an element and the user can't complete their work, the element was structural — keep it. The dispatcher's `DeliveryCard` (in-register calibration surface, see below) is the canonical reference — title, key facts, status row, nothing else.

**4. Detail concentration translates.** Range Rovers spend their detail budget in *specific places* — door pulls, gear selectors, dial textures, air vent surrounds. The exterior is restrained; **points of human touch are jewelry**. Bridgeable does the same. Platform-wide language is restrained; points of interaction (accent action button, focused input ring, important controls) are crafted with attention disproportionate to surrounding surface. **The user's hand lands on jewelry, even though surrounding surface is calm.** This separates "minimalist" from "minimalist with care."

Implementation: accent primary buttons get the detail budget — the accent token is precisely calibrated, hover/active states are deliberate, focus rings are crafted, the radius is exactly right. The surrounding card chrome is calm — `shadow-level-1`, no perimeter border, generous padding. The composition reads as "calm surface + jewel button" — not as "decorated surface where the button blends in."

The principle has a corollary: **don't sprinkle detail evenly across the surface.** A platform with accent borders, accent dividers, accent icons, accent everything reads as decorated. A platform with accent concentrated at action surfaces reads as considered.

**5. Quietness translates as sensory quietness.** A Range Rover is *acoustically* quiet — the engineering investment in noise/vibration/harshness is enormous. The digital equivalent is **sensory quietness**: no unnecessary motion, no notification noise, no celebratory feedback, no bouncing animations, no startling color changes, no "great job!" moments. The platform doesn't compete for attention. It's a calm space the operator works inside.

Implementation: motion is purposeful (Section 6) — animation conveys state change, not delight. No spring bounce except where physical mass is implied (drag lift). No celebration on save. No confetti. No animated checkmarks. No icons that bounce on hover. The platform is busy when the work is busy; otherwise it's silent.

**6. Architectural quality translates.** Range Rovers reference modernist architecture — they look more like buildings than cars. Bridgeable references architecture too. **Surfaces are architectural — they have weight, hierarchy, structure.** A Pulse dashboard is a room, not a page. A Focus is a space you enter, not a modal that appears. The metaphors are spatial and architectural rather than documentary or playful. The internal language matches: surfaces, spaces, rooms, edges, weights — closer to how architects talk than how UI designers usually talk.

Implementation: Section 1's "two moods" use architectural references (terrace, lounge), not document references (page, sheet) or consumer references (feed, timeline). Code comments + commit messages reflect the same vocabulary — "the focus-core-positioner is a containing block," "the kanban lane carries no chrome of its own; cards float on it as material objects." This vocabulary discipline shows up in Bridgeable code throughout.

**7. Time-resistance translates.** Range Rover design ages well because it doesn't chase trends. Bridgeable made in 2026 should look right in 2036. Avoid current-decade signals. **No glassmorphism, no AI-purple gradients, no rounded-everything maximalism.** The platform should look like it could have been designed in 2018 and could plausibly release in 2034 — a span where the design values remain coherent because they're not pegged to a specific moment's fashion.

Implementation: every visual decision is checked against "would this date the platform?" Trend conventions are explicitly forbidden in Section 10. The reference family in Section 0 is itself time-resistant by construction — Leica looked right in 1954, Wegner chairs look right today. Bridgeable inherits the property by referring to that family.

**8. Commitment frame translates.** Range Rovers are objects you live with — maintain, have a relationship with, part of your life over years. Bridgeable should feel the same. **Not disposable software; an operating environment licensees commit to and grow with.** The aesthetic communicates that. Heavy in the good sense — substantial, made-to-last, worth the relationship. The opposite of disposable consumer apps designed to be light and forgettable.

Implementation: visual weight is permitted — surfaces have presence, type has authority, the accent has gravity. The platform doesn't shrink itself to seem unimposing. It carries the weight of the work being done. A licensee who commits to Bridgeable should feel the platform commits back.

**9. British-ness is worth naming.** Range Rover has a specifically *British* sensibility — restrained, understated, slightly reserved, more concerned with rightness than display. American luxury (Cadillac) is about **scale and presence**. German luxury (Mercedes, BMW) is about **engineering visibility**. Italian luxury (Ferrari) is about **emotional theater**. **British luxury (Range Rover, Bentley, Aston Martin) is about not having to prove it.** The thing is good; you'll see if you look closely; we're not going to point at it. This is the right register for operators doing serious work. Not flashy, not theatrical, just correct.

Implementation: the platform never announces its quality. No "premium" badges. No "designed by" signatures. No theatrical onboarding. No look-at-me moments. The quality reveals itself in use — a dispatcher who works in Bridgeable for a week notices the type cadence, the spacing rhythm, the accent weight, the shadow character. They don't get sold those things up front. The platform is good; they'll see if they look closely; we're not going to point at it.

**10. Reference point outside software entirely.** Most software design happens in dialogue with other software — designers look at Notion, Linear, Figma, Stripe. The result is convergence; software narrows toward a small range of patterns. **Taking the reference point from outside software (vehicle design philosophy from a specific cultural tradition) escapes that convergence.** Design decisions are calibrated against a different, deeper reference. The platform doesn't look like other SaaS — not because differentiation was the goal, but because the optimization axis is different.

This is how genuinely distinctive design happens. Apple under Ive: Braun and Dieter Rams, not other computer companies. Teenage Engineering: analog synthesizers and Soviet industrial design, not other gadget makers. Linear: pre-computer information design (signal flags, factory shop tickets, library catalogs) more than other web apps. **The best design identities come from references adjacent to but outside the medium.** Range Rover → operational software is exactly that move.

Implementation: when calibrating a new component, the question is NOT "how does Linear / Notion / Stripe handle this?" The question is "how does the reference family handle the *equivalent function* in physical objects?" A button is a control surface — what does a Land Rover gear selector look like? An empty state is a quiet moment — what does a workshop look like when no work is in progress? A loading indicator is a "machine is preparing" signal — what does a Leica's mirror flip-up sound like? The translations are not literal; the references force the optimization axis off the SaaS-convergence axis.

### Detail concentration — the single principle most often missed

Translation principle 4 deserves emphasis because it's the principle most often missed when implementing the rest correctly. A platform can have:
- Honest materials (token system correct)
- Correct proportions (spacing scale correct)
- Restraint (chrome removed where unjustified)
- Sensory quietness (animations purposeful)
- Architectural register (vocabulary right)
- Time-resistance (no trend conventions)
- Commitment frame (substantial weight)
- British register (not announcing itself)

— and STILL feel generic, because **every element is calibrated to the same level of attention**. Restraint without detail concentration produces an aesthetic that's "minimalist," but flat. The Range Rover register is "minimalist with care": the body is calm, the door pulls are jewelry. Without the jewelry, restraint becomes austerity, and austerity becomes generic.

**The rule:** Identify the points of human touch — the buttons that get clicked, the inputs that get focused, the controls that get operated, the icons that signal state — and concentrate detail there. The surrounding surface must be calm enough that the detail reads as concentrated. If detail is sprinkled everywhere, no element gets to be jewelry.

**What gets the detail budget:**
- Primary action buttons (accent, with calibrated hover + active states + focus ring)
- Focused input rings (accent at `--focus-ring-alpha` with the precise glow specification)
- Status indicators that carry decision weight (the icon-row hole-dug badge, the chat unread chip, the +N attached-ancillary badge)
- The accent count chip on the AncillaryPoolPin header
- Hover-revealed affordances (eye-icon peek triggers, the dismiss X on cards)
- The few touchpoints in a complex surface where attention should land

**What does NOT get the detail budget:**
- Surface backgrounds (calm, material, not decorated)
- Card chrome perimeters (no border — material via lift + shadow)
- Lane / column / region containers (typography-led headers, no boxed-in chrome)
- Icons in dense rows (uniform stroke weight, uniform color from text-content-muted, uniform size)
- Most type (consistent scale, consistent weight, no decorative emphasis)
- Most spacing (predictable scale, no signature-moment rhythms outside intentional places)

The composition reads correctly when a user looking at a Bridgeable surface can name three or four things their eye lands on, and those three or four things are the ones the dispatcher needs to act on. If the eye lands on chrome, decoration, or surfaces that aren't actionable, detail concentration failed.

### The British register

Translation principle 9 also deserves emphasis. The *British luxury sensibility* is the cultural orientation that distinguishes Bridgeable from peer platforms aimed at the same operator audience. It's the register that says "not having to prove it."

**The British register, contrasted:**

|Tradition | What it signals | Sample products |
|---|---|---|
| American luxury | Scale, presence, "look at me" | Cadillac Escalade, Tesla Model X, Apple Watch Ultra |
| German luxury | Engineering visibility, "look how this works" | Mercedes S-Class, BMW M5, Leica M11 |
| Italian luxury | Emotional theater, "feel this" | Ferrari, Lamborghini, Alessi homewares |
| Japanese restraint | Spiritual minimalism, "less is more, intentionally" | Muji, mid-period Apple, Sony WH-1000XM |
| **British luxury** | **Not having to prove it. "It's good; you'll see; we're not going to point at it"** | **Range Rover, Bentley, Aston Martin, Linn turntables, Rolls-Royce, the Leica M-series (Solms-era German design but distinctly British in restraint)** |

Bridgeable sits in the British register. **Not announcing its quality is itself a quality marker.** A platform that needs to put "Premium" badges, "designed by" signatures, "powered by AI" disclaimers, or "celebrating excellence" empty states in front of users to communicate seriousness has already failed — those announcements are the tell that the underlying quality wasn't strong enough to communicate itself.

**Implementation rules from the British register:**
- No version-number marketing (the platform doesn't say "v3.0 — now with...!")
- No theatrical onboarding sequences (a single Pulse + a working demo is the orientation; no four-step intro tour)
- No success theater (no confetti, no "amazing!" messages, no "you're crushing it" celebrations)
- No "AI" badges or sparkle icons announcing intelligence (intelligence shows up by being right, not by waving a flag)
- No designer / engineer signatures in the UI (the platform speaks; the makers don't announce themselves)
- No "premium" or "professional" feature gating styling (gating is functional, not theatrical — see Phase 8a Settings space treatment)

The British register is what allows Bridgeable to be **substantial without being heavy**. American luxury would make the platform heavy by adding scale. German luxury would make it heavy by exposing engineering. Italian luxury would make it heavy by adding theater. The British register makes it substantial by *withholding announcement* — the weight is real, you just have to be in the platform for a few hours to feel it.

### Why a reference outside software

Translation principle 10 is the meta-rationale for everything else in Section 0. The choice of Range Rover (or any reference outside software) is not arbitrary. It's a deliberate move to escape SaaS convergence.

Most software gets designed in dialogue with other software. Designers look at Notion, Linear, Figma, Stripe, Vercel, Apple's HIG, Google's Material. The result is convergence — software narrows toward a small range of patterns. SaaS platforms in 2024–2026 are remarkably indistinguishable from each other because they all reference each other. The optimization axis is "be a slightly better version of [reference platform]," and that axis collapses inward.

**The Bridgeable move: take the reference point from outside software entirely.** Calibrate against vehicle design philosophy from a specific cultural tradition (British luxury, embodied by Land Rover). The optimization axis becomes "is this consistent with the design DNA of that reference?" — and that axis is *orthogonal* to the SaaS-convergence axis. The platform doesn't look like Notion, Linear, or Stripe — not because differentiation was the goal, but because the optimization axis is somewhere else entirely.

**Historical precedent for this move:**

- **Apple under Jonathan Ive.** Reference: Braun and Dieter Rams, not other computer companies. Result: Apple products that didn't look like PCs. The iMac G3 (1998), iPod (2001), iPhone (2007) all referenced industrial design from outside the computer industry. Apple was distinctive because the optimization axis was "this is good industrial design," not "this is a better PC."
- **Teenage Engineering.** Reference: analog synthesizers from the 1960s + Soviet industrial design + airline cabin aesthetics, not other consumer electronics. Result: products that don't look like other gadgets. The OP-1 (2011), TX-6 (2022), EP-133 (2023) all carry references that other consumer-electronics designers don't reach for.
- **Linear.** Reference: pre-computer information design — factory shop tickets, library catalogs, signal flags — more than other project-management software. Result: Linear feels different from Asana / Jira / Trello in a way that's hard to articulate but immediately legible.
- **Bridgeable.** Reference: Range Rover design philosophy + British luxury sensibility + workshop-with-tools-in-place + Leica/Teenage-Engineering-as-tools. Result: operational software for the physical economy that doesn't feel like other SaaS platforms.

**The implementation discipline this rationale demands:**

When calibrating a new component, the wrong question is "how does Linear handle this?" or "what would the Notion equivalent look like?" The right question is one of:
1. **How does the reference family handle the equivalent function in physical objects?** A button is a control surface — what does a Land Rover gear selector look like? An empty state is a quiet moment — what does a workshop look like when no work is in progress?
2. **What design instinct from the reference family applies here?** Restraint? Material honesty? Detail concentration? Quietness? Architectural proportion?
3. **If the question must reach for software references, reach for software *outside* the SaaS convergence:** Bloomberg Terminal density, Linear restraint, Apple HIG-tier polish — but check that the reference doesn't itself collapse into SaaS-warm convergence (modern Notion does; mid-period Linear doesn't).

This discipline keeps the optimization axis off the convergence axis. It's why Bridgeable cards don't look like Stripe cards. It's why Bridgeable buttons don't look like shadcn buttons. It's why the accent token sits where it sits.

### The relationship between Section 0 and Section 1

Section 0 defines the **object** — what kind of tool Bridgeable is. Section 1 defines the **settings** — what light it's observed under. Both must hold simultaneously.

A surface that reads as Mediterranean morning (Section 1, light) but as a generic SaaS dashboard (Section 0 violated) has the right warmth but the wrong character. A surface that reads as workshop-tool-grade (Section 0 honored) but as cold lab fluorescence (Section 1 violated) has the right character but the wrong setting. The platform achieves its identity only when both layers are present.

**Mental model:** Picture a Range Rover Defender pulled up to the Mediterranean terrace at morning, then the same vehicle parked outside the lounge in the evening. The vehicle's paint color — call it a deep terracotta or earthen ochre — is the same architectural color in both rooms. The light around it changes (warm garden sun → warm lounge lamp); the paint itself does not. Section 0 is what the tool is (the vehicle's color and form); Section 1 is where the tool is observed (the terrace, the lounge). The architectural color holds identity in either room. That superposition — same object, two settings — is Bridgeable.

(The previous version of this mental model used a Leica M body's brass top plate as the metaphor — "the brass is the object's material, the morning sun lands on the brass without changing what the brass is." That metaphor served the brass-era spec where the accent was a metal observed under different lights. Aesthetic Arc Session 2 retired brass and locked the accent to single-value deepened terracotta; the Range Rover paint metaphor better captures "architectural color in either room.")

### The aesthetic test

Codified as the platform's single-rule QA heuristic. Every visual element on Bridgeable must pass this test before shipping.

**Rule:** Before shipping any visual element, ask: *would this look like it was made by the same team that designed the rest of Bridgeable, applied with the design DNA articulated above? Does it share the qualities — restrained, materially honest, architecturally proportioned, quietly confident, time-resistant?*

- If **yes** → ship.
- If it drifts toward **generic SaaS warmth** (warmth as decoration rather than material), **consumer-app playfulness** (rounded-everything maximalism, gamification, celebration animations), **laboratory cold** (clinical, neutral, sterile), **current-decade trend-chasing** (gradient meshes, glassmorphism, neumorphism, AI-aesthetic), or **decorative flourish** (ornament without function) — refine before shipping.

**The test is design DNA coherence, not vehicle styling.** Not "would this look like a HUD?" Not "would this fit in a vehicle?" Those framings risk over-literal interpretation. The Range Rover reference is the *DNA*: restrained, materially honest, architecturally proportioned, quietly confident, made to last. The test is whether a new surface carries that DNA — not whether it looks like an automotive artifact. A correctly-built Bridgeable surface should look like *Bridgeable*, not like a Range Rover, while sharing the underlying design discipline.

**Sub-tests when the primary test is ambiguous:**

- *Time-resistance check.* Imagine this surface in a screenshot dated 2036. Does it embarrass anyone? If it shows a 2020s convention (the things listed in §10 anti-patterns), it fails.
- *Quietness check.* Cover the surface with a hand and try to recall whether you noticed any single decorative element. If yes, that element is too loud. If no, the chrome is calibrated correctly.
- *Reference-family check.* Imagine this surface placed alongside the Linear inbox, the Leica M9 product page, the Teenage Engineering OP-1 packaging. Does it feel like it belongs in that company? If yes, the register is right. If it feels like it'd be more at home in a Notion onboarding tour or a Slack channel header, the register has drifted.
- *Operator-respect check.* Would an operator with thirty years in a precast plant feel respected by this surface? Or would they feel patronized by emoji, illustrations, or condescending copy? Bridgeable users include people whose work is the physical economy. The visual language must match the seriousness of the work.

### Anti-patterns specific to Section 0

Generic-SaaS warm drift. The single most common failure mode in a platform that has the right tokens but the wrong character. Symptoms: warm gray surfaces with rounded-everything corners, accent buttons next to pastel illustrations, restrained typography next to celebratory animations, dim backdrop next to a stock smiling-team-photo. Each individual choice may be on-token; the composite reads as Notion-with-a-different-palette rather than as Bridgeable. Fix: review the eight qualities. Identify which are absent. Pull each toward presence.

Reference-family literalism. Translating the reference into surface decoration — a leather-grain background because Filson briefcase, a terracotta radial gradient because Leica top plate, a workshop pegboard pattern because workshop. The references are *imaginative briefs*, not visual specifications. The character translates; the artifacts do not.

Trend-tied visual conventions. Anything that places Bridgeable in a specific year — current-decade gradients, glassmorphism panes, neumorphism extrusions, soft-everything Apple consumer aesthetic, theatrical AI aesthetics (purple-to-pink gradients with sparkles). Time-resistance fails if the surface tells you what year it shipped.

Decorative warmth. Warmth used to make surfaces "feel friendly" rather than to express material. Pastel cream backgrounds with no purpose, soft drop shadows on flat content, accent borders on cards that don't need emphasis. The warmth in Bridgeable is materially earned — surfaces are warm because they are observed in warm light, not because warmth is decorative. When warmth is present without justification, the register drifts toward generic-SaaS.

Consumer-app maximalism. Rounded-everything (radius >16px on standard surfaces), celebration moments (confetti, animated checkmarks with sparkles, "great job!" copy), illustrative onboarding tours, decorative empty states with cheerful illustrations replacing functional information. These are correct in consumer software; they are wrong in operator software. Bridgeable's users are not customers being delighted; they are operators doing work.

Workshop-tool aesthetic without the discipline that makes workshop tools work. Information density without legibility. Density-as-virtue produces Bloomberg-Terminal-without-Bloomberg's-decades-of-typography-discipline — dense AND illegible. Density requires *more* design, not less. If a dense view is hard to scan, density became clutter.

### Calibration against existing surfaces (April 2026 baseline)

These surfaces serve as in-house calibration points. New surfaces compared against these should feel like they belong; surfaces that feel different need refinement.

**In-register surfaces** (achieve all eight qualities, evoke the right character):

- **Funeral Schedule kanban DeliveryCard** (`frontend/src/components/dispatch/DeliveryCard.tsx`). `bg-surface-elevated` + `shadow-level-1`, no perimeter border, restrained typography hierarchy (eyebrow + truncated FH headline + subhead + service-time line + icon-row status). Floats on the lane background as a material object. Accent status indicator (chat unread chip) used as functional emphasis. This is the canonical "card as material" reference for the platform.
- **Scheduling Focus core after Phase 4.4.2 container removal** (`frontend/src/components/focus/Focus.tsx`). Content floats directly on dimmed-blurred backdrop. No unifying container. Each child element provides its own visual weight via elevation tokens. "Focus is a mode, not a modal." The aesthetic register is most legible here because nothing decorative is present.
- **AncillaryPoolPin** (`frontend/src/components/dispatch/scheduling-focus/AncillaryPoolPin.tsx`). Compact rows with no decorative chrome (Phase 4.3b.3.2 removed the grip icon). Eyebrow + truncated label + subhead per row. Accent count chip on header. Whole-row drag with no handle. Workshop-tool register applied at small scale.
- **QuickEditDialog** (`frontend/src/components/dispatch/QuickEditDialog.tsx`). Section-grouped form (Assignment / Delivery state) with `text-micro uppercase tracking-wider` eyebrows. Form fields use the canonical input shell. No celebration on save; no decorative chrome. Restrained, considered, operator-grade.
- **Accent primary buttons platform-wide.** Functional emphasis via the cross-mode accent thread. No icon clutter. Solid surface, contained label. The same button reads as native to both Mediterranean morning and cocktail lounge evening — material continuity across modes.

**Drift surfaces** (have at least one quality missing; flagged for revisit):

- **Manufacturing dashboard onboarding banner** (per CLAUDE.md Aesthetic Arc Phase II audit). Pre-Aesthetic-Arc had a setup banner with rocket emoji that violated Operator-respect + Quietness. Aesthetic Arc Phase II's Batch 1a refresh closed most of this; verify any remaining vestigial emoji or celebratory copy.
- **WidgetChrome decorative grip icon** (`frontend/src/components/focus/canvas/WidgetChrome.tsx:259`). Retained from Phase A Session 3.5 as a "decorative drag affordance" with `pointer-events: none`. Per the post-4.3b.3.2 platform principle ("drag handles are an anti-pattern"), this icon now violates Considered Materiality (decorative, not earned) and Quietness (visible without functional purpose). Flagged in PRODUCT_PRINCIPLES.md drag-interactions section as tech debt; revisit when WidgetChrome is next touched.
- **BlockLibrary grip icon** (`frontend/src/components/workflow/BlockLibrary.tsx:549`). Same pattern as WidgetChrome — pre-existing decorative grip. Same rationale to retire.
- **Legacy pages still on shadcn defaults** (~213 pages per Aesthetic Arc Phase II audit, pre-batch-1). Most of those pages render coherently because their primitives have been refreshed (Sessions 2–3), but some page-level chrome (banners, headers, empty states) still uses generic shadcn semantic classes. Flagged for natural-touch refactor; the Aesthetic Arc batches close them progressively.
- **Status-pill ad-hoc rendering sites** (~1305 ad-hoc Tailwind status-color usages noted in Aesthetic Arc Phase II audit). Most sites should migrate to `<StatusPill>` or `<Badge variant="info|warning|success|error">` per the Session 3 status-color recipe. Until they do, individual sites read as "platform with status colors" rather than as "platform with the canonical status color treatment."

These calibration points are not aspirational — they exist in the codebase today. New surfaces should compare against them; refactor passes should pull drift surfaces toward the in-register surfaces.

### What this section provides Sonnet

When building any new visual surface, Sonnet should:

1. **Read the eight qualities (above).** They are the platform's character.
2. **Apply the aesthetic test** before shipping. If the surface fails any sub-test, pull toward the in-register calibration surfaces above.
3. **Reach for Section 1's mood anchors** for color, warmth, material character, atmosphere. Section 1 carries the *settings*; Section 0 carries the *object*.
4. **Reach for Sections 2–9** for specific values — token names, shadow specs, type scale, spacing scale, motion timing.
5. **Reach for Section 10** when something feels off and the cause needs localization.

When in doubt about whether a surface evokes the right register, the path is:

- **Eight qualities** (Section 0) — does the surface achieve them?
- **Mood anchors** (Section 1) — does the surface fit the morning-or-evening mood?
- **In-register calibration surfaces** (Section 0, above) — does the surface feel like it belongs alongside DeliveryCard, the post-4.4.2 Focus core, AncillaryPoolPin?
- If any of those answers is no, the surface needs refinement before shipping.

---

## Section 1 — Philosophy & The Two Moods

Bridgeable presents in two modes: **light** and **dark**. These are not generic themes. They are two specific felt experiences, each with its own sensory character. They share a platform identity but express it at two different times of day.

### The two moods

**Light mode — Mediterranean garden morning.**
A stone terrace in a European garden, high above the Mediterranean. Clear morning air. Warm sun filtered through olive branches or a stone archway. A cappuccino on a linen-covered table. The light is bright but warm, the air is crisp, and everything has been placed with care. Refined, not rustic. Unhurried, not sleepy.

**Dark mode — cocktail lounge evening.**
A high-end lounge in low warm light. Deep charcoal surfaces with presence, not absence. Pools of warm light catching the tops of surfaces. Deepened terracotta details on dark walnut. The dark is intimate, considered, and adult. Focused, not gloomy. Weighted, not heavy.

These two moods are **the same platform observed at two times of day.** The continuity is not visual similarity — morning and evening don't look alike — but material and intent. The same terracotta catches morning sun and evening lamplight. The same restraint governs both. A user who shifts from light to dark should feel they have stayed in the same place as the hour changed, not traveled to a different app.

### The meta-anchor: deliberate restraint

Both moods share a single underlying quality: **deliberate restraint.** Every element justifies its presence. Nothing is accidental, decorative-for-decoration's-sake, or generic.

**Rule:** Every visible element must earn its place. If a color, border, shadow, or flourish cannot be justified against the mood or the information it carries, remove it.

**Rationale:** Both moods — refined morning garden and intimate evening lounge — are restrained environments. Neither is cluttered, busy, or showy. Restraint is what makes each mood legible as *curated* rather than generic. Without this rule, the two moods drift toward decoration (morning becomes "sunny and cute"; evening becomes "dark and moody") instead of holding their felt character.

**Implementation:**
- Rules out: stock color choices ("default blue"), decorative gradients that serve no purpose, density that signals inability to decide what to remove, anything that looks accidentally generated rather than deliberately chosen.
- Rules in: specific colors for specific reasons, components that feel substantial (not flimsy, not over-engineered), empty space treated as a design element, choices that look obvious in retrospect but required taste to make.

### Light mode anchors

Five sensory anchors define light mode. Every downstream decision — color tokens, shadow specs, spacing — derives from these and should be verifiable against them.

**1. Warm cream linen base.**
- **Rule:** The primary surface color is a warm cream with noticeable material presence — like pale linen or washed pale stone in morning light. Not pure white. Not clinical. Not gray. The page reads as "warm material catching morning sun."
- **Rationale:** Pure white reads as clinical, sterile, or generic web-default. Gray reads as cold or corporate. A near-white off-white reads as cautious. A cream with genuine warmth and slight material presence establishes morning character in the single most-visible element on screen — the background itself. The canonical garden reference (see references below) anchors this as cream linen, not as near-white.
- **Implementation:** High-but-not-maximum lightness, low-but-noticeable chroma, warm hue. Specific values locked in Section 3.

**2. Clear warm diffuse light.**
- **Rule:** Shadows are warm-tinted, low-contrast, with slightly more edge definition than a fully diffuse overcast shadow. The mood is "shade under an olive tree on a stone terrace in clear morning air" — not "cloudy overcast" and not "hard noon sun."
- **Rationale:** Shadows carry most of the atmospheric character of a mode. Cool gray shadows would contradict the warm light. Fully diffuse shadows would read as sleepy or hazy. Hard-edged shadows would read as harsh. The target is clear-but-warm — legible edges, warm tint, restrained contrast.
- **Implementation:** Shadow color uses a warm hue (same family as accent/surface warmth), low opacity, medium blur, small-to-medium offset. Specific values locked in Section 6.

**3. Deepened terracotta as the primary warm accent.**
- **Rule:** Primary actions, focus states, emphasis, and active indicators use deepened terracotta. Not bright gold. Not yellow. Not red. Deepened terracotta — warm, earthen, architectural, with the weight of fired clay rather than the gleam of metal.
- **Rationale:** The accent is the material thread that ties morning to evening. The same architectural color reads as itself under garden sun and lounge lamplight — what makes "same platform, different hour" legible across modes. Terracotta is refined rather than rustic in this register: it belongs on the terrace floor as much as on the lounge wall, holding identity in either room without changing value. (Aesthetic Arc Session 2 retired the prior aged-brass accent — brass on warm cream read as "musty wall" rather than as craftsmanship; the yellow chroma fought the substrate's warmth instead of complementing it. See §2 cross-mode rule for the full rationale.)
- **Implementation:** Warm hue in the deep red-orange / earthen-clay family (oklch hue ~39), moderate lightness, moderate chroma. Specific values locked in Section 3. Secondary/supporting accents deferred to Section 3 when palette is specified in context.

**4. Unhurried motion.**
- **Rule:** Animations settle rather than snap. The motion character is considered, not snappy. Easing favors ease-out; things arrive gently.
- **Rationale:** Morning garden mood is unhurried. Fast snappy motion contradicts the felt target. But motion must still feel responsive — unhurried is not slow-for-slowness's-sake.
- **Implementation:** Specific durations and easing curves locked in Section 6. Durations expressed as a named scale, not ad-hoc millisecond values.

**5. Generous breathing room.**
- **Rule:** Padding, line height, and spacing between elements are generous by default. Content has space around it. The implicit message is "we have time, this is considered, you are not being rushed."
- **Rationale:** Cramped layouts contradict the refined-morning mood. A European garden terrace is not crowded. Space around elements signals that each element was placed deliberately — which reinforces deliberate restraint.
- **Implementation:** Base spacing scale and line-height defaults locked in Section 5. Density exceptions (data tables, scheduling boards) addressed in the density note below.

### Dark mode anchors

Five sensory anchors define dark mode. Same derivation principle as light mode.

**1. Deep warm cozy charcoal base.**
- **Rule:** The primary surface color is a deep warm charcoal that leans toward leather, warm wood, or lamplit plaster. Not pure black. Not blue-gray. Not neutral charcoal. A warm amber undertone, cozier than a generic dark mode.
- **Rationale:** Pure black reads as OLED-generic or as void. Blue-gray dark modes read as cold or corporate. Neutral warm charcoal is closer but still reads as "office at night." The cozy lounge mood requires the dark itself to feel like warm material — like leather or aged wood in lamplight — which means more warm chroma and a hue in the amber-brown family, not the neutral-warm family. The canonical lounge reference (see references below) shows the direction; "cozier than the reference" pushes slightly further.
- **Implementation:** Low lightness, low-but-noticeable chroma, hue in the amber-brown range (warmer than light-mode surfaces, per the warm-family asymmetry principle in Section 2). Specific values locked in Section 3.

**2. Concentrated warm light pools.**
- **Rule:** Elevated surfaces catch warm-tinted highlights from above, suggesting focused light sources. Flat surfaces fade into the dark. Elevation is communicated by light, not by outline.
- **Rationale:** Cocktail lounge lighting is pooled and directional — table lamps, recessed spots, candle-level warmth on select surfaces. Diffuse overall lighting would read as "office at night," not "lounge." This anchor is what makes the dark feel intimate rather than institutional.
- **Implementation:** Elevated surfaces use a subtle top-edge highlight and/or a slightly lifted surface color. Non-elevated surfaces do not. The gradient is meaningful (signals elevation), not atmospheric (applied to everything). Specific treatment locked in Section 6.

**3. Deepened terracotta as the primary warm accent (single value across modes).**
- **Rule:** Accents are the **same deepened terracotta** as light mode — same hex, same oklch value. Active states (currently-selected items, drop targets) communicate via the two-token pattern: `--accent-subtle` background + `--accent` border. Hover communicates via `--accent-hover` (the brighter terracotta variant).
- **Rationale:** Single-value-across-modes accent locks the architectural color in either room. The terracotta wall and the terracotta tile floor of the canonical references read as the same color under morning sun or evening lamplight. The substrate around it changes (cream linen → warm charcoal); the accent itself does not. This is a deliberate departure from the prior aged-brass spec, where the accent shifted lightness across modes ("the metal observed under different light"). The new rule is closer to a Range Rover paint color than to a metal-catching-light material — it holds identity regardless of ambient.
- **Implementation:** `--accent` resolves to the same `oklch(0.46 0.10 39)` value in both modes. Contrast against L=0.16 charcoal is ~3.2:1 (passes WCAG 2.4.7 3:1 for non-text accents). `--content-on-accent` is light cream in BOTH modes (~6.5:1 contrast on accent fill, AAA), making accent buttons read as "warm terracotta button with cream text" universally — not the brass-era asymmetric "glowing pill with dark text" that brass's lighter dark-mode value enabled. Specific values locked in Section 3.

**4. Material, not paint.**
- **Rule:** Surfaces feel like material — leather, wood, brushed metal, stone in low light — rather than flat paint. Elevation on dark surfaces is communicated through **two cooperating cues**: (1) a **surface-lightness lift with a hue shift toward warmer amber** — cards sit at a higher-lightness, warmer-hue surface value than the page beneath them (the metal of the bar rail feels warmer where the pendant light catches it), and (2) a **wider dim top-edge highlight** that reads as focused light from above (the pendant itself catching the top edge of the material). The platform does not use discrete perimeter borders on elevated cards — edges emerge from the lift + shadow-halo + highlight stack. Borders are used selectively on components where the edge carries structural meaning (inputs, table rules, focus indicators).
- **Rationale:** Cocktail lounge surfaces are material. You can feel the wood of the bar, the leather of the seat, the brass of the rail. "Material, not paint" is the durable principle. In the lounge, surfaces don't have painted outlines around them — they have light that falls on them and material that catches it. Mapping that to UI: cards are differentiated by how they **absorb and reflect the warm light**, not by lines drawn around them. Light mode uses a lift cue alone (morning light is ambient-and-diffuse, no focused highlight) plus a warm shadow halo; dark mode adds the top-edge highlight because evening light is directional (pendants, spots) and surfaces catch it on a specific edge.
- **Implementation:** Cards carry `bg-surface-elevated` (the warmer-hue lifted surface) and `shadow-level-1` (the three-layer composition: tight ground shadow + soft atmospheric halo + dark-mode-only 3px inset top-edge highlight via `--shadow-highlight-top`). Overlays (dialogs, popovers) use the same treatment scaled up via `shadow-level-2`. NO `border border-border-subtle` on the card perimeter — the material cues carry the full edge-signaling load. Specific treatments locked in Section 6.
- **History note:** The original anchor-4 prose listed three cue OPTIONS ("top-edge highlight, surface gradient, OR warm hairline border") as equally-valid material-not-paint techniques. A Tier-2 inference-based adjustment (April 2026) misread this as "cards apply all three" and added a canonical perimeter border to the Card primitive. Tier-4 measurement of the approved reference (`docs/design-references/IMG_6085.jpg`) showed the canonical design uses only two cues (lift + highlight); the perimeter border was removed. The learning: when a canonical reference exists, sample it directly before inferring from prose. "Images win over prose" applies to diagnosis as well as design authority.

**5. Deliberate, weighted motion.**
- **Rule:** Motion character is the same as light mode — unhurried, ease-out, settles rather than snaps — but with a slightly more weighted feel. Evening tempo. Like settling into a chair rather than moving through a doorway.
- **Rationale:** Evening mood is more deliberate than morning mood. Motion should reflect this without becoming sluggish. The difference is felt in character, not in dramatic timing differences.
- **Implementation:** Shared motion system with mode-scoped adjustments where needed. Specific durations and easing locked in Section 6.

### Density is allowed; clutter is not

Both moods default to breathing room, but Bridgeable has legitimately dense views — scheduling boards, case lists, quote tables, the full-plant yard display. The moods must survive density.

**Rule:** Dense views retain the mood. They earn their density by making every element legible and purposeful. Density is not an excuse for clutter; clutter is what happens when density is not designed.

**Rationale:** A scheduling board with 40 entries can still feel like Mediterranean morning if the entries are well-typed, well-spaced within their constraints, and the surrounding chrome stays calm. A case list can still feel like evening lounge if the typography is restrained and the background stays warm. Density without design produces clutter, which breaks both moods by violating deliberate restraint. The anchors apply at all densities — the implementation varies.

**Implementation:**
- Dense views may compress the base spacing scale, but do not abandon it. Compressed spacing is still proportional.
- Dense views do not add decorative elements to fill perceived emptiness. Empty cells, quiet rows, and calm chrome are correct.
- Dense views still use the mode's shadow, border, and accent treatments. The accent still appears where accent belongs; it just appears smaller.
- The test: zoom out on a dense view. Does it still read as morning garden (or evening lounge) at a glance? If yes, the mood survived. If it reads as "dashboard" or "data table," the mood was lost to density.

### The terracotta thread

**Rule:** Deepened terracotta is the single architectural color that appears in both modes as the primary warm accent. It is the platform's material signature.

**Rationale:** Without a thread across modes, light and dark become two unrelated themes. With the terracotta thread, they become two expressions of the same place. A user moving between modes should feel the accent holds identity in either room — the room's light changed, the architectural color did not. This is the single most important continuity decision in the document.

**Implementation:** `--accent` is one value — `oklch(0.46 0.10 39)` (#9C5640) — used identically in both modes. Hover brightens to `oklch(0.54 0.10 39)` (#B46A4D) in both modes — universal "lift" signal, not asymmetric press-in/glow. The accent is not used decoratively; it marks primary action, focus, and emphasis in both modes. It is the thing the eye goes to, in both morning and evening. Aesthetic Arc Session 2 (April 2026) retired the prior aged-brass thread; see §2 cross-mode rule for the migration rationale.

### Canonical mood references

Two images serve as the canonical anchors for the two moods. They should be stored in project knowledge alongside this document and referenced whenever this section's prose leaves ambiguity.

**Light mode — `design-ref-light.png`:** A stone terrace in a European garden, high above the Mediterranean. Pergola with climbing bougainvillea, terracotta lantern, terracotta tile floor, warm stone walls, a table set with pale linen, potted olives and herbs, the sea visible beyond a wrought-iron railing. This image is the canonical anchor for the light-mode mood. When a prose rule in this document could be interpreted two ways, default to the interpretation closer to this image.

Specific anchor points in the reference:
- The linen tablecloth is the closest analog to the base surface color.
- The terracotta of the lantern and chair frames is the canonical accent hue.
- The shadows under the pergola and under the table show the target shadow character: warm, low-contrast, softly edged.
- The terracotta floor is an example of a warm *structural* material, not a UI accent. It confirms that terracotta belongs to floor/foundation, not to emphasis or action.
- The sea blue in the distance is a muted atmospheric cool note, deferred for now per Section 3.

**Dark mode — `design-ref-dark.png`:** A high-end cocktail lounge in low warm light. Walnut bar top, terracotta pendants in a row, a warm charcoal textured wall with a brass sun sculpture, leather club chairs, distant city view through mullioned windows. This image is the canonical anchor for the dark-mode mood, with the following correction: our dark mode should feel **cozier** than this image — warmer overall, more absorbed light, smaller implicit scale. The grand lounge in the reference is the direction; a smaller warmer version is the target.

Specific anchor points in the reference:
- The brass pendant lamp interiors and the sun sculpture in the photograph are the brass-in-evening-light reference for the original aged-brass spec. **Aesthetic Arc Session 2 (April 2026) retired aged-brass; the canonical accent is now deepened terracotta `#9C5640` regardless of what the photograph's metal elements show.** The lounge photograph is still the canonical mood anchor for surface tones, shadow character, and atmosphere — but the accent value is locked independently.
- The charcoal wall is the direction for the base surface, pulled slightly warmer and browner for the cozy target.
- The wood of the bar top and the leather of the chairs are examples of the "material, not paint" principle applied at full intensity. UI surfaces should echo this in restraint — they should feel like material without mimicking specific textures.
- The pools of light from the pendants are the elevation logic: light where attention belongs, warm dark elsewhere.

### Canonical scope — what counts as a reference, what doesn't

`docs/design-references/` contains **exactly two canonical mood-anchor files:**

- `design-ref-light.png` — the Mediterranean garden terrace photograph
- `design-ref-dark.png` — the cocktail lounge photograph

These are the platform's external mood anchors. They are **photographs of real spaces**, not UI renders, and that is load-bearing: their value comes from being grounded in physical material reality that the design language is translating into pixels. Their warmth, their shadow character, their brass patina — these are observed from reality, not specified.

Other files in `docs/design-references/` fall into two non-canonical categories:

**Pattern references** (e.g., `card-pattern-reference-*.png`) — renderings of UI compositions approved during design work. Used for structural decisions: card shape, spacing, radius, typography hierarchy, component composition. **Never measured for color values** — doing so closes a circular calibration loop because the rendering was produced from the tokens being calibrated. Pattern references answer "what should this look like structurally"; mood anchors answer "what should this feel like materially."

**Archive** (in the `archive/` subfolder) — historical mockups, superseded designs, work-in-progress captures. Kept for history; not authoritative for anything current.

**Conflict resolution:** when mood anchor and pattern reference disagree, **mood anchor wins** for color, material character, atmosphere, elevation feel, shadow character, and accent hue. **Pattern reference wins** for layout, composition, spacing, radius, and typography hierarchy. This split is non-negotiable: reversing it re-introduces the circular calibration problem.

### The calibration chain

When the design language requires token calibration — because a prose rule is ambiguous, or a perceived drift needs measurement — the calibration chain must be:

```
External mood anchor (design-ref-*.png)
    ↓ sample directly (e.g. PIL)
    ↓ identify the photographed material that maps to the UI surface
    ↓ (per prose analogies above: "the charcoal wall is the direction
    ↓  for the base surface"; "the walnut bar top is the direction for
    ↓  elevated surfaces catching warm light")
    ↓
Token values (tokens.css + DL §3, mirror-synchronized)
    ↓
UI rendering (primitives + pages)
    ↓
Pattern reference (card-pattern-reference-*.png)
    — captures approved UI composition at a point in time
    — feeds back into structural decisions (spacing, layout, radius)
    — NEVER feeds back into color calibration
```

Never this:

```
UI mockup / pattern reference (derivation — already downstream of tokens)
    ↓ sample the mockup
    ↓
Token values ← CIRCULAR — calibrates tokens against their own output
```

### When the mood anchors don't cover a UI concern

The mood photographs depict physical spaces, not UI. They don't show stat cards, tables, form controls, modals, or any other software composition. When a UI decision must be made that the mood anchors don't demonstrate, the correct method is **derivation via §2 translation principles**, not approximation via pattern references.

Example: the mood anchor shows a walnut bar top catching pendant light — that's the elevation principle in its natural form. A stat card doesn't exist in the photo, but the principle applies: a card surface catches implied warm light relative to the ambient dark. Derive the card treatment from the principle, not from an existing mockup of what a card "should" look like. Pattern references may confirm the composition *after* the principle-derived treatment is applied, but they don't originate color or material decisions.

This matters because pattern references feel tempting when mood anchors seem "not specific enough" to answer a UI question. That temptation is exactly where circular calibration enters. The correct response to "the mood anchor doesn't show this exact UI element" is to derive from §2 principles, not to reach for an internal artifact that does show the element.

### How to use the references

- When writing a new component, compare it to the mood anchors first. Does the light-mode version feel like it could exist on that terrace? Does the dark-mode version feel like it could exist in that lounge (but cozier)?
- When specifying a new color, verify via PIL sampling against the mood anchor, then adjust per §2 translation principles.
- When specifying a new layout, structure, or composition, verify against pattern references (if one exists for that component) and §5 spacing principles.
- When in doubt about warmth, density, or material character, the **mood anchors** win over prose.
- When in doubt about layout, structure, or composition, the **pattern references** win over ad-hoc design.
- When both are silent, derive from §2 translation principles. Do not reach for an internal artifact that appears to answer the question; that path is where the circular calibration anti-pattern (§10) enters.

### Calibration history

**Tier 5 (April 2026)** — first calibration of tokens against the external mood photographs per the calibration chain above. PIL-sampled `design-ref-dark.png` (cocktail lounge) and `design-ref-light.png` (Mediterranean garden) at the material analogs named in the "specific anchor points" sections above (charcoal wall / walnut bar top / pendant interiors / under-pergola shadows / linen tablecloth / lantern), converted to OKLCH, compared to then-current tokens, and corrected three sets:

- **`--surface-elevated` (dark)** L=0.20 → L=0.28. Prior value sat in the walnut-grain-dark range; corrected to the "catching pendant light" range per §1 dark anchor 2.
- **`--surface-base` (light)** chroma 0.018 → 0.030. Photo measured linen at C=0.037; backed off slightly because token→UI-at-scale amplifies perceived warmth.
- **`--shadow-color-{subtle, base, strong}`** (both modes) — lifted L, doubled C, hue shifted 3–5° warmer. Prior tokens composited darker + cooler than the anchors' photographed shadows.
- **`--surface-raised` (dark)** L=0.24 → L=0.32 derived proportionally from the elevated lift.

Prior tiers 2–4 attempted calibration against an approved UI mockup (`IMG_6085.jpg`, now in `archive/`) which was itself downstream of the then-current tokens — a circular calibration loop (§10). Tier 5 anchors to the external mood photographs per §1's calibration chain; the circular-calibration anti-pattern and this calibration-chain requirement were formalized in the same arc.

Explicit non-corrections (values held against photo deltas with specific rationale):

- **`--surface-base` (dark)** L=0.16 held. Photo measured charcoal wall at L=0.21 (bright), but §1 prose specifies "pulled slightly warmer and browner for the cozy target" — cozier = darker + more absorbed. Token sits at the dark "cozy" end of the wall's variance.
- **`--surface-base` (dark)** hue 59 held. Photo measured h=114 (olive-tinted charcoal), token at h=59 (warmer amber). Direction-correct per §1 "warmer and browner" correction.
- **Dark brass** (L=0.70) held — *obsolete after Aesthetic Arc Session 2.* The brass spec retired entirely; the new accent is single-value deepened terracotta `oklch(0.46 0.10 39)`. Original Tier-5 rationale: photo's pendant-interior measurement (L=0.80) was of the directly-illuminated bright interior — closer to an active/hover brass state than a base state. Retained as historical context.
- **Light brass** held — *obsolete after Aesthetic Arc Session 2.* Original Tier-5 rationale: measurement unreliable (sampling hit aged-wood frame rather than polished metal). Retained as historical context.

Future calibrations should cite this history when making further adjustments.

---

## Section 2 — Translation Principles

Section 1 defines the moods as felt experiences. Section 3 will define exact token values. This section is the bridge: the rules that connect anchors to values, so that anchors are verifiable against implementation and future decisions have a principled derivation path rather than arbitrary choice.

**How to use this section:**
- Sonnet reads this section to understand the *rules* that govern color, shadow, and material decisions.
- Sonnet reads Section 3 to get *the specific values* that comply with those rules.
- Section 3 values must fall within Section 2 ranges. If they don't, one of the two sections is wrong.
- When a new color, shadow, or material treatment is needed and doesn't exist in Section 3, this section tells Sonnet how to derive it.

### Color space: oklch

**Rule:** All color values are expressed in oklch. Hex, rgb, and hsl are not used in tokens. CSS may compile to rgb/hex at the browser level, but the design system authors in oklch exclusively.

**Rationale:** oklch gives us three things the design language needs and that hsl/rgb don't: perceptually uniform lightness (L=0.5 looks equally bright regardless of hue, which is false in hsl), independent hue/chroma/lightness axes (we can adjust one without the others shifting), and a predictable chroma axis that corresponds to how saturated a color actually appears. This matters most for the terracotta thread — the same accent hue has to work at different lightness values in light and dark modes, and only oklch lets us lock hue while adjusting lightness without the color drifting.

**Implementation:** All tokens in Section 3 are authored as `oklch(L C H)` values. CSS custom properties use the `oklch()` function directly. Tailwind config references oklch. When communicating colors in documentation or prompts, oklch is the canonical form.

### The warm-hue family

**Rule:** All surface colors, shadow colors, and neutral tokens sit in a warm hue family — hue angle between **70 and 95** in oklch. This applies in both light and dark modes. Accents may sit outside this range (the accent sits OUTSIDE this range — see warm-family asymmetry below; a future cool supporting accent would not be); surfaces and their shadows do not.

**Rationale:** Coherence across the platform requires that the backgrounds and shadows share a hue family. If the light-mode background is warm (hue ~85) but the light-mode shadow is neutral gray (hue effectively undefined or cool), the shadow contradicts the mood. Same for dark mode: if the charcoal is warm but the card elevation shadow is cool, the lounge mood breaks. Locking the surface-and-shadow hue family is the single most important coherence rule in the platform — it's what makes morning feel like morning in every corner of the UI, not just on the page background.

**Implementation:**
- Light-mode base surface: hue 75–90
- Dark-mode base surface: hue 70–90
- All shadow colors: hue 60–90
- All neutral text colors (which are tinted, not pure): hue 70–95
- Accents are not bound by this rule but accent does NOT fall in this range — terracotta sits at hue ~39 (hue ~75–85), which is why accent reads as a stable counterpoint rather than as an accent bolted onto neutral chrome.

### Translation rules per anchor

Each anchor from Section 1 translates to oklch ranges. Section 3 picks specific values within these ranges.

**Warm cream linen base (light mode, anchor 1)**
- **Lightness:** 0.94–0.97
- **Chroma:** 0.008–0.020
- **Hue:** 80–92
- **Verification test:** Place a pure white (`oklch(1 0 0)`) patch next to the chosen base. The base should read as "cream linen" or "pale warm stone" against the pure white, not as "off-white gray" and not as "bright white." If the chosen base reads as gray next to pure white, chroma is too low or hue is too cool. If it reads as near-white, lightness is too high — the base should have noticeable material presence, not clinical brightness.
- **Reference correction note:** An earlier draft of this range specified lightness 0.97–0.99 and chroma 0.005–0.015. The canonical garden reference (see Section 1 references) shows that the closest analog surface — the linen tablecloth — has more warmth and more material presence than near-white. This range was adjusted to match the reference, moving from "warm off-white" to "cream linen."

**Clear warm diffuse shadow (light mode, anchor 2)**
- **Shadow color lightness:** 0.25–0.45 (shadows are not black; they are dark warm tones at low opacity)
- **Shadow color chroma:** 0.02–0.05 (some color, not neutral)
- **Shadow color hue:** 60–85 (warm, possibly slightly more orange than the surface hue to read as "sunlit shadow")
- **Shadow opacity:** 0.06–0.14 (low contrast; shadows are felt, not stamped)
- **Shadow blur:** medium — specific values in Section 6
- **Verification test:** A shadow should look warm-tinted when isolated on a neutral background. If a card's shadow looks gray when you screenshot it against white, it's wrong.

**Deepened terracotta (both modes, light-mode anchor 3 and dark-mode anchor 3)**
- **Hue:** 35–43 (narrow, locked across modes; deep red-orange / earthen-clay, NOT amber-yellow)
- **Lightness:** 0.42–0.50 (single value across modes — the architectural-color rule)
- **Chroma:** 0.09–0.11 (single value across modes)
- **Hover state (both modes):** lightness rises to 0.50–0.58 — the universal "lift" signal. Hue does not shift. Chroma may rise minimally; the lift is primarily a lightness step.
- **Verification test:** The accent placed on cream linen (L=0.94) and on warm charcoal (L=0.16) should read as the same architectural color in two rooms. If light-mode and dark-mode accents look like different colors, the spec has drifted from the locked single-value rule. Contrast against L=0.16 charcoal must clear WCAG 2.4.7 3:1 for non-text accent (~3.2:1 at the locked value); contrast against L=0.94 cream is comfortable (~5:1).
- **History note (April 2026):** This anchor previously specified aged brass — hue 70–78, lightness shifting 0.62–0.72 (light) → 0.68–0.78 (dark) for "same metal observed under different light." Aesthetic Arc Session 2 retired the brass spec after extended evaluation showed brass-on-warm-cream read as "musty wall" rather than craftsmanship — the yellow chroma fought the substrate's warmth. Deepened terracotta keeps the warmth-and-architectural register without the yellow-chroma issue. The single-value-across-modes rule replaces the "metal observed under two lights" framing with "the architectural color is one thing in either room" — closer to a Range Rover paint color than to brass-on-camera-body. See cross-mode rule below for full context.

**Deep warm cozy charcoal base (dark mode, anchor 1)**
- **Lightness:** 0.14–0.20
- **Chroma:** 0.008–0.020
- **Hue:** 55–75
- **Verification test:** Place pure black (`oklch(0 0 0)`) next to the chosen base. The base should read as "warm leather" or "cozy lamplit dark material" against pure black, not as "almost black" and not as "gray." If it reads as near-black, lightness is too low. If it reads as gray or blue-gray, chroma is too low or hue is outside the warm-amber range.
- **Reference correction note:** Earlier drafts specified lightness 0.18–0.24 and less chroma. After two rounds of in-context verification against the lounge reference, the range was pulled deeper (accommodating a locked value at 0.16) to support the cozier-than-reference direction. The dark mode reads as properly-evening lamplit rather than early-evening dimmed.

**Concentrated warm light pools (dark mode, anchor 2)**
- Elevated surfaces use a lifted base: lightness +0.03 to +0.06 from the base charcoal, same hue family, same low chroma.
- Top-edge highlight (where used): a 1px line at lightness 0.35–0.45, hue 75–85, low chroma 0.01–0.03, opacity 0.3–0.6. The highlight reads as reflected warm light, not as a border.
- **Verification test:** Raise a card on the dark background. Does it feel lit from above, or does it feel outlined? If outlined, the treatment failed — outlines are not how this mood expresses elevation.

**Material, not paint (dark mode, anchor 4)**
- Not a color range — a treatment principle. Implementation in Section 6.
- Constraint: any material treatment (gradient, highlight, hairline edge) must be subtle enough that it doesn't read as decoration. If a user notices the gradient, it's too strong. The correct level is "feels like material" without being able to point to what makes it so.

### Warm-family asymmetry across modes

**Rule:** Light mode's warm family centers on hue 80–92 (warm cream, pale stone, clear morning light). Dark mode's warm family centers on hue 55–75 (lamplight, leather, warm wood, evening amber). The family is warm in both modes but leans noticeably more orange-amber in dark mode. The accent (deepened terracotta, hue ~39) sits *below* the warm-family range — it's a deliberate architectural color, not a member of the surface-family — and reads as a stable counterpoint to the warm substrate in either mode.

**Rationale:** Symmetric hues across modes produce a dark mode that reads as "daylight dimmed" rather than "evening lamplight." The cozy lounge mood requires that the ambient warmth shift, not just the lightness. Morning sun filtered through garden air has a different color temperature than evening lamps through leather-lined walls. The asymmetry encodes this difference. The accent sits outside this asymmetry deliberately: it is the platform's architectural color, observed against shifting ambient light. Both the cream-linen substrate and the warm-charcoal substrate complement the same terracotta; neither absorbs nor distorts it.

**Implementation:**
- Non-accent surfaces in light mode use hues in 80–92.
- Non-accent surfaces in dark mode use hues in 55–75.
- Accent uses a single fixed value across modes (locked per the cross-mode rule below).
- When deriving a new surface color for dark mode, pull its hue toward 55–75 even if the light-mode equivalent is at 85. Do not copy the light-mode hue into dark mode.

### Shadows persist in dark mode

**Rule:** Dark mode has shadows. Elevated elements cast warm-tinted shadows on the base surface, low-contrast but visible as atmosphere. Shadows in dark mode are not dropped, not replaced by borders, and not replaced solely by top-edge highlights.

**Rationale:** A common dark-mode pattern drops shadows entirely and communicates elevation via color lightness and borders only. This pattern produces "flat dark UI" — legible but cold. The cozy lounge mood depends on soft warm shadows filling the space between elements, the way real shadows fill the space under and around objects in lamplight. A dark mode without shadows reads as institutional; a dark mode with warm low-contrast shadows reads as intimate.

**Implementation:**
- Dark-mode shadow color: lightness 0.08–0.16, chroma 0.005–0.015, hue 50–70, opacity 0.30–0.55.
- Dark-mode shadows are *larger and softer* than light-mode shadows — shadows in low light naturally diffuse more. Blur is higher, offset is similar.
- The top-edge highlight (where used on elevated surfaces) is an *additional* cue, not a replacement for the shadow. Elevated surfaces get both: a warm top-edge highlight and a warm soft shadow below.
- Verification test: screenshot an elevated card on the dark base. Can you see the shadow as a warm slightly-darker patch around and below the card? If the shadow is invisible, opacity is too low. If it reads as gray or black, hue is wrong.

### The terracotta cross-mode rule

**Rule:** Deepened terracotta is **one color, one value, used identically in both modes**. The full oklch triplet is locked: lightness 0.46, chroma 0.10, hue 39 (`oklch(0.46 0.10 39)` ≈ `#9C5640`). Hover brightens to `oklch(0.54 0.10 39)` (≈ `#B46A4D`) — universal "lift" signal across both modes. Active states (currently-selected items, drop targets) compose via the two-token pattern `bg-accent-subtle` + `border-accent`. The accent does not shift lightness across modes.

**Rationale — the architectural-color rule:** The prior aged-brass spec used a "same metal observed under different light" framing — brass shifted lightness across modes (0.66 light → 0.70 dark) to maintain legibility. That works for a metal that genuinely catches and reflects ambient light. For Bridgeable's register, the closer mental model is **a Range Rover paint color**: it holds its identity in either room. The terracotta wall and the terracotta tile floor of the canonical references (the Mediterranean garden's terracotta lantern + tile, the lounge's terracotta pendants on dark walnut) read as the same color whether observed at morning or evening — because the color *is* the architectural decision, and only the surrounding ambient changes. This framing aligns with the operator-in-calm-room register: the workshop tool's accent is constant across the day; the workshop's light is what shifts. Single-value-across-modes also simplifies the token system (one canonical accent value, not two) and removes any drift risk from per-mode tuning.

**Why brass retired (April 2026):** Aged brass on warm-cream substrate read "musty wall" rather than craftsmanship. Brass's yellow chroma (hue ~73) fought the substrate's warmth (hue ~82) instead of complementing it — adjacent warm-yellow on warm-cream produces a flat, undifferentiated wash rather than the intended jewelry-on-stone composition. Terracotta (hue ~39) sits well below the warm-cream substrate's hue range, providing genuine chromatic contrast without leaving the warm family. The result reads as "earthen architectural detail on warm stone" rather than "yellow detail on yellow stone." Cocktail lounge dark mode also benefits: terracotta against L=0.16 warm charcoal reads with weight and presence; brass against the same substrate read as too-bright glow against too-dim dark. The single-value lock further reinforces the platform's British-register aesthetic — the accent doesn't need to perform differently under different conditions; it is what it is.

**Implementation:**
- `--accent` is `oklch(0.46 0.10 39)` — single locked value, not a range. This is *the* accent of the platform.
- The light-mode `--accent` and dark-mode `--accent` use the same triplet.
- `--accent-hover` is `oklch(0.54 0.10 39)` — single locked value, both modes. Universal lift on hover.
- `--accent-muted` and `--accent-subtle` are alpha-composited over the accent base (`rgba(156, 86, 64, 0.20)` and `rgba(156, 86, 64, 0.10)` respectively); no per-mode value.
- `--content-on-accent` is `oklch(0.98 0.006 82)` (light cream) in **both** modes — the accent is dark enough that cream text reads ~6.5:1 contrast (AAA) universally. This replaces brass-era asymmetric content-on-brass (cream in light, dark charcoal in dark) — symmetric pairing matches the single-value accent.
- `--accent-active` is **intentionally absent**. The current Bridgeable "active state" semantic is "this is the currently selected item" (DateBox active, nav active), implemented via `bg-accent-subtle` + `border-accent`. Not "this button is being pressed right now." If momentary press feedback is needed later, introduce `--accent-active` then; reducing token surface area now prevents ambiguity (developers using `--accent-active` for selected-item state instead of press state).
- Any new accent-adjacent variant must justify itself against the single-value rule. Variants of the existing accent (subtle, muted) compose via alpha; new accent values for distinct semantic roles (e.g., a destructive accent, a success accent) get their own token entries in Section 3 and the status-tokens system, not as accent-adjacent variants.

### Deriving a new color

When a new color is needed — a new status color for a new vertical, a new informational accent, a visualization palette — use this derivation procedure:

**Step 1: Identify the nearest anchor.**
Is this color a surface? A shadow? An accent? A status indicator? Map it to the closest anchor concept. If it doesn't map to any existing anchor, stop and ask whether a new anchor is needed (this is a design language change, not a token addition).

**Step 2: Start from the anchor's oklch range.**
Use the anchor's lightness, chroma, and hue ranges as the starting point.

**Step 3: Adjust the minimum necessary axis.**
If the new color needs to be distinguishable from the anchor (e.g., a new status color distinct from accent), adjust the single axis that carries the distinction and leave the others alone. For semantically distinct colors (error, warning, success), adjust hue. For variants of the same semantic role (hover, active, disabled), adjust lightness.

**Step 4: Verify against both modes.**
The new color must work in both light and dark modes. If it's a single token, it needs two values (one per mode). Apply the cross-mode consistency principle: lock hue, shift lightness.

**Step 5: Verify against the mood.**
Place the new color against the mode's base surface and a sample component. Does it feel like it belongs in the garden / lounge, or does it feel bolted on? If bolted on, the chroma is likely too high or the hue is outside the warm family. Pull it back toward the warm family and lower the chroma until it feels native.

**Anti-rule:** Do not pick a new color by starting from a generic palette (Material, Tailwind defaults, Bootstrap) and "warming it up." Start from the anchor. Generic palettes carry generic mood, and warming them after the fact produces colors that read as "slightly warmed generic" rather than as native to Bridgeable.

### Verification posture

Every color decision in Section 3 and beyond should be verifiable by reading this section. The test:

1. Pick any token from Section 3.
2. Identify which translation rule governs it.
3. Confirm the token's oklch values fall within the rule's ranges.
4. Confirm the token passes the rule's verification test (the "looks like X against Y" checks above).

If any step fails, either the token is wrong or this section is wrong. Both are fixable; silent drift is not.

## Section 3 — Color System

This section commits to specific oklch values for every semantic color token in the platform. All values fall within the ranges specified in Section 2 and are verifiable against Section 2's rules. Section 3 is the *answer*; Section 2 is the *test*.

**Mirror discipline:** The values in this section and `frontend/src/styles/tokens.css` **must stay synchronized**. A change to either requires a same-commit update to the other. Documentation drift between this canonical reference and the implementation is treated as a defect. Sonnet should verify this invariant before committing any token change.

**Structure:**
- The three anchor tokens are locked explicitly.
- Derived tokens (elevated surfaces, text, borders, muted variants) are derived from anchors per Section 2's translation rules.
- Status colors (error, warning, success, info) are derived using Section 2's "Deriving a new color" procedure.
- The full token table lists every CSS variable name and its light-mode and dark-mode values.

### Anchor tokens (locked)

These are the three decisions that everything else in the color system derives from. Changing one of these values invalidates every derived token and requires a full re-derivation.

| Token | Light mode | Dark mode |
|---|---|---|
| **Surface base** | `oklch(0.94 0.018 82)` | `oklch(0.16 0.012 65)` |
| **Accent (deepened terracotta, primary accent)** | `oklch(0.46 0.10 39)` | `oklch(0.46 0.10 39)` |

Accent locked at **single value** across modes per the cross-mode rule (the architectural-color rule, §2). Surface base hue asymmetric across modes (82 in light, 65 in dark) per Section 2's warm-family asymmetry rule. The accent retired aged-brass in Aesthetic Arc Session 2 (April 2026); see §2 cross-mode rule for the full migration rationale.

### Semantic token naming convention

Tokens use the pattern `--{role}-{variant}` where role describes what the color is *for* (surface, content, accent, status) and variant describes its specific use (base, elevated, muted, strong).

- **surface** — backgrounds, cards, panels, anything that content sits on
- **content** — text, icons, anything that sits on a surface
- **accent** — terracotta and any future accents, used for emphasis and action
- **border** — lines that separate or outline surfaces
- **shadow** — shadow colors (not opacities, which are separate)
- **status** — semantic state colors (error, warning, success, info)

Variants:
- **base** — default state
- **elevated** — one step lifted above the surrounding surface (e.g., a card on a page)
- **raised** — two steps lifted (e.g., a modal on a card-filled page)
- **muted** — lower-contrast version for secondary use
- **subtle** — even lower contrast, for tertiary use
- **strong** — higher-contrast version for emphasis
- **hover / active / focus / disabled** — interactive state modifiers

Not every token has every variant. The table below lists all defined tokens.

### Surface tokens

**Rationale:** Elevation in this platform is communicated by **two coordinated dimensions of color change**: lightness and hue. An elevated surface is lighter AND warmer-hued than the base. Light mode uses a uniform ~0.025 lightness step per elevation level — morning light is ambient-and-diffuse, so the delta stays small. Dark mode uses a **non-uniform step**: base→elevated is ~0.12 OKLCH (the big leap where surfaces begin "catching warm light"), elevated→raised is ~0.04 (overlays are one level more lifted than their containing context). Dark mode also shifts hue warmer at each elevation step — this is the second material dimension. The non-uniform dark-mode step and the hue progression together encode DL §1 dark-mode anchor 2 ("concentrated warm light pools"): flat base surfaces fade into the dark; elevated surfaces are where directional warm light lands.

| Token | Light mode | Dark mode |
|---|---|---|
| `--surface-base` | `oklch(0.94 0.030 82)` | `oklch(0.16 0.010 59)` |
| `--surface-elevated` | `oklch(0.965 0.014 82)` | `oklch(0.28 0.014 81)` |
| `--surface-raised` | `oklch(0.985 0.010 82)` | `oklch(0.32 0.016 85)` |
| `--surface-sunken` | `oklch(0.91 0.020 82)` | `oklch(0.13 0.010 55)` |

*Notes:*
- Chroma decreases slightly as lightness increases in light mode — the lightest surfaces approach near-white and carry less warmth. This is intentional: the raised surface feels like "paper catching more light" rather than "saturated pale." Tier-5 calibration (April 2026) against design-ref-light.png linen tablecloth raised `--surface-base` chroma 0.018 → 0.030; photo measured C=0.037, token backed off to 0.030 because token→UI-at-scale amplifies perceived warmth.
- Chroma increases slightly as lightness increases in dark mode — elevated surfaces carry *more* warmth, because they're catching more of the implied warm lamplight. This is the cocktail lounge material logic.
- **Dark-mode hue progression** is the second material-not-paint dimension: `base` sits at h=59 (the cool-amber foundation), `elevated` shifts to h=81 (the warmer-amber "catches more lamplight" treatment), `raised` continues to h=85 (most-elevated, most-directly-lit). `sunken` drops to h=55 (cooler, recessed-from-light). The hue shift IS what makes a dark elevated surface feel like "warm metal catching pendant light" rather than just "a lighter shade of the same surface." Without the hue shift, lightness-lift alone reads as monotone grading and doesn't deliver the "material, not paint" anchor.
- **Dark-mode non-uniform step (Tier-5):** base→elevated L=0.12 is deliberately larger than elevated→raised L=0.04. The mood-anchor scenario (walnut bar top catching pendant light) shows a dramatic luminance difference between the charcoal wall (base, ~L=0.21 measured, pulled darker to L=0.16 per §1 "cozier than reference" correction) and the walnut surface directly under the pendant (elevated, measured L=0.40-0.52 at bulk, L=0.91 at highlight). Token L=0.28 sits deliberately below the bulk-walnut value because a UI card at pixel-coverage scale reads brighter than a textured material sample in a photo; L=0.28 preserves the catching-light signal without over-brightening the card. Elevated→raised then uses the smaller 0.04 step because "raised" is overlay-level hierarchy, not material-level hierarchy — one step more lifted, not "catching fundamentally different light."
- `surface-sunken` is used for deep-recessed areas (inset panels, code blocks, sidebar backgrounds that sit below the page level). Not commonly used; defined for consistency.
- **Reconciliation history (April 2026):** pre-Tier-4, dark-mode tokens used a static h=65 across the elevation stack. Tiers 2–4 attempted progressive calibration against an approved UI mockup (IMG_6085.jpg, now archived). Tier-5 sampled the external mood anchors directly (`design-ref-dark.png` cocktail lounge + `design-ref-light.png` Mediterranean garden) per the §1 calibration chain and corrected `--surface-elevated` (dark) L=0.20→0.28, `--surface-raised` (dark) L=0.24→0.32, `--surface-base` (light) C=0.018→0.030, and the three shadow-color tokens in both modes. Tier-4 hue progression (59→81→85) retained — directionally correct. Tier-2 three-layer shadow composition (tight ground + soft halo + 3px inset highlight) retained — architecturally correct.

### Content tokens (text and icons)

**Rationale:** Text is never pure black on light mode or pure white on dark mode. Both are tinted with warm hue to belong to the platform's warm family. Contrast against surfaces is tuned to meet WCAG AA at minimum for body text; `content-base` and `content-strong` meet AAA on `surface-base`.

| Token | Light mode | Dark mode |
|---|---|---|
| `--content-strong` | `oklch(0.22 0.015 70)` | `oklch(0.96 0.012 80)` |
| `--content-base` | `oklch(0.30 0.015 70)` | `oklch(0.90 0.014 75)` |
| `--content-muted` | `oklch(0.48 0.014 70)` | `oklch(0.72 0.014 70)` |
| `--content-subtle` | `oklch(0.62 0.012 70)` | `oklch(0.55 0.012 68)` |
| `--content-on-accent` | `oklch(0.98 0.006 82)` | `oklch(0.98 0.006 82)` |

*Notes:*
- `content-strong` is for headings and critical emphasis. `content-base` is body text.
- `content-muted` is secondary text (captions, metadata). `content-subtle` is tertiary (placeholder text, disabled states).
- `content-on-accent` is the color used for text/icons placed *on* accent surfaces (e.g., label on a primary terracotta button). **Same value in both modes** (light cream with warm tint) per Aesthetic Arc Session 2 — terracotta at L=0.46 is dark enough that cream text clears WCAG AAA contrast (~6.5:1) symmetrically across both modes. This replaces the brass-era asymmetric pattern (cream in light, dark charcoal in dark for the "glowing pill with dark text" aesthetic) — symmetric pairing matches the single-value-across-modes accent rule.

### Border tokens

**Rationale:** Borders are subtle by default. Bridgeable does not rely on hard borders to create structure — elevation and spacing do most of the structural work, and borders provide gentle definition where needed. In dark mode, borders can also serve as "warm metal edges" per the material-not-paint anchor.

| Token | Light mode | Dark mode |
|---|---|---|
| `--border-subtle` | `oklch(0.88 0.012 80) / 0.6` | `oklch(0.35 0.015 65) / 0.5` |
| `--border-base` | `oklch(0.82 0.015 78) / 0.8` | `oklch(0.42 0.018 68) / 0.7` |
| `--border-strong` | `oklch(0.70 0.020 76)` | `oklch(0.55 0.025 70)` |
| `--border-accent` | `rgba(156, 86, 64, 0.70)` | `rgba(156, 86, 64, 0.70)` |

*Notes:*
- Borders use alpha compositing (noted with `/ N`) by default so they adapt subtly to the surface they're on.
- `border-accent` is used sparingly — for focus states, selected items, and accent-edged emphasis. Single value across modes per the cross-mode accent rule (§2). Not a general-purpose border.
- `border-strong` is the only border that uses a solid color (no alpha). Used for table rules, divider lines that need to hold their weight.

### Shadow tokens

**Rationale:** Shadows are warm-tinted in both modes per Section 2's warm-hue family rule. Dark mode shadows persist (they don't disappear) per the "shadows persist in dark mode" principle, but they're lower contrast and warmer than light mode.

| Token | Light mode | Dark mode |
|---|---|---|
| `--shadow-color-subtle` | `oklch(0.40 0.045 78) / 0.06` | `oklch(0.11 0.020 65) / 0.35` |
| `--shadow-color-base` | `oklch(0.40 0.045 78) / 0.10` | `oklch(0.09 0.020 65) / 0.45` |
| `--shadow-color-strong` | `oklch(0.37 0.050 75) / 0.16` | `oklch(0.08 0.020 65) / 0.55` |
| `--shadow-highlight-top` | *not used* | `oklch(0.32 0.010 61) / 0.9` |

*Notes:*
- `shadow-highlight-top` is the top-edge highlight used on elevated surfaces in dark mode per Section 2's "material, not paint" anchor. It's a thin (1px) inset highlight that reads as reflected warm light. Not used in light mode.
- Shadow composition (blur, offset) is specified separately in Section 6.

### Card material treatment tokens (Aesthetic Arc Session 4.6 — mode-aware)

**Rationale:** Pre-Session-4.5, cards composed `bg-surface-elevated + shadow-level-1` and read as flat outlined panels rather than physical material. The four tokens below add the **edge highlights + edge shadows + ambient lift** layer that turns a card into a tactile object on a substrate. Section 11 Pattern 2 documents the composition recipe; these tokens carry the values.

**Session 4.5 → 4.6 calibration history.** Session 4.5 shipped these tokens single-value-across-modes per the architectural-color rule. Visual verification revealed the single-value approach failed against actual substrate: light mode top-edge highlight (`rgba(255,240,220,0.05)` warm-cream tint) is invisible on cream substrate by definition; light-mode `0.35` bottom-edge reads as a hard border on cream; ambient with `-4px` spread + `10px` blur is too tight to read as "lift"; dark-mode `0.35` bottom-edge is too subtle on charcoal; dark-mode `5%` top-edge is redundant with `shadow-level-1`'s existing `3px 90%` top highlight (`--shadow-highlight-top`). Session 4.6 makes these tokens **mode-aware** because they're *perceptual* tokens (they need different values to produce the same perceptual signal against different substrates), not *identity* tokens (like `--accent` which keep one value across modes per §2). The "same physical edge in either room" semantic is preserved by tuning values so each mode reads the edge consistently.

| Token | Light mode | Dark mode | Composition role |
|---|---|---|---|
| `--card-edge-highlight` | `rgba(255, 255, 255, 0.45)` | `transparent` | Top-edge 1px inset via `inset 0 1px 0 var(...)`. Light mode: visible white catch-light on cream (substrate L=0.965 + 45% white = perceptual lift). Dark mode: no-op — defers to `shadow-level-1`'s existing 3px top-edge highlight via `--shadow-highlight-top`. |
| `--card-edge-shadow` | `rgba(0, 0, 0, 0.20)` | `rgba(0, 0, 0, 0.50)` | Bottom-edge 1px inset via `inset 0 -1px 0 var(...)`. Light mode tuned softer to avoid hard-border read on cream; dark mode strengthened for visible bottom-edge cue on charcoal. |
| `--card-ambient-shadow` | `0 8px 20px -4px rgba(0, 0, 0, 0.18)` | `0 8px 24px -4px rgba(0, 0, 0, 0.45)` | Drop shadow with larger blur and less negative spread than Session 4.5 (which used `4px/10px/-4px` — too tight). Light mode lighter alpha for cream substrate; dark mode stronger for atmospheric halo against charcoal. |
| `--flag-press-shadow` | `rgba(0, 0, 0, 0.15)` | `rgba(0, 0, 0, 0.30)` | Right-of-flag 1px inset via `inset 1px 0 0 var(...)`. Pattern 3 left-edge flag pressed-in detail. Light mode lighter for cream; dark mode stronger for charcoal. |

*Notes:*
- The four compose alongside (not replacing) `--shadow-level-1`. A canonical card carries: edge highlight + edge shadow + ambient lift + level-1's tight ground + atmospheric halo (+ dark-mode top-edge highlight via `--shadow-highlight-top`).
- `--flag-press-shadow` is conditional on flag presence — `border-l-transparent` cards omit the press shadow (no flag → no press detail). Pattern 3 flag width canonical: 2px.
- **Why mode-aware here when accent tokens are single-value:** identity tokens (terracotta `--accent`, sage-green `--accent-confirmed`) carry the same hue/lightness across modes because they ARE the same color in either room. Perceptual-composition tokens (these four) carry the same *perceptual signal* across modes — but the values needed to produce that signal differ because cream-substrate vs charcoal-substrate respond to alpha values differently. The architectural-color rule binds identity tokens; perceptual tokens have a separate compatibility rule documented per-token.
- **Calibration history:** Session 4.5 single-value (failed visual verification); Session 4.6 mode-aware (current). Pre-Session-4.5 Tier-2 calibration shipped only `shadow-level-1` for card material — read as flat panel. Session 4.5 added the four tokens; Session 4.6 mode-tuned them per-substrate.

### Jewel-set inset ring token (Aesthetic Arc Session 4.5 + 4.7 strengthening)

**Rationale:** Pattern 3 second-channel status indicators (HoleDugBadge canonical) need a recessed ring that reads as physical jeweled inlay. Pre-Session-4.5 the inset shadow was inline arbitrary value `[inset_0_1px_2px_rgb(0_0_0/0.15)]` single value; promoted to mode-aware token per Pattern 3 doc-spec. **Session 4.7** strengthened both modes after visual verification: Session 4.5 values produced too subtle a recess when paired with status-*-muted badge backgrounds (only 0.04 OKLCH delta from card surface) — the badge looked like a colored chip, not a jeweled inlay. Session 4.7 darkens the badge fill to `--surface-base` (~0.12 OKLCH below card) AND strengthens the inset alphas. Together: visible recessed well with icon as inlay.

| Token | Light mode | Dark mode |
|---|---|---|
| `--shadow-jewel-inset` | `inset 0 1px 2px rgba(0, 0, 0, 0.25)` | `inset 0 1px 2px rgba(0, 0, 0, 0.50)` |

*Notes:*
- Dark-mode value strengthens to 0.50 because dark substrate compresses low-lightness deltas — Session 4.5's 0.30 paired with status-*-muted backgrounds was too subtle on charcoal.
- Single composition value (offset + blur don't change across modes; only alpha changes per substrate response).
- Applied via `box-shadow: var(--shadow-jewel-inset)` on the indicator's chip element. Pattern 3 reference implementation pairs this token with a badge background of `bg-surface-base` (substantially darker than card surface) — the bg darker fill + inset shadow together produce the well effect; either alone is too subtle.
- Calibration history: Session 4.5 single-value 0.15 (single mode) → mode-aware 0.15/0.30 → Session 4.7 strengthened to 0.25/0.50.

### Widget elevation tier tokens (Aesthetic Arc Session 4.7 + 4.8)

**Rationale:** Pre-Session-4.7, Pattern 1 tablet widgets (AncillaryPoolPin canonical) used `shadow-level-1` (the same elevation token as cards within the work surface). Visual verification confirmed widgets and cards appeared at similar elevation levels — but Pattern 1 + PLATFORM_INTERACTION_MODEL specify widgets float MORE than core/cards (they're summoned manipulable tablets ON TOP of operations, not equivalent to the work surface). Session 4.7 introduced the widget elevation tier; **Session 4.8 amplified** to make the hierarchy unmistakable.

**Calibration history.** Session 4.7 shipped single-shadow values (light `0 12px 28px -6px black-25%`, dark `0 12px 32px -6px black-55%`). Visual verification confirmed pin still read as "elevated card" not "tablet hovering." Session 4.8 introduces:

1. **Layered atmospheric shadow** — 3 layers per mode (inner tight halo + mid-distance lift + atmospheric haze) instead of single shadow. The layered composition reads as a tablet floating in atmospheric space, not as a card with stronger shadow.
2. **`translateY(-2px)` transform** via `--widget-tablet-transform` token — applied to the widget tablet outer element. Subtle physical offset combined with layered shadow creates genuine "summoned object hovering" register.

**Elevation hierarchy (bottom up):**
1. **Substrate** — page background, no shadow
2. **Core element** — kanban core, primary work surface, no widget-tier lift
3. **Cards within core** — DeliveryCard, AncillaryCard. `--card-ambient-shadow` (mid-tier, 8/20 light or 8/24 dark, alpha 0.18 / 0.45)
4. **Widgets** — AncillaryPoolPin, future floating tablets, summoned objects. `--widget-ambient-shadow` (higher-tier layered atmospheric shadow) + `--widget-tablet-transform` (translateY(-2px)) plus shadow-level-1's existing material edges, composed via `--shadow-widget-tablet`

| Token | Light mode | Dark mode | Composition role |
|---|---|---|---|
| `--widget-ambient-shadow` | `0 4px 12px -2px black-10%, 0 16px 32px -4px black-25%, 0 32px 56px -8px black-30%` | `0 4px 12px -2px black-30%, 0 16px 32px -4px black-55%, 0 32px 56px -8px black-65%` | Layered atmospheric shadow (3 layers) — inner tight halo + mid-distance lift + atmospheric haze |
| `--widget-tablet-transform` | `translateY(-2px)` | `translateY(-2px)` | Subtle physical lift offset; combined with layered shadow creates "summoned object hovering" register |
| `--shadow-widget-tablet` | `var(--shadow-level-1), var(--widget-ambient-shadow)` | (same — composes the mode-aware variants) | Composite token used by Pattern 1 tablets via `shadow-[var(--shadow-widget-tablet)]` |

*Notes:*
- Mode-aware per-substrate response (same discipline as `--card-ambient-shadow`): light mode lighter alphas for cream substrate; dark mode stronger alphas for charcoal atmospheric halo.
- `--shadow-widget-tablet` is a syntactic convenience — it composes shadow-level-1 (existing material edges + dark-mode top highlight) + the widget-ambient-shadow layers into a single token reference for clean Tailwind arbitrary-value usage.
- `--widget-tablet-transform` applied via inline `style={{ transform: "var(--widget-tablet-transform)" }}` on the widget outer element. AncillaryPoolPin doesn't itself drag — only its CONTENTS (PoolItem rows) drag via dnd-kit — so the static transform doesn't conflict with drag mechanics. Future widgets that DO drag will need to compose this transform into their drag-position transform string.
- Future floating widgets (drive-time matrix pins, staff availability pins, future Pulse cards) inherit `--shadow-widget-tablet` + `--widget-tablet-transform` via Pattern 1 tablet treatment composition.
- The card-tier ambient (`--card-ambient-shadow`) and widget-tier ambient (`--widget-ambient-shadow`) are separate tokens so cards within a widget would render at the card tier, NOT the widget tier — the hierarchy is by surface role, not by nesting.

### Accent tokens

**Rationale:** Deepened terracotta is the only locked accent. A supporting accent (potentially a muted cool note) is deferred per earlier scope decisions. Sections 2 and 3 are authored to accommodate a cool supporting accent in the future if needed; no current tokens depend on one existing.

| Token | Light mode | Dark mode |
|---|---|---|
| `--accent` | `oklch(0.46 0.10 39)` | `oklch(0.46 0.10 39)` |
| `--accent-hover` | `oklch(0.54 0.10 39)` | `oklch(0.54 0.10 39)` |
| `--accent-muted` | `rgba(156, 86, 64, 0.20)` | `rgba(156, 86, 64, 0.20)` |
| `--accent-subtle` | `rgba(156, 86, 64, 0.10)` | `rgba(156, 86, 64, 0.10)` |
| `--accent-confirmed` | `oklch(0.58 0.05 138)` | `oklch(0.58 0.05 138)` |

*Notes:*
- **Single value across modes.** Per Aesthetic Arc Session 2, `--accent` does not shift across light/dark — the architectural-color rule (§2 cross-mode rule). #9C5640 deepened terracotta reads as the same color in both rooms; the substrate around it changes, the accent itself does not.
- **Hover universally brightens.** `--accent-hover` is `#B46A4D` (~L 0.54) in both modes. The "lift signal" semantic replaces the brass-era asymmetric press-in (light) / glow (dark) pattern. Universal lift matches the Apple Pro era execution standard reference (Linear, Stripe, Pro apps universally use lift on hover).
- **No `--accent-active`.** The current "active state" semantic in Bridgeable is "this is the currently selected item" (DateBox active, nav active), implemented via the two-token pattern: `--accent-subtle` background + `--accent` border. Not "this button is being pressed right now" (momentary press feedback). If momentary press is needed later, introduce `--accent-active` then; reducing token surface area now prevents ambiguity.
- **Muted** (`rgba(156, 86, 64, 0.20)`) is the slightly more saturated wash for backgrounds that need to signal accent-adjacency without being accent itself (e.g., an accent-tinted badge background). Alpha allows it to compose with whatever surface it sits on.
- **Subtle** (`rgba(156, 86, 64, 0.10)`) is the barest accent tint, used for the canonical selected-item background and very quiet hover/active surfaces (e.g., the fill of a hover state on a menu item).
- **All variants lock the same hue (~39 oklch / red-orange terracotta family). No exceptions** — except `--accent-confirmed` (introduced Aesthetic Arc Session 4.5), which is a **distinct hue (~138 olive-green family)** intentionally — the "confirmed" token is the architectural counterpart to terracotta, not a terracotta variant. Hex equivalent `#7d9170`. Reads as "stamped/approved" mark on a document, calmer than `--status-success` (saturated alert-green at hue 135 / chroma 0.12+ used by Alert / StatusPill / Banner primitives). `--accent-confirmed` is scoped to DL §11 Pattern 3 first-channel left-edge flags ("confirmed" state); status-success continues to drive every other success-semantic surface. Single value across modes per the architectural-color rule (same discipline as `--accent`).

### Status tokens

**Rationale:** Status colors (error, warning, success, info) are derived per Section 2's "Deriving a new color" procedure. They must feel native to the platform's warm family — not bolted-on generic red/yellow/green/blue. Each status hue is chosen to be distinguishable from the others and from accent while sitting within the platform's overall warmth.

Derivation approach:
- **Error (red)** — hue in the warm-red family (20–30), distinct from accent (hue 39). Chroma moderate-high for urgency.
- **Warning (amber)** — hue adjacent to the warm-cream substrate range (60–65). Distinguishable from accent but clearly in the same warm family.
- **Success (green)** — hue in the warm-olive-green family (130–140), pulling slightly yellow rather than blue-green. This ties to the living-green garden anchor from the light-mode reference.
- **Info (blue-gray)** — hue in the muted-Mediterranean range (220–230), low chroma to stay restrained. This is also the place where the deferred "cool supporting accent" partially appears, as an informational cue rather than a structural accent.

| Token | Light mode | Dark mode |
|---|---|---|
| `--status-error` | `oklch(0.55 0.18 25)` | `oklch(0.68 0.17 25)` |
| `--status-error-muted` | `oklch(0.92 0.04 25)` | `oklch(0.22 0.07 25)` |
| `--status-warning` | `oklch(0.70 0.14 65)` | `oklch(0.76 0.14 65)` |
| `--status-warning-muted` | `oklch(0.94 0.04 65)` | `oklch(0.24 0.06 65)` |
| `--status-success` | `oklch(0.58 0.12 135)` | `oklch(0.70 0.13 135)` |
| `--status-success-muted` | `oklch(0.93 0.04 135)` | `oklch(0.22 0.05 135)` |
| `--status-info` | `oklch(0.55 0.08 225)` | `oklch(0.70 0.09 225)` |
| `--status-info-muted` | `oklch(0.93 0.03 225)` | `oklch(0.22 0.04 225)` |

*Notes:*
- Status `muted` variants are backgrounds for status callouts (the yellow tint behind a warning message). Status `base` is the foreground (border, icon, bold text).
- Warning is close to accent hue (65 vs 73) but meaningfully different. The 8° gap is enough that they don't confuse; use warning for *transient* state signals (form validation, inline warnings) and accent for *affordance* (actionable emphasis). They should not appear adjacent in the same component.
- Info chroma is noticeably lower than the others. This is deliberate — info is the coolest color in the system and needs restraint to avoid reading as out-of-place against the warm platform.
- Success hue (135) is yellow-green, not blue-green. This matches the olive/garden green of the light-mode reference and reads as organic rather than synthetic.
- **Aesthetic Arc Session 4 (M1) adjustment — dark-mode `status-*-muted` backgrounds.** Pre-Session-4 dark-mode muted lightness values were 0.28/0.30 with chroma 0.05–0.08. That placed `text-status-{X}` on `bg-status-{X}-muted` at 3.83–4.32:1 — below WCAG AA 4.5:1 for body text. Current values (L 0.22/0.24, chroma eased) clear 5.0–5.4:1. Visually aligns with Section 2 dark-mode anchor "concentrated warm light pools" — status callouts read as lamplight at low angle rather than a washed-out tinted rectangle.

### Full CSS variable list

The final CSS variables for implementation. Sonnet uses these exact names.

```css
:root {
  /* Surfaces */
  --surface-base: oklch(0.94 0.030 82);
  --surface-elevated: oklch(0.965 0.014 82);
  --surface-raised: oklch(0.985 0.010 82);
  --surface-sunken: oklch(0.91 0.020 82);

  /* Content */
  --content-strong: oklch(0.22 0.015 70);
  --content-base: oklch(0.30 0.015 70);
  --content-muted: oklch(0.48 0.014 70);
  --content-subtle: oklch(0.62 0.012 70);
  --content-on-accent: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.88 0.012 80 / 0.6);
  --border-base: oklch(0.82 0.015 78 / 0.8);
  --border-strong: oklch(0.70 0.020 76);
  --border-accent: rgba(156, 86, 64, 0.70);

  /* Shadows */
  --shadow-color-subtle: oklch(0.40 0.045 78 / 0.06);
  --shadow-color-base: oklch(0.40 0.045 78 / 0.10);
  --shadow-color-strong: oklch(0.37 0.050 75 / 0.16);

  /* Accent — deepened terracotta, single value across modes
     (Aesthetic Arc Session 2, April 2026 — see §2 cross-mode rule).
     `--accent-active` intentionally absent; selected-item state
     uses `--accent-subtle` background + `--accent` border. */
  --accent: oklch(0.46 0.10 39);
  --accent-hover: oklch(0.54 0.10 39);
  --accent-muted: rgba(156, 86, 64, 0.20);
  --accent-subtle: rgba(156, 86, 64, 0.10);

  /* Status */
  --status-error: oklch(0.55 0.18 25);
  --status-error-muted: oklch(0.92 0.04 25);
  --status-warning: oklch(0.70 0.14 65);
  --status-warning-muted: oklch(0.94 0.04 65);
  --status-success: oklch(0.58 0.12 135);
  --status-success-muted: oklch(0.93 0.04 135);
  --status-info: oklch(0.55 0.08 225);
  --status-info-muted: oklch(0.93 0.03 225);

  /* Focus ring alpha — default (Session 4, m2).
     Composed into the accent focus ring via
     `color-mix(in oklch, var(--accent) calc(var(--focus-ring-alpha) * 100%), transparent)`. */
  --focus-ring-alpha: 0.40;
}

[data-mode="dark"] {
  /* Surfaces — Tier-4 measurement-based correction (April 2026):
     calibrated to IMG_6085.jpg sampled values. Hue progresses with
     elevation (h=59→81→85) per §1 anchor 4 "Material, not paint" —
     this is the second material dimension the prior tokens missed.
     Tier-3's lightness bumps (L=0.22 / L=0.27) reverted to pre-
     Tier-3 values (L=0.20 / L=0.24) which match reference. */
  --surface-base: oklch(0.16 0.010 59);
  --surface-elevated: oklch(0.28 0.014 81);
  --surface-raised: oklch(0.32 0.016 85);
  --surface-sunken: oklch(0.13 0.010 55);

  /* Content — `--content-on-accent` flipped to LIGHT cream in dark mode
     (was dark charcoal pre-Session-2 for the brass-era "glowing pill
     with dark text" aesthetic). Terracotta at L=0.46 is dark enough
     that cream text clears WCAG AAA in both modes — symmetric pairing
     matches the single-value-across-modes accent rule. */
  --content-strong: oklch(0.96 0.012 80);
  --content-base: oklch(0.90 0.014 75);
  --content-muted: oklch(0.72 0.014 70);
  --content-subtle: oklch(0.55 0.012 68);
  --content-on-accent: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.35 0.015 65 / 0.5);
  --border-base: oklch(0.42 0.018 68 / 0.7);
  --border-strong: oklch(0.55 0.025 70);
  --border-accent: rgba(156, 86, 64, 0.70);

  /* Shadows — Tier-4 correction (April 2026):
     --shadow-highlight-top calibrated to reference measurement.
     Reference shows 3-pixel top-edge band at L≈0.30; value below
     matches the dimmer-per-pixel, wider band (see §6 Shadow
     specifications for the 3px inset width). */
  --shadow-color-subtle: oklch(0.11 0.020 65 / 0.35);
  --shadow-color-base: oklch(0.09 0.020 65 / 0.45);
  --shadow-color-strong: oklch(0.08 0.020 65 / 0.55);
  --shadow-highlight-top: oklch(0.32 0.010 61 / 0.9);

  /* Accent — single value across modes (same as light mode).
     Aesthetic Arc Session 2: brass retired, terracotta locked
     across both modes per the architectural-color rule. */
  --accent: oklch(0.46 0.10 39);
  --accent-hover: oklch(0.54 0.10 39);
  --accent-muted: rgba(156, 86, 64, 0.20);
  --accent-subtle: rgba(156, 86, 64, 0.10);

  /* Status (Session 4 M1: muted backgrounds tightened for WCAG AA) */
  --status-error: oklch(0.68 0.17 25);
  --status-error-muted: oklch(0.22 0.07 25);
  --status-warning: oklch(0.76 0.14 65);
  --status-warning-muted: oklch(0.24 0.06 65);
  --status-success: oklch(0.70 0.13 135);
  --status-success-muted: oklch(0.22 0.05 135);
  --status-info: oklch(0.70 0.09 225);
  --status-info-muted: oklch(0.22 0.04 225);

  /* Focus ring alpha — dark-mode override (Session 4, m2).
     0.40 → 0.48 lifts contrast on `--surface-raised` from
     ~3.00:1 (WCAG 2.4.7 edge) to ~3.5:1. */
  --focus-ring-alpha: 0.48;
}
```

### Verification note

Every value in the table above should pass Section 2's verification tests. Anyone auditing this section can:
1. Take any token
2. Look up its governing rule in Section 2
3. Confirm the oklch value falls inside the rule's range
4. Run the verification test (e.g., "place against pure white, does it read as cream?")

If any token fails, either the token is wrong or Section 2 is wrong. Both are fixable; silent drift is not.

## Section 4 — Typography

Typography carries as much mood as color. The wrong typeface on the right palette produces an interface that feels incoherent — the colors say "Mediterranean morning" and the letters say "generic SaaS." This section picks the typefaces and specifies how they're used.

### Typeface family

> **Aesthetic Arc Session 4 update (April 26, 2026).** The platform's typeface family migrated from **IBM Plex** to **Fraunces (display) + Geist (body) + Geist Mono (data)**. Rationale: the previous "single-family" Plex coherence prioritized unification over role-specific voice. Session 4's three-family approach gives each role the typeface that best carries its register: Fraunces serif as "engraving" for proper nouns + display, Geist as modern restrained sans for body + UI, Geist Mono as precision register for data. Sections below updated to reflect the new families; the rationale narrative threading "single-designer-voice" is retired in favor of role-specific voice. Migration shape: atomic swap, no transitional alias period. The 19 prior `font-plex-serif` utility uses became `font-display`; the 44 `font-plex-mono` uses became `font-mono`; the 55 `font-plex-sans` uses split between `font-sans` (default Geist) and `font-display` (Fraunces) per content semantics — proper nouns + display moments to Fraunces, body/labels/controls to Geist.

Bridgeable uses **three coordinated typefaces**, one per role:

- **Fraunces** — humanist serif. Used for: proper nouns (funeral home names, family names, decedent names), H1/H2 page headings, large display numerals (dashboard stats, agent card counts), card titles when they ARE proper nouns. Carries the "engraving" register — a name rendered in Fraunces has the weight of a name, not a form-field value.
- **Geist** — clean modern sans. Used for: body prose, labels, button text, controls, descriptions, secondary text. The default. Geist's restrained letterforms read as considered modern UI without the mechanical character of Plex; aligns with Apple Pro era (Layer 3) execution standard's "type meticulously chosen" discipline.
- **Geist Mono** — precision monospace. Used for: all numerals (times, counts, dates in compact form, reference numbers), eyebrow uppercase tracking, technical data values, code blocks, tabular alignments. The mono register is the platform's vocabulary layer for "this is data, this is precise." See Pattern 4 in Section 11.

**Rationale (post-migration):** Fraunces, Geist, and Geist Mono are coordinated by intent rather than by shared designer. Fraunces's humanist serif carries the gravitas-moment weight Plex Serif used to (proper nouns, display titles) but with sharper, more contemporary letterforms. Geist's modern restrained sans replaces Plex Sans's mechanical-but-warm character with cleaner, more Apple-Pro-era letterforms — better fit for the Layer 3 execution bar. Geist Mono replaces Plex Mono with a sibling face — same designer-system as Geist, so eyebrow + body + numerals all coordinate. The role-specific approach trades the "single designer's voice" coherence Plex offered for stronger role-fit per surface; the platform's shared design DNA carries through Section 0 (visual values) + Section 11 (treatment patterns) rather than through typeface family alone.

**Implementation:**
- **Fraunces** — `--font-fraunces`, exposed as `font-display` Tailwind utility. Variable font (weights 100–900). Used at 500 (medium) for proper-noun text in cards; 500–600 for display headings.
- **Geist** — `--font-geist`, exposed as `font-sans` Tailwind utility (the default; setting `--font-sans` to Geist makes any unprefixed text node resolve to Geist). Variable font (weights 100–900). Used at 400 / 500 / 600 per the existing weight discipline.
- **Geist Mono** — `--font-geist-mono`, exposed as `font-mono` Tailwind utility. Variable font (weights 100–900). Used at 400 for data, 500 for emphasized data. Tabular figures by default.
- **Loading:** Self-hosted via `@fontsource-variable/fraunces`, `@fontsource-variable/geist`, `@fontsource-variable/geist-mono`. Subset to Latin. Variable fonts ship a single file per family covering all weights. Preload not strictly required for variable fonts at our scale (~100KB combined gzipped); deferred to natural-touch refactor if FOUC surfaces.

**Legacy IBM Plex tokens retained for one-release grace.** `--font-plex-sans` / `--font-plex-serif` / `--font-plex-mono` continue to exist in tokens.css but are aliased to the new families:
- `--font-plex-sans` → `var(--font-geist)`
- `--font-plex-serif` → `var(--font-fraunces)`
- `--font-plex-mono` → `var(--font-geist-mono)`

Aliases prevent breakage during the migration window. Codebase sweep replaces all `font-plex-*` utility uses; aliases will retire when zero references remain (target: end of Aesthetic Arc).

### When to use each face

**Geist (sans)** is the default. Use it for everything unless a rule below specifies otherwise. Tailwind utility: `font-sans` (or unprefixed — the default font-family).

**Fraunces (display, serif)** is used for:
- **Proper nouns on operational cards.** Funeral home names, family names, decedent names, cemetery names *when proper*. Renders the proper noun as an "engraving" — different from surrounding data, weighted with the noun's significance. See Section 11 Pattern 2.
- **H1 / H2 page headings.** Page-level titles on hub surfaces, settings pages, focus surfaces. The serif treatment marks the page-level anchor; the rest of the page is Geist body.
- **Day-switcher labels** (Funeral Scheduling Focus). The day label "Today, April 25" carries the H3 weight and the popover-trigger semantics; Fraunces gives it presence at the center of the switcher.
- **Card titles when they ARE proper nouns** — see Pattern 2.
- **Large display numerals** — dashboard stats, agent card counts, hero numbers. The `text-display` and `text-h1` numerals at scale read with Fraunces's serif character; this is the one mono-rule exception (large display numerals favor display serif over mono per established hub patterns).
- **Signature moments on marketing and portal surfaces** (welcome messages, gratitude language).
- **Quoted language.** Pull-quotes, testimonials, memorial language.

Tailwind utility: `font-display`.

Fraunces is wrong for:
- Dashboard data (that's mono — see Pattern 4). Times, counts, reference numbers stay mono regardless of placement.
- Navigation, buttons, form labels, controls (all stay sans).
- Long-form body text (Fraunces is a display serif; extended reading should stay in Geist sans).
- Marketing headlines selling a product (those go to body sans + bold weight rather than serif).

**Geist Mono** is used for structured data + the precision register:
- **All numerals** — times (`15:00`, `ETA 17:00`), counts (`3`, `+1`), dates in compact form (`Apr 25`, `Apr 27`), reference numbers (`FC-2026-0001`), migration names (`fh_02_cross_tenant`).
- **Eyebrow uppercase tracking** — `text-micro uppercase tracking-wider` labels. Even though eyebrows are text not numbers, the precision register fits — eyebrows signal "this is a labeled section, here's what it is."
- **Code blocks, command-bar input, technical literal system language.**
- **Columns of numbers in tables** where decimal alignment matters (tabular figures).

Tailwind utility: `font-mono`.

Mono is wrong for:
- Regular numbers in prose ("there are three drivers" — the number is part of the sentence, font-sans).
- Phone numbers, addresses, long-form dates ("April 25, 2026") — these read more naturally in sans.
- Decorative use where the typewriter feel is aesthetic rather than functional.

### Type scale

The scale is modular, based on a 1.25 ratio (major third). Every size is expressed in rem with a 16px root. Sonnet implements sizes via Tailwind's `text-{size}` classes; the classes below map to the design language names.

| Token | Size (rem) | Size (px at 16px root) | Line height | Use |
|---|---|---|---|---|
| `text-display-lg` | 3.052 | 48.83 | 1.1 | Signature display moments only (hero surfaces, major page titles on marketing) |
| `text-display` | 2.441 | 39.06 | 1.15 | Display serif page titles on case detail, vault order, signature pages |
| `text-h1` | 1.953 | 31.25 | 1.2 | Primary page titles |
| `text-h2` | 1.563 | 25.00 | 1.25 | Section headings |
| `text-h3` | 1.25 | 20.00 | 1.3 | Subsection headings, card titles |
| `text-h4` | 1.125 | 18.00 | 1.35 | Small section labels, prominent list items |
| `text-body` | 1.0 | 16.00 | 1.55 | Default body text |
| `text-body-sm` | 0.875 | 14.00 | 1.5 | Secondary text, compact layouts, form helper text |
| `text-caption` | 0.75 | 12.00 | 1.45 | Metadata, timestamps, tertiary labels |
| `text-micro` | 0.6875 | 11.00 | 1.4 | Floor size — badge labels, very small indicators |

**Rationale:**
- The 1.25 ratio is more conservative than the 1.333 "perfect fourth" ratio common in display-heavy design. Conservative ratio suits Bridgeable because most content is utility-oriented; dramatic size contrast would fight the deliberate-restraint meta-anchor.
- Line heights decrease as size increases, per normal typographic practice. Body text at 1.55 gives the generous breathing room specified in Section 1, anchor 5 (light mode) without becoming loose.
- `text-micro` is a floor. Nothing smaller. If something needs to be smaller than 11px, the information architecture is wrong — you're trying to cram something into a space that's too small.

### Weight discipline

Bridgeable uses **three weights only**: Regular (400), Medium (500), Semibold (600). No bold. No light. Hierarchy is created by size, color, and size-weight pairing — not by piling on weights.

**Weight rules:**
- **Regular (400)** — body text, UI labels, form input values, navigation items, secondary text, captions.
- **Medium (500)** — headings (H1 through H4), primary action labels on buttons, active navigation, table column headers, card titles, emphasized inline text.
- **Semibold (600)** — reserved for critical emphasis only. Primary page titles on high-stakes pages (when paired with Plex Serif Semibold), accent buttons that represent the primary action on a screen, status labels that require attention (errors, warnings in active state).

**Rationale:** Fewer weights produces more consistent hierarchy. Three weights is enough to create clear emphasis without inviting weight-soup (the UI problem where every element has been bolded to "emphasize" it, producing a page where nothing emphasizes anything). The discipline is hard but the payoff is a platform that reads as considered rather than urgent.

**Italic usage:** Italics are allowed but used sparingly. Correct uses: titles of works, foreign-language terms, genuine emphasis inline (rare). Wrong uses: decorative emphasis, UI labels, button text, headings. Italic is a semantic tool, not a style tool.

### Size-weight pairings

The type scale pairs with weights in specific combinations. Deviation from these pairings requires explicit design justification.

| Role | Size token | Face | Weight | Notes |
|---|---|---|---|---|
| Display page title | `text-display` | Fraunces (`font-display`) | 500 | Case detail, vault order, signature pages |
| Primary page title | `text-h1` | Fraunces (`font-display`) | 500 | Standard page titles |
| Section heading | `text-h2` | Fraunces (`font-display`) | 500 | Section breaks within a page |
| Subsection heading | `text-h3` | Fraunces (`font-display`) | 500 | Card titles, form section headers, day-switcher label |
| Compact heading | `text-h4` | Geist (`font-sans`) | 500 | Small headers, labels, list item titles |
| Proper noun on card | `text-body-sm` | Fraunces (`font-display`) | 500 | Funeral home / family / decedent names — the "engraving" treatment per Pattern 2 |
| Body default | `text-body` | Geist (`font-sans`) | 400 | Paragraphs, descriptions, most content |
| Body emphasis | `text-body` | Geist (`font-sans`) | 500 | Emphasized inline text (use sparingly) |
| Body secondary | `text-body-sm` | Geist (`font-sans`) | 400 | Helper text, metadata in body context |
| UI label | `text-body-sm` | Geist (`font-sans`) | 500 | Form labels, button text, navigation |
| Primary action button | `text-body-sm` | Geist (`font-sans`) | 600 | Accent buttons representing the primary screen action |
| Caption | `text-caption` | Geist (`font-sans`) | 400 | Timestamps in prose, author attribution |
| Caption emphasis | `text-caption` | Geist (`font-sans`) | 500 | Metadata requiring attention |
| Data — identifier | varies | Geist Mono (`font-mono`) | 400 | Case numbers, IDs, migration names |
| Data — time | `text-body-sm` or `text-caption` | Geist Mono (`font-mono`) | 400 | Times, ETAs, durations |
| Data — count | varies | Geist Mono (`font-mono`) | 400 | Counts on chips, badge numerals |
| Data — date compact | `text-caption` or `text-[0.8125rem]` | Geist Mono (`font-mono`) | 400 | Date boxes (Apr 25), tabular date strings |
| Data — code | `text-body-sm` | Geist Mono (`font-mono`) | 400 | Code blocks, command-bar input |
| Eyebrow uppercase | `text-micro` | Geist Mono (`font-mono`) | 400–500 | Section labels (`SCHEDULING`, `ANCILLARY POOL`); precision register applies to text labels too per Pattern 4 |

### Paragraph rules

**Line length:** Body text wraps at **62–72 characters per line** as a comfortable reading measure. Enforce with a max-width around `34rem` (545px at 16px root). Wider measures produce reading strain; narrower measures produce rag that looks nervous.

**Line height:** Body text uses 1.55. Captions use 1.45. Headings use 1.2–1.35 per the scale above. Deviation requires justification.

**Paragraph spacing:** Between paragraphs, use `margin-bottom` equal to the line height — roughly 1.55em for body text. Do not use double line breaks or larger gaps; the visual rhythm should feel like continued thought, not "new section."

**Letter spacing (tracking):** Plex Sans does not need tracking adjustment at most sizes. Exceptions:
- Micro text (11px) — add `+0.01em` tracking to improve legibility at small sizes.
- All-caps text — add `+0.05em` tracking (all-caps always needs more tracking). Use sparingly; all-caps is not a Bridgeable pattern for body content, only for very specific small labels (e.g., section eyebrows).

### Numerals

Plex Sans ships with both proportional and tabular figures. Use:
- **Proportional figures** in running text (most uses).
- **Tabular figures** in tables, data columns, financial displays, anywhere numbers align vertically.

CSS: `font-variant-numeric: tabular-nums` for the tabular case.

Plex Mono is inherently tabular — all characters are fixed-width — so numeric alignment is automatic in mono contexts.

### Text color

Text colors are defined in Section 3 (`content-strong`, `content-base`, `content-muted`, `content-subtle`, `content-on-accent`). Typography does not redefine them; it specifies *when* each is used.

**Content-strong** — headings, display text, primary page titles, critical emphasis. The darkest content color in each mode.

**Content-base** — default body text. Used for the bulk of reading content. Meets WCAG AAA against `surface-base`.

**Content-muted** — secondary information: metadata, helper text, captions, less-important labels. Still legible but visually recessed.

**Content-subtle** — tertiary information: placeholder text, disabled state, timestamps in de-emphasized contexts, informational background.

**Content-on-accent** — text rendered *on* accent surfaces (buttons, accent-filled badges). Never used for text rendered on any other surface.

### Dark-mode typography adjustments

Per Section 2's warm-family asymmetry, text colors shift hue across modes (75 in light, 80 in dark for strong text). Typography itself — size, weight, line height, face — does not change between modes. One exception:

**Font smoothing:** In dark mode, enable `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale`. This reduces the perceived weight of light text on dark backgrounds, which otherwise reads too bold because of the eye's tendency to flare bright text into surrounding dark. Without this, dark-mode text can feel like it's wearing more weight than it should.

In light mode, leave font smoothing at browser default (subpixel antialiasing). This preserves sharpness at small sizes.

### Anti-patterns specific to typography

- **Using Plex Serif for body text or form labels.** It's a display face. Extended reading in a display serif is fatiguing and signals "trying hard."
- **Using Plex Mono for regular numbers.** Prices in running prose, dates in sentences, and percentages in body text should stay in Plex Sans. Mono is for *alignment-requiring* data.
- **Piling on weight for emphasis.** A semibold heading followed by a semibold subhead followed by semibold emphasis within body text is weight-soup. Pick one level of emphasis per visual region.
- **All-caps body text.** All-caps is for tiny labels (eyebrows, section tags), never for paragraphs or headings longer than a few words.
- **Mixing non-Plex fonts.** No exceptions. Adding a third font family breaks the single-voice principle and produces incoherence that takes real work to notice but real time to fix.
- **Italic for decorative emphasis.** Italics carry semantic meaning (titles of works, foreign terms, genuine emphasis). Decorative italic reads as trying hard and usually just weakens the emphasis it's trying to create.

## Section 5 — Spacing & Layout

Spacing carries the breathing room anchor from Section 1. Layout carries the structural decisions that determine how content is arranged on screen. Both are mostly mechanical once the base unit and scale are set — but the mechanical rules have to be explicit, because spacing inconsistency is the single easiest way for a system to drift into incoherence.

### Base unit

The atomic spacing value is **4px**. Every spacing, sizing, and layout value in the system is a multiple of 4.

**Rationale:** 4px gives enough granularity for dense data views (case lists, scheduling boards, tables) where the difference between 8px and 12px row gaps matters, while remaining disciplined enough that the scale doesn't become chaotic. 8px would force coarser choices that are wrong for dense content; 2px or 1px would invite arbitrary values. 4px is the standard default in modern systems (matches Tailwind's default scale) and is enough granularity without license.

**Implementation:**
- Every spacing, padding, margin, gap, sizing token is a multiple of 4px.
- Tailwind's default spacing scale is used directly: `p-1` (4px), `p-2` (8px), `p-3` (12px), `p-4` (16px), `p-5` (20px), `p-6` (24px), `p-8` (32px), `p-10` (40px), `p-12` (48px), `p-16` (64px), `p-20` (80px), `p-24` (96px).
- Non-multiples are forbidden. A developer needing 15px has mis-specified; the right answer is 12 or 16.

### Spacing scale

The system uses a named scale keyed to semantic purpose, not just to raw pixel values. Sonnet picks from the scale by purpose, not by guessing pixel values.

| Token | Value | Purpose |
|---|---|---|
| `space-0` | 0 | No spacing. Explicit zero. |
| `space-0.5` | 2px | Hairline. Almost never used; reserved for micro-adjustments. |
| `space-1` | 4px | Tight spacing — icon-to-label gaps, tightly-coupled elements. |
| `space-2` | 8px | Close spacing — related items within a component, form field gaps in dense forms. |
| `space-3` | 12px | Compact spacing — secondary padding, row gaps in dense tables. |
| `space-4` | 16px | **Default component padding.** The base unit for most UI padding. |
| `space-5` | 20px | Comfortable spacing — padding inside cards, gaps between form fields in standard forms. |
| `space-6` | 24px | Generous component spacing — padding inside larger cards, vertical rhythm between paragraphs. |
| `space-8` | 32px | Section spacing — gap between related sections within a page. |
| `space-10` | 40px | Region spacing — gap between distinct content regions. |
| `space-12` | 48px | Major section spacing — gap between major page sections. |
| `space-16` | 64px | Hero spacing — top/bottom padding on major page-top regions. |
| `space-20` | 80px | Rare — used for hero surfaces on marketing pages. |
| `space-24` | 96px | Rare — reserved for signature moments on external-facing pages. |

**The density-default bias:** Spacing defaults favor the generous side of the scale. A new card's default padding is `space-5` (20px), not `space-4` (16px). A new page's default region spacing is `space-10` (40px), not `space-8` (32px). This encodes the "generous breathing room" anchor from Section 1 by default; tightening requires deliberate choice.

**Dense overrides:** Dense views (data tables, scheduling boards, yard displays, case lists with many rows) use an explicit tighter scale:
- Row padding: `space-2` or `space-3` instead of `space-4`.
- Inter-row gaps: `space-1` or `space-2`.
- Card padding in dense contexts: `space-4` instead of `space-5` or `space-6`.

Dense overrides are compressions of the same scale — they do not introduce new values. A dense row padded at 12px is still on the scale; a dense row padded at 14px is a violation.

**Verification test for any component:** Does the spacing feel deliberate, or does it feel like someone picked whatever looked "about right"? The test is whether every padding, margin, and gap in the component maps to a named scale value. If a spacing value is off-scale, it's wrong, even if it looks correct.

### Component padding conventions

These are the default paddings for common component types. They establish the system's rhythm.

| Component | Default padding | Dense variant |
|---|---|---|
| Button | `py-2.5 px-5` (10px / 20px) | `py-2 px-3` (8px / 12px) |
| Text input | `py-2.5 px-4` (10px / 16px) | `py-2 px-3` (8px / 12px) |
| Card | `p-6` (24px) | `p-4` (16px) |
| Hero card (e.g., case detail) | `p-8` or `p-10` (32px or 40px) | *not applicable* |
| Modal | `p-6` (24px) | `p-4` (16px) |
| Table cell | `py-3 px-4` (12px / 16px) | `py-2 px-3` (8px / 12px) |
| Table header cell | `py-2.5 px-4` (10px / 16px) | `py-2 px-3` (8px / 12px) |
| List item | `py-3 px-4` (12px / 16px) | `py-2 px-3` (8px / 12px) |
| Navigation item | `py-2.5 px-3` (10px / 12px) | — |
| Page container | `p-8` or `p-10` (32px or 40px) | `p-4` or `p-6` (16px or 24px) |

Button note: the 10/20 padding produces a button that feels substantial rather than squeezed. Buttons too-small are a common SaaS anti-pattern; Bridgeable's buttons feel like they were placed deliberately, which matches the meta-anchor.

### Layout approach: flexible with max-widths

Bridgeable does not use a global column grid. Pages use content-appropriate max-widths. Components that need internal grids (dashboards with resizable widgets) define their own — at the component level, not the page level.

**Rationale:** A global 12-column grid is the right tool for marketing and editorial layouts, where content flows within predetermined column boundaries. It is the wrong tool for application UI, where content dictates the layout — a case detail page, a scheduling board, and a command-bar overlay have nothing in common structurally, and forcing them into a shared 12-column grid produces rigid layouts that fight the content. Bridgeable is primarily application UI, so the default is flexible layout with max-widths. Dashboards get their own internal grid because drag-to-resize widgets require a column substrate, but that is a dashboard-component concern, not a page-layout concern. This distinction must be explicit because design systems routinely conflate the two.

**Page-level layout:**
- Pages have a single primary content container with a max-width appropriate to the content.
- The container is centered horizontally with even left/right padding (`p-8` or `p-10` typical).
- Navigation (top bar, side bar) sits outside the content container and spans the viewport.
- No global column grid. Each page decides its own structure.

### Max-width tokens

Max-width tokens define the common page widths. Sonnet picks a token by content type, not by guessing pixel widths.

| Token | Value | Use |
|---|---|---|
| `max-w-reading` | 34rem (544px) | Reading content — body prose, long-form text, articles. Matches the 62–72 character reading measure from Section 4. |
| `max-w-form` | 40rem (640px) | Single-column forms — case creation, vault order entry, contact forms. |
| `max-w-content` | 56rem (896px) | Standard content pages — case detail, order detail, most app pages with mixed content. |
| `max-w-wide` | 72rem (1152px) | Wide content pages — pages with multiple content regions side-by-side. |
| `max-w-dashboard` | 96rem (1536px) | Dashboard and data-dense views — hubs, scheduling boards, list views. |
| `max-w-full` | 100% | Full-viewport pages — yard display, plant floor view, anything that consumes available space. |

**Default:** If no max-width token is specified for a page, `max-w-content` is the default.

**Selection logic for Sonnet:**
- Long-form prose → `max-w-reading`
- Single-column form with a handful of fields → `max-w-form`
- Case detail, order detail, standard mixed-content page → `max-w-content`
- Page with a primary region plus a secondary sidebar → `max-w-wide`
- Dashboard, hub, scheduling board, data-dense list → `max-w-dashboard`
- Plant floor, yard display, kiosk → `max-w-full`

### Dashboards — internal 12-column widget grid

Dashboards are the one place a column grid exists in Bridgeable, and it is strictly a **component-level** concern: the widget substrate inside a dashboard container. It is not a page layout grid.

**Rule:** Dashboard widgets sit in a 12-column internal grid that supports drag-to-resize widget sizing. Each widget declares a column span (1–12) and a row span (1–N). The grid exists to enable resize and reflow, not to govern page layout.

**Rationale:** Drag-to-resize widgets require a column substrate because users need snap targets — continuous-pixel resizing produces unusable jitter. A 12-column grid provides enough granularity that widgets can be sized meaningfully (full-width = 12, half = 6, third = 4, quarter = 3) without creating an infinite number of layout permutations. This is a Workflow Arc commitment and is scoped to dashboard widgets only.

**Implementation:**
- Dashboard containers define `grid-template-columns: repeat(12, minmax(0, 1fr))` with `gap: space-4` (16px) between widgets.
- Widgets specify `grid-column: span N` and `grid-row: span M`.
- The grid is inside the dashboard container. The dashboard container itself sits inside a page layout that uses a max-width per the table above (typically `max-w-dashboard`).
- Widgets may contain their own internal layouts — lists, tables, charts, mini-forms — and those internal layouts do not participate in the dashboard grid.

**Non-dashboard pages:** Do not use a 12-column grid. Do not add `grid-template-columns: repeat(12, ...)` to non-dashboard layouts "for consistency." The consistency is across dashboards, not across all pages.

### Vertical rhythm

Spacing between stacked content follows predictable vertical rhythm.

- **Paragraph-to-paragraph within prose:** `space-4` (16px) — roughly one line of body text, producing "continued thought" rhythm.
- **Subsection heading to body content:** `space-3` (12px) — tight, because the heading and the content it introduces belong together.
- **Body content to next subsection heading:** `space-6` (24px) — generous, because the transition is a new subsection.
- **Section heading to body content:** `space-4` (16px).
- **Section to next section:** `space-10` (40px).
- **Major region to next major region:** `space-12` (48px) or `space-16` (64px).

The asymmetric rhythm (tight below headings, generous above them) is important — it visually associates headings with the content they introduce rather than treating the heading as equidistant between its content and the content above.

### Responsive behavior

Bridgeable is primarily a desktop-first application. Mobile responsiveness is supported for specific use cases (family portals, mobile-dispatch views for plant operators, driver apps) but most admin UI assumes a desktop viewport.

**Breakpoints:**
- `sm`: 640px — phone landscape, small tablet
- `md`: 768px — tablet portrait
- `lg`: 1024px — tablet landscape, small laptop
- `xl`: 1280px — standard laptop
- `2xl`: 1536px — large desktop

**Responsive spacing behavior:**
- Below `md` (768px), page container padding compresses from `p-8` / `p-10` to `p-4` / `p-6`.
- Below `md`, dense views compress further into their dense variants.
- Card padding compresses one step in the scale (space-6 → space-4) below `md`.
- Max-widths do not change; smaller viewports simply hit the viewport edge with appropriate padding.

Mobile is explicitly scoped: the family portal (public-facing mobile), the plant operator mobile dispatch, and the driver app. All other Bridgeable UI may degrade gracefully on mobile but is not designed for it. A user who opens the admin dashboard on their phone gets a readable but unoptimized experience; this is intentional, not a failure.

### Anti-patterns

- **Using arbitrary spacing values** (13px, 14px, 18px, etc). If the value is not on the scale, it is wrong.
- **Introducing a global 12-column grid** for non-dashboard pages. The 12-column grid is a dashboard widget substrate; bringing it to page layout rigidifies UI that should be content-driven.
- **Packing dense views without using the dense scale.** Dense views use smaller but still on-scale values. "Just tighten the padding by a couple px" produces off-scale values.
- **Inconsistent page-to-page max-widths** for similar content types. If two pages show case details, they use the same max-width. Drift produces platforms that feel inconsistent even when individual pages look fine.
- **Heroic hero sections.** Pages starting with 160px of empty vertical space before any content. The generous-default bias applies within the scale; `space-24` (96px) is the ceiling for rare signature moments, not the default.

## Section 6 — Surface and Behavior

This section specifies how surfaces express physical presence (elevation, shadows, borders, material treatments) and how they respond to interaction (motion, timing, easing). Surface and behavior are grouped because they together create "how things feel physically" — separating them into different sections would scatter the co-creators of that feel.

The color values used here are specified in Section 3; this section specifies how they're *applied* — the geometry, the composition, the timing.

### Elevation system

Bridgeable uses four levels of elevation. Elevation communicates depth and hierarchy: what's primary, what's lifted, what's recessed.

| Level | Name | Use |
|---|---|---|
| 0 | Base | Page background, default surface. Everything starts here. |
| 1 | Elevated | Cards, panels, grouped content. The default "lifted" level. |
| 2 | Raised | Modals, dropdown menus, popovers. One level above the surrounding UI. |
| 3 | Floating | Command bar, toasts, tooltips. Temporary overlays that sit above everything. |

A level-1 card on a level-0 page is the default case. A level-2 modal over a level-1 card means the modal reads as "above the page." A level-3 floating element sits above all other levels.

**Rule:** Elevation is monotonic within a visible region. A level-1 card should not contain a level-2 element (except modals/popovers triggered from within it). Mixing elevation levels inside the same visual region produces incoherent depth perception.

### Shadow specifications

Shadows are the primary mechanism for communicating elevation in light mode and a co-mechanism (with surface lightness and top-edge highlights) in dark mode. Per Section 2, all shadow colors are warm-tinted.

**Light mode shadows:**

| Level | Shadow composition |
|---|---|
| 0 (base) | *no shadow* |
| 1 (elevated) | `0 2px 8px var(--shadow-color-base)` |
| 2 (raised) | `0 8px 24px var(--shadow-color-base), 0 2px 6px var(--shadow-color-subtle)` |
| 3 (floating) | `0 16px 40px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base)` |

**Dark mode shadows (three-layer composition — finalized in Tier-4, April 2026):**

| Level | Shadow composition |
|---|---|
| 0 (base) | *no shadow* |
| 1 (elevated) | `0 1px 3px var(--shadow-color-strong), 0 4px 16px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top)` |
| 2 (raised) | `0 2px 4px var(--shadow-color-strong), 0 12px 32px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top)` |
| 3 (floating) | `0 3px 6px var(--shadow-color-strong), 0 24px 56px var(--shadow-color-strong), 0 8px 20px var(--shadow-color-strong), inset 0 3px 0 var(--shadow-highlight-top)` |

**Notes on the composition:**

- Dark-mode shadows are larger and softer than light-mode shadows — shadows in low light naturally diffuse more. The blur is roughly 2x the light-mode equivalent at each level.
- **Dark mode uses a three-layer composition for every elevation level** (tight grounding shadow + soft atmospheric halo + 3px inset top-edge highlight). The tight grounding shadow roots the element on the page surface. The soft halo provides atmospheric depth. The inset highlight catches implied lamplight on the top edge. Three layers are necessary because low-lightness surface deltas are perceptually compressed in dark mode — the warm base color alone doesn't carry enough elevation signal.
- Light-mode shadows use a one-shadow composition at level 1 and a two-shadow composition at levels 2–3. Material presence in light mode comes from the warm base color itself and the shadow warmth, not from explicit reflection + grounding.
- Dark-mode shadows include a **3px** `inset 0 3px 0` top-edge highlight using `--shadow-highlight-top` (`oklch(0.32 0.010 61 / 0.9)`). The 3px width is measurement-calibrated (reference IMG_6085.jpg shows a 3-pixel highlight band at L≈0.30 — a wider dimmer band reads as a focused light pool catching the top edge, a 1-pixel hairline does not). This is the "material, not paint" anchor (§1 dark-mode anchor 4) expressed concretely: elevated surfaces catch implied lamplight on their top edge. The highlight reads as focused light caught on a warm surface, not as a border outline.
- **Reconciliation history (April 2026):** pre-Tier-2, dark-mode shadows used a simpler two-layer composition (soft halo + inset highlight only) with L=0.42 α=0.45 highlight. Live rendering read less-distinct than the approved reference. Tier 2 added tight grounding shadows + strengthened the highlight to L=0.48 α=0.65, AND inferred from §1 anchor 4 prose that a canonical perimeter border on the Card primitive would help. Tier 3 further bumped dark-mode surface lightness. User visual verification after Tier 3 still didn't match the reference. Tier 4 sampled the reference directly via PIL (`docs/design-references/IMG_6085.jpg`) — a UI mockup, not the mood anchor — and calibrated tokens to it. **Tier 5** then sampled the external mood anchors (`design-ref-dark.png` cocktail lounge + `design-ref-light.png` Mediterranean garden) per the §1 calibration chain, and corrected three axes Tier 4 had left wrong:
    - **Dark elevated surface lightness** lifted L=0.20 → 0.28 (Tier 4 sat in walnut grain-dark; Tier 5 moved to walnut catching-light range).
    - **Dark raised surface lightness** lifted L=0.24 → 0.32 proportionally.
    - **Light base chroma** increased 0.018 → 0.030 (photo-calibrated linen tablecloth warmth).
    - **Shadow-color tokens** (all three, both modes) lifted L + doubled C + hue-shifted 3-5° warmer — photo shadows are warmer and softer than prior tokens composited.
  Tier-4 hue progression (dark mode h=59→81→85) was directionally correct and retained. Tier-2 three-layer shadow composition (tight ground + soft halo + 3px inset highlight) was architecturally correct and retained; only the shadow-color and highlight parameters changed.
- **Learning (canonicalized in CLAUDE.md + §10 anti-pattern):** when a canonical reference exists in `docs/design-references/`, sample it directly via PIL before inferring tuning values from prose anchors. §1 "images win over prose" applies to diagnosis as well as design authority. **The reference must be EXTERNAL** to the implementation chain (a photograph, not a UI mockup that was itself generated against the current tokens) — sampling a downstream artifact creates a circular calibration loop (§10). Tiers 2–3 inferred from prose alone and accumulated drift. Tier 4 measured against a UI mockup and closed a circular loop. Tier 5 measured against the external mood photograph and corrected to the actual anchor.

### Border treatment

Borders in Bridgeable are subtle by default. Structural hierarchy comes from elevation and spacing, not from hard borders. Borders provide definition where needed without dominating.

**Default border usage:**
- Surfaces use `--border-subtle` when a border is needed at all.
- Interactive elements (inputs, dropdowns) use `--border-base` for visible definition.
- `--border-strong` is reserved for content that needs to hold its weight (table column rules, section dividers that carry real structural meaning).
- `--border-accent` is used for focus states and selected states only. Not a general-purpose border.

**Card perimeter: no border.**
Cards in this platform do not carry a discrete perimeter border. Card edges emerge from the composition of (a) **surface lightness + hue lift** (`--surface-elevated` at the warmer-amber hue per §3 dark-mode progression), (b) **shadow halo** (the soft atmospheric shadow that darkens the page surface just outside the card), and (c) **top-edge highlight** in dark mode (the 3px inset catching implied lamplight on the top edge). This three-mechanism stack delivers the "material, not paint" anchor (§1 dark-mode anchor 4) without the line-drawn outline that a perimeter border would imply. A painted outline suggests "this is a drawn shape on a surface"; the composition suggests "this is a material object sitting on another surface."

The canonical reference (`docs/design-references/IMG_6085.jpg` dark, `IMG_6084.jpg` light) shows no visible perimeter border pixel on the card — edge transitions are shadow-halo-mediated, not border-mediated.

**Reconciliation history (April 2026):** Tier-2 (inference-based) added `border border-border-subtle` to the Card primitive, reading §1 anchor 4 prose to mean "apply all three cues including hairline border." Tier-4 (measurement-based) sampled the reference directly and found no perimeter border pixel. Border addition was reverted in Tier 4 for both modes (light and dark).

**Overlay perimeter: no border.**
Dialogs, popovers, dropdown menus, and slide-overs do not carry a perimeter border either. Same rationale as cards: the shadow + surface composition carries the elevation signal; a border would over-specify.

**Where borders DO apply:**
- **Inputs, textareas, select triggers**: need a definite interactable-edge signal. Use `--border-base` (solid, visible); transitions to `--border-accent` on focus.
- **Table column/row rules**: structural dividers inside a table. Use `--border-subtle` for light rules, `--border-base` for column separators that need weight.
- **Focus indicators**: accent focus rings via the `.focus-ring-accent` utility (separate from border; uses `box-shadow` ring composition per Focus states section).
- **Explicit status-bordered callouts**: Alert / StatusPill / Badge status variants may use `border-status-*` colors as part of their status-family expression. These are component-specific, not a general surface-edge rule.
- **Section dividers inside cards**: `border-t border-border-subtle` on CardFooter separates the footer zone from the card body. This is an INTERNAL divider (one line inside a surface), not a perimeter outline.

**What NOT to add borders to:**
- Page backgrounds (the page IS the surface, not an element on a surface).
- Card perimeters (canonical rule above).
- Overlay perimeters (canonical rule above).
- Row items in lists — rely on row padding + horizontal divider `border-b border-border-subtle` where rules are needed.
- Badge/pill primitives — they use `bg-*-muted` color fill; adding a border would conflict with the pill shape's visual weight.
- Buttons — the button has its own chrome (background + text color + shadow on hover). A perimeter border on accent primary would be visually redundant.

**Border radius scale:**

| Token | Value | Use |
|---|---|---|
| `radius-none` | 0 | Flush elements, edge-to-edge content. |
| `radius-sm` | 4px | Badges, small pills, compact inline elements. |
| `radius-base` | 6px | Buttons, inputs, compact cards. **Default.** |
| `radius-md` | 8px | Standard cards, dropdown menus, popovers. |
| `radius-lg` | 12px | Large cards, modals, signature surfaces. |
| `radius-xl` | 16px | Hero surfaces, marketing cards. |
| `radius-full` | 9999px | Circular elements, fully-rounded pills. |

**Rationale:** The scale is conservative. Aggressive rounding (20px+) reads as playful or consumer-app; the cocktail lounge and Mediterranean garden moods both favor moderate, considered rounding. 6px as the default produces buttons and inputs that feel substantial without being either squared (too formal) or pill-shaped (too casual).

### Focus states

Focus indicators must be visible, substantial, and on-brand. They use the accent for recognition — the focus ring is *the* accent signal for "this element has your attention."

**Focus ring specification:**
- **Color:** `--accent` with 40% opacity for the ring itself.
- **Width:** 3px outside the element.
- **Offset:** 2px from the element edge.
- **Composition:** `box-shadow: 0 0 0 2px var(--surface-base), 0 0 0 5px color-mix(in oklch, var(--accent) 40%, transparent)`. The first shadow creates a gap between the element and the ring; the second shadow is the ring itself.
- **Radius:** Matches the element's own radius.
- **Transition:** Fades in with `duration-quick` and `ease-settle`.

**Rule:** Every focusable element must have a visible focus state. Removing focus rings for aesthetic reasons is forbidden. A focus state may be styled to match the component (e.g., a button's focus ring might be slightly tighter), but it must always be visible and must always use accent.

**Rationale:** Focus states are an accessibility floor (WCAG 2.4.7) and also a platform signal — the accent focus ring is the platform saying "I see you." Generic outline focus rings read as browser-default; branded focus rings read as "this app was designed."

### Motion timing scale

Bridgeable uses five named durations. Sonnet picks a duration by motion type, not by guessing millisecond values.

| Token | Value | Use |
|---|---|---|
| `duration-instant` | 100ms | Micro-transitions — color changes, small opacity shifts, immediate hover feedback. |
| `duration-quick` | 200ms | Standard hovers, focus ring appearance, small UI reactions. |
| `duration-settle` | 300ms | Dropdowns opening, tooltips, small overlays, most UI transitions. |
| `duration-arrive` | 400ms | Modals entering, side panels opening, major element appearances. |
| `duration-considered` | 600ms | Page transitions, significant state changes, dashboard widget reflows. |

**Mode parity:** Light and dark mode use the same duration scale. Section 1 described dark mode as "slightly slower" in character; this is achieved through easing curves and visual weight (larger shadows, more material presence), not through longer durations. Durations under ~50ms different are below perceptual threshold, and varying them per mode adds implementation complexity without felt benefit.

**Duration selection logic for Sonnet:**
- Is this a hover, focus, or tiny state change? → `duration-quick` (or `duration-instant` for especially small changes)
- Is this a dropdown, tooltip, or small overlay? → `duration-settle`
- Is this a modal, side panel, or large appearance? → `duration-arrive`
- Is this a page transition or significant layout shift? → `duration-considered`

### Easing curves

Bridgeable uses two named easing curves. Both are ease-out-dominant, producing the "settles rather than snaps" feel from Section 1.

| Token | Curve | Use |
|---|---|---|
| `ease-settle` | `cubic-bezier(0.2, 0, 0.1, 1)` | Entrances, arrivals, appearances. Aggressive deceleration at the end — things *arrive* rather than fade in. |
| `ease-gentle` | `cubic-bezier(0.4, 0, 0.4, 1)` | Exits, dismissals, fades. More symmetric, less dramatic. |

**Rule:** Entrances use `ease-settle`; exits use `ease-gentle`. Do not use browser-default `ease` or linear transitions. Those read as unstyled and break the considered-motion character of the platform.

**Rationale:** The two-curve system mirrors the real-world asymmetry of how things enter and leave attention. Something arriving in your field of view demands notice; something leaving should recede quietly. Using the same curve for both produces motion that feels mechanical; distinguishing them produces motion that feels considered.

### Specific motion patterns

Common UI transitions specify both duration and easing. These are the defaults; deviation requires justification.

| Pattern | Duration | Easing | Notes |
|---|---|---|---|
| Hover color change | `duration-quick` | `ease-settle` | |
| Focus ring appearance | `duration-quick` | `ease-settle` | |
| Button press feedback | `duration-instant` | `ease-settle` | Slight scale down (e.g., `scale-97`) on active. |
| Dropdown opening | `duration-settle` | `ease-settle` | Opacity fade + slight Y translate (4px). |
| Dropdown closing | `duration-quick` | `ease-gentle` | Opacity fade only. |
| Tooltip appearance | `duration-settle` | `ease-settle` | With a short delay (150ms) before triggering. |
| Modal entering | `duration-arrive` | `ease-settle` | Opacity fade + slight scale (0.98 → 1.0). Backdrop fades with same duration. |
| Modal exiting | `duration-settle` | `ease-gentle` | Opacity fade only. |
| Side panel opening | `duration-arrive` | `ease-settle` | X translate from edge. |
| Side panel closing | `duration-settle` | `ease-gentle` | X translate back to edge. |
| Toast appearance | `duration-settle` | `ease-settle` | Opacity fade + slight Y translate. |
| Page transition | `duration-considered` | `ease-settle` | Content fades; new content fades in. |

**Button press note:** The slight scale-down on active (`scale-97`, roughly 97% of original size) provides tactile feedback without being cartoonish. This is the one place the "material, not paint" anchor shows up in motion — buttons feel like they can be pressed.

**Tooltip delay note:** The 150ms delay before tooltips appear prevents "drive-by tooltips" when the user's cursor transits across elements. Without the delay, tooltips flash on and off during normal mouse movement.

### Reduced motion

Per accessibility requirements (see Section 8), the system respects `prefers-reduced-motion: reduce`.

**Rule:** When reduced motion is requested, all duration tokens collapse to `duration-instant` (100ms) or zero, and translate/scale animations are removed. Opacity fades are retained because they do not cause motion sickness.

**Implementation:**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 100ms !important;
    transition-duration: 100ms !important;
    scroll-behavior: auto !important;
  }

  /* Remove specific motion-intensive transforms */
  .modal-enter, .panel-enter, .toast-enter {
    transform: none !important;
  }
}
```

Reduced motion does not remove all transitions — it removes motion-intensive ones (translate, scale, slide). Color changes and opacity fades remain, because they are not motion in the vestibular sense.

### Surface composition patterns

Common surface patterns combine elevation, shadow, border, radius, and (in dark mode) top-edge highlight. These are the canonical compositions.

**Card (level 1):**
```css
background: var(--surface-elevated);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-1);
padding: var(--space-6);
```

**Modal (level 2):**
```css
background: var(--surface-raised);
border-radius: var(--radius-lg);
box-shadow: var(--shadow-level-2);
padding: var(--space-6);
max-width: var(--max-w-form);
```

**Dropdown / popover (level 2):**
```css
background: var(--surface-raised);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-2);
padding: var(--space-2);
border: 1px solid var(--border-subtle); /* Subtle definition at small sizes where shadow alone isn't enough */
```

**Toast (level 3):**
```css
background: var(--surface-raised);
border-radius: var(--radius-md);
box-shadow: var(--shadow-level-3);
padding: var(--space-4) var(--space-5);
```

**Floating command bar (level 3):**
```css
background: var(--surface-raised);
border-radius: var(--radius-lg);
box-shadow: var(--shadow-level-3);
border: 1px solid var(--border-accent); /* Accent edge signals primary interaction surface */
padding: var(--space-4);
```

### Tooltip patterns

Tooltips are labels on hover and accessible names for assistive tech (`aria-label`). They are not secondary text, not tutorials, and not replacements for visible labels. Keep them short — under 10 words is ideal.

**Describe state, not action, when state matters.** Toggle-like elements with a meaningful active state should carry state-aware labels:

- Active: `"Active: {name}"` or `"Currently viewing {name}"` — describes what the user sees
- Inactive: `"Switch to {name}"` or `"Open {name}"` — describes the action a click would take

The anti-pattern: a toggle with the same tooltip on every state. Example: a DotNav dot labeled `"Switch to Operations"` when Operations is already the active space. The label is a misdirection — it promises an action that either doesn't fire (user is already there) or does nothing visible.

This pattern applies to: space switchers, tab selectors, sidebar navigation items, toggle buttons, mode toggles. It does NOT need to apply to links that navigate to new contexts (a "Customers" nav link can say "Customers" in every state — navigating to a page you're already on is a well-understood no-op).

**Hover vs. click vs. focus.** Tooltips appear on hover AND focus (WCAG 2.2 requires focus visibility). They must not require hover to read — screen readers already have `aria-label`. The visible tooltip is a bonus for pointer users.

**Don't duplicate visible labels.** A button with visible "Save" text and a tooltip that says "Save" is noise. Tooltips augment labels that are icons, truncated, or elided for density.

### Anti-patterns

- **Hard drop shadows** (`box-shadow: 2px 2px 0 black`). These read as "brutalist web design" or "MS Paint." Bridgeable shadows are soft, warm, atmospheric.
- **Neutral gray shadows.** Violates the warm-hue family rule from Section 2. All shadows are warm-tinted.
- **Dark mode without shadows.** Violates the "shadows persist in dark mode" rule. Dark mode UI without shadows reads as flat institutional software, not as cozy lounge.
- **Over-rounded surfaces.** Radius above 16px on standard UI elements reads as consumer-app or playful. Bridgeable favors moderate, considered rounding.
- **Sharp 90° corners on interactive elements.** Buttons and inputs with no rounding read as utilitarian or cold. Even a 4px radius signals considered design.
- **Motion with `ease` or `linear` timing.** These read as browser-default. The platform uses `ease-settle` or `ease-gentle`.
- **Excessive motion.** Every UI change animated, every hover with a transition, every element bouncing on load. Bridgeable's motion is considered — used where it aids comprehension, absent where it would be noise.
- **Removing focus rings.** Never. Focus rings are an accessibility requirement and a platform signal.
- **Elevation inversions.** A card with a shadow sitting on top of a modal (which should have a larger shadow). The monotonic elevation rule prevents this.

## Section 7 — Iconography & Imagery

Icons and imagery are the visual vocabulary of the platform beyond type and color. They communicate actions, entities, and status without language. This section specifies the icon library, how icons are used, and how images are treated.

### Icon library

Bridgeable uses **Lucide** for all UI icons. No other icon library is used anywhere in the platform.

**Rationale:** Lucide's 2px-stroke rounded-line character sits naturally against the warm palette and the Plex letterforms — both carry that "considered, slightly warm, engineered" quality. The ~1,500-icon set is wide enough that Sonnet can find a specific icon for a specific concept (vault, cemetery, workflow, tenant, product line) rather than forcing generic substitutes. Using a single library across the entire platform enforces visual consistency without effort; mixing libraries produces visible inconsistency that takes real work to notice and real time to fix.

**Implementation:**
- React: `import { IconName } from "lucide-react"` — version `0.383.0` is already available in the artifact environment.
- Non-React contexts: `lucide` for vanilla JS, `lucide-static` for static SVGs.
- Do not import individual icons from other libraries for "one-off" needs. If Lucide does not have an icon for a specific concept, the right answer is to adapt or omit — not to reach for another library.

### Icon sizing scale

Icons use a named size scale keyed to their surrounding context. Sonnet picks by context, not by guessing pixel values.

| Token | Size | Stroke | Use |
|---|---|---|---|
| `icon-xs` | 12px | 1.5px | Micro labels, inline indicators, tight badge contexts. |
| `icon-sm` | 14px | 1.5px | Icons inside dense UI (table rows, list items, form field adornments). |
| `icon-base` | 16px | 2px | **Default.** Icons in buttons, navigation items, standard UI. |
| `icon-md` | 20px | 2px | Primary action icons, card header icons, section headers. |
| `icon-lg` | 24px | 2px | Hero icons, empty-state illustrations, prominent UI icons. |
| `icon-xl` | 32px | 2px | Large feature icons, onboarding, major status indicators. |
| `icon-2xl` | 48px | 2px | Signature moments — major empty states, hero illustrations. |

**Stroke width rules:**
- Icons at 16px and above use Lucide's default 2px stroke.
- Icons at 14px and below use 1.5px stroke — Lucide's default 2px stroke looks too heavy at small sizes.
- Set via `strokeWidth` prop: `<IconName size={14} strokeWidth={1.5} />`

### Icon color

Icons inherit color from their context via `currentColor` (Lucide's default behavior). This means icons automatically adopt the appropriate content color from Section 3 based on where they sit.

**Default icon colors:**
- Icons in body text or default UI → `content-base`
- Icons in muted contexts (captions, helper text) → `content-muted`
- Icons in primary actions (accent buttons) → `content-on-accent`
- Icons in accent-tinted contexts (selected states, focused items) → `accent`
- Icons communicating status → the corresponding status color (`status-error`, `status-warning`, `status-success`, `status-info`)

**Rule:** Icons do not use decorative colors. An icon is colored by what it *means*, not by what would look pretty. A status icon is colored by status semantics; a navigation icon is colored by whether the item is active; an accent icon indicates primary action or active focus. Arbitrary color choice on icons produces the "which icon is colored and why" confusion that degrades UI legibility.

### Icon usage patterns

**Buttons:** Icons may appear alone (icon-only buttons) or paired with text. When paired, the icon sits before the text with `space-2` (8px) gap.

```jsx
<Button>
  <Check size={16} strokeWidth={2} />
  Approve All
</Button>
```

**Navigation items:** Icons appear before labels with `space-3` (12px) gap. Active navigation items use accent color for both icon and label; inactive items use `content-muted` for the icon and `content-base` for the label.

**Form field adornments:** Icons inside input fields (search icons, status indicators, unit markers) use `icon-sm` (14px) and `content-muted`. They sit with `space-3` (12px) padding from the field edge.

**Status indicators:** Status icons appear before status labels with `space-2` gap. Icon color matches the status (`status-error`, etc); label uses a darker shade of the same hue for contrast.

**Decorative icons in prose:** Generally avoided. Icons should earn their place by communicating something language doesn't. Pure decoration fights deliberate restraint.

### Icon selection principles

- **Prefer recognizable over clever.** A ✉ icon for messaging is better than a novel metaphor, even if the novel metaphor is more interesting. Users should not have to decode icons.
- **One concept per icon; one icon per concept.** A "trash" icon means "delete" — not also "archive" or "clear." Using the same icon for multiple concepts produces ambiguity; using different icons for the same concept produces inconsistency.
- **Prefer action icons to noun icons for buttons.** A button labeled "Save" with a disk icon is worse than a button labeled "Save" with a check icon, because the check communicates completion (the *result* of saving) while the disk communicates storage medium (an implementation detail users don't care about).
- **Avoid icon-only buttons except for universally-recognized actions.** Close (×), menu (☰), search (🔍), settings (⚙) are safe. "Approve" and "Reject" should have labels. When in doubt, label the button; icons alone force users to guess.

### Platform-specific icon mappings

For recurring Bridgeable concepts, use these specific Lucide icons to avoid drift across the platform:

| Concept | Icon | Rationale |
|---|---|---|
| Vault (burial) | `Box` | Evokes the physical object; used consistently for vault-related features. |
| Case (funeral home) | `FileText` | A case is fundamentally a document-rooted entity. |
| Cemetery | `Trees` | Evokes the physical location; more specific than a generic "location" pin. |
| Tenant | `Building2` | Organizations as buildings; consistent with industry conventions. |
| Workflow step | `Circle` (completed: `CheckCircle2`, active: `Circle` with accent ring, pending: `Circle` muted) | The step progression pattern. |
| Approve / confirm | `Check` | Universal completion indicator. |
| Reject / cancel | `X` | Universal negation. |
| Edit | `PenLine` | More specific than a generic pencil; signals content editing. |
| Delete | `Trash2` | Lucide's trash icon; the "2" suffix is the updated glyph. |
| Settings | `Settings` | Standard cog. |
| Search | `Search` | Standard magnifier. |
| Command bar | `Command` | The "⌘" glyph; reinforces the keyboard-first Cmd+K affordance. |
| User / person | `User` | Individual person. |
| Team / multiple users | `Users` | Group of people. |
| Time / schedule | `Clock` | Time-specific events. |
| Calendar | `Calendar` | Date-specific or calendar-view contexts. |
| Notification | `Bell` | Standard bell. |
| Error / alert | `AlertCircle` | Status-error contexts. |
| Warning | `AlertTriangle` | Status-warning contexts. |
| Success | `CheckCircle2` | Status-success contexts. |
| Info | `Info` | Status-info contexts. |
| External link | `ExternalLink` | Links that leave the platform or open a new surface. |
| Add / new | `Plus` | Creation actions. |
| Close | `X` | Close modal, dismiss panel. |
| Menu | `Menu` | Hamburger for mobile or collapsed navigation. |
| Arrow forward | `ArrowRight` | Proceed, continue, advance step. |
| Arrow back | `ArrowLeft` | Return, previous step. |
| Chevron (expand/collapse) | `ChevronRight`, `ChevronDown` | Collapsible sections, accordion indicators. |

This mapping is not exhaustive. When a new concept needs an icon, pick from Lucide, document the mapping in this table (via update to this document), and use it consistently across the platform.

### Imagery

Bridgeable uses real imagery sparingly. The platform is utility software; imagery appears in specific contexts, not as decoration.

**Where imagery appears:**
- **User/contact avatars.** Person photos, initials fallback.
- **Tenant logos.** Organization logos in tenant-specific contexts (funeral home branding on family portals, plant branding on manufacturing dashboards).
- **Product photography.** Vault product images, precast product images, Redi-Rock block images — for resale catalogs, product configurators, and quote generation.
- **Empty states.** Illustrated empty states where a concept is easier to communicate visually than linguistically.
- **Marketing and external surfaces.** Family-facing portals, public websites, onboarding flows.

**Where imagery does not appear:**
- Decorative photography on admin UI pages. No "office workers smiling at laptops" stock photography anywhere in the platform.
- Hero banners on internal pages. The admin UI has no need for hero imagery.
- Illustrated headers on dashboards or hubs. The warmth of the palette and typography is enough atmosphere; illustrations would fight deliberate restraint.

### Image treatment

**Avatars:**
- Square source images rendered as circles (`radius-full`).
- Fallback: initials on a `accent-accent-muted` background with `content-on-accent` text color.
- Sizes: `avatar-sm` (24px), `avatar-base` (32px), `avatar-md` (40px), `avatar-lg` (56px), `avatar-xl` (80px).

**Tenant logos:**
- Preserve aspect ratio; do not crop or distort.
- Contained within a fixed bounding box; whitespace within the box is the tenant's responsibility in their logo asset.
- For tenants without a logo asset, use the tenant name in Plex Sans Medium as a wordmark placeholder.

**Product photography:**
- Photographed against neutral backgrounds (warm off-white or transparent, never stark white or gray).
- Rendered at product catalog contexts with `radius-md` rounded corners.
- Ratio-preserving; never cropped to square except in grid views where consistency requires it.

**Empty-state illustrations:**
- Use Lucide icons at `icon-2xl` (48px) or larger, centered, in `content-muted` color, rather than custom illustrations.
- The illustration is the icon plus the accompanying copy — not a separate drawn image. This keeps the visual language of empty states aligned with the rest of the platform.

**Rationale for icon-only empty states:** Custom illustrations introduce a new visual style that has to be maintained alongside Lucide, Plex, and the color system. Unless Bridgeable commits to a specific illustration style (which is a major design undertaking), icon-based empty states provide appropriate visual presence without opening a new surface-area of design decisions. If at some future point the platform commits to an illustration style, that is an addition to this document, not a side-decision.

### Image quality and loading

- Product and marketing imagery loads at 2x pixel density (retina) with appropriate srcsets for smaller viewports.
- All `<img>` elements include meaningful `alt` text; decorative images use `alt=""` explicitly.
- Images above the fold use `loading="eager"`; images below use `loading="lazy"`.
- Avatars have a placeholder fallback that renders immediately while the image loads (initials on accent-muted background) — never blank circles.

### Anti-patterns

- **Mixing icon libraries.** Under no circumstances. Lucide for everything.
- **Colored icons for decoration.** Icons are colored by semantic meaning. A "blue trash icon" because blue looks nice is wrong; a "status-error trash icon" because deletion is destructive is correct.
- **Stock photography on admin UI.** Generic smiling-office-worker imagery is never appropriate for Bridgeable admin surfaces.
- **Novel icon metaphors for standard actions.** "Save" is a check or a disk. "Delete" is a trash can. Novel metaphors for standard actions produce guessing games.
- **Icon-only buttons for non-universal actions.** Icon-only "Approve" buttons are ambiguous. Approve, reject, delete, archive all require labels. Only universal actions (close, menu, search) are safe as icon-only.
- **Oversized decorative icons.** Icons at 64px+ used purely for decoration on a standard page read as consumer-app. The 48px `icon-2xl` is the ceiling for most UI; larger sizes are reserved for true signature moments.
- **Inconsistent icon sizes within a single UI region.** A list of items where each has an icon should use the same icon size across all items, even when the items have different content lengths.

## Section 8 — Accessibility Floor

Accessibility is not a post-hoc audit concern for Bridgeable. It is a baseline quality that shipped UI must meet. This section specifies the minimum requirements — the *floor* — below which no shipped component is allowed to sit. Individual components may exceed these requirements; none may fall below them.

This section is mechanical synthesis of rules established earlier in the document plus the specific WCAG requirements every UI ships with. Sonnet should read this section as a checklist to verify against during every component build.

### Target: WCAG 2.2 Level AA

Bridgeable targets **WCAG 2.2 Level AA** as its baseline. Specific requirements are called out below; the full WCAG document governs any case not explicitly addressed here.

**Why AA and not AAA:** AAA requirements (e.g., 7:1 contrast for body text, sign-language alternatives for prerecorded video) are appropriate for specific domains (government, healthcare-direct-care) but add cost that does not materially improve usability for Bridgeable's user base. AA is the widely-accepted professional floor for business software. Specific tokens in the system exceed AA and approach AAA where it's cheap to do so (e.g., `content-strong` on `surface-base` is near-AAA in both modes).

### Color contrast

Per Section 3, the content color tokens were designed with contrast ratios in mind. The specific requirements:

**Body text:**
- `content-base` on `surface-base` — must meet 4.5:1 (AA body text)
- `content-base` on `surface-elevated` — must meet 4.5:1
- `content-base` on `accent` — addressed by the dedicated `content-on-accent` token

**Large text (18pt+ or 14pt+ bold):**
- `content-muted` on `surface-base` — must meet 3:1 (AA large text)

**UI components and graphical objects:**
- Interactive element boundaries (button borders, input borders, focus indicators) — must meet 3:1 against adjacent colors (AA non-text contrast)
- Icon colors that convey meaning — must meet 3:1 against their background

**Status colors:**
- Status colors used for text or icons must meet 4.5:1 (text) or 3:1 (non-text) against their backgrounds. Status `muted` variants are backgrounds, so the pairing of status foreground color on status-muted background must itself meet contrast requirements.

**Rule:** Any proposed color pairing must be verified against these ratios before shipping. Sonnet verifies using a contrast-checking tool (the oklch values make this straightforward via any WCAG contrast calculator) and documents the verified ratio in the component's implementation notes.

**What not to rely on:** Color alone to communicate state. A red status label must also include a word ("Error") or an icon (`AlertCircle`). A required form field must not be marked only by red asterisk color — it needs a text marker. This is WCAG 1.4.1 (Use of Color) and it applies everywhere in the platform.

### Focus indication

Per Section 6, every focusable element has a visible focus state using the accent focus ring. This is the single most important accessibility rule in the platform and the one most often violated in SaaS UI.

**Requirements:**
- Every interactive element (buttons, links, inputs, checkboxes, radios, custom controls) must have a visible focus state.
- The focus state must meet 3:1 contrast against the adjacent background.
- The focus ring must not be removed via `outline: none` without providing an equivalent replacement (which Bridgeable's accent focus ring satisfies).
- Focus state must be visible via keyboard navigation, not just mouse clicks.
- Focus moves in a logical order — roughly top-to-bottom, left-to-right for LTR content — and never traps the user in a sub-region without an escape path.

**Rule:** If Sonnet writes `outline: none` in any component, the very next rules must define the accent focus ring. Removing focus rings for aesthetics is a violation regardless of how the design is styled otherwise.

### Keyboard navigation

Every workflow in Bridgeable must be completable via keyboard alone. The Command Bar (Cmd+K) is a primary keyboard affordance and should always be reachable without a mouse.

**Keyboard requirements:**
- All interactive elements are focusable via Tab (and reachable by Shift+Tab for reverse order).
- Modals trap focus until dismissed; focus returns to the trigger element on close.
- Dropdown menus respond to Arrow keys for navigation and Enter/Space to select.
- Escape dismisses modals, dropdowns, popovers, and tooltips.
- Tab order follows visual order.
- The Command Bar opens with `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux) from anywhere in the app.
- Skip-to-content links are provided on pages with significant navigation chrome.

**Custom interactive elements:** Any custom-built control (e.g., a custom dropdown, a custom date picker) must replicate standard keyboard behavior of its HTML equivalent. A custom dropdown responds to Arrow keys, Home/End, typeahead, and Escape like a native `<select>`. Shortcuts exist; replicating expected behavior is not optional.

### Screen reader support

Bridgeable uses semantic HTML first, ARIA where necessary.

**Requirements:**
- Use semantic HTML elements (`<button>`, `<nav>`, `<main>`, `<header>`, `<article>`, `<section>`, `<label>`) rather than styled `<div>`s.
- All form inputs have associated `<label>` elements (or `aria-label` for cases where a visible label is truly inappropriate).
- Buttons use `<button>`, links use `<a>`. Clickable `<div>`s are forbidden.
- Images have meaningful `alt` text; decorative images use `alt=""` explicitly.
- Icon-only buttons include `aria-label` describing the action.
- Status regions that update dynamically use `aria-live` ("polite" for non-urgent, "assertive" for critical).
- Form validation errors are announced via `aria-describedby` pointing to the error text.
- Modal dialogs use `<dialog>` or `role="dialog"` with `aria-modal="true"` and an `aria-labelledby` pointing to the dialog title.

**ARIA philosophy:** The first rule of ARIA is not to use ARIA. Prefer semantic HTML. Use ARIA only when semantic HTML cannot express what's needed (e.g., for custom controls or dynamic regions). Incorrect ARIA is worse than no ARIA.

### Reduced motion

Per Section 6, the system respects `prefers-reduced-motion: reduce`. This is repeated here because it is an accessibility floor requirement, not just a motion design preference.

**Requirements:**
- Motion-intensive animations (translate, scale, slide, rotate) are removed when reduced motion is requested.
- Opacity fades and color transitions are retained — they do not cause vestibular issues.
- Parallax scrolling, auto-playing video, and autoplay carousels respect reduced motion and stop automatic playback.
- Durations collapse to `duration-instant` (100ms) or zero.

### Touch target size

Per WCAG 2.2 (Target Size Level AA = 24×24 CSS pixels):

**Requirements:**
- Interactive targets are at least 24×24 CSS pixels.
- Preferred minimum: 44×44 CSS pixels (Apple HIG guideline, broadly adopted).
- Buttons with `py-2.5 px-5` padding (per Section 5) exceed both thresholds for any text label.
- Icon-only buttons must be explicitly sized to meet the minimum — e.g., a 16px icon in a button with enough padding that the button itself is at least 44×44 (realistically 16px icon + 12px padding each side = 40px, which rounds acceptably close; use 14px padding to land solidly at 44).

**Rule:** Any interactive element smaller than 24×24 CSS pixels is a violation. Targets crowded close together need at least 8px of spacing between them to avoid accidental activation.

### Form accessibility

Forms are particularly accessibility-sensitive. Bridgeable forms meet these requirements:

- Every input has a visible, persistent label (not placeholder-as-label).
- Labels are clickable and focus the associated input (via `<label>` element).
- Required fields are indicated with both a visible marker (e.g., asterisk) and `required` / `aria-required="true"` attributes.
- Error messages are associated with inputs via `aria-describedby` and announced on submit (not on every keystroke, which is noisy for screen readers).
- Error messages explain what's wrong and what to do, not just "Invalid." (e.g., "Email must contain @ and a domain" rather than "Invalid email.")
- Field-level validation errors appear adjacent to the field (below it) with a clear visual indicator (status-error color + `AlertCircle` icon) and associated text.
- Fieldsets group related fields (address fields, date components) with a `<legend>` describing the group.
- Autocomplete attributes are used for common fields (`autocomplete="email"`, `autocomplete="given-name"`, etc.) so password managers and browser autofill work correctly.

### Responsive and zoom support

- The platform functions correctly at 200% browser zoom (WCAG 1.4.4 Resize Text).
- Text reflows rather than truncating or horizontal-scrolling at 200% zoom.
- The platform is usable at viewports down to 320px wide for the explicitly mobile-scoped surfaces (per Section 5).
- No fixed-height text containers that prevent text from reflowing.

### Language and internationalization

- The root `<html>` element declares the content language (`<html lang="en">`).
- Alternate-language content uses `lang` attributes on the containing element.
- Bridgeable does not currently support internationalization, but UI strings are structured to allow future localization (strings in a translation table, not hardcoded in components).
- RTL (right-to-left) language support is deferred. When added, layouts will flip with CSS logical properties (`margin-inline-start` rather than `margin-left`).

### Testing and verification

Every shipped component is verified against:

1. **Automated contrast checking** — all color pairings meet required ratios.
2. **Keyboard-only navigation** — the component is fully usable without a mouse.
3. **Screen reader testing** — VoiceOver (macOS), NVDA (Windows), or equivalent announces the component correctly.
4. **Focus visibility** — the accent focus ring appears on every focusable element.
5. **Reduced motion** — component degrades correctly when `prefers-reduced-motion: reduce` is set.
6. **Zoom test** — component functions at 200% browser zoom.

**Rule:** Sonnet treats this as a shipping gate. A component that fails any of the six checks is not ready to ship, regardless of visual polish.

### Anti-patterns

- **Removing focus rings** (`outline: none` without replacement). The single most common accessibility failure. Forbidden.
- **Placeholder-as-label forms.** The placeholder disappears when the user types, leaving no indication of what the field is. Use visible labels.
- **Color-only status indication.** Status communicated purely by color (e.g., a red border around a field) fails users who can't distinguish that color and screen reader users. Always pair color with text or icon.
- **Clickable divs.** `<div onClick={...}>` is not a button. Use `<button>`.
- **Icon-only buttons without `aria-label`.** The visual icon doesn't exist for screen readers.
- **Auto-playing animations without pause.** Violates WCAG 2.2.2. All motion that plays for longer than 5 seconds must have a pause control.
- **Disabling zoom** (`<meta name="viewport" content="user-scalable=no">`). Forbidden. Users must be able to zoom.
- **Tab traps without escape.** A modal or overlay that takes focus but has no way to dismiss via keyboard traps screen reader and keyboard users.

## Section 9 — Implementation

This section translates everything above into the concrete code structure Sonnet uses to implement the design language. The goal is that Sonnet can read this section and immediately set up or modify the design system without needing to re-derive anything from earlier sections.

### Technology stack

The Bridgeable design system is implemented using:

- **CSS custom properties (CSS variables)** as the primary token mechanism. All tokens from Section 3 are defined as CSS variables at `:root` and overridden for `[data-mode="dark"]`.
- **Tailwind CSS** as the utility framework. Tailwind config consumes the CSS variables so Tailwind classes resolve to design tokens.
- **PostCSS** for CSS processing.
- **`@fontsource`** packages for self-hosted Plex fonts.
- **`lucide-react`** for icons.

No CSS-in-JS libraries (styled-components, emotion). Tailwind + CSS variables handles all styling.

### File structure

Design system files live under `/app/styles/` in the Bridgeable repo:

```
/app/styles/
├── tokens.css          # All CSS custom properties (Section 3)
├── base.css            # Reset, body defaults, Plex loading
├── fonts.css           # @fontsource imports, font-face declarations
├── utilities.css       # Custom utility classes beyond Tailwind
└── globals.css         # Entry point that imports the above + Tailwind
```

**Import order in `globals.css`:**

```css
@import "./fonts.css";
@import "./tokens.css";
@import "./base.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

@import "./utilities.css";
```

Tokens load before Tailwind base so Tailwind can reference them in the config. Custom utilities load after Tailwind utilities so they can override or extend them.

### Mode switching

Light mode is the default. Dark mode is activated by setting `data-mode="dark"` on the `<html>` element.

**CSS structure:**

```css
:root {
  /* Light mode tokens (defaults) */
  --surface-base: oklch(0.94 0.030 82);
  /* ... all light tokens ... */
}

[data-mode="dark"] {
  /* Dark mode overrides */
  --surface-base: oklch(0.16 0.012 65);
  /* ... all dark tokens ... */
}
```

**Mode switching logic (React):**

```jsx
// In the root layout component
function setMode(mode) {
  document.documentElement.setAttribute('data-mode', mode);
  localStorage.setItem('bridgeable-mode', mode);
}

// On initial load, before any component renders
const savedMode = localStorage.getItem('bridgeable-mode');
if (savedMode) {
  document.documentElement.setAttribute('data-mode', savedMode);
} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.documentElement.setAttribute('data-mode', 'dark');
}
```

**Flash-of-wrong-mode prevention:** The mode attribute must be set before React hydration to prevent a flash of light mode when dark is the user's preference. Use a synchronous inline `<script>` in the document head that reads localStorage and sets `data-mode` before any CSS is applied.

**User-facing mode toggle (Nav Bar Completion, April 2026):** The visible UI control is a Sun/Moon button rendered in the AppLayout top header (`components/layout/ModeToggle.tsx`), mounted immediately before the `NotificationDropdown`. The icon represents the *destination* state, not the current state — in light mode, the button shows `<Moon />` (click to go dark); in dark mode, `<Sun />` (click to go light). This matches the GitHub / Linear / Vercel convention and the common user intuition that a button icon signals what will happen, not what is already happening.

Accessibility rules for the toggle:
- `aria-label` describes the *action* ("Switch to dark mode"), not the state ("Dark mode: off"). Per WCAG recommendation for toggle buttons.
- `aria-pressed` reflects the *current* toggle state (`true` when dark, `false` when light). Screen readers announce both the available action and the current state.
- `focus-ring-accent` utility for keyboard focus (see Section 6 focus-state spec).

Runtime wiring: the toggle consumes `useMode()` from `lib/theme-mode.ts`, which returns `{mode, toggle}` and delegates to `useThemeMode` (the underlying `[mode, setter]` tuple). Shared state — no duplication.

```jsx
// ModeToggle usage (simplified):
import { useMode } from "@/lib/theme-mode";

function ModeToggle() {
  const { mode, toggle } = useMode();
  const isDark = mode === "dark";
  const Icon = isDark ? Sun : Moon;
  const next = isDark ? "light" : "dark";
  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} mode`}
      aria-pressed={isDark}
      title={`Switch to ${next} mode`}
      className="... focus-ring-accent"
    >
      <Icon aria-hidden="true" />
    </button>
  );
}
```

Once the toggle ships, **all aesthetic verification for subsequent sessions must cover both modes**, not just the mode currently in focus. The toggle is the primary channel users have to experience both moods; bugs that only surface in one mode are disproportionately impactful.

### Full `tokens.css`

The complete token definitions from Section 3, plus the tokens introduced in Sections 4–7:

```css
:root {
  /* ============ COLOR TOKENS ============ */

  /* Surfaces */
  --surface-base: oklch(0.94 0.030 82);
  --surface-elevated: oklch(0.965 0.014 82);
  --surface-raised: oklch(0.985 0.010 82);
  --surface-sunken: oklch(0.91 0.020 82);

  /* Content */
  --content-strong: oklch(0.22 0.015 70);
  --content-base: oklch(0.30 0.015 70);
  --content-muted: oklch(0.48 0.014 70);
  --content-subtle: oklch(0.62 0.012 70);
  --content-on-accent: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.88 0.012 80 / 0.6);
  --border-base: oklch(0.82 0.015 78 / 0.8);
  --border-strong: oklch(0.70 0.020 76);
  --border-accent: rgba(156, 86, 64, 0.70);

  /* Shadows */
  --shadow-color-subtle: oklch(0.40 0.045 78 / 0.06);
  --shadow-color-base: oklch(0.40 0.045 78 / 0.10);
  --shadow-color-strong: oklch(0.37 0.050 75 / 0.16);

  /* Accent — deepened terracotta, single value across modes
     (Aesthetic Arc Session 2). `--accent-active` intentionally
     absent; selected-item state uses --accent-subtle + --accent.
     `--accent-confirmed` (Session 4.5) is the architectural
     stamped-green counterpart to terracotta — see §3 + §11
     Pattern 3 first-channel left-edge flag confirmed state. */
  --accent: oklch(0.46 0.10 39);
  --accent-hover: oklch(0.54 0.10 39);
  --accent-muted: rgba(156, 86, 64, 0.20);
  --accent-subtle: rgba(156, 86, 64, 0.10);
  --accent-confirmed: oklch(0.58 0.05 138);

  /* Status */
  --status-error: oklch(0.55 0.18 25);
  --status-error-muted: oklch(0.92 0.04 25);
  --status-warning: oklch(0.70 0.14 65);
  --status-warning-muted: oklch(0.94 0.04 65);
  --status-success: oklch(0.58 0.12 135);
  --status-success-muted: oklch(0.93 0.04 135);
  --status-info: oklch(0.55 0.08 225);
  --status-info-muted: oklch(0.93 0.03 225);

  /* Card material treatment (Aesthetic Arc Session 4.6 — mode-
     aware). Light-mode values calibrated for cream substrate
     (L=0.965 elevated). Dark-mode override below for charcoal
     substrate (L=0.28 elevated). See §3 "Card material treatment
     tokens" + §11 Pattern 2 for composition recipe and the
     Session-4.5→4.6 calibration history. */
  --card-edge-highlight: rgba(255, 255, 255, 0.45);
  --card-edge-shadow: rgba(0, 0, 0, 0.20);
  --card-ambient-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.18);
  --flag-press-shadow: rgba(0, 0, 0, 0.15);

  /* Jewel-set inset ring (Aesthetic Arc Session 4.5 + 4.7) —
     light mode 0.25. Dark mode override 0.50 in [data-mode="dark"].
     Session 4.7 strengthening from initial 0.15/0.30. */
  --shadow-jewel-inset: inset 0 1px 2px rgba(0, 0, 0, 0.25);

  /* Widget elevation tier (Aesthetic Arc Session 4.7 + 4.8).
     Session 4.8 amplified to layered atmospheric shadow + translateY
     transform after Session 4.7 single-shadow read as "elevated card."
     Higher-tier lift than --card-ambient-shadow per Pattern 1
     elevation hierarchy (widgets float more than cards). See §3
     "Widget elevation tier tokens" for full rationale + calibration
     history. Light mode here; dark override below. */
  --widget-ambient-shadow:
    0 4px 12px -2px rgba(0, 0, 0, 0.10),
    0 16px 32px -4px rgba(0, 0, 0, 0.25),
    0 32px 56px -8px rgba(0, 0, 0, 0.30);
  --widget-tablet-transform: translateY(-2px);
  --shadow-widget-tablet: var(--shadow-level-1), var(--widget-ambient-shadow);

  /* ============ ELEVATION SHADOWS ============ */
  --shadow-level-1: 0 2px 8px var(--shadow-color-base);
  --shadow-level-2: 0 8px 24px var(--shadow-color-base), 0 2px 6px var(--shadow-color-subtle);
  --shadow-level-3: 0 16px 40px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base);

  /* ============ TYPOGRAPHY TOKENS ============ */
  --font-sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-serif: "IBM Plex Serif", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  --text-display-lg: 3.052rem;
  --text-display: 2.441rem;
  --text-h1: 1.953rem;
  --text-h2: 1.563rem;
  --text-h3: 1.25rem;
  --text-h4: 1.125rem;
  --text-body: 1rem;
  --text-body-sm: 0.875rem;
  --text-caption: 0.75rem;
  --text-micro: 0.6875rem;

  /* ============ BORDER RADIUS ============ */
  --radius-none: 0;
  --radius-sm: 4px;
  --radius-base: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  /* ============ MOTION ============ */
  --duration-instant: 100ms;
  --duration-quick: 200ms;
  --duration-settle: 300ms;
  --duration-arrive: 400ms;
  --duration-considered: 600ms;

  --ease-settle: cubic-bezier(0.2, 0, 0.1, 1);
  --ease-gentle: cubic-bezier(0.4, 0, 0.4, 1);

  /* ============ MAX-WIDTHS ============ */
  --max-w-reading: 34rem;
  --max-w-form: 40rem;
  --max-w-content: 56rem;
  --max-w-wide: 72rem;
  --max-w-dashboard: 96rem;
}

[data-mode="dark"] {
  /* Surfaces — Tier-4 measurement-based correction (April 2026):
     calibrated to IMG_6085.jpg sampled values. Hue progresses with
     elevation (h=59→81→85) per §1 anchor 4 "Material, not paint" —
     this is the second material dimension the prior tokens missed.
     Tier-3's lightness bumps (L=0.22 / L=0.27) reverted to pre-
     Tier-3 values (L=0.20 / L=0.24) which match reference. */
  --surface-base: oklch(0.16 0.010 59);
  --surface-elevated: oklch(0.28 0.014 81);
  --surface-raised: oklch(0.32 0.016 85);
  --surface-sunken: oklch(0.13 0.010 55);

  /* Content — `--content-on-accent` symmetric with light mode (cream)
     per Aesthetic Arc Session 2. Was dark charcoal pre-Session-2 for
     the brass-era "glowing pill with dark text" aesthetic; now light
     cream both modes (terracotta dark enough for AAA cream contrast). */
  --content-strong: oklch(0.96 0.012 80);
  --content-base: oklch(0.90 0.014 75);
  --content-muted: oklch(0.72 0.014 70);
  --content-subtle: oklch(0.55 0.012 68);
  --content-on-accent: oklch(0.98 0.006 82);

  /* Borders */
  --border-subtle: oklch(0.35 0.015 65 / 0.5);
  --border-base: oklch(0.42 0.018 68 / 0.7);
  --border-strong: oklch(0.55 0.025 70);
  --border-accent: rgba(156, 86, 64, 0.70);

  /* Shadows — Tier-4 correction (April 2026):
     --shadow-highlight-top calibrated to reference measurement. */
  --shadow-color-subtle: oklch(0.11 0.020 65 / 0.35);
  --shadow-color-base: oklch(0.09 0.020 65 / 0.45);
  --shadow-color-strong: oklch(0.08 0.020 65 / 0.55);
  --shadow-highlight-top: oklch(0.32 0.010 61 / 0.9);

  /* Accent — single value across modes per the cross-mode rule. */
  --accent: oklch(0.46 0.10 39);
  --accent-hover: oklch(0.54 0.10 39);
  --accent-muted: rgba(156, 86, 64, 0.20);
  --accent-subtle: rgba(156, 86, 64, 0.10);

  /* Status */
  --status-error: oklch(0.68 0.17 25);
  --status-error-muted: oklch(0.28 0.08 25);
  --status-warning: oklch(0.76 0.14 65);
  --status-warning-muted: oklch(0.30 0.07 65);
  --status-success: oklch(0.70 0.13 135);
  --status-success-muted: oklch(0.28 0.06 135);
  --status-info: oklch(0.70 0.09 225);
  --status-info-muted: oklch(0.28 0.05 225);

  /* Dark mode shadows — Tier-2 three-layer composition:
     tight grounding shadow + soft halo + inset top-edge highlight. */
  --shadow-level-1: 0 1px 3px var(--shadow-color-strong), 0 4px 16px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top);
  --shadow-level-2: 0 2px 4px var(--shadow-color-strong), 0 12px 32px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top);
  --shadow-level-3: 0 3px 6px var(--shadow-color-strong), 0 24px 56px var(--shadow-color-strong), 0 8px 20px var(--shadow-color-strong), inset 0 3px 0 var(--shadow-highlight-top);

  /* Jewel-set inset ring — dark-mode override (Session 4.5 + 4.7).
     Strengthened to 0.50 alpha because charcoal substrate compresses
     low-lightness deltas. Session 4.7 lifted from initial 0.30. */
  --shadow-jewel-inset: inset 0 1px 2px rgba(0, 0, 0, 0.50);

  /* Widget elevation tier — dark-mode override (Session 4.7 + 4.8).
     Session 4.8 layered atmospheric shadow: charcoal substrate
     amplifies each layer (0.30 / 0.55 / 0.65 alpha). Combined with
     --widget-tablet-transform: translateY(-2px), the pin reads as
     floating object hovering above operations. */
  --widget-ambient-shadow:
    0 4px 12px -2px rgba(0, 0, 0, 0.30),
    0 16px 32px -4px rgba(0, 0, 0, 0.55),
    0 32px 56px -8px rgba(0, 0, 0, 0.65);

  /* Card material treatment — dark-mode overrides (Aesthetic Arc
     Session 4.6). Strengthens light-mode values to carry the same
     perceptual signal against charcoal substrate. Edge highlight
     transparent because shadow-level-1 already carries the warm
     top-edge cue via --shadow-highlight-top. See §3 mode-aware
     block. */
  --card-edge-highlight: transparent;
  --card-edge-shadow: rgba(0, 0, 0, 0.50);
  --card-ambient-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.45);
  --flag-press-shadow: rgba(0, 0, 0, 0.30);
}
```

### Tailwind configuration

Tailwind is configured to consume the CSS variables. The config extends rather than replaces the default theme, keeping Tailwind's spacing scale (which matches the 4px base from Section 5) while adding semantic tokens.

> **Implementation note — Tailwind v4 vs. v3:** Bridgeable uses **Tailwind v4** via `@tailwindcss/vite`, where theme configuration lives in an `@theme inline { ... }` block inside CSS, not in a separate `tailwind.config.js` file. The JS config example below is illustrative of the semantic tokens Tailwind should expose; the live implementation is in `frontend/src/index.css` (Aesthetic Arc Session 1). Translation rules:
> - `colors.surface.base = 'var(--surface-base)'` → `--color-surface-base: var(--surface-base);`
> - `fontSize['display-lg'] = [size, { lineHeight, fontWeight }]` → three lines: `--text-display-lg: ...;` + `--text-display-lg--line-height: ...;` + `--text-display-lg--font-weight: ...;`
> - `boxShadow['level-1'] = '...'` → `--shadow-level-1: var(--shadow-level-1);`
> - `transitionTimingFunction.settle` → `--ease-settle: var(--ease-settle);`
> - `maxWidth.reading` → `--container-reading: var(--max-w-reading);` (v4's `--container-*` generates `max-w-*` + `@container`)
> - `transitionDuration.quick` → `@utility duration-quick { transition-duration: var(--duration-quick); }` — Tailwind v4's `--duration-*` is NOT an auto-utility namespace, so explicit `@utility` declarations are required.
>
> The v3 JS config below is retained because it's the clearest semantic description of what Tailwind exposes; read it as intent, not as a file to author. See `frontend/src/index.css` + `frontend/src/styles/base.css` for the live mapping.

```js
// tailwind.config.js
import { fontFamily } from 'tailwindcss/defaultTheme';

export default {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['selector', '[data-mode="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: {
          base: 'var(--surface-base)',
          elevated: 'var(--surface-elevated)',
          raised: 'var(--surface-raised)',
          sunken: 'var(--surface-sunken)',
        },
        content: {
          strong: 'var(--content-strong)',
          base: 'var(--content-base)',
          muted: 'var(--content-muted)',
          subtle: 'var(--content-subtle)',
          'on-accent': 'var(--content-on-accent)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          base: 'var(--border-base)',
          strong: 'var(--border-strong)',
          accent: 'var(--border-accent)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          active: 'var(--accent-hover)',
          muted: 'var(--accent-muted)',
          subtle: 'var(--accent-subtle)',
        },
        status: {
          error: 'var(--status-error)',
          'error-muted': 'var(--status-error-muted)',
          warning: 'var(--status-warning)',
          'warning-muted': 'var(--status-warning-muted)',
          success: 'var(--status-success)',
          'success-muted': 'var(--status-success-muted)',
          info: 'var(--status-info)',
          'info-muted': 'var(--status-info-muted)',
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', ...fontFamily.sans],
        serif: ['IBM Plex Serif', ...fontFamily.serif],
        mono: ['IBM Plex Mono', ...fontFamily.mono],
      },
      fontSize: {
        'display-lg': ['var(--text-display-lg)', { lineHeight: '1.1', fontWeight: '500' }],
        'display': ['var(--text-display)', { lineHeight: '1.15', fontWeight: '500' }],
        'h1': ['var(--text-h1)', { lineHeight: '1.2', fontWeight: '500' }],
        'h2': ['var(--text-h2)', { lineHeight: '1.25', fontWeight: '500' }],
        'h3': ['var(--text-h3)', { lineHeight: '1.3', fontWeight: '500' }],
        'h4': ['var(--text-h4)', { lineHeight: '1.35', fontWeight: '500' }],
        'body': ['var(--text-body)', { lineHeight: '1.55' }],
        'body-sm': ['var(--text-body-sm)', { lineHeight: '1.5' }],
        'caption': ['var(--text-caption)', { lineHeight: '1.45' }],
        'micro': ['var(--text-micro)', { lineHeight: '1.4', letterSpacing: '0.01em' }],
      },
      borderRadius: {
        'sm': 'var(--radius-sm)',
        'DEFAULT': 'var(--radius-base)',
        'md': 'var(--radius-md)',
        'lg': 'var(--radius-lg)',
        'xl': 'var(--radius-xl)',
        'full': 'var(--radius-full)',
      },
      boxShadow: {
        'level-1': 'var(--shadow-level-1)',
        'level-2': 'var(--shadow-level-2)',
        'level-3': 'var(--shadow-level-3)',
      },
      transitionDuration: {
        'instant': 'var(--duration-instant)',
        'quick': 'var(--duration-quick)',
        'settle': 'var(--duration-settle)',
        'arrive': 'var(--duration-arrive)',
        'considered': 'var(--duration-considered)',
      },
      transitionTimingFunction: {
        'settle': 'var(--ease-settle)',
        'gentle': 'var(--ease-gentle)',
      },
      maxWidth: {
        'reading': 'var(--max-w-reading)',
        'form': 'var(--max-w-form)',
        'content': 'var(--max-w-content)',
        'wide': 'var(--max-w-wide)',
        'dashboard': 'var(--max-w-dashboard)',
      },
    },
  },
  plugins: [],
};
```

### Font loading

Plex is self-hosted via `@fontsource` packages. The subset-latin variants are used; full Unicode subsets are not needed for Bridgeable's English-only current scope.

**Install:**

```bash
npm install @fontsource/ibm-plex-sans @fontsource/ibm-plex-serif @fontsource/ibm-plex-mono
```

**Import in `fonts.css`:**

```css
/* IBM Plex Sans — 400 (Regular), 500 (Medium), 600 (Semibold) + 400 italic */
@import "@fontsource/ibm-plex-sans/400.css";
@import "@fontsource/ibm-plex-sans/400-italic.css";
@import "@fontsource/ibm-plex-sans/500.css";
@import "@fontsource/ibm-plex-sans/600.css";

/* IBM Plex Serif — 500 (Medium) only; display use */
@import "@fontsource/ibm-plex-serif/500.css";

/* IBM Plex Mono — 400 only */
@import "@fontsource/ibm-plex-mono/400.css";
```

**Preload the most-used weights** via Next.js / framework font preloading or manual `<link rel="preload">` tags. The most-used weights are Plex Sans 400 (body) and 500 (headings).

### `base.css`

Global resets and body defaults:

```css
*, *::before, *::after {
  box-sizing: border-box;
}

html {
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.55;
  color: var(--content-base);
  background: var(--surface-base);
  -webkit-text-size-adjust: 100%;
}

[data-mode="dark"] {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  min-height: 100vh;
}

h1, h2, h3, h4, h5, h6 {
  font-weight: 500;
  color: var(--content-strong);
  margin: 0;
}

p {
  margin: 0;
}

button {
  font-family: inherit;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: var(--duration-instant) !important;
    transition-duration: var(--duration-instant) !important;
    scroll-behavior: auto !important;
  }
}

/* Focus-visible default (components override with the accent ring) */
:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--surface-base),
    0 0 0 5px color-mix(in oklch, var(--accent) 40%, transparent);
  transition: box-shadow var(--duration-quick) var(--ease-settle);
}
```

### Component patterns — code examples

These are canonical implementations of common components. Sonnet uses these as starting points.

**Primary button:**

```jsx
function PrimaryButton({ children, ...props }) {
  return (
    <button
      className="
        inline-flex items-center gap-2
        px-5 py-2.5
        bg-accent hover:bg-accent-hover
        text-content-on-accent
        font-medium text-body-sm
        rounded
        shadow-level-1
        transition-colors duration-quick ease-settle
        active:scale-[0.97] transition-transform
        focus-visible:outline-none
      "
      {...props}
    >
      {children}
    </button>
  );
}
```

**Card (level 1):**

```jsx
function Card({ children, className = '' }) {
  return (
    <div
      className={`
        bg-surface-elevated
        rounded-md
        shadow-level-1
        p-6
        ${className}
      `}
    >
      {children}
    </div>
  );
}
```

**Form input:**

```jsx
function Input({ label, error, id, ...props }) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="text-body-sm font-medium text-content-base"
      >
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className="
          px-4 py-2.5
          bg-surface-raised
          border border-border-base
          rounded
          text-body text-content-strong
          transition-colors duration-quick ease-settle
          focus-visible:outline-none focus-visible:border-accent
        "
        {...props}
      />
      {error && (
        <span
          id={`${inputId}-error`}
          className="flex items-center gap-1.5 text-caption text-status-error"
        >
          <AlertCircle size={14} strokeWidth={1.5} />
          {error}
        </span>
      )}
    </div>
  );
}
```

**Modal:**

```jsx
function Modal({ open, onClose, title, children }) {
  // Focus trap, escape to close, backdrop click to close all handled
  // by Radix UI Dialog or equivalent — not re-implemented per component.

  return (
    <Dialog.Root open={open} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay className="
          fixed inset-0
          bg-black/40
          transition-opacity duration-arrive ease-settle
        " />
        <Dialog.Content className="
          fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
          w-full max-w-form
          bg-surface-raised
          rounded-lg
          shadow-level-2
          p-6
          transition-[opacity,transform] duration-arrive ease-settle
        ">
          <Dialog.Title className="text-h3 font-medium text-content-strong mb-2">
            {title}
          </Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

### Utility classes beyond Tailwind

A few patterns warrant custom utilities in `utilities.css`:

```css
@layer utilities {
  /* Reading measure — body prose */
  .prose-reading {
    max-width: var(--max-w-reading);
    font-size: var(--text-body);
    line-height: 1.55;
  }

  /* Tabular numerals for tables and financial displays */
  .tabular {
    font-variant-numeric: tabular-nums;
  }

  /* Elevation utilities */
  .elevated-card {
    background: var(--surface-elevated);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-level-1);
  }

  /* Accent focus ring — explicit utility for custom controls */
  .focus-ring-accent:focus-visible {
    outline: none;
    box-shadow:
      0 0 0 2px var(--surface-base),
      0 0 0 5px color-mix(in oklch, var(--accent) 40%, transparent);
    transition: box-shadow var(--duration-quick) var(--ease-settle);
  }
}
```

### Do / Don't examples

**DO: Use semantic tokens.**
```jsx
<div className="bg-surface-elevated text-content-base">
```

**DON'T: Use raw color values.**
```jsx
<div className="bg-[oklch(0.965_0.014_82)] text-[oklch(0.30_0.015_70)]">
```

**DO: Use the elevation shadow tokens.**
```jsx
<div className="shadow-level-1">
```

**DON'T: Compose shadows manually.**
```jsx
<div className="shadow-[0_2px_8px_rgba(0,0,0,0.1)]">
```

**DO: Use named durations and easings.**
```jsx
<div className="transition-colors duration-quick ease-settle">
```

**DON'T: Hardcode timing.**
```jsx
<div className="transition-colors duration-[180ms] ease-[cubic-bezier(0,0,0.2,1)]">
```

**DO: Use Plex Serif only for gravitas moments.**
```jsx
<h1 className="font-serif text-display">John Michael Smith</h1>
```

**DON'T: Use Plex Serif for UI chrome.**
```jsx
<button className="font-serif">Save</button>
```

**DO: Scale icon stroke with size.**
```jsx
<Check size={14} strokeWidth={1.5} />
<Check size={20} strokeWidth={2} />
```

**DON'T: Use default stroke at small sizes.**
```jsx
<Check size={12} />  {/* Lucide default 2px stroke is too heavy at 12px */}
```

### CI and tooling

Recommended tooling to enforce the design language mechanically:

- **ESLint rule** against arbitrary Tailwind values (e.g., `text-[#123456]`, `p-[17px]`). Forces tokens.
- **Stylelint** to forbid raw hex/rgb/hsl values in CSS files; oklch only.
- **Axe-core** integration tests on rendered components to catch accessibility regressions.
- **Visual regression testing** (Playwright snapshots) to catch unintended visual drift after design system changes.

These are recommendations, not currently enforced. They become increasingly valuable as the codebase grows past the single-developer stage.

### Layering tokens

Overlay-family components previously used literal `z-50` values inline (see `components/ui/dialog.tsx`, `popover.tsx`, `dropdown-menu.tsx`, `tooltip.tsx`). The literal-index approach works fine for a small overlay set but does not scale to a platform with three overlay tiers (dropdowns, modals, Focus) and a Command Bar that intentionally sits above everything except toasts.

Phase A Session 1 introduces a layering-token system. New overlay code uses these tokens via `style={{ zIndex: "var(--z-focus)" }}` rather than Tailwind `z-*` utilities (Tailwind v4 does not ship arbitrary `z-[var(--x)]` utilities by default, and adding them as `@theme` keys would overload the theme namespace for a small set of values). Existing `z-50` literals in the overlay family are not retrofit — refactor on natural-touch basis in a later cleanup session.

| Token | Value | Intended use |
|---|---|---|
| `--z-base` | `0` | Default content flow |
| `--z-elevated` | `10` | Cards, elevated surfaces, return pill |
| `--z-dropdown` | `50` | Dropdowns, peek panels |
| `--z-focus` | `100` | Focus primitive overlay (Phase A) |
| `--z-modal` | `105` | Dialogs, sheets, slide-overs. **Above `--z-focus`** so Dialogs opened from inside a Focus (e.g. QuickEdit from a scheduling card) render above the Focus Popup. Bumped from `80` in Phase A Session 4.2.6 after QuickEditDialog mounted successfully but rendered behind the Focus overlay, appearing invisible to the user. Focus is exclusive so no non-nested Dialog is simultaneously active — there is no conflict at this layer. |
| `--z-command-bar` | `110` | Command bar — intentionally above Focus + Modal per architecture, though it is hidden while a Focus is open per Phase A Session 1 decision |
| `--z-toast` | `120` | Toast notifications |
| `--z-tooltip` | `130` | Tooltips — topmost transient UI feedback. Above toast so a tooltip over a toast is still readable; added in Phase A Session 4.2.4 after tooltips inside Focus cores rendered at `z-50` and disappeared behind the Popup. |

Definition in `styles/tokens.css` mirrors the above verbatim per the tokens.css header discipline ("edit DESIGN_LANGUAGE.md first, then port the change here"). If you are adding a new overlay tier, add it in this table first with a clear rationale, then port to `tokens.css` in the same commit.

## Section 10 — Anti-Patterns

This section consolidates anti-patterns from every prior section into one reference. It is the document's diagnostic layer: when shipped UI feels wrong, this is where to look for what specifically broke.

Anti-patterns are organized by what they break. Each entry names the violation, the specific rule it breaks (with the section it comes from), and why it matters.

### Anti-patterns that break the object's character (Section 0)

These are the highest-altitude failures — the surface may pass every individual rule (tokens correct, spacing on-scale, type within the system) yet still feel wrong because the *register* drifted. When these fail, the platform reads as "warm SaaS" or "consumer app" rather than as Bridgeable.

**Generic-SaaS warm drift.** Violates the eight qualities (Section 0) collectively. Symptoms: warm gray surfaces with rounded-everything corners, accent buttons next to pastel illustrations, restrained typography next to celebratory animations, dim backdrop next to a stock smiling-team photo. Each individual choice may be on-token; the composite reads as Notion-with-a-different-palette rather than as Bridgeable. Fix: review the eight qualities. Identify which are absent. Pull each toward presence.

**Reference-family literalism.** Violates Section 0's "DO NOT translate" list. Translating the imaginative brief into surface decoration — leather-grain backgrounds because Filson, terracotta radial gradients because Leica top plate, workshop pegboard patterns because workshop. The references are imaginative briefs, not visual specifications. Character translates; artifacts do not.

**Trend-tied visual conventions.** Violates time-resistance (Section 0 quality 5). Anything that places Bridgeable in a specific year — current-decade gradient meshes, glassmorphism panes, neumorphism extrusions, soft-everything Apple consumer aesthetic, AI-aesthetic purple-to-pink-with-sparkles. Time-resistance fails if a screenshot tells you what year it shipped.

**Decorative warmth.** Violates Section 0's considered-materiality quality. Warmth used to make surfaces "feel friendly" rather than to express material. Pastel cream backgrounds with no purpose, soft drop shadows on flat content, accent borders on cards that don't need emphasis. Bridgeable warmth is materially earned — surfaces are warm because observed in warm light, not because warmth is decorative.

**Consumer-app maximalism.** Violates Section 0's workshop-tool-grade quality. Rounded-everything (radius >16px on standard surfaces), celebration moments (confetti, animated checkmarks with sparkles, "great job!" copy), illustrative onboarding tours, decorative empty states with cheerful illustrations replacing functional information. Correct in consumer software; wrong in operator software.

**Workshop aesthetic without workshop discipline.** Violates Section 0's calm-expensiveness quality combined with Section 1's deliberate-restraint. Information density without legibility — Bloomberg Terminal aesthetic without Bloomberg's decades of typography discipline. Density requires *more* design, not less. If a dense view is hard to scan, density became clutter.

When any of the above fires, refer to the **in-register calibration surfaces** named in Section 0 (DeliveryCard, post-4.4.2 Focus core, AncillaryPoolPin, QuickEditDialog, accent primary buttons). Pull the failing surface toward those references rather than toward generic SaaS conventions.

### Anti-patterns that break the warm-hue coherence

**Neutral gray backgrounds or shadows.** Violates the warm-hue family rule (Section 2). A single neutral gray element in an otherwise warm platform reads as "out of place" even when no one can articulate why. This is the single most common subtle drift — developers reach for neutral gray by reflex. The fix is always to pull the hue into the 70–95 warm family.

**Pure white or pure black.** Violates anchors 1 in both modes (Section 1). Pure white reads as clinical; pure black reads as void. Both break the material presence the platform depends on. No component should use `#fff`, `#000`, or their oklch equivalents. Light surfaces live in the warm-cream family; dark surfaces live in the warm-charcoal family.

**Blue-gray dark mode.** Violates dark-mode anchor 1 (Section 1) and the warm-family asymmetry rule (Section 2). A blue-gray dark mode reads as "office at night" — cold, institutional, generic. Bridgeable's dark mode is warm — leather, wood, lamplit. If the dark mode reads as cold, the hue has drifted out of the 55–75 range.

**Decorative color for its own sake.** Violates deliberate restraint (Section 1 meta-anchor). A button colored blue because blue looks friendly, an icon colored green because green looks fresh, a background tinted purple because purple looks sophisticated. Every color decision must be justified by what it communicates, not by aesthetic appeal in isolation.

### Anti-patterns that break the accent thread

**Multiple accent colors competing for primary emphasis.** Violates the cross-mode accent rule (Section 2). Deepened terracotta is *the* primary accent. If another color is competing for primary emphasis — a blue "Save" button next to a terracotta "Approve" button, for example — one of them is miscast. The accent marks primary action, focus, and emphasis. A secondary accent may exist but it does not compete for primary attention.

**Accent that shifts value across modes.** Violates the architectural-color rule (Section 2). The accent is single-value: `oklch(0.46 0.10 39)` in BOTH light and dark modes. If the light-mode accent and dark-mode accent read as different colors, someone has accidentally restored the brass-era asymmetric pattern. Both must sit at the locked oklch triplet.

**Hover that darkens instead of brightens.** Violates the universal lift rule (Section 2). `--accent-hover` is `oklch(0.54 0.10 39)` — brighter than the base accent — in both modes. The brass-era asymmetric pattern (light mode darkens for press-in, dark mode brightens for glow) is retired; hover universally brightens as a "lift signal" matching Apple Pro era execution standards (Linear, Stripe, Pro apps).

**Active state styled as button-press rather than selected-item.** Violates the two-token active-state pattern (Section 2). Active state in Bridgeable means "this is the currently selected item" (DateBox active, nav active, drop target). Implement via `bg-accent-subtle` background + `border-accent` border. NOT via a darker/brighter accent fill — there is no `--accent-active` token. If momentary press feedback is later needed, that introduces a new `--accent-active` token; until then, do not invent one.

**Accent used decoratively.** Violates deliberate restraint. The accent marks primary action, focus, emphasis, or the accent-muted backgrounds derived from it. Accent sprinkled through a UI for visual warmth — an accent border here, an accent divider there — dilutes the meaning of the accent. When accent appears, the eye should go there. Decorative accent stops being signal and becomes noise.

### Anti-patterns that break deliberate restraint

**Density that signals inability to decide what to remove.** Violates the meta-anchor (Section 1) and the density-is-allowed-but-clutter-is-not rule (Section 1). Dense views earn their density by making every element legible and purposeful. Cramming a dashboard full of elements because removing any felt arbitrary produces clutter. When density is necessary, it must be designed; when it's not, it must be removed.

**Decorative flourishes that serve no purpose.** Violates deliberate restraint. Gradients applied to cards for visual interest, subtle patterns in the background, "hero" animations on dashboard load. Every element must justify its presence. If the answer to "why is this here?" is "it looks nice," the element is a violation.

**Generic stock imagery.** Violates deliberate restraint and Section 7's imagery rules. Office workers smiling at laptops, handshakes, generic cityscapes. These read as stock and undermine the "curated, intentional, adult" character the platform depends on. No decorative photography on admin UI.

**Default Bootstrap / Material / Tailwind aesthetics.** Violates the generic-palette anti-rule from Section 2's "Deriving a new color" procedure. Default blue, default gray borders, default shadow stacks from generic libraries produce interfaces that look like every other SaaS platform. The whole point of this design language is that Bridgeable doesn't look generic.

### Anti-patterns that break mood coherence between modes

**Symmetric hues across modes.** Violates the warm-family asymmetry rule (Section 2). If light mode and dark mode use the same hue values for surfaces, dark mode reads as "daylight dimmed" rather than "evening lamplight." Light mode surfaces live at hue 80–92; dark mode surfaces live at hue 55–75. This asymmetry encodes the morning/evening difference.

**Dropping shadows in dark mode.** Violates the "shadows persist in dark mode" principle (Section 2 and Section 6). Dark mode shadows are warm, soft, low-contrast — but they exist. Flat dark UI reads as cold institutional; warm shadowed dark UI reads as intimate lounge.

**Light mode that reads as sterile.** Violates light anchor 1 (Section 1). If the light mode reads as clinical or near-white rather than as warm cream with material presence, the base surface has drifted toward pure white or its chroma is too low. Pull the base back toward the cream linen anchor.

**Material-as-decoration.** Violates the "material, not paint" anchor (Section 1) and the top-edge highlight rule (Section 2). Gradient surfaces applied to every card, glossy reflections on buttons, skeuomorphic textures. Material presence is subtle — it's the inset 1px top-edge highlight on elevated dark-mode surfaces, not a decorative gradient. If a user notices the material effect, it's too strong.

### Anti-patterns that break typography

**Plex Serif used for body text or UI chrome.** Violates Section 4's serif usage rules. Serif is a display face for gravitas moments. Using it for form labels, button text, or extended body prose produces interfaces that look like they're trying hard. The rule: serif only for decedent names, primary titles on high-stakes pages, signature moments.

**Plex Mono for regular numbers.** Violates Section 4. Prices in prose, dates in sentences, percentages in body text read better in Plex Sans with tabular figures. Mono is for alignment-required data (case IDs, timestamps in tables, code).

**Weight-soup.** Violates the three-weight discipline (Section 4). Semibold headings followed by semibold emphasis in body text followed by semibold labels in forms. Every piece of text fighting for attention means no piece of text gets it. Pick one level of emphasis per visual region.

**All-caps paragraphs.** Violates the typography anti-pattern list (Section 4). All-caps is for small labels (eyebrows, section tags). Longer all-caps text reads as shouting and becomes unreadable. Even all-caps headings should be short.

**Decorative italic.** Italic carries semantic meaning (titles of works, foreign terms, genuine emphasis). Italicizing for visual variety weakens the emphasis it's trying to create and produces interfaces that feel fussy.

**Wide reading measures.** Violates the 34rem / 62–72-character rule (Section 4, Section 5). Body text that stretches across the full width of a wide viewport is fatiguing to read. Every prose container has a max-width; no exceptions.

**Mixing non-Plex fonts.** Violates the single-voice principle (Section 4). Adding a third font family because "this heading would look nice in a different serif" breaks the coherence the whole type system depends on.

### Anti-patterns that break spacing and layout

**Off-scale spacing values.** Violates Section 5's 4px-base rule. 13px padding, 22px margin, 18px gap. If the value isn't a multiple of 4, it's wrong, regardless of how it looks.

**Global 12-column grid for non-dashboard pages.** Violates Section 5's layout approach. The 12-column grid is strictly a dashboard-component substrate. Applying it to page layouts produces rigid, form-fits-function UI that fights content-driven layouts.

**Cramped defaults.** Violates the generous-default bias (Section 5) and the "generous breathing room" anchor (Section 1). New components defaulting to the tight end of the spacing scale produce platforms that feel cramped even when spacing values are individually correct. The default is generous; tightening requires deliberate choice.

**Inconsistent max-widths for similar content.** Violates Section 5's max-width token system. Two case detail pages with different max-widths produce platforms that feel inconsistent even when individual pages look fine.

**Hero sections with excessive vertical padding.** Violates the deliberate-restraint meta-anchor. Pages starting with 160px of empty space before any content. `space-24` (96px) is the ceiling for rare signature moments, not a routine choice.

### Anti-patterns that break surface and behavior

**Hard drop shadows.** Violates Section 6's shadow specifications. `box-shadow: 2px 2px 0 black` reads as brutalist or MS Paint. Bridgeable shadows are soft, warm, and atmospheric.

**Over-rounded surfaces.** Violates Section 6's border radius scale. Radius above 16px on standard UI elements reads as consumer-app or playful. Bridgeable favors moderate rounding; 6px is the default.

**Sharp 90-degree corners on interactive elements.** Violates the restraint principle. Even 4px radius signals considered design; raw corners read as utilitarian.

**Browser-default easing.** Violates Section 6's motion rules. `transition: all 0.3s ease` produces generic motion. The platform uses `ease-settle` and `ease-gentle`.

**Excessive motion.** Violates deliberate restraint. Every hover transitioning, every element fading in on scroll, every UI state change animated. Motion is used where it aids comprehension, absent where it would be noise.

**Removing focus rings.** Violates Section 6 and Section 8. The single most common accessibility failure. `outline: none` without an equivalent replacement is forbidden.

**Elevation inversions.** Violates Section 6's monotonic elevation rule. A card with shadow depth greater than the modal it sits under produces incoherent depth perception.

### Anti-patterns that break iconography

**Mixing icon libraries.** Violates Section 7. One library (Lucide) across the entire platform. Under no circumstances is a second library imported "just for this one icon."

**Decorative icon colors.** Violates Section 7. Icons are colored by semantic meaning — status, interactivity, brand role — not by aesthetic preference. A blue trash icon because blue looks nice is wrong.

**Icon-only buttons for non-universal actions.** Violates Section 7 and Section 8. Approve, Reject, Delete, Archive all require labels. Only universal actions (close, menu, search) are safe as icon-only.

**Novel icon metaphors for standard actions.** Violates Section 7. Save is a check. Delete is a trash can. Inventing new metaphors for established actions forces users to guess.

**2px stroke at 12px size.** Violates the stroke-width rules in Section 7. Small icons use 1.5px stroke. Default stroke at small sizes reads as overweight.

**Inconsistent icon sizes within a single region.** Violates Section 7. A list where each item has an icon uses the same icon size across all items.

### Anti-patterns that break accessibility

**Removing focus rings.** Named again because it's the single most common violation. Forbidden. Section 6 and Section 8.

**Placeholder-as-label forms.** Violates Section 8. Placeholders disappear when users type, leaving no indication of what the field is. Use visible labels.

**Color-only status indication.** Violates WCAG 1.4.1 (Section 8). Red border with no text or icon fails users who can't distinguish color and screen reader users. Always pair color with text or icon.

**Clickable divs.** Violates Section 8. `<div onClick={...}>` is not a button. Use `<button>`.

**Icon-only buttons without `aria-label`.** Violates Section 8. The visual icon doesn't exist for screen readers.

**Disabling zoom.** Violates Section 8. Users must be able to zoom. `user-scalable=no` is forbidden.

**Tab traps without escape.** Violates Section 8. Modals and overlays that take focus but provide no keyboard dismiss path trap keyboard and screen reader users.

### Anti-patterns that break implementation

**Arbitrary Tailwind values.** Violates Section 9. `bg-[#f5f5f5]`, `p-[17px]`, `text-[14.5px]` bypass the token system. Every value should resolve to a design token.

**Raw color values in CSS.** Violates Section 9. Hex, rgb, and hsl are not used in tokens. oklch only. Values in CSS files outside the token definitions should reference variables, not raw values.

**Manual shadow composition.** Violates Section 9. Use `shadow-level-1`, `-2`, `-3`. Hand-composing shadows produces inconsistency and misses the dark-mode top-edge highlight.

**Hardcoded transition durations.** Violates Section 9. Named durations (`duration-quick`, `duration-settle`, etc.) only.

**Flash of wrong mode.** Violates Section 9's mode-switching requirements. Dark mode users seeing light mode flash on page load is a mode-switching implementation bug. The synchronous inline script in document head is required.

**Circular calibration — measuring rendered output against itself.**

Violates §1's reference-images-win-over-prose discipline. When calibrating tokens to a reference, the reference must be external to the implementation chain. Sampling a rendered UI artifact to calibrate the tokens that produced it creates a self-consistent measurement loop: the tokens will match the artifact, but that only proves consistency with the artifact, not fidelity to the mood anchor upstream. The artifact is already downstream of the tokens; reaching back to it for calibration closes the loop against itself.

**Rule:** When sampling for token calibration, the reference must be external to the platform's implementation chain — a photograph of a real space, a physical material swatch, a printed color card, an object the design language was originally derived from. Never a UI render, a Figma mockup generated against the current tokens, or a screenshot of the live platform.

**Detection questions (must answer all three before measuring):**

1. *Where did this image come from?* If it was generated in a chat session, rendered by the platform, or exported from a design tool configured against the current palette — it's inside the loop.
2. *Could this image have been produced without the current tokens existing?* If no, it's downstream of the tokens and unsuitable for calibration.
3. *Does this image depict physical material reality (a photograph of a real space/object) or does it depict a UI rendering?* Only the former is valid as a mood anchor.

If any answer puts the image inside the implementation chain, it cannot be used for color calibration. It may still be valid as a pattern reference (see §1) — but color decisions must come from external mood anchors only.

---

### How to use this section

**When reviewing shipped UI:**
- Scan the anti-pattern list mentally. Does anything on the page match an entry?
- If something feels off but no specific anti-pattern matches, the feel is probably tied to a Section 1 anchor — review those.
- If a component is failing multiple anti-patterns, it probably needs rebuilding, not patching.

**When building new components:**
- Don't consult this section proactively during every build — that produces defensive, generic work.
- Consult it when something feels off during review and you want to localize what's wrong.

**When updating this document:**
- New anti-patterns discovered through shipped experience belong here.
- Anti-patterns that turn out to have legitimate exceptions should be updated with the exception noted, not removed.
- This section grows as the platform grows; it's the accumulated diagnostic wisdom of the design language.

---

## Section 11 — Material Treatment Patterns

Eight canonical material treatment patterns. Established Aesthetic Arc Session 4 (April 26, 2026) as the platform's reference vocabulary for all surfaces beyond the foundational tokens. Where Sections 1–6 specify *substrate* (color, type, surface, motion), Section 11 specifies *treatment* (how those tokens compose into a card, a tablet, a status indicator, a switcher).

These patterns answer: "you have the tokens — now what does a *card* look like? What does a *floating tablet* look like? How do *status indicators* compose?" Section 0 governs *what* the platform feels like; Section 11 governs *how* recurring surface roles materialize that feel.

The patterns are reference-implementation-driven. Each cites the canonical component (`DeliveryCard`, `AncillaryPoolPin`, etc.) where the pattern is realized. Future surfaces matching the role apply the pattern; the canonical component is the source of truth for "what this looks like in code."

### Pattern 1 — Tablet treatment (floating widgets)

**The pattern.** Widgets read as summoned material objects floating in workspace, not as static UI containers. Per [PLATFORM_INTERACTION_MODEL.md](PLATFORM_INTERACTION_MODEL.md): tablets are the materialization unit; they float, are individually present, and don't enclose other content as containers.

**Composition:**
- **Drawn edges** — material composition that reads as physical edges, not soft shadow halos. The tablet has real structure.
- **Widget-tier elevation (Aesthetic Arc Session 4.7)** — tablets float MORE than core elements per the elevation hierarchy (substrate → core → cards within core → widgets). Composed via `--shadow-widget-tablet` token (`var(--shadow-level-1), var(--widget-ambient-shadow)`). The widget-ambient layer adds wider blur + larger y-offset + stronger alpha than `--card-ambient-shadow`, signaling "this object floats further from the work surface than cards do." See §3 "Widget elevation tier tokens" for the canonical token block + the complete hierarchy.
- **Surface lift** — `bg-surface-elevated` (or `/85` alpha + `backdrop-blur-sm` when sitting over a dimmed-blurred backdrop, e.g. inside Focus). The tablet is material; the substrate behind shows through subtly.
- **Sharp architectural corners (Aesthetic Arc Session 4.7 + 4.8)** — `rounded-none` (0px). Pattern 1 tablets are architectural materialized objects per Section 0 ("sharp at architectural scale, soft at touchable"). Calibration history: pre-Session-4.7 was `rounded-md` (8px) which read pillowy → Session 4.7 to `rounded-[2px]` (DOM-verified sharp) → **Session 4.8 visual verification** revealed the 2px corner read SOFT despite DOM-correctness because the frosted-glass surface treatment (bg/85 + backdrop-blur(8px)) fundamentally softens visible edges regardless of border-radius. Session 4.8 locked `rounded-none` as the irreducible-minimum sharpness within the canonical frosted-glass Pattern 1 surface treatment. **This is a Pattern 1 vs Pattern 2 corner distinction**: solid-fill surfaces (Pattern 2 cards, DateBoxes) carry architectural corners at 2px (the fill does the work); frosted-glass tablets (Pattern 1) need 0px because the semi-transparent + blurred fill blends edges into substrate. Same architectural register, different surface treatments require different corner values to produce equivalent perceptual sharpness.
- **Bezel with grip indicator (left side, 28px column)** — a structural left-edge zone where the user's eye lands when arranging the tablet. **28px dedicated column** with a 1px right border (`border-r border-border-subtle/30`) separating it from the content area. **Two short vertical grip lines** centered in the column (each ~12px tall × 2px wide, 2px apart, `bg-content-muted/30`) — the macOS column-resize-handle vocabulary. Always visible (subtle), not hover-revealed. Signals "this is a tablet you can grab and arrange," consistent with the Tony Stark / Jarvis interaction model.
- **Mono label header** — uppercase eyebrow in `font-mono` (Geist Mono) `text-micro tracking-wider` + a clean h3 subhead in `font-sans` (Geist). The label tells the user what tablet they're looking at without competing with content.
- **Count chip** in accent (terracotta) when applicable — small `font-mono` numeral on accent surface, jewelry-register signal.

**When to apply.** Any Canvas widget per the widget framework (`focus-registry.ts` + `widget-renderers.ts`). Future Pulse surface widgets, AncillaryPoolPin, drive-time matrix pins, staff availability pins. The tablet pattern is what makes the workspace feel like a workshop with tools-to-hand rather than a page with embedded panels.

**When NOT to apply.** Inline content that's part of the page flow (a card on a hub dashboard isn't a tablet — it's a card). Modal dialogs (those carry their own overlay-family chrome). The kanban core itself (it's the work surface, not a tablet floating on the work surface).

**Reference implementation.** [`AncillaryPoolPin`](frontend/src/components/dispatch/scheduling-focus/AncillaryPoolPin.tsx) — the canonical example post-Aesthetic-Arc-Session-4.7. Composition: 28px dedicated left-edge bezel column with two vertical grip lines (macOS column-resize-handle vocabulary, established Session 4.5), 2px sharp architectural corners (Session 4.7), widget-tier composite shadow `var(--shadow-widget-tablet)` for higher elevation than cards (Session 4.7), mono uppercase eyebrow ("ANCILLARY POOL"), terracotta count chip, surface-elevated/85 with backdrop-blur. The pin visibly floats further from the work surface than DeliveryCards do — the wider/deeper widget-ambient halo is the perceptual cue.

**Calibration history** (Pattern 1 reference component):
- Session 4 (initial): horizontal top bezel pill (Pattern 1 doc deviation)
- Session 4.5: restructured bezel to canonical left-side 28px column
- Session 4.6: card material treatment mode-aware calibration applied to pin's underlying surface tokens
- Session 4.7: sharp 2px corners + widget-tier elevation tokens (`--shadow-widget-tablet`) — pin now visibly floats above cards per the elevation hierarchy

### Pattern 2 — Card material treatment

**The pattern.** Cards across the platform share consistent material vocabulary so a dispatcher scanning the kanban builds one mental model that applies everywhere a card appears.

**Composition:**
- **Sharp architectural corners (Aesthetic Arc Session 4.7 + 4.8 surface-list lock)** — `rounded-[2px]` (2px) for solid-fill surfaces. Per Section 0 "sharp at architectural scale, soft at touchable" — operational cards are architectural elements (not touchable affordances). Pre-Session-4.7 was `rounded-md` (8px) which read pillowy; 2px reads as architectural precision.

  **Surfaces inheriting the 2px architectural-corner spec (Session 4.8 explicit list):**
  - DeliveryCard (Pattern 2 reference — solid `bg-surface-elevated` fill)
  - AncillaryCard (Pattern 2 inheritor when refactored — Session 5)
  - DateBox (peripheral interactive surface in Focus chrome — `bg-surface-elevated/50` semi-solid fill, still carries 2px sharply)
  - Future operational card surfaces (Pulse cards, peek panel entity cards, command-bar entity portals, briefing breakdown cards)
  - DeliveryCard inner body button (focus-ring outline target — consistency with outer card)
  - Drag overlay preview (preserves card chrome during drag — same 2px)

  **Surfaces NOT inheriting the 2px spec — Pattern 1 frosted-glass tablets** use `rounded-none` (0px) because frosted-glass surface treatment (bg/85 + backdrop-blur) softens visible edges at any border-radius value. See Pattern 1 corner-spec note for the calibration distinction.

  **Touchable controls (buttons, inputs, popovers, dialogs)** retain their primitive-defined corners (`rounded-md` typical) per Section 0 chef's-knife analogy — touchable affordances are softer than architectural elements. The 2px architectural lock applies to surface-level operational cards, not control-level interactive primitives.
- **Material chrome (Aesthetic Arc Session 4.5 + 4.6)** — the card composes a multi-layer box-shadow that reads as physical material rather than outlined panel. Required composition (in order):
  ```
  inset 0 1px 0 var(--card-edge-highlight)    /* top-edge catch-the-light */
  inset 0 -1px 0 var(--card-edge-shadow)      /* bottom-edge shadow line */
  var(--card-ambient-shadow)                   /* lift-from-substrate */
  var(--shadow-level-1)                        /* existing tight ground + atmospheric halo */
  ```
  The four card-material tokens are **mode-aware** (Session 4.6). Light mode: white-45% top highlight (visible catch-light on cream), black-20% bottom edge (soft hairline), `0 8px 20px -4px black 18%` ambient (soft lift). Dark mode: transparent top highlight (defers to shadow-level-1's existing 3px 90% warm top), black-50% bottom edge (visible on charcoal), `0 8px 24px -4px black 45%` ambient (strong atmospheric halo). Pre-Session-4.5 cards composed `bg-surface-elevated + shadow-level-1` only and read as flat outlined panels. Session 4.5 added the four tokens single-value-across-modes; Session 4.6 mode-tuned them per-substrate after visual verification confirmed single-value failed against actual substrate at both ends. See §3 "Card material treatment tokens" for the canonical mode-aware token table.
- **Proper-noun text in `font-display`** (Fraunces serif) at proper size — funeral home name as "the engraving," the most important text on the card. The serif treatment marks the proper noun (a person's family, a funeral home name, a cemetery name when proper) as different from the surrounding data; it carries the weight of a name.
- **Cemetery + city paired with mid-dot separator** — cemetery primary value at `text-content-base`, city in lower value (`text-content-muted`), mid-dot in `text-content-faint`. See Pattern 5 for the hierarchy rule.
- **Time and counts in `font-mono`** (Geist Mono) — numerals carry tabular alignment + precision register. Numerals at lighter weight than surrounding type label ("15:00 Funeral Home" — the digits read as data, the label as prose).
- **Vault info with mid-dot separator** — vault type · status, status in lower value, same hierarchy pattern.
- **Foot-row icons at consistent 14px stroke weight** — quiet color at rest (`text-content-muted`), brighten on hover. Lucide icons platform-canonical.
- **Jewel-set status indicators** — confirmation marks sit in recessed rings via `box-shadow: var(--shadow-jewel-inset)`, feel like physical jeweled inlays rather than flat circles. See Pattern 3.
- **Left-edge flags carrying signal meaning** — 2px wide accent flag with right-side press shadow. See Pattern 3.
- **Document badges as stamped reference numbers** — corner-mounted, mono numeral, terracotta, like reference marks on a precision instrument (when applicable).

**When to apply.** Any operational card surface — DeliveryCard, AncillaryCard, PeekPanel entity cards, Pulse operational cards, command-bar entity portals.

**When NOT to apply.** Hub-page summary cards (those are dashboard widgets — apply Pattern 1 if floating, or hub-card patterns separately). System notifications (those use Alert/Banner primitives).

**Reference implementation.** [`DeliveryCard`](frontend/src/components/dispatch/DeliveryCard.tsx) — post-Aesthetic-Arc-Session-4.7 the canonical example. Material chrome composition (mode-aware edge highlight + edge shadow + ambient drop + level-1), 2px sharp architectural corners, **3px** left-edge flag wired to hole-dug semantic with right-side `--flag-press-shadow`, jewel-set hole-dug indicator with `bg-surface-base` darker fill + strengthened `--shadow-jewel-inset`, funeral home name in font-display (Fraunces), times in font-mono, mid-dot hierarchy on cemetery/city + vault/equipment lines.

**Calibration history** (Pattern 2 reference component):
- Session 4: shadow-level-1 only — flat outlined panel
- Session 4.5: 4 single-value material tokens added — still flat in light mode (edge-highlight 5% warm-cream invisible on cream substrate)
- Session 4.6: 4 tokens converted to mode-aware (white-45% top in light, transparent in dark deferring to shadow-level-1's existing 3px 90% top) — passed material-lift verification both modes
- Session 4.7: flag width 2px → 3px (visible at production density), corners rounded-md → rounded-[2px] (architectural register), jewel-set badge bg → surface-base (visible recess) — all three gaps closed, reference component locked

### Pattern 3 — Status indicator system (two-channel)

**The pattern.** Status communicated through dual channels for legibility: a left-edge flag (color signal) and a corner-mounted jewel-set indicator (icon + recessed ring). Same semantic, redundant for scan-and-act surfaces where one channel might be missed.

**Composition:**
- **Left-edge flag (3px wide, canonical post-Session-4.7)** — 3px solid left border. Color carries the signal:
  - `border-l-accent` (terracotta) → needs-attention
  - `border-l-accent-confirmed` (sage-green, `#7d9170` ≈ `oklch(0.58 0.05 138)`) → confirmed
  - `border-l-transparent` (or absent) → neutral

  Calibration history: Pre-Session-4.5 3px width range (specified "2-3px"); `border-l-status-success` for confirmed. Session 4.5: 2px canonical + `--accent-confirmed` for confirmed (architectural-stamp register, distinct from status-success). **Session 4.7**: reverted to 3px after visual verification confirmed 2px on production-density cards (178-280px wide) was perceptually invisible. 3px reads as a clear architectural-edge accent. See §3 Accent tokens for the `--accent-confirmed` rationale.
- **Flag press shadow (Aesthetic Arc Session 4.5)** — when flag is non-transparent, the card carries an additional `inset 1px 0 0 var(--flag-press-shadow)` (1px right-of-flag pressed-in shadow, black 20%). Reads as "pressed-in detail beside the flag" rather than "paint stripe applied to the surface." Critical for flag-as-structural register; without it, the flag reads as paint.
- **Jewel-set indicator** — bottom-right or icon-row position. Composition (Session 4.7 canonical):
  - **Badge background**: `bg-surface-base` — substantially darker than card surface (`bg-surface-elevated`). The ~0.12 OKLCH lightness delta produces the visible "well below the surface" read. Pre-Session-4.7 used status-*-muted backgrounds with only ~0.04 delta — the badge looked like a colored chip, not a jeweled inlay.
  - **Inset shadow**: `box-shadow: var(--shadow-jewel-inset)` — mode-aware (light 0.25 / dark 0.50 — see §3 jewel-inset block). Reads as physical recess.
  - **Icon color**: maps to status semantic. `text-accent` for needs-attention (terracotta `?`), `text-accent-confirmed` for confirmed (sage-green `✓`), `text-content-muted` for neutral (explicit "no").

  Together: the icon sits IN the well, not ON the surface. The composition reads as physical jeweled inlay. Calibration: Pre-Session-4.5 hard-coded inline single-value `[inset_0_1px_2px_rgb(0_0_0/0.15)]`; Session 4.5 promoted to mode-aware `--shadow-jewel-inset` token (0.15/0.30); Session 4.7 strengthened both modes (0.25/0.50) AND swapped badge bg to surface-base for visible recess.

**When to apply.** Any card or row representing operational state where the dispatcher's primary read is "is this thing OK or does it need attention?" Examples: hole-dug status (DeliveryCard), proof-approval status (urn engraving), invoice-overdue status, certificate-pending status.

**When NOT to apply.** Generic interactive elements (those use focus rings + hover states). Status text alone (Alert / Banner primitives). The flag + jewel pattern is for cards/rows; not a global "every status everywhere" rule.

**Reference implementation.** [`DeliveryCard`](frontend/src/components/dispatch/DeliveryCard.tsx) post-Session-4.5 — 2px left-edge flag wired to hole-dug status (unknown=terracotta accent, yes=accent-confirmed sage-green, no=transparent), with right-side flag-press-shadow when flag is non-transparent; HoleDugBadge with `--shadow-jewel-inset` ring (mode-aware jewel-set treatment).

### Pattern 4 — Numeric mono treatment

**The pattern.** All numeric data values use `font-mono` (Geist Mono). Numerals lighter weight than surrounding type labels for hierarchy.

**Why the precision register matters.** A time, a count, a reference number is *data* — it has structure, it's read precisely, it benefits from tabular alignment when stacked. Putting numerals in mono signals "this is data, this is precise" — different from prose. The mono register is a vocabulary layer; the user develops a stable read of "mono = data" across the platform.

**Composition:**
- **Times** — `15:00`, `ETA 17:00`, `Start 6:30am`. Always `font-mono tabular-nums`.
- **Counts** — `3`, `+1`, `0`. Always `font-mono`.
- **Reference numbers** — document badges, case numbers (`FC-2026-0001`), invoice numbers. Always `font-mono`.
- **Compact dates** — `Apr 25`, `Apr 27`. Always `font-mono` when in tabular/eyebrow contexts. (Long-form dates in body prose may stay sans — judgment call.)
- **Weight discipline** — numerals at 400 (regular) when paired with 500 (medium) labels. The label is the noun, the data is the value; visual weight reflects that.

**When to apply.** Times, counts, reference numbers, dates in compact form, technical data values. Eyebrow uppercase labels (precision register fits even though they're not numbers — see Pattern 1's mono label header).

**When NOT to apply.** Numbers in prose ("there are three drivers" → font-sans, not font-mono — the number is part of the sentence, not data). Phone numbers and addresses (those read more naturally in font-sans).

**Reference implementation.** Times across DeliveryCard (`15:00 Church · ETA 17:00`), count chips on AncillaryPoolPin (terracotta count chip), date boxes in scheduling switcher (`Apr 24` / `Apr 26`).

### Pattern 5 — Mid-dot separators with hierarchy

**The pattern.** Compress related-but-different-priority data into a single line with mid-dot separators (` · `), assigning value hierarchy via color tokens.

**Composition:**
- Mid-dot character: `·` (U+00B7 middle dot) wrapped in `text-content-faint` (or `text-content-muted` if `--content-faint` token absent — substrate dependent)
- Primary value: `text-content-strong` or `text-content-base`
- Secondary values: `text-content-muted`
- Tertiary values: `text-content-muted` or `text-content-faint`
- Spacing: ` · ` (space, mid-dot, space) — narrow but readable

**Why this pattern works.** Lines like "Cemetery · City · Vault" carry related data with different operational priority. The dispatcher cares MOST about cemetery (where), then city (which one if disambiguation needed), then vault (specifics). Visual hierarchy via color (not size) keeps the line scannable while the order of importance reads at a glance.

**When to apply.** Multi-value lines on cards where values are related but ranked. Examples: "Cemetery · City" on DeliveryCard, "Vault · Equipment" on DeliveryCard, "Customer · Order #" on operational cards, "Family · Date" on case lists.

**When NOT to apply.** Two-value pairs that are equally weighted (use commas or layout). Three-plus-value lists where order isn't meaningful (use tags or chips). Decorative chrome ("Fast · Reliable · Honest" marketing copy doesn't belong here).

**Reference implementation.** [`DeliveryCard`](frontend/src/components/dispatch/DeliveryCard.tsx) — cemetery + city, vault + equipment, time + location + ETA all use the pattern.

### Pattern 6 — Day switcher with anchor hierarchy

**The pattern.** Multi-day navigation with a dominant center day and smaller satellite peek/slide affordances flanking it.

**Composition:**
- **Eyebrow above center** — `font-mono text-micro uppercase tracking-wider text-content-muted` ("SCHEDULING" or similar surface label).
- **Center day in `font-display`** (Fraunces serif) at H3 size, clickable as the popover trigger for any-day jump. Architectural weight at the center.
- **Flanking date boxes at smaller scale** — peek/slide affordances per Phase 4.4.3. Subtler treatment than center: small footprint, transparent surface, full-strength border (per Aesthetic Arc Session 1.6 calibration), `font-mono` date numerals at 13px, eyebrow weekday at micro tracking-wider.
- **Active state on satellites** — brass jewelry: `border-accent` + `bg-accent-subtle/50` (cross-surface vocabulary with PoolItem hover + DeliveryCard attach feedback).

**When to apply.** Multi-day or multi-period navigation surfaces. Funeral Scheduling Focus header (canonical), future scheduling boards, calendar pickers in compact form.

**When NOT to apply.** Single-period surfaces (no flanking needed). Date pickers proper (those use the standard Calendar primitive). Generic timeline / activity feeds (different mental model — show all, no center).

**Reference implementation.** [`SchedulingKanbanCore`](frontend/src/components/dispatch/scheduling-focus/SchedulingKanbanCore.tsx) header — eyebrow + center H2 with chevron + flanking DateBoxes. Pattern established Phase 4.4.3 (Aesthetic Arc Session 0); refined through Sessions 1, 1.5, 1.6.

### Pattern 7 — Column header treatment

**The pattern.** Column headers (kanban driver lanes, Unassigned column, future grouped surfaces) share consistent visual vocabulary so the user reads "this is a column" identically across columns.

**Composition:**
- **Column name in `font-sans`** (Geist) at appropriate weight — typically `text-body-sm font-medium text-content-strong`.
- **Hairline divider underneath** — 1px `border-base` or `border-subtle`, full column width.
- **Count in `font-mono`** — small numeral, `text-caption text-content-muted` (or `text-content-subtle` when count is zero).
- **"Unassigned" italic in accent color** — terracotta italic (subtle but signals "this is the one that's different from the regular driver columns"). Optional sub-label "needs driver" in `font-mono text-micro uppercase tracking-wider text-content-muted` right-aligned ("stamped-metal label" register).

**When to apply.** Any column header in a multi-column layout where columns are peers but might include a "special" column (Unassigned, Backlog, etc).

**When NOT to apply.** Table column headers (those use the Table primitive's existing treatment). Section headers in single-column layouts (those are Section primitives, not column headers).

**Reference implementation.** [`SchedulingKanbanCore`](frontend/src/components/dispatch/scheduling-focus/SchedulingKanbanCore.tsx) `SchedulingLane` — driver lane headers + Unassigned lane header. Refinement to apply Pattern 7 fully scheduled for Aesthetic Arc Session 5.

### Pattern 8 — Schedule status with jewel-style indicators

**The pattern.** Status notes attached to a scheduling state ("Schedule finalized at 2pm", "Drag-rearrange will revert to draft", etc.) use jewel-style indicators with interactive consequence affordance.

**Composition:**
- **Jewel-set status mark** — small icon (CheckCircle, AlertCircle) in a recessed ring with faint glow (`box-shadow: inset 0 1px 2px ... + 0 0 8px var(--status-success)/20%`). Color matches semantic (success-green, warning-amber, accent-terracotta).
- **Status text in `font-sans`** body weight — readable, not decorative.
- **Interactive consequences underlined dotted in accent** — when text describes a consequence ("…will revert to draft"), the consequence span carries `border-bottom: 1px dotted var(--accent)` or `text-decoration: dotted underline accent` to signal "this is interactive — the action it describes is real."

**When to apply.** Status notes on scheduling surfaces (finalize banner, draft banner, revert warning). Future state-machine annotations on workflow surfaces.

**When NOT to apply.** Generic Alert / Banner patterns (those use the Alert primitive). Inline status pills (those use StatusPill).

**Reference implementation.** [`SchedulingKanbanCore`](frontend/src/components/dispatch/scheduling-focus/SchedulingKanbanCore.tsx) finalize-status note ("Schedule finalized. Drag-rearrange will revert to draft.") — initial implementation Phase 3 / Session 1; full Pattern 8 application scheduled for Aesthetic Arc Session 5+.

### Cross-references

These patterns compose. A DeliveryCard applies Patterns 2 (card material), 3 (status two-channel), 4 (numeric mono), and 5 (mid-dot hierarchy). An AncillaryPoolPin applies Patterns 1 (tablet) and 4 (mono labels + count chip). A SchedulingKanbanCore header applies Patterns 6 (day switcher) and 7 (column header) and (in the finalize note) Pattern 8.

When designing a new surface:
1. Identify the surface's role (card? tablet? column header? status note?).
2. Apply the relevant pattern from this section.
3. Verify against Section 0 thesis tests (would the same team have made this?).
4. Verify against Section 11's "When NOT to apply" guards — patterns are meant for specific roles, not general aesthetic decoration.

When the platform's design vocabulary needs a new pattern (a role not covered by the eight above), add a new pattern to this section in a numbered slot. Document role, composition, when-to-apply, when-not-to-apply, and reference implementation. Patterns are the platform's shared design DNA at the surface-treatment layer; growing the pattern library is how the platform's vocabulary deepens.

---

## Section 12 — Widget Library Architecture

Widgets are the platform's universal materialization unit. A widget is a self-contained, reusable piece of operational content with a declared visual contract, multi-variant density taxonomy, vertical-aware visibility, and surface-flexible composition. Widgets land on Pulse (Monitor), Focus (Decide), Spaces (Configure), and command bar peek panel content (Act) — same library, different surfaces.

This section defines the widget contract + variant taxonomy + visibility model + composition rules. Section 11 Pattern 1 is the visual contract widgets inherit; Section 12 is the architectural contract that turns a Pattern 1 tablet into a registered, configurable, vertical-scoped, multi-variant widget.

Established Widget Library spec session (April 2026), post-investigation deliverable. Subsequent implementation phases tracked in [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md) widget library subsection + [AESTHETIC_ARC.md](AESTHETIC_ARC.md) session log.

### 12.1 Foundational frame

**Widgets are the universal materialization unit.** Per [PLATFORM_INTERACTION_MODEL.md](PLATFORM_INTERACTION_MODEL.md), the platform's interaction model is *summon → arrange → park → dismiss* with floating tablets as the materialization unit. Widgets ARE those tablets at the architectural layer — registered components with consistent shape, summonable from the catalog, arrangeable on Pulse / Focus / sidebar, dismissible per surface lifecycle.

**Universal across surfaces.**
- **Pulse (Monitor)**: composed widget grid per Space, role-driven defaults, drag-rearrange + resize-to-variant-swap.
- **Focus (Decide)**: canvas-pinned widgets at canonical anchors (Pattern 1 tablet treatment); Focus core element renders the workspace, surrounding widgets reference it.
- **Spaces (Configure)**: widget pins in sidebar render at Glance variant; click navigates to fuller variant on Pulse OR opens floating tablet.
- **Command bar (Act)**: peek panels stay separately routed (per entity type), but their content composition USES widget components — visual language unified, routing primitive distinct.
- **Operations Board / Vault Overview / hub dashboards (legacy)**: existing grid surfaces continue working; widgets migrate to unified contract incrementally "as touched."

**Inherits Pattern 1 (Section 11) as visual contract.** Every widget is a Pattern 1 tablet at heart. The composition principles — frosted-glass surface (or solid-fill on opaque substrates) + drawn edges via shadow-level-1 + bezel + grip indicator on left side + mono label header + terracotta count chip when applicable — apply across all widgets. Variant-specific chrome reduction (Glance omits bezel + eyebrow) is the only canonical deviation.

**Inherits widget elevation tier (Section 3) for floating surfaces.** Widgets that float (Focus canvas tablets, command bar tablets, future Pulse pins) compose `var(--shadow-widget-tablet)` + `transform: var(--widget-tablet-transform)` per Aesthetic Arc Session 4.8 calibration. Widgets that mount in fixed-grid surfaces (Pulse grid cells, Vault Overview, Operations Board) use `var(--card-ambient-shadow)` (the card-tier elevation) — they ARE cards at that point, not floating tablets.

**Architectural payoff.** A widget like `recent_activity` declares once, renders across four surfaces with surface-appropriate variant + chrome. A vertical-specific widget like `funeral_schedule` is invisible to a manufacturing tenant by construction (4-axis filter §12.4). The catalog is one consistent flow for the user: pick a widget, pick where it lives. The platform produces a Pulse for one tenant that's structurally identical to another's, but visibly different by virtue of vertical-aware filtering — which is the architectural payoff Section 12 delivers.

### 12.2 Variant taxonomy

Every widget declares one or more variants. Variants are first-class citizens, not bolted-on size modes. **Glance / Brief / Detail / Deep** is the canonical four-tier taxonomy.

| Variant | Density | Default surfaces | Typical content |
|---|---|---|---|
| **Glance** | Minimal | Sidebar pin, Pulse rail, future Watch tier | Single number / icon + short label; optional accent count chip; no header chrome |
| **Brief** | Focused | Pulse grid 2×1, Focus stack tier, sidebar mobile | Header + 3-5 row list OR single chart OR small KPI cluster |
| **Detail** | Rich | Pulse grid 2×2 / 3×2, Focus canvas tier, Spaces dashboard | Header + scrollable list with secondary metadata + interactions |
| **Deep** | Maximum | Focus canvas tier, dedicated Pulse zone, modal on small surfaces | Section-stacked content; multi-pane; dense data; the widget at full editorial scope |

**Names map to user mental model.** "Give me a brief on cemetery status" → Brief variant. "I want the detail on this customer" → Detail variant. "Open the deep view of the pour schedule" → Deep variant. "Just the glance" → the count + label. The names reinforce platform identity *and* compose naturally with how operators speak.

**Names future-proof surface metaphors.** Glance = Watch tier (when Bridgeable Watch ships). Brief = phone tier. Detail = tablet/desktop tier. Deep = primary work surface. The taxonomy ports cleanly across form factors without rename churn.

**Variant compatibility matrix.**

| Variant | Canvas (Focus) | Grid (Pulse / Spaces dashboard / Vault Overview) | Stack rail (mobile Focus) | Floating tablet (command bar peek) | Sidebar pin |
|---|---|---|---|---|---|
| Glance | ✗ (too small) | ✓ (1×1) | ✓ (compressed) | ✓ | ✓ |
| Brief | ✓ | ✓ (2×1 typical) | ✓ | ✓ | ✗ (too big for sidebar) |
| Detail | ✓ | ✓ (2×2 typical) | ✓ (scroll-snap one tile) | ✗ (too big) | ✗ |
| Deep | ✓ | ✓ (full-row) | ✗ (use modal expand) | ✗ | ✗ |

**Variant defaults per surface.**
- Pulse pin: surface picks **Brief** as the universal default.
- Spaces sidebar pin: **Glance** (the only valid sidebar variant).
- Focus canvas pin: **Brief** or **Detail** (dispatcher decides; tablets need real estate).
- Command bar peek panel: **Brief** (focused work surface, action-with-content).
- Operations Board / Vault Overview: existing `default_size` becomes the **Brief** variant; other variants land incrementally "as touched."

**User-driven variant change.**
- Pulse + dashboard surfaces: drag-resize triggers variant swap when crossing variant breakpoints.
- Focus canvas: explicit variant picker in WidgetChrome (right-click menu / settings popover).
- Spaces sidebar: Glance only — to upsize, user repins to Pulse instead.
- Command bar: Brief only — to upsize, user opens Focus.

**Intelligence-driven variant selection (Phase W-5, post-September).** Defaults are role-driven + surface-driven (this section). Intelligence-suggested variants based on observed engagement + available space land Phase W-5. Phase W-1 through W-4 ship "default + manual" only. The taxonomy is forward-compatible.

**Anti-patterns.**

*Variant-per-component duplication.* Don't ship four separate React components per widget. Use ONE component that receives `variant_id` as a prop and switches internal rendering. Internal switch on `variant_id` keeps each widget's state, data hooks, and core logic in one file. Grid sizing CSS lives on the surface, not the widget.

*Variants as visibility toggles.* Glance ≠ "hide most fields"; Detail ≠ "show everything." Each variant has a *deliberate* content scope:
- **Glance**: the one number that matters
- **Brief**: the actionable list (3-5 items)
- **Detail**: the scrollable workspace with metadata + interactions
- **Deep**: the complete view, multi-section

Variants reflect intent, not just spatial budget. A widget with the same content rendered at 4 different sizes is doing variants wrong. A widget showing different *editorial* density per variant is doing variants right.

*Variants without surface compatibility declarations.* If a widget doesn't have a Glance variant, it can't be sidebar-pinned. The compatibility matrix is enforced — not aspirational. If a surface needs a variant the widget doesn't have, the widget is unavailable on that surface (catalog UI hides it; defense in depth at fetch + render).

### 12.3 Widget contract

The unified contract single-sources the widget definition. Both canvas and dashboard widgets adopt this shape; surface discriminator on props lets one component render correctly across surfaces.

**`WidgetDefinition<TConfig>`** (single source of truth):

```typescript
type WidgetSurface =
  | "pulse_grid"          // Pulse responsive grid
  | "focus_canvas"        // Focus free-form canvas
  | "focus_stack"         // Focus stack rail (mobile tier)
  | "spaces_pin"          // Spaces sidebar pin
  | "floating_tablet"     // command bar floating tablet
  | "dashboard_grid"      // Operations Board / Vault Overview / hub dashboards
  | "peek_inline"         // peek panel content composition (no chrome)

type Vertical =
  | "manufacturing"
  | "funeral_home"
  | "cemetery"
  | "crematory"

interface WidgetDefinition<TConfig = unknown> {
  // Identity
  widget_id: string                    // dot-namespaced, e.g., "scheduling.ancillary-pool"
  display_name: string                 // catalog UI human label
  description: string                  // catalog browsable description
  icon: string                         // Lucide icon name; rendered in header + catalog tile

  // Variant declaration (Glance / Brief / Detail / Deep)
  variants: WidgetVariant[]            // ordered, default first; at least one required
  default_variant_id: string           // resolves to one of variants[].variant_id

  // Visibility & gating (4-axis filter — see §12.4)
  required_permission?: string         // role-based, e.g., "delivery.view"
  required_module?: string             // tenant module flag (`company_modules` table)
  required_extension?: string          // cross-tenant integration (e.g., "urn_sales")
  required_vertical?: Vertical[] | "*" // vertical scoping; array = any-of, "*" = cross-vertical (default if omitted)
  required_role?: string[]             // optional, finer-grained than permission

  // Surface compatibility
  supported_surfaces: WidgetSurface[]  // which surfaces this widget can render on
  default_surfaces: WidgetSurface[]    // which surfaces seed this widget by default in role-driven layouts

  // Per-instance configuration
  config_schema?: ConfigSchema<TConfig> // shape validated; reuses saved-view config schema patterns
  default_config?: TConfig

  // Intelligence integration (Phase W-5)
  intelligence_keywords: string[]      // discovery hints — when Intelligence might surface this widget
  intelligence_relevance?: RelevanceFn // optional ranking signal for catalog ordering / variant selection
}

interface WidgetVariant {
  variant_id: "glance" | "brief" | "detail" | "deep"

  // Sizing — both grid + free-form supported
  grid_size: { cols: number; rows: number }              // for fixed-grid surfaces
  canvas_size: { width: number; height: number | "auto"; maxHeight?: number }  // for free-form surfaces

  // Component
  component: ComponentType<WidgetVariantProps<TConfig>>
  density: "minimal" | "focused" | "rich" | "deep"       // metadata for Intelligence + UI

  // Hard constraints
  min_dimensions?: { width: number; height: number }      // surface refuses smaller
  required_features?: string[]                            // some variants need extra context (e.g., "drag-context", "dnd-kit-context")
}
```

**`WidgetVariantProps`** (the per-component contract):

```typescript
interface WidgetVariantProps<TConfig = unknown> {
  widget_id: string                    // unique instance id (telemetry, drag, persistence)
  config: TConfig                      // resolved per-instance config (default merged with user overrides)
  surface: WidgetSurface               // discriminator — widget adapts internal layout per surface
  variant_id: "glance" | "brief" | "detail" | "deep"

  // Surface-injected context (optional, depending on surface)
  size_hint?: { width: number; height: number }          // computed pixel dimensions for this slot
  is_edit_mode?: boolean                                  // grid surfaces in edit mode
  is_active?: boolean                                     // for stacked / icon-tier widgets, which is currently visible

  // No data props — data ownership stays with widgets via feature contexts (canvas convention) or shared hooks (dashboard convention)
}
```

**Key contract decisions.**

- **Single component per widget**, internal switch on `variant_id`. Reduces duplication, keeps state + data hooks shared, makes variant-aware logic obvious. Per Decision 5 in spec session.
- **Data ownership flexible per surface convention.** Canvas widgets continue using feature contexts (e.g., `useSchedulingFocus()`); dashboard widgets continue using `useWidgetData(url)`; SavedView-backed widgets use `executeSavedView()`. The contract doesn't dictate. Per Decision 6.
- **No mandatory lifecycle hooks.** React's mount / unmount + props are the contract. Surface-level chrome (`WidgetChrome` for canvas, `WidgetWrapper` for grid, future `TabletShell` for floating) handles drag / resize / dismiss; widgets don't observe those.
- **Surface discriminator on props.** A widget rendering on Pulse grid vs Focus canvas vs floating tablet may want to adapt internal layout (e.g., omit secondary actions on grid, expand them on canvas). The discriminator gives the widget the signal without forcing a separate component.
- **Per-instance configuration via `config_schema`.** Reuses the same shape as saved-view config schemas (Phase 2 UI/UX arc). A widget like `saved_view` accepts `config = { view_id }`; `funeral_schedule` accepts `config = { date_offset, finalize_filter? }`; `recent_activity` accepts `config = { entity_types?, limit? }`. Validated against schema; user overrides stored per-instance.

### 12.4 Visibility & gating model

Widgets gate visibility on **five orthogonal axes**, all evaluated AND-wise. Defense-in-depth: filter applied at three points (catalog UI fetch, layout fetch, render dispatch) so a widget never accidentally renders for a user who shouldn't see it.

**The five axes.**

1. **Permission** (`required_permission`) — role-based gate. The user must hold the named permission via their role assignment. Examples: `delivery.view`, `customers.view`, `invoice.approve`. Backed by existing role / permission / role_permissions tables.
2. **Module** (`required_module`) — tenant capability flag. The tenant must have the named module enabled via `company_modules` table. Examples: `crm`, `accounting`, `scheduling`. Cross-vertical capability gates.
3. **Extension** (`required_extension`) — opt-in cross-tenant integration. The tenant must have the extension active via `tenant_extensions`. Examples: `urn_sales`, `wastewater`, `redi_rock`, `rosetta`, `npca_audit_prep`. Extensions are the *front door for installing capabilities*; not every product line is an extension (vault is built-in baseline — see axis 5).
4. **Vertical** (`required_vertical`) — industry preset. The tenant's `Company.vertical` value must match one of the declared verticals, OR the widget declares `"*"` (cross-vertical, default).
5. **Product Line** (`required_product_line`) — operational scoping. The tenant must have the named product line activated via `tenant_product_lines.is_enabled = True`, OR the widget declares `"*"` (cross-line, default). Per [BRIDGEABLE_MASTER §5.2.1](BRIDGEABLE_MASTER.md), product line is the *operational reality* of what the tenant runs; distinct from extension (the activation surface). Vault is auto-seeded baseline for manufacturing-vertical tenants without extension activation; vault widgets gate on `required_product_line: ["vault"]`.

**Composition.** All five axes are AND-evaluated. A widget like `urn_catalog_status` declares:
```typescript
required_vertical: ["manufacturing"],
required_extension: "urn_sales",
required_product_line: ["urn_sales"],
required_permission: "products.view",
```
The widget is visible to a user only if: tenant.vertical = "manufacturing" AND tenant has `urn_sales` extension AND tenant has `urn_sales` product line activated AND user has `products.view` permission. Composable, predictable, declarative.

A widget like `vault_schedule` declares (note no extension required — vault is baseline, not extension-installed):
```typescript
required_vertical: ["manufacturing"],
required_product_line: ["vault"],
required_permission: "production.view",
```

**The `required_vertical` semantics.**
- `["funeral_home"]` — single-vertical (visible only to funeral_home tenants)
- `["funeral_home", "cemetery"]` — multi-vertical (visible to either)
- `"*"` — cross-vertical (visible to all verticals, default if omitted)

**The `required_product_line` semantics.**
- `["vault"]` — single-line (visible only when vault product line activated for the tenant)
- `["vault", "redi_rock"]` — multi-line (visible when either line activated)
- `"*"` — cross-line (visible regardless of which lines the tenant runs, default if omitted)

Per Decision 9, `required_vertical` is **optional with default `"*"`**, and `required_product_line` follows the same convention. Forces explicit declaration only for line-specific widgets, not every widget. Cross-line widgets (`recent_activity`, `today`, `operator_profile`) declare `"*"` or omit. Per-line widgets (`vault_schedule`, `redi_rock_schedule`, `wastewater_schedule`, `urn_catalog_status`) declare their line(s) explicitly.

**Defense-in-depth filter sites.**
1. **Catalog UI fetch** (`/widgets/available?page_context=...`): backend filters by all five axes; response is the visible-to-this-user catalog. Catalog UI shows ONLY available widgets.
2. **Layout fetch** (`/widgets/layout?page_context=...`): backend filters layout entries by current visibility; widgets the user has lost access to (e.g., vertical change, role change, extension deactivation, product-line deactivation) are stripped from the layout response. Persisted layout retains them; rendered layout doesn't show them.
3. **Render dispatch**: `getWidgetRenderer(widget_id)` checks current visibility one more time at render. If the widget is somehow in the layout but the user fails the gate, render returns a "widget no longer available" placeholder (recovery path; rare).

**Invisible-not-disabled discipline.** A widget the user can't see is not rendered as locked / grayed-out / "Pro feature" gated. It's simply absent from the catalog. The user doesn't perceive the existence of widgets they can't access. This matches Section 0 calibration ("calm by default, intentional materialization") and the broader platform discipline of inviting invitations vs gated reveals.

**Pattern reuse.** This 5-axis filter mirrors `vault.hub_registry`'s `required_permission` + `required_module` + `required_extension` triple, extended with `required_vertical` and `required_product_line`. Same evaluation logic, same defense-in-depth pattern. The widget library inherits the discipline; consumers (catalog UI, dashboard hooks, render dispatch) reuse the filter helper.

**Mode-aware rendering vs. mode-aware visibility.** Operating mode (`production` / `purchase` / `hybrid`) is **NOT a sixth axis** — operating mode does not gate visibility. Per-line mode-aware widgets (`vault_schedule`, `line_status`) are visible whenever the line is activated; the widget's render path branches on `TenantProductLine.config["operating_mode"]`. Production-mode tenants see pour calendar; purchase-mode tenants see incoming PO calendar; hybrid-mode tenants see unified composition. Same widget, mode-aware rendering. Visibility = "is this line activated"; rendering = "in what mode does this line operate." Two distinct concerns, intentionally separated.

### 12.5 Composition rules per surface

Each surface that hosts widgets has specific layout, lifecycle, persistence, and variant-default conventions. The unified contract (§12.3) carries through; the surface discipline differs.

**Catalog filtering carries through every surface.** The 5-axis filter (§12.4) — including the product-line axis — applies at catalog fetch for every surface below. A user on a manufacturing tenant with vault + urn_sales lines activated sees `vault_schedule` and `urn_catalog_status` in the catalog. A user on the same tenant whose lines drop urn_sales (admin deactivates the extension or product line) loses `urn_catalog_status` from their catalog the next fetch — Pulse layouts strip it, Spaces sidebar pin grays it, Focus removes it. **Product-line filtering is uniform across surfaces**; mode-aware rendering happens *inside* the widget once visibility passes.

**Focus (Decide) — canvas free-form, anchor-positioned.**
- **Layout style**: 8-anchor positioning (top-left / top-center / top-right / left-rail / right-rail / bottom-left / bottom-center / bottom-right) + offset + width / height. Existing canvas widget primitive (Phase 4.3b.3.1 + Aesthetic Arc Session 4.8).
- **Lifecycle**: mount on Focus open via `POST /focus/{type}/open`; persist via `focus_sessions.layout_state`; unmount on close; debounced layout writes (500ms). Per Phase A Session 4.
- **Variant defaults**: **Brief** or **Detail** (Focus is a deliberate-action workspace; tablets need real estate). Compact (Glance) variants render in stack tier (mobile Focus); icon tier (narrow viewport) bypasses widgets entirely.
- **Interactivity**: **full action surface for the Focus core**, where workspace-level decisions live (finalize, multi-record coordination, conflict resolution). Canvas-pinned widgets within Focus follow §12.6a Widget Interactivity Discipline — bounded micro-actions on the widget; complex decisions remain in the Focus core itself.
- **Resize**: WidgetChrome `useResize` swaps variant when crossing variant breakpoints; otherwise fluid within current variant.
- **Multiple instances**: allowed, rare per Focus shape.
- **Tier degradation** (Phase A Session 3.7 cascade):
  - Canvas tier → Brief / Detail / Deep (whatever the canonical variant the user pinned)
  - Stack tier → Brief (compressed where needed)
  - Icon tier → Glance (or icon button only — variants lower than Glance render as bottom-sheet expand)
  - StackExpandedOverlay → Detail (full reveal of stack-tier tile)
- **Visual chrome**: frosted-glass tablet treatment (Pattern 1 + widget-tier elevation per §3 + bezel + grip indicator). Per Aesthetic Arc Session 4.8.

**Pulse (Monitor) — composed responsive grid per Space.**
- **Layout style**: CSS responsive grid (`grid-template-columns: repeat(auto-fit, minmax(varies, 1fr))`) with grid_size from variant declaration.
- **Lifecycle**: per-Space; load on Space activation; persist via `User.preferences.spaces[space_id].pulse_layout` JSONB. Per Decision 7. Migrate to dedicated table later if Pulse layouts grow complex.
- **Variant defaults**: **Brief** for most; **Glance** for KPI rail; **Detail** for primary work-surface zones. Role-driven (Pulse seeds different defaults for director vs accountant vs production-manager).
- **Interactivity**: Widget Interactivity Discipline (§12.6a) applies. Bounded micro-actions execute in-place on the Pulse-pinned widget — drag a delivery, mark a status, update a field. Decisions navigate to Focus — clicking a "needs decision" affordance opens the relevant Focus with the decision context preloaded. Pulse is the persistent reference + light-action surface; Focus is the deliberate-decision surface.
- **Resize**: drag-rearrange + drag-resize via existing `useDashboard` pattern, but with **variant-swap on size-change** instead of just scaling content. Crossing the variant breakpoint flips the variant.
- **Multiple instances**: allowed and common (e.g., two `funeral_schedule` widgets — today, this week — with different `config.date_offset`).
- **Visual chrome**: solid-fill card treatment via `WidgetWrapper` (header bar + refresh / menu / edit affordances). Card-tier ambient shadow (not widget-tier — Pulse widgets are cards within the work surface, not floating tablets).

**Spaces (Configure) — sidebar pinned, Glance only.**
- **Layout style**: vertical list (`PinnedSection` above nav). Existing Phase 3 + 8e.1 mechanism.
- **Lifecycle**: pin / unpin via `space-context.tsx`; persist via `User.preferences.spaces[].pins[]`. Existing.
- **Widget integration** (Decision 2): Spaces pins gain `pin_type: "widget"` with `target: widget_id` and `config: TConfig`. Single user mental model: catalog flow → pin to Pulse OR pin to sidebar.
- **Variant default**: **Glance** (sidebar real estate is narrow, ~240px wide).
- **Interactivity**: minimal — Glance variants typically surface zero interactions per §12.6a per-variant declarations (count + label only). Tap navigates to Detail/Deep variant on Pulse OR opens Focus where the entity / workspace lives. Sidebar pins are reference + navigation, not action surfaces.
- **Resize**: not supported. Glance is the only valid sidebar variant. To upsize, user repins to Pulse.
- **Multiple instances**: allowed, constrained by `MAX_PINS_PER_SPACE = 20` cap.
- **Visual chrome**: minimal — pin row matches existing nav-item / saved-view pin styling. Glance variant content + optional accent count chip. NO bezel, NO eyebrow, NO mono header — Glance variant chrome reduction (§12.8).
- **Click**: navigates to fuller variant on Pulse (if pinned there too) OR opens floating tablet (command bar style).

**Command bar (Act) — floating tablet, ephemeral.**
- **Layout style**: floating tablet beside command bar input (or below). Current peek-panel architecture.
- **Lifecycle**: ephemeral by default — summon on entity resolution, dismiss on Esc / backdrop click. Can be **parked** per PLATFORM_INTERACTION_MODEL (post-September spatial workspace).
- **Variant default**: **Brief** (focused work surface, typical action-with-content).
- **Interactivity**: Widget Interactivity Discipline (§12.6a) applies to peek-composed widget content. Reference + bounded actions (mark contacted, quick note, single-field update) execute in-place on parked peeks. Considered changes navigate to Focus or the entity's dedicated page.
- **Resize**: not supported. Command bar tablets are bounded; user upsizes by opening Focus.
- **Peek panel relationship** (Decision 3): peek panels stay separately routed (per entity type). They MAY internally compose widget components for content (e.g., embed `recent_activity` widget at Brief variant inside an entity peek). Visual language unified, interaction surface unified, routing primitive distinct.
- **Visual chrome**: floating-tablet treatment via future `TabletShell` (frosted-glass + bezel + grip + parking surface). Widget-tier elevation per §3.

**Operations Board / Vault Overview / hub dashboards (legacy migrating).**
- **Layout style**: existing `useDashboard` + `WidgetGrid` pattern (CSS grid, dnd-kit reorder, edit-mode toggle).
- **Lifecycle**: existing — load on page mount, persist via `user_widget_layouts`.
- **Variant defaults**: **Brief** (existing `default_size` becomes the Brief variant's `grid_size`).
- **Interactivity**: existing widget-internal interactions preserved during migration (each widget's current bounded actions remain). New variant builds adopt §12.6a discipline. Decisions navigate to relevant Focus / entity page (existing pattern, formalized).
- **Migration**: backfill widget_definitions to declare `variants[]` with one Brief variant matching current shape. Other variants land incrementally "as touched" (Decision 10).
- **Visual chrome**: existing `WidgetWrapper` (header + chrome) + card-tier shadow.

### 12.6 Workspace cores have widget views (canon)

**The canon: every Focus core element has a corresponding widget representation. Widgets surface workspace state for reference and bounded micro-actions. Decisions involving trade-off evaluation remain in workspaces (Focus).**

The widget is **NOT a read-only mirror**; it's an **abridged interactive surface** showing the same data with a reduced action surface area. Edits that don't require evaluating trade-offs are widget-appropriate. Edits that require holistic evaluation are Focus-required.

This is the bridge between the Focus primitive (deliberate-action workspace) and the Pulse primitive (passive monitoring). Operators handle quick state flips from widgets; complex coordination happens in Focus.

**Canonical examples.**

*Funeral Scheduling Focus core (kanban) → Funeral Schedule Widget.* The Focus core renders the kanban with full editing + decision affordances: drag deliveries between lanes, attach ancillaries, click cards to QuickEdit, **finalize the schedule**, **rebalance driver workloads**, **resolve scheduling conflicts**, day-switch + rebuild. The Funeral Schedule Widget at Detail variant renders the SAME kanban data — same cards, same lanes, same status indicators — and supports **bounded interactions**: drag a delivery between drivers (single reassignment), mark hole-dug (single state flip), update ETA / start time (single field), toggle ancillary attachment (single linkage), quick note (single annotation). The widget does NOT support: finalize, bulk reassignment, day navigation, conflict resolution, schedule rebuild — those are Focus-required because they involve evaluating trade-offs across multiple records or committing to a decision.

*Future Arrangement Focus core → Arrangement Widget.* When the Arrangement primitive (FH vertical) ships, the same pattern applies: the widget surfaces case progression with bounded interactions (mark a stage complete, add a quick note, flag for follow-up); decisions about case routing or arrangement reschedule require Focus.

*Future Vault Schedule Focus core (manufacturing) → Vault Schedule Widget.* Per cold-start catalog scope: the Vault Schedule Widget will exist at Brief / Detail / Deep variants when Vault Schedule Focus exists; widget supports single pour / single PO reassignment + individual status updates; production line rebalancing or supplier-coordination decisions require Focus. The widget is **mode-aware** (per [BRIDGEABLE_MASTER §5.2.2](BRIDGEABLE_MASTER.md)): production-mode tenants see pour-schedule render path; purchase-mode tenants see incoming-PO render path; hybrid-mode tenants see unified composition. Same widget, different content per `TenantProductLine.config["operating_mode"]`. Each non-vault product line has its own analogous schedule widget (`redi_rock_schedule`, `wastewater_schedule`) — same naming convention, same mode-aware contract.

**Why this matters.** If widgets were truly read-only, operators would be forced into Focus for every micro-update — friction without payoff. If widgets had full editing capability, the workspace metaphor would muddy — no clear "where do I do which work" answer. Threading the needle: **widgets are reference + micro-actions; Focus is considered decisions + complex coordination**. Two genuinely different work modes.

**Architectural implication: shared data layer.** Widget Detail / Deep variants embed the Focus core's data layer (e.g., the same `useSchedulingFocus()` context, or the same backend endpoint) with a deliberately reduced interaction surface. The widget component IS NOT a copy of the Focus core's component; it's a sibling render of the same data with different chrome + filtered interaction set. Glance / Brief variants typically render summary projections (counts, status pills) over the same data source. Mutations from widgets share the Focus core's mutation paths (e.g., the same `assignDriver(deliveryId, driverId)` service call) — single source of truth for state writes regardless of where the action originated.

**Pattern documentation.** When a new Focus type ships, the spec includes the widget-view requirement: declare which variants the widget supports (matching surface compatibility), which interactions each variant exposes (per §12.6a discipline), and what "click on widget" navigates to (typically the Focus open URL with appropriate context, but may also be a deeper variant view first).

### 12.6a Widget Interactivity Discipline

**The principle: state changes are widget-appropriate; decisions belong in Focus.**

The criterion is **interaction complexity**, not editability. Quick state flips don't require entering a workspace; multi-variable decisions do.

**Tests for widget-appropriateness.** An interaction is widget-appropriate if all four hold:

1. **Bounded scope.** The interaction touches one record / one field / one relationship at a time.
2. **No coordination required.** The user can complete the interaction without considering effects on other work.
3. **Reversible / low-stakes.** The interaction is a state flip, not a commit-to-decision moment.
4. **Time-bounded.** The interaction takes seconds, not minutes of consideration.

If any of the four fails, the interaction is Focus-required.

**Examples table** (canonical reference for widget catalog authors):

| Interaction type | Widget? | Focus? | Reasoning |
|---|---|---|---|
| Mark single delivery hole-dug | ✓ | – | Single state flip, bounded |
| Drag one delivery between drivers | ✓ | – | Single reassignment, immediate |
| Bulk reassign multiple deliveries | – | ✓ | Multi-record, requires coordination |
| Update one ETA | ✓ | – | Single field, bounded |
| Finalize / commit schedule | – | ✓ | Decision moment, irreversible |
| View customer card | ✓ | – | Reference only |
| Edit customer relationship details | – | ✓ | Multi-field, considered |
| Add quick note | ✓ | – | Annotation, bounded |
| Resolve scheduling conflict | – | ✓ | Trade-off evaluation |
| Confirm ancillary pickup | ✓ | – | Single state flip |
| Reorganize ancillary pool assignments | – | ✓ | Multi-record coordination |
| Mark task complete | ✓ | – | Single state flip |
| Reassign task to different person | ✓ | – | Single reassignment, immediate |
| Add subtasks to a task | ✓ | – | Bounded annotation, reversible |
| Approve / reject anomaly | ✓ | – | Single decision-record (the anomaly itself encapsulates the trade-off; widget surfaces the decision per item) |
| Rebalance entire team's workload | – | ✓ | Multi-record coordination, requires Focus |
| Quick status update on a record | ✓ | – | Single state flip |
| Multi-step workflow execution | – | ✓ | Sequential coordination |
| Toggle a setting | ✓ | – | Single config flip |
| Adjust rules / policies | – | ✓ | Considered decision affecting future state |

**Per-variant interaction declarations.** Widget definitions declare which interactions each variant surfaces. Glance variants typically surface zero interactions (count + label only). Brief variants surface 1-3 most-common bounded interactions. Detail / Deep variants surface the full bounded interaction set for the widget. Surfacing decisions consistent across variants — Glance never surfaces what Brief doesn't; Brief never surfaces what Detail doesn't.

**Convention vs schema.** Per-variant interaction declarations may be expressed as schema (`WidgetVariant.supported_interactions: string[]`) or convention (documented per widget; enforced by code review + the canonical examples table above). Recommendation: **convention for Phase W-1 + W-2, schema for Phase W-3 onward** if interaction discoverability becomes catalog-relevant (e.g., "show me widgets that let me approve anomalies"). Phase W-3 widget builds declare per-variant supported interactions in their definition file as documentation-comments + Storybook examples; full schema surfaces if needed.

**Why this discipline matters.** Without it, widgets either become micro-Focuses (full editing surface, workspace metaphor collapses) or read-only viewers (forced trip to Focus for every flip, friction). The discipline produces a coherent platform where: operators handle quick work in widgets; complex work happens in Focus; both surfaces share data + mutation paths; user mental model stays clean ("am I considering trade-offs? open Focus. just flipping a flag? do it here").

**Cross-reference.** This discipline relates to PLATFORM_INTERACTION_MODEL.md *summon → arrange → park → dismiss* by adding the action discipline at the materialization unit. Widgets ARE tablets, and tablets host bounded interactions; full workspaces (Focus) host considered decisions.

### 12.7 Entity cores have widget views (canon)

**The canon: every first-class entity has a corresponding card widget that renders the entity's primary fields with declared variants. Widget Interactivity Discipline (§12.6a) applies — bounded entity edits are widget-appropriate; multi-field record changes require Focus or the entity's dedicated page.**

Same pattern at entity scope. Customer entity → Customer Card Widget. Order entity → Order Card Widget. Cemetery entity → Cemetery Card Widget. Case entity → Case Card Widget.

**Variant taxonomy applies.**
- **Glance**: entity name + status indicator + key count (e.g., customer name + "3 open invoices")
- **Brief**: entity name + 3-5 primary fields + most-recent-action affordance + bounded interactions (mark contacted, quick note, status flip)
- **Detail**: full primary record + recent activity feed + secondary fields scrollable + bounded edit set (single-field updates, status changes, quick annotations)
- **Deep**: typically opens dedicated entity detail page rather than rendering inline — Deep IS the entity's editing surface for considered changes

**Bounded entity interactions (per §12.6a discipline).**

Widget-appropriate (Brief / Detail variants):
- **Status flip** (mark contacted, mark archived, toggle active/inactive)
- **Quick note** (single annotation on the entity)
- **Single-field update** (update phone number, update email)
- **Tag / flag** (add a tag, flag for review)
- **Quick assignment** (assign to user, set owner)

Focus-required (or entity's dedicated detail page):
- **Multi-field record changes** (full contact-info update, relationship-restructure)
- **Linking entities** (associating customer with new account, relationship rules)
- **Decision moments** (approve credit limit increase, write off bad debt, archive permanently)
- **Workflows that touch multiple entities** (merge duplicate customers, transfer cases between FHs)

The discipline parallels workspace-core widgets: easy state flips happen in the widget; considered changes happen in the entity's dedicated workspace.

**Relationship to command bar peek panels.** Per Decision 3, peek panels stay separately routed (entity-type registered renderers). But peek content composition USES widget components. A peek of a Customer entity renders the Customer Card Widget at Brief variant inside the peek panel chrome — including the bounded interactions. A user hovering a customer reference + clicking-to-park the peek can mark contacted, add a quick note, etc., from the parked peek. Same Brief variant, same interactions, different routing primitive.

**Lifecycle distinction.**
- **Pinned widgets persist** — user pins Customer Card Widget for Hopkins Funeral Home to their Pulse; it stays until unpinned. Bounded interactions available throughout the pinned lifetime.
- **Peek widgets are ephemeral** — user hovers a customer reference in a saved view, peek summons the Customer Card Widget at Brief variant for the duration of the hover (or click-to-park if hover-to-click promotion). Bounded interactions available during the peek session.

Same visual vocabulary (Brief variant of Customer Card Widget renders identically in both contexts), same interaction set, different lifecycle (pinned vs ephemeral). The user perceives the widget consistently; the routing primitive handles persistence differently.

**Architectural implication: entity widgets are catalog citizens.** A Customer Card Widget is in the catalog like any other widget. User can pin it to Pulse with `config = { customer_id }` to permanently surface a particular customer + interact with it via bounded actions. User can also encounter it ephemerally via peek panels with the same interaction surface. Same registered widget, different consumption.

**Why entity card widgets matter.** Entities are the operational nouns; users reference them constantly + need bounded interactions on them constantly. Without entity card widgets, every entity-rendering surface (peek, Pulse pin, sidebar pin, search result tile) reinvents its own card composition + bounded-edit surface — divergence at scale. Centralizing entity rendering in widgets means: one Customer Card composition, one set of bounded interactions, used wherever a customer surfaces.

### 12.8 Tablet materialization integration

Pattern 1 (Section 11) defines the tablet-treatment composition. Section 12 inherits it with surface-driven adaptations and variant-driven chrome reduction.

**Surface-driven chrome decisions.** The variant component itself doesn't pick its own chrome. The SURFACE wraps the widget appropriately:

- **Canvas surface (Focus)** wraps in `WidgetChrome` — drag handle, dismiss X, resize zones, frosted-glass tablet treatment. Section 11 Pattern 1 + Aesthetic Arc Session 4.8 calibration (rounded-none, layered widget-tier shadow, translateY transform).
- **Grid surface (Pulse / Vault Overview / Operations Board)** wraps in `WidgetWrapper` — header bar with icon + title, refresh / menu / edit affordances, solid-fill card treatment. Card-tier ambient shadow.
- **Floating tablet (command bar peek)** wraps in future `TabletShell` — frosted-glass + bezel + grip + parking surface. Same Pattern 1 frosted-glass treatment as Focus canvas tablets.
- **Sidebar pin (Spaces)** wraps in `PinnedItem` — compact row, no chrome. Glance variant content rendered directly.
- **Peek panel (entity card content)** wraps in PeekHost (separately routed) — frosted-glass tablet, but content is Brief variant of an entity widget.

**Cross-mode behavior.**
- Frosted-glass treatment for tablets sitting over dimmed or blurred substrate (Focus, command bar tablet, peek panel) → `bg-surface-elevated/85` + `backdrop-blur-sm` + `rounded-none` (Aesthetic Arc Session 4.8).
- Solid-fill treatment for cards mounted in opaque surfaces (Pulse, Vault Overview, Operations Board, Spaces dashboards) → `bg-surface-elevated` + `rounded-[2px]` (Pattern 2 architectural-corner spec).

The Pattern 1 vs Pattern 2 distinction (Aesthetic Arc Session 4.8 canon): different surface treatments require different corner values to produce equivalent perceptual sharpness. Frosted-glass widgets use 0px; solid-fill widgets use 2px. Same architectural register.

**Glance variant chrome reduction.** At Glance size (single number / icon), the bezel + mono eyebrow + grip indicator overhead consumes more visual real estate than the content. Resolution: **Glance variants OMIT bezel + OMIT eyebrow header**. They render as pure-content tiles with just the count chip + label. The tablet chrome scales WITH the variant — fuller chrome for fuller content, minimal chrome for minimal content. This is a Pattern 1 sub-rule documented for the variant taxonomy.

**Watch-tier translation (post-September).** Glance variant maps cleanly to Apple Watch / iPhone widget-stack tier. Brief maps to iOS Medium widget. Detail maps to iOS Large. Deep maps to dedicated app deep-link. Even though watch deployment is post-September, the variant taxonomy is forward-compatible — a deliberate choice. Pattern 1 chrome reductions extend naturally to smaller tiers (Glance on watch is the same composition as Glance on sidebar).

### 12.9 Persistence model

Persistence is per-surface, not unified. Each surface has different access patterns and constraints; forcing a single storage layer fights those constraints. The IN-MEMORY layout shape IS unified (`WidgetState[]` with `widget_id`, `variant_id`, `position`, `config`); the STORAGE layer differs.

| Surface | Storage | Schema location | Access pattern |
|---|---|---|---|
| Focus canvas | `focus_sessions.layout_state` JSONB | `r48_focus_sessions_and_layout_defaults` migration | Per-user per-Focus session; 3-tier resolve (active → recent → tenant default → registry); 500ms debounced writes |
| Operations Board / Vault Overview / hub dashboards | `user_widget_layouts` table | Existing (pre-Widget Library) | Per-user per-page-context; row-level updates on layout change |
| Spaces sidebar pins | `User.preferences.spaces[].pins[]` JSONB | `r41_user_space_affinity` and earlier | Per-user; Spaces config holds pin array; max 20 pins per Space |
| Pulse | `User.preferences.spaces[space_id].pulse_layout` JSONB | Extended in Phase W-2 / W-4 | Per-user per-Space; same JSONB column as Spaces config; Phase 3 trade-off (no new table for bounded config) |
| Command bar peek | Session-scoped (in-memory) | None — ephemeral | Per-session; resets on browser refresh; not persisted (peek is hover-summoned) |

**Why distributed.** Each surface has different access patterns:
- Focus needs fast 3-tier resolve with optimistic seed; benefits from the layout state being colocated with the Focus session.
- Dashboards need stable per-page-context layouts; benefit from a normalized table.
- Spaces pins are bounded (≤ 20 per Space, ≤ 7 Spaces per user); JSONB is appropriate.
- Pulse layouts are similarly bounded; share Spaces' JSONB approach.
- Command bar peeks are ephemeral by design.

Forcing all into one table breaks one or more access patterns. Each surface's storage choice is deliberate.

**In-memory layout shape unified.** Across all surfaces, the layout in memory is a `WidgetState[]` with consistent fields:

```typescript
interface WidgetState<TConfig = unknown> {
  instance_id: string                  // unique per-instance UUID
  widget_id: string                    // catalog reference
  variant_id: "glance" | "brief" | "detail" | "deep"
  position: WidgetPosition             // surface-specific shape
  config: TConfig                      // per-instance config
}
```

`WidgetPosition` is a discriminated union per surface:

```typescript
type WidgetPosition =
  | { surface: "focus_canvas"; anchor: WidgetAnchor; offsetX: number; offsetY: number; width: number; height: number | "auto"; maxHeight?: number }
  | { surface: "pulse_grid" | "dashboard_grid"; col: number; row: number; col_span: number; row_span: number }
  | { surface: "spaces_pin"; sort_order: number }
  | { surface: "floating_tablet"; ephemeral: true }
```

Surface code reads only the relevant variant; widget components only see `WidgetVariantProps` (which doesn't include position — surfaces handle positioning).

**Migration discipline.** Existing widgets keep their existing storage. New widgets land on the unified contract. Mechanical migration is "as touched" (Decision 10). No big-bang migration; both frameworks coexist 1-2 release windows.

### 12.10 Reference implementation

Fourteen canonical widgets serve as reference implementations for the Widget Library Architecture. The first three demonstrate the cross-vertical + workspace-core + vertical-scoped patterns. The next two (added during the Product Line + Operating Mode canon session, April 2026) demonstrate per-line + mode-aware patterns. The next four (added during Phase W-3a Foundation Widget Cluster, April 2026) demonstrate the **cross-vertical + cross-line foundation widget** pattern shipped at the start of the W-3 cold-start catalog work. Two more (added during Phase W-3b Cross-Surface Infrastructure Widgets, April 2026) demonstrate the **config-driven user-authored widget catalog** pattern (`saved_view`) and the **per-user scoped narrative widget** pattern (`briefing` — promotion of an existing primitive surface to widget contract). The final three (added during Phase W-3d Manufacturing Per-Line Widgets, April 2026) demonstrate the **first concrete activation of the 5-axis filter end-to-end** — vault_schedule is the **first concrete workspace-core widget canonical reference** with mode-aware rendering; line_status is the **first cross-line aggregator using the multi-line builder pattern**; urn_catalog_status is the **first widget exercising the `required_extension` axis**. Together these three exercise vertical + product_line + extension axes simultaneously, completing the 5-axis filter coverage.

**1. Funeral Schedule Widget (workspace-core widget).**
- Cold-start catalog: `funeral_schedule`
- Variants: Glance + Brief + Detail + Deep
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`
- Vertical: `["funeral_home"]`
- Demonstrates: §12.6 "Workspace cores have widget views" canon + §12.6a Widget Interactivity Discipline. Same kanban data as Funeral Scheduling Focus core, **abridged interactive surface** with bounded micro-actions; complex decisions remain in Focus.
- Data source: shared with Focus via `useSchedulingFocus()` context (when widget is canvas-pinned in Focus) OR via direct backend fetch (when widget is on Pulse outside Focus). Mutations route through the same service calls as Focus.
- Per-variant content + interactions:
  - **Glance** — today's delivery count + finalize status. Interactions: none (count + label only). Tap navigates to Brief or Focus.
  - **Brief** — lane summary (counts by driver) + key alerts. Interactions: drag delivery between drivers (single reassignment), mark hole-dug status (single state flip), tap card to expand summary.
  - **Detail** — full kanban with hole-dug indicators + ancillary pool summary. Interactions: drag deliveries between drivers, mark hole-dug, update single ETA / start time, toggle ancillary attachment, quick note on a delivery.
  - **Deep** — kanban + ancillary pool + flanking-day peek (post-Phase-4.4.4). Same interaction set as Detail.
- **NOT supported in any variant**: finalize schedule, day-switch / day-rebuild, bulk reassignment, conflict resolution, schedule rebuild after disruption, adding new deliveries. Those are decision moments that require the Focus core's full editing chrome + workspace context.
- Click "open in Focus" affordance (always present in Brief / Detail / Deep): launches Focus with the widget's current day pre-loaded.

**2. Ancillary Pool Widget (canvas widget upgraded).**
- Cold-start catalog: `ancillary_pool`
- Variants: Glance + Brief + Detail
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`
- Vertical: `["funeral_home"]`
- Demonstrates: migration of existing AncillaryPoolPin (Phase 4.3b.3) from canvas-only widget to multi-variant catalog widget + §12.6a Widget Interactivity Discipline.
- Data source: `useSchedulingFocus()` (Focus canvas) OR `/api/v1/dispatch/pool` (Pulse / Spaces).
- Per-variant content + interactions:
  - **Glance** — pool count (terracotta count chip). Interactions: none.
  - **Brief** — top 5 pool items with FH name + product. Interactions: drag-attach to delivery (when in Focus canvas), mark item confirmed (single state flip), quick note.
  - **Detail** — full scrollable list with drag-source affordance. Interactions: same as Brief plus mark confirmed in bulk-of-one (per-item), edit pickup notes per item.
- **NOT supported in any variant**: pool reorganization (multi-record coordination), bulk reassignment, decision moments around competing pool priorities. Those route to Focus.

**3. Recent Activity Widget (cross-vertical reference).**
- Cold-start catalog: `recent_activity`
- Variants: Glance + Brief + Detail
- Surface compatibility: `pulse_grid`, `spaces_pin`, `dashboard_grid`, `peek_inline`
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Demonstrates: cross-vertical widget rendering across all surfaces with same component, different variants.
- Data source: `useWidgetData("/api/v1/vault/activity/recent?limit=10")` with auto-refresh.
- Per-variant content + interactions:
  - **Glance** — count of new activity since last viewed. Interactions: none.
  - **Brief** — 5 most recent activities with type icons + timestamps. Interactions: tap an activity to navigate to the related entity (peek or page).
  - **Detail** — 20 most recent activities with full descriptions + entity links. Interactions: tap to navigate (no in-place edits — Recent Activity is a reference-only widget, the activities themselves don't have widget-level state to flip).
- Used inside peek panels (entity detail context) at Brief variant.

**4. Vault Schedule Widget (per-line + mode-aware reference).**
- Cold-start catalog: `vault_schedule`
- Variants: Glance + Brief + Detail + Deep
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`
- Vertical: `["manufacturing"]`
- Product line: `["vault"]`
- Permission: `production.view`
- Demonstrates: **per-line + mode-aware rendering**. Same widget, different render path per `TenantProductLine.config["operating_mode"]` value. Reference for every other per-line schedule widget the platform builds (`redi_rock_schedule`, `wastewater_schedule` follow the same pattern with same naming convention).
- Data source (per mode):
  - **Production mode** — `useVaultProductionSchedule()` reading `work_orders`, `production_log_entries`, `production_mold_configs` for the user's tenant (existing pour-schedule data path).
  - **Purchase mode** — `useVaultPurchaseSchedule()` reading `licensee_transfers` for the user's tenant where the tenant is the *receiving* party (incoming POs from supplier licensees).
  - **Hybrid mode** — both data sources merged, ordered by date, render annotates each row with mode source ("Pour: Monticello x4" vs "Incoming: Empire State, Concord vault x2").
- Per-variant content + interactions:
  - **Glance** — today's schedule item count + status indicator (production: "today's pour load: 4 vaults"; purchase: "today's incoming: 2 deliveries"; hybrid: "today: 4 pours / 2 incoming"). Interactions: none. Tap navigates to Brief or Focus.
  - **Brief** — next 5 schedule items grouped by date. Production-mode rows show pour assignments + crew; purchase-mode rows show supplier + tracking + ETA. Interactions: tap an item to peek (single-record view); single status flip per item (production: mark pour complete; purchase: mark received).
  - **Detail** — full week of schedule items with pour-vs-receive distinction visible. Interactions: drag single pour to reassign crew (production), update single ETA (both modes), mark single status flip per row, quick note per row.
  - **Deep** — Detail + flanking-day peek (multi-day visible) + bulk-of-one filtering by vault type. Same interaction set as Detail (no bulk operations — bulk reassignment routes to Focus).
- **NOT supported in any variant**: schedule rebuild, bulk reassignment, multi-record coordination, finalize day's schedule, decision moments around pour-vs-purchase trade-offs (e.g., "should we pour this in-house or buy from neighbor"). Those are Focus-required.
- **Mode-flip at runtime**: when an admin flips the tenant's vault `operating_mode` in `TenantProductLine.config`, the next render of `vault_schedule` swaps render path. No widget reinstall; no layout migration. Single widget, mode-aware contract.
- **Decision sequence (per-line widget naming convention)**: each product line gets its own schedule widget named `<line_key>_schedule`. Vault is the canonical reference; Redi-Rock + wastewater + future lines follow. The naming is **mode-agnostic** (not "pour_schedule" — that leaked production-mode bias).

**5. Line Status Widget (cross-line aggregator + mode-aware reference).**
- Cold-start catalog: `line_status`
- Variants: Brief + Detail (no Glance — line status is operational-health information that doesn't compress to count-only)
- Surface compatibility: `pulse_grid`, `dashboard_grid`
- Vertical: `["manufacturing"]`
- Product line: `"*"` (renders for any active line; aggregates whichever lines the tenant has activated)
- Permission: `production.view`
- Demonstrates: **cross-line aggregator with per-line drill-down**. Replaces the implicit vault-only "production_status" assumption pre-canon. Production tenants see pour-status rows; purchase tenants see incoming-supply-status rows; hybrid tenants see both. Mode-awareness operates per active line, not at the widget level.
- Data source: composes per-line data sources (`useVaultProductionSchedule` for vault production rows, `useVaultPurchaseSchedule` for vault purchase rows, similar for redi_rock + wastewater + urn_sales) into a unified line-by-line summary.
- Per-variant content + interactions:
  - **Brief** — one row per active product line, status indicator + headline metric. Production-mode lines show "On track / behind / blocked" with today's pour count; purchase-mode lines show supplier delivery status with today's incoming count; hybrid lines show both metrics inline. Interactions: acknowledge alerts (single state flip per alert).
  - **Detail** — same row structure with expanded metrics: production-mode rows show crew utilization + mix design + this-week trend; purchase-mode rows show supplier on-time % + days-to-deliver + this-week supplier exception count. Interactions: + status flip per line (acknowledge a flagged line); tap a line to navigate to that line's `<line_key>_schedule` widget at Detail variant or open the relevant Focus.
- **NOT supported in any variant**: trade-off decisions across lines (e.g., "should we re-prioritize redi_rock production over vault to meet a deadline"), capacity rebalancing, bulk acknowledgments. Those are Focus-required when the relevant Focus types ship; until then, line-level decisions are deferred to detail pages.
- **The "operations_status" / "production_status" rename:** pre-canon a `production_status` widget was specified for manufacturing tenants, implicitly assuming all lines are production-mode. Canon supersedes with `line_status` — mode-agnostic, per-line health, cross-line aggregation. Any future "overall operations health" widget across all lines (if a need emerges) lands as a separate `operations_status` widget composing `line_status`-style rows alongside non-line operational health (orders pending, deliveries in flight, etc.). For September: `line_status` is the canonical per-line health widget; standalone `production_status` and `operations_status` widgets are not built unless explicit need surfaces.

**6. Today Widget (Phase W-3a foundation reference — vertical-aware aggregation).**
- Cold-start catalog: `today`
- Variants: Glance + Brief
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/TodayWidget.tsx`
- Demonstrates: **cross-vertical foundation widget with per-vertical-and-line content rendering**. Same widget for every tenant; the BACKEND service (`app/services/widgets/today_widget_service.py`) dispatches to per-(vertical, active product line) category builders. Manufacturing+vault tenants get vault deliveries + ancillary pool + unscheduled count. Other verticals get a thoughtful empty state + a vertical-aware `primary_navigation_target` (`/dispatch` for mfg, `/cases` for FH, `/interments` for cemetery, `/crematory/schedule` for crematory). Pattern locks the **multi-line builder shape** for future per-line breakdowns: when redi_rock activates, `_build_manufacturing_redi_rock_categories` plugs in alongside the vault builder without restructuring.
- Data source: `GET /api/v1/widget-data/today` with 5-min auto-refresh. Tenant-scoped via `Company.id == user.company_id` filter; resolves "today" in the tenant's `Company.timezone` so a 23:30 tenant-local delivery doesn't bleed into "tomorrow" for non-UTC zones.
- Per-variant content + interactions:
  - **Glance** — date label + total count of relevant items. Interactions: tap to summon the tenant's `primary_navigation_target` (single navigate; no edit, no acknowledge).
  - **Brief** — date header + per-category breakdown rows ("5 vault deliveries", "2 ancillary items waiting", "3 unscheduled"), each clickable for navigation. Empty-state rendering: "Nothing scheduled today" + "Open schedule →" CTA pointing at the vertical's primary work surface. Interactions: tap a row to navigate.
- **NOT supported in any variant**: state flips, edits, decision moments. Today is a **reference widget** — it surfaces what's relevant; clicking through is the primary affordance.

**7. Operator Profile Widget (Phase W-3a foundation reference — auth-context-only widget).**
- Cold-start catalog: `operator_profile`
- Variants: Glance + Brief
- Surface compatibility: `pulse_grid`, `spaces_pin`, `dashboard_grid`
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/OperatorProfileWidget.tsx`
- Demonstrates: **auth-context-only widget — NO backend call.** The widget reads entirely from `useAuth()` (full user identity + role + permissions/modules/extensions counts) + `useSpacesOptional()` (active space name). Establishes the pattern: not every widget needs a data endpoint. Some widgets render context already in scope.
- Per-variant content + interactions:
  - **Glance** — initials avatar (24×24, terracotta-muted background) + first/last name + role label. Interactions: tap to summon `/settings/profile`.
  - **Brief** — larger avatar (32×32) + full name + email header + role/active-space/access-summary rows + "Manage profile →" footer CTA. The access summary uses singular/plural-aware labels: "1 permission" vs. "3 permissions"; extensions row omitted when zero. Interactions: footer CTA navigates to `/settings/profile`.
- **NOT supported in any variant**: profile editing, role/permission changes. Those happen on the dedicated settings page per §12.6a (decisions belong in Focus / dedicated surfaces).
- **Defensive null behavior:** when mounted outside a tenant auth scope (e.g., misconfigured Storybook story), the dispatcher returns `null` rather than crashing. The widget is auth-required by definition.

**8. Recent Activity Widget (Phase W-3a foundation reference — V-1c endpoint reuse with shim).**
- Cold-start catalog: `recent_activity`
- Variants: Glance + Brief + Detail
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`, `peek_inline`
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/RecentActivityWidget.tsx`
- Demonstrates: **endpoint reuse with minimal shim**. Backed by the V-1c `GET /api/v1/vault/activity/recent` endpoint extended Phase W-3a with an optional `actor_name` field populated server-side via User join (additive — existing V-1c consumers ignore the new field). No new backend endpoint. The pattern: when an existing endpoint is "almost right" for widget consumption, prefer additive Pydantic shim over new endpoint surface area.
- Data source: `GET /api/v1/vault/activity/recent` with `limit=10` (Glance/Brief) or `limit=50` (Detail), 5-min auto-refresh. Tenant-scoped via the existing V-1c filter chain.
- Per-variant content + interactions:
  - **Glance** — count of recent events. Interactions: tap to summon `/vault/crm`.
  - **Brief** — top 5 most recent events, each row "{actor_name} {verb} · {company_name} · {relative_time}". Interactions: tap row to navigate to the related CRM company; "View all →" footer CTA.
  - **Detail** — top 50 events with category filter chips (All / Comms / Work / System) collapsing the activity_type vocabulary into a smaller user-facing taxonomy. Interactions: tap row to navigate; tap chip to filter (toggles `aria-selected` for a11y).
- **Used inside peek panels** at Brief variant per §12.5 composition rules (`peek_inline` surface) — peek panels stay separately routed but compose this widget's components for content. Cross-surface reuse is the pattern; per-surface reinvention is what the widget library prevents.
- **NOT supported in any variant**: activity editing (notes are read-only here; full edit happens on the entity detail page), follow-up management, comment threading. Per §12.6a — recent_activity is a reference widget, not an action surface.

**9. Anomalies Widget (Phase W-3a foundation reference — bounded state-flip + tenant isolation).**
- Cold-start catalog: `anomalies`
- Variants: Brief + Detail (**NO Glance** — anomalies need at least Brief context per §12.10; count alone doesn't communicate severity or actionability)
- Surface compatibility: `pulse_grid`, `focus_canvas`, `spaces_pin`, `dashboard_grid`
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/AnomaliesWidget.tsx`
- Demonstrates: **canonical widget-appropriate state-flip interaction** (Acknowledge) + **explicit tenant isolation in widget data sources**. Backed by the existing `agent_anomalies` table (Phase 1+ accounting agent infrastructure) with explicit tenant scoping via `AgentJob.tenant_id` join. Real production data — Wilbert licensee tenants running accounting agents have unresolved anomalies this widget surfaces directly. Phase W-5 (Intelligence-detected anomalies) extends the data source rather than replacing the widget.
- Data source: `GET /api/v1/widget-data/anomalies` (severity-sorted critical → warning → info, then created_at desc). Acknowledge action: `POST /widget-data/anomalies/{id}/acknowledge` with optional `resolution_note`.
- Severity vocabulary per `app.schemas.agent.AnomalySeverity` (3 levels — NOT 4 as some prior canon drafts suggested):
  - **critical** → `text-status-error` / `border-l-status-error` (terracotta)
  - **warning** → `text-status-warning` / `border-l-status-warning` (terracotta-muted)
  - **info** → `text-status-info` / `border-l-status-info`
- Per-variant content + interactions:
  - **Brief** — top 4 most-critical anomalies, each row: severity icon + description + agent type + relative timestamp + Acknowledge button (single icon, hover-reveal). Header shows "{N} critical · {M} total" when criticals present, else "{M} unresolved". Interactions: tap row body to navigate to investigation; tap Acknowledge to flip state. Footer "View all {N} →" when total exceeds displayed.
  - **Detail** — full list with severity filter chips (All / Critical / Warning / Info) + bulk-of-one acknowledge actions per row + scrollable. Interactions: same as Brief plus chip filter toggles severity visibility.
- **The Acknowledge action is the canonical §12.6a test case** for widget-appropriate interactions:
  1. ✅ Bounded scope: single anomaly per click
  2. ✅ No coordination required: independent of other anomalies
  3. ✅ Reversible / low-stakes: false-alarm acks can be re-investigated via audit log
  4. ✅ Time-bounded: instant
  Vocabulary: UI says "Acknowledge"; data action sets `resolved=true` + records `resolution_note`; audit log records `action="anomaly_resolved"` for accuracy at the data layer. Per CLAUDE.md §12 Spec-Override Discipline: the data model uses `resolved` not `acknowledged` (model precedes the widget); widget UI vocabulary kept as "Acknowledge" because that's the user's mental model.
- **Tenant isolation** (load-bearing security gate): `agent_anomalies` has no direct `company_id` column; tenant scoping flows through `agent_job_id` FK → `AgentJob.tenant_id`. Every query in `app/services/widgets/anomalies_widget_service.py` explicitly joins `AgentJob` and filters `AgentJob.tenant_id == user.company_id`. The acknowledge endpoint re-validates tenant ownership BEFORE mutation; cross-tenant `anomaly_id` returns 404 (not 403, to avoid leaking existence). Verified explicitly via `TestTenantIsolation` test class with explicit cross-tenant fixtures.
- **NOT supported in any variant**: bulk acknowledge across many anomalies (would require selection model + multi-record coordination — Focus-required); anomaly authoring (anomalies are agent-generated, not user-authored); routing rules (which agent emits which severity is configured at agent level, not widget level).
- **Empty state** (Brief + Detail): "All clear" + sage `CheckCircle2` icon — accent-confirmed sage signals "good state" without using the celebratory accent terracotta. The empty state is a **first-class operational signal** ("nothing to worry about"), not an accidental absence.

**10. Saved View Widget (Phase W-3b cross-surface infrastructure reference — config-driven user-authored widget catalog).**
- Cold-start catalog: `saved_view`
- Variants: Brief + Detail + Deep (**NO Glance** — saved views need at minimum a list to be informative; count alone doesn't communicate row content + sort + group)
- Surface compatibility: `pulse_grid`, `dashboard_grid`, `focus_canvas` — **excludes `spaces_pin`** because sidebar requires Glance per §12.2 compatibility matrix and saved_view declares no Glance.
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/SavedViewWidget.tsx`
- Demonstrates: **the user-authored widget catalog without widget code**. A single `saved_view` widget definition + a `config: {view_id: <uuid>}` per-instance configuration mechanism turns every saved view in `vault_items.metadata_json.saved_view_config` into a widget instance. Tenants extend their effective widget catalog by authoring saved views; no code ship required. Pattern supersedes the pre-W-3b assumption that every "show me a list of X" needs its own widget definition. Phase W-3b Commit 0 closed the prerequisite — the pin contract carries `config` JSONB end-to-end through dispatch sites (`PinnedSection`, `Canvas`, `StackRail`, `BottomSheet`, `StackExpandedOverlay`, `WidgetGrid`).
- Data source: thin wrapper around the existing V-1c `SavedViewWidget` (`frontend/src/components/saved-views/SavedViewWidget.tsx`). The W-3b foundation wrapper reads `props.config.view_id`, validates it, and delegates rendering to V-1c — including the V-1c renderer's 7 presentation modes (list / table / kanban / calendar / cards / chart / stat) + visibility checks + cross-tenant masking. **Reuse over rebuild**: zero changes to V-1c.
- Per-variant content + interactions:
  - **Brief** — full V-1c rendering at compact density (`showHeader=false`; widget framework's container provides chrome). Surface-size constraints in `WidgetDefinition.variants.brief.canvas_size` (320×auto, maxHeight 400). Interactions per V-1c renderer (click-through to entity row, mode-specific affordances).
  - **Detail** — full V-1c rendering at standard density (`showHeader=true`). 480×auto, maxHeight 600. Same V-1c interaction set.
  - **Deep** — canvas-mounted maximum density. 640×auto, maxHeight 800. Same V-1c interaction set.
- **Empty state**: when `config.view_id` is missing or invalid, the widget renders an empty-state card (`Layers` icon + "No saved view configured" + "Pick a saved view from the library to display it here." copy + "Open saved views library →" link to `/saved-views`). Per Q4 fallback (b): inline picker dropdown deferred until a `PATCH /spaces/{space}/pins/{pin}` endpoint ships. Phase W-3b is widget shipping, not infrastructure expansion — settings-link fallback is honest about the missing PATCH path.
- **Sidebar pin rejection** (canonical guard): the Phase W-2 `add_pin` surface check rejects `pin_type="widget" + target_id="saved_view"` against a Spaces sidebar because `supported_surfaces` doesn't include `spaces_pin`. Defense-in-depth: even if a legacy layout pre-dates the rejection (or a misconfigured pin slips through), the dispatcher's defensive fallback renders Detail rather than crashing. Belt and suspenders.
- **NOT supported in any variant**: in-place saved view editing (rename, change query, change presentation, change visibility), saved view duplication, saved view deletion. Those are decision moments — full editing happens at `/saved-views/{view_id}` per §12.6a. The widget surfaces; the page owns.
- **Cross-tenant masking inheritance**: the V-1c renderer applies cross-tenant field masking automatically when `caller_company_id != owner_company_id`; the widget inherits this behavior without re-implementing it.

**11. Briefing Widget (Phase W-3b cross-surface infrastructure reference — per-user scoped narrative).**
- Cold-start catalog: `briefing`
- Variants: Glance + Brief + Detail (**NO Deep** — briefing detail is informationally complete; Deep would just re-render the dedicated `/briefing` page in widget chrome, which §12.6a discourages because heavy actions belong on the page, not the widget)
- Surface compatibility: `pulse_grid`, `spaces_pin`, `dashboard_grid`, `focus_canvas` — **excludes `peek_inline`** because briefing is per-user content, not entity-scoped; peek panels compose around an entity, neither of which a briefing has.
- Vertical: `"*"` (cross-vertical)
- Product line: `"*"` (cross-line)
- Reference component: `frontend/src/components/widgets/foundation/BriefingWidget.tsx`
- Demonstrates: **per-user scoping via existing primitive infrastructure** + **promotion of an existing surface to widget contract**. The Phase 6 BriefingCard (a dashboard element on manufacturing-dashboard.tsx) was already a complete-enough rendering; W-3b promotes it to the widget contract by wrapping it with variant-aware tablets without touching the data path. The `useBriefing` hook (Phase 6) drives all variant rendering. Per-user scoping is enforced server-side at the `/briefings/v2/latest` endpoint (which filters by `user_id == current_user.id`); the widget itself does no user filtering — the endpoint contract is the security boundary, not the widget. Pattern: when an existing primitive renders the right content, prefer thin variant-aware wrapper over rebuild.
- Data source: `useBriefing(briefing_type)` hook → `GET /api/v1/briefings/v2/latest?briefing_type={morning|evening}` with auto-retry-once on transient failure (Phase 7 `useRetryableFetch`). Per-user scoped server-side; the widget never sees other users' briefings.
- Per-instance briefing-type config: `config.briefing_type` ("morning" | "evening", default "morning"). Future tenants can pin a Glance "End of day summary" alongside the morning briefing for two complementary sidebar entries.
- Per-variant content + interactions:
  - **Glance** — sidebar-density single-line strip: briefing-type icon (Sunrise / Sunset) + "Morning briefing" / "End of day summary" label + unread accent dot when `briefing.read_at == null`. Frosted-glass tablet treatment per Pattern 1 (sidebar Glance). Empty state: "No briefing yet" routes to `/briefing`. Interactions: tap navigates to `/briefing/{id}` (or `/briefing` when empty). No state flips.
  - **Brief** — condensed card: briefing-type icon + title + narrative excerpt truncated to 320 chars at last-word-boundary + active space pill + Unread pill (when `read_at == null`) + "Read full briefing →" link. Empty state CTA. Interactions: tap "Read full" or click anywhere on the card → `/briefing/{id}`.
  - **Detail** — full narrative (no truncation) + structured-section preview cards (Queues, Flags, Pending decisions — top 5 each, severity dot per flag) + Read full link. Renders only known structured-section keys; unknown keys silently skipped per the Phase 6 contract.
- **NOT supported in any variant**: Mark-read (server stamp on `briefing.read_at`), Regenerate (Intelligence-billed regenerate), Preferences editing. All three live on `/briefing` and `/settings/briefings` per §12.6a — the dedicated page owns heavy + irreversible + Intelligence-cost actions; the widget surfaces.
- **Sidebar pin acceptance** (the §12.2 + §12.10 rule in action): the Phase W-2 `add_pin` surface check accepts `pin_type="widget" + target_id="briefing"` against a Spaces sidebar because `briefing` declares `Glance + spaces_pin`. The pin defaults `variant_id="glance"` per §12.2. This contrasts directly with widget #10 (`saved_view`) which is rejected for the same sidebar pin — same canon, opposite outcome, both correct.
- **Coexist-with-legacy discipline**: the Phase 6 `BriefingCard` component is NOT replaced by W-3b. Manufacturing-dashboard + order-station continue to mount `BriefingCard` directly (page-level rendering). The W-3b `BriefingWidget` is the **catalog-citizen** widget contract; Phase 6 `BriefingCard` is the **page-mounted** component. Both render briefing content; they have different consumers. Future natural-touch refactors may migrate page mounts onto the widget; this is not a W-3b deliverable.

**12. Vault Schedule Widget (Phase W-3d workspace-core canonical reference — mode-aware rendering).**
- Cold-start catalog: `vault_schedule`
- Variants: Glance + Brief + Detail + Deep (full set — workspace-core widgets are first-class)
- Surface compatibility: `pulse_grid`, `spaces_pin`, `dashboard_grid`, `focus_canvas` — excludes `peek_inline` (schedule is not entity-scoped)
- Vertical: `["manufacturing"]`
- Product line: `["vault"]`
- Reference component: `frontend/src/components/widgets/manufacturing/VaultScheduleWidget.tsx`
- Reference service: `backend/app/services/widgets/vault_schedule_service.py`
- Demonstrates: **first concrete workspace-core widget canonical reference per §12.6** + **mode-aware rendering per BRIDGEABLE_MASTER §5.2.2**. Production mode reads `Delivery` rows (kanban shape — same data the scheduling Focus core consumes); purchase mode reads incoming `LicenseeTransfer` rows (this tenant as `area_tenant_id`); hybrid composes both. **Why Delivery is the canonical scheduling entity (not SalesOrder):** ancillary items (urns, cremation trays, flowers) are **independent SalesOrders** sold separately to the funeral home customer. A funeral home ordering "1 vault + 1 urn + 1 tray" creates THREE SalesOrders → THREE Deliveries. Driver assignment + scheduling lives on Delivery (logistics concept), not SalesOrder (commercial concept). The widget consumes Delivery rows; the kanban card enriches each row with SalesOrder context (deceased name, line items, service location) at render time. See PLATFORM_ARCHITECTURE.md §9 + BRIDGEABLE_MASTER §5.2 for the SalesOrder vs Delivery distinction.
- Data sources (per mode):
  - **Production mode** — `Delivery` rows where `requested_date == today`, `scheduling_type IS NULL OR == "kanban"`, `status != "cancelled"`. Bulk-fetches linked `SalesOrder` rows for context enrichment + `Delivery` rows attached via `attached_to_delivery_id` for ride-along ancillary count.
  - **Purchase mode** — `LicenseeTransfer` rows where `area_tenant_id == this_tenant`, `service_date >= today AND < today+7 days`, `status IN (pending, accepted, in_progress, fulfilled)`. The tenant is the *receiver* of incoming POs from a supplier licensee.
  - **Hybrid mode** — both data sources composed; Brief stacks production + purchase sections; Detail shows driver lanes (production) + date buckets (purchase) in a unified rendering.
- Per-variant content + interactions:
  - **Glance** — count + mode-aware label ("X deliveries" / "X incoming" / "X scheduled" hybrid). Interactions: tap to summon mode-appropriate primary navigation target (`/dispatch` for production/hybrid; `/licensee-transfers/incoming` for purchase). Unassigned-warning dot when production has unassigned deliveries.
  - **Brief** — header (date + mode badge), per-section breakdown (production: assigned vs unassigned + ancillary attachment; purchase: top 5 incoming by service_date), "Open in scheduling Focus" footer link.
  - **Detail** — per-driver lane breakdown (production rows grouped by `primary_assignee_id`, "Unassigned" lane flagged with `data-unassigned="true"` for visual emphasis); per-service-date bucket breakdown (purchase rows grouped by date); attached ancillary count surfaced inline ("+2" indicator on parent vault delivery row).
  - **Deep** — same content shape as Detail; renderer chrome provides additional vertical room (max-height 900px). Workspace-core canon: Deep is informationally complete at Detail's grouping; Deep doesn't add a new layout, just more vertical space for long lists.
- **Bounded interactions per §12.6a (workspace-core canon)**: mark hole-dug status, drag delivery between drivers (single reassignment), update single ETA / start time, attach/detach ancillary, quick note. **NOT supported in any variant**: finalize schedule, day-switch / day-rebuild, bulk reassignment, conflict resolution, schedule rebuild after disruption, adding new deliveries — those are decision moments that require the Focus core's full editing chrome + workspace context. The "Open in scheduling Focus" affordance is always present in Brief / Detail / Deep.
- **Empty states**: tenant without vault product line activated → "Vault not enabled" + CTA to `/settings/product-lines`. Vault enabled but zero work today → "Nothing scheduled" + mode-appropriate CTA. Hybrid mode shows production sections only when production has work; purchase sections only when purchase has work — empty branches don't render section headers.

**13. Line Status Widget (Phase W-3d cross-line aggregator — multi-line builder pattern reference).**
- Cold-start catalog: `line_status`
- Variants: Brief + Detail (NO Glance — operational health doesn't compress to count-only per §12.10)
- Surface compatibility: `pulse_grid`, `dashboard_grid`, `focus_canvas` — excludes `spaces_pin` (no Glance variant) and `peek_inline` (not entity-scoped)
- Vertical: `["manufacturing"]`
- Product line: `"*"` (cross-line aggregator — renders for whichever lines the tenant has activated)
- Reference component: `frontend/src/components/widgets/manufacturing/LineStatusWidget.tsx`
- Reference service: `backend/app/services/widgets/line_status_service.py`
- Demonstrates: **first concrete cross-line aggregator** + **canonical multi-line builder pattern** (mirrors `today_widget_service.py`). Per active `TenantProductLine`, the dispatcher calls a per-line health builder: `_build_vault_health(db, tid, mode, today)` for vault (real metrics today); `_build_placeholder_health(line_key, display_name, mode)` for redi_rock / wastewater / urn_sales / rosetta (placeholder rows with `status="unknown"` until each line's metrics aggregator ships). When a future cluster wires real metrics for redi_rock or urn_sales, that line's row activates without restructuring; the aggregator stays mode-agnostic at the dispatcher level.
- Data source: `app.services.widgets.line_status_service.get_line_status(db, user)` queries `TenantProductLine` for active lines, dispatches per `line_key`. Vault health composes today's `Delivery` count + driver assignment distribution (production mode) or incoming `LicenseeTransfer` count (purchase mode) or both (hybrid).
- Per-line health vocabulary (canonical):
  - **on_track** — green; metrics nominal
  - **behind** — amber; metrics show slippage (production: >25% unassigned; purchase: pending transfers exist)
  - **blocked** — red; critical issue (heuristic placeholder for future capacity-vs-load analysis)
  - **idle** — neutral; line enabled but no work today
  - **unknown** — neutral; placeholder until line aggregator ships
- Per-variant content + interactions:
  - **Brief** — one row per active line: status icon + display name + headline metric ("8 pours today" / "no incoming today" / "8 pours · 2 incoming" hybrid). Click "→" navigates to that line's `<line_key>_schedule` widget at Detail (or Focus when ready). `data-attention="true"` on the widget root when any line is `behind` / `blocked` — gives shells/sidebars a regression-safe hook for visual emphasis.
  - **Detail** — same row structure with expanded metrics (per-line metrics dict surfaces non-zero values: `production_today`, `production_assigned`, `production_unassigned`, `purchase_today`, `purchase_pending`). Mode badge per row (Production / Purchase / Hybrid). Click-through CTA opens line-specific schedule.
- **NOT supported in any variant**: trade-off decisions across lines (e.g., "should we re-prioritize redi_rock production over vault to meet a deadline"), capacity rebalancing, bulk acknowledgments. Those are Focus-required when relevant Focus types ship. Per §12.6a — line_status surfaces health; decisions belong elsewhere.
- **Empty state**: tenant with no active product lines → "No product lines active" + CTA to `/settings/product-lines`.

**14. Urn Catalog Status Widget (Phase W-3d extension-gated reference — first `required_extension` axis activation).**
- Cold-start catalog: `urn_catalog_status`
- Variants: Glance + Brief (NO Detail/Deep — catalog management is the page's job; widget surfaces health)
- Surface compatibility: `pulse_grid`, `spaces_pin`, `dashboard_grid`, `focus_canvas` — excludes `peek_inline` (catalog is not entity-scoped)
- Vertical: `["manufacturing"]`
- Product line: `["urn_sales"]`
- **Required extension: `"urn_sales"`** ← first widget catalog entry exercising this axis
- Reference component: `frontend/src/components/widgets/manufacturing/UrnCatalogStatusWidget.tsx`
- Reference service: `backend/app/services/widgets/urn_catalog_status_service.py`
- Demonstrates: **first widget exercising the `required_extension` axis of the 5-axis filter end-to-end**. Phase W-1 implemented extension gating in `widget_service.get_available_widgets`; Phase W-3a + W-3b cross-vertical widgets used `"*"` for the extension axis. urn_catalog_status is the first concrete activation: visible only to tenants with the `urn_sales` extension activated AND the urn_sales product line enabled. Tests in `backend/tests/test_urn_catalog_status_widget.py::TestExtensionGatingEndToEnd` verify the filter actually gates: `(no urn_sales extension) → invisible`; `(extension activated + product_line enabled) → visible`; `(extension activated, product_line missing) → invisible` (the 5-axis filter is AND-wise: every axis must pass).
- Data source: `urn_catalog_status_service.get_urn_catalog_status(db, user)` queries `UrnProduct` (active + non-discontinued counts split by `source_type`), `UrnInventory` (low-stock identification: stocked SKUs where `qty_on_hand <= reorder_point AND reorder_point > 0`; reorder_point=0 means "no monitoring" and is excluded), `UrnOrder` (recent order count over last 7 days).
- Per-variant content + interactions:
  - **Glance** — single-line "{N} SKUs" + low-stock dot when `low_stock_count > 0`. Interactions: tap navigates to `/urns/catalog`. Reports "No catalog yet" when total_skus=0.
  - **Brief** — 4 metric rows (Stocked / Drop-ship / Low stock / Orders 7d) + low-stock list when applicable (top 3 lowest-stock SKUs with format `{sku} {name} {qty_on_hand}/{reorder_point}`). Footer "Open catalog →" link. `data-low-stock="true"` on the widget root when any SKU is at-or-below reorder point.
- **NOT supported in any variant**: adjusting stock levels, modifying reorder points, marking SKUs discontinued or active, ordering replenishment from suppliers. Catalog management lives at `/urns/catalog`. Per §12.6a — view-only with click-through.
- **Empty state**: tenant with extension activated but no products → "Catalog is empty" + CTA to `/urns/catalog`.

### Per-line widget naming convention

Per [BRIDGEABLE_MASTER §5.2](BRIDGEABLE_MASTER.md) Product Line Activation model, the platform builds per-line widgets following a stable naming convention:

| Pattern | Examples | Visibility (axis 5) |
|---|---|---|
| `<line_key>_schedule` | `vault_schedule`, `redi_rock_schedule`, `wastewater_schedule`, `urn_catalog_status` (urn line variant) | `required_product_line: ["<line_key>"]` |
| Cross-line aggregators | `line_status` | `required_product_line: "*"` (renders for whichever lines are active) |

**Naming discipline.**
- **Mode-agnostic.** The widget name does not embed an operating mode (`pour_schedule` would leak production bias; `vault_schedule` is correct because vault may run in production OR purchase OR hybrid mode).
- **Line-specific.** Per-line widgets carry the `line_key` exactly as it appears in `tenant_product_lines.line_key` so `required_product_line` filtering is unambiguous.
- **Plural avoided.** `vault_schedule` not `vaults_schedule`; the line is the noun.
- **Snake_case.** Matches the rest of the widget catalog (`recent_activity`, `urn_catalog_status`, etc.).

When a new product line activates the platform, three artifacts ship together:
1. Line registry entry (CODE-side: `line_key` + display_name + vertical association + default `operating_mode` + extension association if any)
2. `<line_key>_schedule` widget (per-line schedule + mode-aware rendering)
3. Line presence in `line_status` aggregator (automatic via the aggregator's per-active-line render loop)

Optional follow-ups: `<line_key>_status` standalone widget (if line has health metrics independent of schedule), `<line_key>_inventory` widget (if line has inventory worth surfacing), `<line_key>_pricing` widget (if pricing dynamics warrant). All follow the same `<line_key>_*` naming convention.

### Per-variant interaction declaration pattern

For Phase W-1 + W-2, per-variant interaction declarations are **convention** — documented in widget definition comments + canonical examples table (§12.6a) + reference implementations above. Phase W-3 widget builds declare per-variant supported interactions in their definition file as documentation; Phase W-3+ may promote to schema-level declaration if interaction discoverability becomes catalog-relevant.

The discipline is more important than the mechanism: when building a widget at any variant, ask the four §12.6a tests for each candidate interaction. If an interaction passes all four tests at the variant's content scope, surface it. If any test fails, route to Focus or the entity's dedicated page.

**Cold-start catalog widget interaction summary** (full per-variant declarations land in widget files; this is the consolidated canonical reference):

| Widget | Glance | Brief | Detail | Deep |
|---|---|---|---|---|
| `funeral_schedule` | None | drag, hole-dug | + ETA, ancillary, note | (same as Detail) |
| `ancillary_pool` | None | drag-attach, confirm, note | + per-item edits | n/a |
| `recent_activity` | None | tap-to-navigate | tap-to-navigate | n/a |
| `today` | None | acknowledge alerts | + dismiss completed items | n/a |
| `operator_profile` | None | switch active space | + edit role-driven defaults | n/a |
| `anomalies` | n/a | approve/reject/snooze (single anomaly) | + note per anomaly | n/a |
| `arrangement_pipeline` | n/a | tap to peek case | + mark stage complete (single case) | n/a |
| `vault_schedule` | None (count) | reassign single pour OR update single ETA, status flip per row | + quick note per row | + flanking-day peek (same interactions) |
| `urn_catalog_status` | None | tap-to-navigate | n/a | n/a |
| `line_status` | n/a | acknowledge alerts (per line) | + status flip per line | n/a |
| `saved_view` | n/a | execute view + view rows (interactions per saved-view config) | + filter / sort UI | + group / aggregation UI |
| `briefing` | None | tap to expand | + dismiss / mark-read | n/a |

In all rows, decisions involving trade-off evaluation, multi-record coordination, or commit-to-decision moments route to Focus or the entity's detail page. The matrix above is bounded to widget-appropriate interactions per §12.6a discipline.

**Per-line widget mode awareness.** `vault_schedule` interactions in the table above describe the canonical interaction set; the **content** of those interactions is mode-aware. Production-mode interactions operate on pour rows (reassign crew, mark pour complete); purchase-mode interactions operate on incoming-PO rows (update ETA, mark received). Same interaction vocabulary, mode-appropriate target. `line_status` is similarly mode-aware per active line. Future per-line schedule widgets (`redi_rock_schedule`, `wastewater_schedule`) inherit the same mode-aware contract.

**Naming note (canon update).** Pre-canon a `pour_schedule` widget was specified, implicitly assuming production-mode-only operation. Canon renames to `vault_schedule` (mode-agnostic, line-specific) and generalizes the pattern via the per-line naming convention above. Pre-canon `production_status` similarly assumed all lines run in production mode; canon renames to `line_status` (mode-agnostic, per-line health, cross-line aggregator).

**Migration path for existing 25+ widgets.**
- Operations Board widgets (16): wrap in `WidgetVariantProps` adapter, declare 1 Brief variant matching existing `default_size`, backfill `WidgetDefinition` from existing backend rows. Mechanical.
- Vault Overview widgets (9): same as ops-board.
- AncillaryPoolPin: becomes `scheduling.ancillary-pool` definition with 3 variants per above. Light refactor.
- MockSavedViewWidget: retired in favor of real `saved_view` widget definition.
- SavedViewWidget: promoted to first-class `saved_view` widget definition with config = `{view_id}`; 3 variants (Brief / Detail / Deep) matching saved-view presentation modes.
- BriefingCard: promoted to `briefing.morning` and `briefing.evening` definitions, 3 variants each.
- SpringBurialWidget / VaultReplenishmentWidget: become real WidgetDefinitions with `required_vertical` gating + 2 variants each (Glance + Brief).
- Peek panel renderers: stay separate (not widgets) per Decision 3; may internally compose widget components for content.

**Migration sequencing.**
- Phase W-1: contract + types + canvas-side dispatcher extension. No migrations. Foundation only.
- Phase W-2: Spaces pins gain widget pin_type. Existing widgets that have `supported_surfaces` including `spaces_pin` become pinnable to sidebars. Glance variants implemented for the cold-start subset.
- Phase W-3: build the 12 cold-start widgets. Each ships with declared variants.
- Phase W-4: Pulse surface ships, composing the cold-start catalog with role-driven defaults.
- Phase W-5+: long-tail migration of existing 25+ widgets to declared variants, "as touched."

### Cross-references

- **Section 0**: thesis tests — every widget passes "would the same team have made this?" against DeliveryCard + AncillaryPoolPin reference components.
- **Section 11 Pattern 1**: tablet treatment — visual contract widgets inherit.
- **Section 11 Pattern 2**: card material treatment — applied to grid-mounted widgets via `WidgetWrapper`.
- **Section 3 Widget elevation tier tokens**: `--widget-ambient-shadow`, `--widget-tablet-transform`, `--shadow-widget-tablet` — composed by floating-surface widgets.
- **Section 6 Border treatment**: cross-mode corner specs — frosted-glass widgets use rounded-none, solid-fill widgets use rounded-[2px].
- **PLATFORM_INTERACTION_MODEL.md** "The materialization unit — floating tablets": widgets are the canonical realization of the tablet primitive.
- **PLATFORM_ARCHITECTURE.md** §3 (Spaces / Pulse / Monitor) + future Widget Library subsection: phased implementation plan W-1 through W-6.
- **PLATFORM_PRODUCT_PRINCIPLES.md** "Widget Compactness": compact-to-contents canon applies; chrome scales with content, content scales with variant.
- **AESTHETIC_ARC.md** Widget Library Investigation + Specification entries: arc context.

---

## Section 13 — Spaces and Pulse Visual System

### 13.1 Purpose

This section captures the visual language for the Spaces system and Pulse surface. It complements §12 (Widget Library Architecture) by specifying how Space-level composition reads visually and how Pulse's intelligent composition signals its distinctive nature without dominating chrome.

### 13.2 Visual Hierarchy Across Space Types

All Space types share platform visual vocabulary established in §11 (eight patterns) and §12 (widget chrome). Distinctions between Space types are subtle, chrome-level differentiations rather than wholesale visual departures.

#### 13.2.1 Home Space (Pulse) Visual Treatment

Home Pulse renders as composed surface with subtle "intelligence" affordances:
- Standard Pattern 2 widget chrome for pinable widgets
- Standard tablet chrome for intelligence streams
- Tetris layout (no fixed grid columns; intelligence-determined sizing + position)
- Compact viewport-fit content density (no scrolling beyond viewport for primary content)
- Subtle "composed" affordance: brass thread (1px aged-brass divider) above primary work-surface content marking the Operational layer
- No edit mode (user does not customize Pulse content)
- Dismiss affordances on each piece of content (signal collection chrome — see §13.5)

#### 13.2.2 My Stuff and Custom Spaces Visual Treatment

Standard widget grid surface:
- Pattern 2 widget chrome
- Fixed grid columns (responsive to viewport)
- Edit mode toggle (visible drag handles, resize handles, remove affordances when active)
- Add-widget affordance in edit mode (empty cells show "+" CTA)
- User-customization-friendly chrome (clear what's editable vs locked)

#### 13.2.3 Settings / Cross-tenant / Portal Spaces

Detailed visual canon TBD per Space type in separate sessions. Default position: standard chrome with context-appropriate adaptations (Family Portal probably warmer/calmer; Driver Portal probably mobile-first; CPA Portal probably data-heavy with table emphasis).

### 13.3 Pulse Tetris Composition

#### 13.3.1 Layout Engine — viewport-fit canon (Phase W-4a Step 6 rewrite, May 2026)

Pulse is a **viewport-fit composed surface**. Pieces scale linearly with viewport. Total piece height + chrome equals viewport height — Pulse fills the available space, no whitespace at the bottom (within the canonical viewport range; see Question 6 ceiling). Composition engine determines content sizing in proportional units (cols × rows spans); the layout engine derives absolute pixel sizes from the available viewport.

**Architectural reframe (Phase W-4a Step 6).** Pre-Step-6 Pulse used `grid-cols-[repeat(auto-fit,minmax(160px,1fr))]` + `auto-rows-[80px]`. That model's "auto-fit collapse intentional, not regression" claim shipped with the W-4a Pulse infrastructure but proved insufficient against canonical user perception ("bigger viewport, bigger pieces"). Step 6 supersedes: tier-based fixed column counts + fractional viewport-derived row heights. The previous canon's "empty space acceptable" framing is reframed as "empty space is breathing room ABOVE the scale ceiling, not unfilled space below the canonical viewport range."

**Three viewport-width tiers determine column count:**

| Viewport width | Tier | Column count | Notes |
|---|---|---|---|
| `< 600 px` | Mobile | 2 | Pieces with `cols=1` fill half-width; `cols=2` fills full row. **Outside viewport-fit promise** — Pulse falls back to natural-height vertical scroll. See Q5 minimum-readable threshold. |
| `600 – 1024 px` | Tablet | 4 | Viewport-fit active. Pieces with `cols=2` fill half-width; `cols=4`-spanning would fill full row (uncommon — pieces declare cols ≤ 2 today). |
| `≥ 1024 px` | Desktop | 6 | Canonical Pulse experience. The Sunnycrest dispatcher demo composition is calibrated to this tier. |

**Tier transitions are discrete + CSS-transitioned.** Crossing a breakpoint (e.g. user resizing browser window from 1023px → 1025px) jumps column count from 4 → 6. CSS `transition: grid-template-columns 300ms ease-out` smooths the visual handoff so the transition reads as composition adapting rather than layout snapping.

**Within a tier**, both axes use fractional sizing:

```
cell_width  = (container_width  − total_horizontal_gaps) / column_count
cell_height = (available_pulse_height − total_vertical_gaps) / total_row_count
```

Where `total_row_count` is the sum of rows consumed by populated layers under tetris packing. Same `cell_height` applied to every cell in every populated layer — visual coherence per §13.3.2 (a Glance piece in personal layer is the same height as a Glance piece in operational layer).

**Pieces span declared `cols × rows`** (e.g., `vault_schedule` 2×2, `today` 1×1, `anomalies` Brief 2×1). **Spans are constant across tiers** — the relative composition shape stays stable as viewport changes. Larger viewport → bigger cells → bigger pieces, but vault_schedule is always the largest piece and today is always the smallest.

**Tetris packing + dense flow.** `grid-auto-flow: row dense` (added Phase W-4a Step 2.C, retained) lets smaller pieces (e.g. `today` Glance 1×1) backfill empty cells left by larger pieces' spans rather than leaving visible gaps. The composition engine still emits pieces in priority order; dense flow only changes which empty cell each smaller piece lands in, not the order they're placed.

**Mobile fallback (`< 600 px` viewport width)**: Pulse is intentionally outside the viewport-fit promise. The 2-column tier produces cells too narrow + viewport heights too cramped for fit-math to land on readable cell sizes. Mobile renders Pulse as a natural-height vertical scroll: cells use `auto`/`max-content` row sizing, surface scrolls vertically, pieces stack at content-driven sizes. Both presentations are correct for their context — desktop users see Pulse as composed surface; mobile users see Pulse as vertical content stream. This split is honest, not a regression.

**Tier-three threshold** (computed `cell_height < 80 px` on tablet+): even within tier, pathologically heavy compositions (e.g. 8+ row count from a tenant with many anomalies + many ops widgets + populated personal layer) can crush cells below readable. When the chrome budget math produces `cell_height < 80px` for the desktop or tablet tier, Pulse switches to natural-height + scroll mode for that session. `console.warn` fires for observability so the composition shape can be tuned. Reference: §13.3.4.

**Math closure (Phase W-4a Step 6).** The viewport-fit promise is mathematically closed: `cell_height` is the single solved variable that makes total layer heights + chrome budget = viewport height by construction. Reference implementation in §13.3.4 (Viewport-Fit Math).

#### 13.3.2 Layer Visual Demarcation

Four layers compose Pulse content. Visual demarcation between layers is subtle:

- **Personal layer** at top (always first when present)
- **Operational layer** dominates primary work-surface area (largest pieces typically here)
- **Anomaly layer** intermixes with Operational when severity warrants (high-severity anomalies inline with operational content)
- **Activity layer** ambient at periphery (smaller pieces, lower visual weight)

No hard section dividers between layers. Brass-thread (1px aged-brass divider) marks Operational layer boundary subtly. Other layers blend through positioning + sizing rather than chrome.

**Cell-height consistency across layers (Phase W-4a Step 6 amendment).** Every populated layer's cells use the same `cell_height` per §13.3.4 viewport-fit math. A Glance piece in the personal layer is the same height as a Glance piece in the operational layer. Layer-level vertical real estate differs (operational typically takes more rows than personal), but per-cell size stays consistent. This visual coherence is load-bearing for the composed-surface read — different cell heights across layers would fracture Pulse into disconnected sections rather than reading as one composition.

**Transition discipline on cell-height recomputation (Phase W-4a Step 6 amendment).** Layer composition changes (piece dismiss, piece add via late-arriving content, viewport resize crossing a tier boundary) trigger `cell_height` recomputation, which ripples to every cell in every layer. Naive recomputation would cause every piece to resize abruptly — jarring visual jitter. The canonical handling: **300ms ease-out CSS transition on `grid-template-rows` + `--cell-height`** (the latter being the CSS variable PulseSurface exposes for cell sizing). Pieces resize smoothly; the surface reads as composition adapting rather than layout snapping. Dismissals, viewport changes, and late-arriving compositions all share the same transition timing for predictable feel.

**Empty-layer advisory fixed allowance (Phase W-4a Step 6 amendment).** Empty-with-advisory layers ("All clear — nothing needs attention right now.", "Quiet day so far.") render at a fixed 32px height regardless of viewport scale. They sit OUTSIDE the row-count-weighted allocation — the viewport-fit math allocates available height to populated layers' rows, then layers with advisories add their fixed 32px on top of that. Empty-no-advisory layers (e.g., personal layer with no pinned items + no advisory copy) suppress entirely (zero height), as already documented in PulseLayer's render contract.

#### 13.3.2.1 Workspace-core empty-state shape (Phase W-4a Step 2/3 amendment)

Workspace-core widgets per §12.6 preserve their workspace shape in empty states. The kanban shape, calendar shape, or board shape **IS the cognitive affordance** — operators identify the widget by structural shape, not by data presence. Generic empty-state messages (centered icon + body text + CTA) are for non-workspace-core widgets only.

**Distinction:**

- **Data-empty** (workspace exists, no data today): preserve shape. The kanban frame renders with section eyebrows and dashed-border lane placeholders. Header + footer survive. The user reads the widget as "scheduling workspace, currently empty" — not as "what happened to my widget?"
- **Structurally-empty** (workspace not enabled for this tenant — vault product line not active, urn extension not installed, etc.): use a centered "Vault not enabled" message with an enable-workspace CTA. The product line is absent; the workspace shape is moot.

**Reference**: `vault_schedule` Detail variant.
- Data-empty: `data-empty="true"` attribute + section eyebrow ("Production · Driver lanes / 0 total") + dashed-border lane placeholder ("No deliveries scheduled — driver lanes ready") + `data-slot="vault-schedule-empty-section"` + `data-slot="vault-schedule-empty-lane-placeholder"` survive. "Open in scheduling Focus →" footer link survives.
- Structurally-empty: centered icon + "Vault not enabled" title + "Activate the vault product line to see scheduled deliveries here." + "Manage product lines →" CTA. `data-slot="vault-schedule-empty-cta"` distinguishes the centered branch.

Future workspace-core widgets (per-line schedule widgets in W-3d, FH arrangement_pipeline in W-3c) follow the same shape-preserving empty-state pattern.

#### 13.3.3 Multi-stream Within Layers

A layer can contain multiple distinct content streams. Each stream renders as its own piece in tetris layout — emails are one piece, system events another piece, both within Activity layer but visually distinct.

Streams within a layer have visual coherence (similar chrome, similar sizing tendencies) without being grouped into compound containers. The user reads Pulse as composed pieces, not as nested layers.

#### 13.3.4 Viewport-Fit Math (Phase W-4a Step 6, May 2026)

The math that makes `total piece height + chrome = viewport height` close. This subsection is the canonical reference for the implementation; tests + future audits cross-reference against the formulas here.

**Step 1 — Compute available Pulse height from chrome budget.**

```
available_pulse_height = viewport_height
  − APP_HEADER_HEIGHT                  (56 px, always present)
  − BOTTOM_TAB_BAR_HEIGHT_MOBILE       (56 px, mobile only — 0 on tablet/desktop)
  − DOT_NAV_HEIGHT                     (32 px, always present)
  − PULSE_PAGE_PADDING_Y               (48 px = py-6 ×2)
  − BANNER_HEIGHT                      (96 px when first-login banner visible, else 0)
  − LAYER_SPACING_TOTAL                ((N_layers − 1) × 16 px = 48 px for 4 layers)
  − BRASS_THREAD_OVERHEAD              (24 px = mt-2 + pt-4 + 1 px line above operational)
  − empty_layer_advisory_total         (32 px × count_of_empty_layers_with_advisory)
```

For September: hard-coded constants per `frontend/src/components/spaces/PulseSurface.tsx` module-level. Post-September canonical target: dynamic `ResizeObserver` on each chrome element so changes to header height / DotNav height ripple naturally without canon updates. Hard-coded constants must include a TODO comment pointing at this section.

**Step 2 — Determine column count from viewport tier.**

```
column_count =
  2  if viewport_width < 600 px        (Mobile — fallback to natural-height scroll, see §13.3.1)
  4  if 600 ≤ viewport_width < 1024 px (Tablet)
  6  if viewport_width ≥ 1024 px       (Desktop)
```

**Step 3 — Compute total row count from composition shape.**

```
total_row_count = Σ (layer_row_count[i]) for i in populated_layers

where layer_row_count[i] = max(row_index_used + 1) under tetris packing
                          for layer i's pieces with column_count cells per row
```

Tetris packing solved per layer independently; pieces span their declared `(cols, rows)` within the layer's grid. Dense auto-flow lets smaller pieces backfill empty cells; doesn't change `layer_row_count` (still derived from max row index occupied).

**Step 4 — Solve cell_height.**

```
total_vertical_gaps = (total_row_count − 1) × CELL_GAP_Y       (12 px = gap-3 vertical)
                      + (count_of_populated_layer_internal_gaps)
                      // Cell gaps WITHIN a layer's grid only; layer-spacing already in chrome budget

cell_height = (available_pulse_height − total_vertical_gaps) / total_row_count
```

`cell_height` is the single solved variable that makes the composition fit the viewport. Same value applies to every cell in every populated layer.

**Step 5 — Tier-three threshold check.**

```
if cell_height < 80 px AND tier ∈ {Tablet, Desktop}:
  switch to natural-height + scroll mode for this session
  console.warn("[pulse] cell_height < 80px threshold; falling back to scroll mode",
               { cell_height, total_row_count, viewport_height, banner_visible })
```

**Step 6 — Compute --pulse-scale and chrome scaling.**

```
--pulse-scale = clamp(0.875, available_pulse_height / 900, 1.25)
```

`900` is the canonical baseline (1080p desktop minus chrome ≈ 896-900px). Below baseline (compressed), scale dips to 0.875 floor. Above baseline (large desktop, 4K, 5K), scale climbs to 1.25 ceiling. Beyond the ceiling, additional viewport space distributes as cell-internal padding (breathing room) per §13.3.1's "ceiling" framing — typography stays readable at peak Apple form, additional space goes to comfort, not bigger text.

**Step 7 — Apply via CSS variables.**

```css
.pulse-surface {
  --pulse-content-height: <step-1 result>px;
  --pulse-cell-height: <step-4 result>px;
  --pulse-scale: <step-6 result>;
}
.pulse-layer-grid {
  grid-template-columns: repeat(var(--pulse-column-count), 1fr);
  grid-template-rows: repeat(var(--layer-row-count), var(--pulse-cell-height));
  transition: grid-template-rows 300ms ease-out, grid-template-columns 300ms ease-out;
}
```

**Constants documented here**:

| Token | Value | Source / rationale |
|---|---|---|
| `APP_HEADER_HEIGHT` | `56 px` | `frontend/src/components/layout/app-layout.tsx` h-14 |
| `BOTTOM_TAB_BAR_HEIGHT_MOBILE` | `56 px` | `frontend/src/components/layout/mobile-tab-bar.tsx` h-14, mobile only |
| `DOT_NAV_HEIGHT` | `32 px` | `frontend/src/components/layout/DotNav.tsx` (rough vertical claim) |
| `PULSE_PAGE_PADDING_Y` | `48 px` | `py-6` × 2 sides |
| `BANNER_HEIGHT` | `96 px` | Sparkles icon + heading + body + CTA + dismiss X (when present) |
| `LAYER_SPACING` | `16 px` | `space-y-4` between layers |
| `BRASS_THREAD_OVERHEAD` | `24 px` | `mt-2` + `pt-4` + 1px line, above Operational layer only |
| `EMPTY_LAYER_ADVISORY_HEIGHT` | `32 px` | Fixed advisory row, regardless of viewport scale |
| `CELL_GAP_Y` | `12 px` | `gap-3` |
| `MIN_READABLE_CELL_HEIGHT` | `80 px` | Tier-three threshold for natural-height-scroll fallback |
| `MOBILE_BREAKPOINT` | `600 px` | Below = mobile fallback (natural-height-scroll) |
| `TABLET_BREAKPOINT` | `1024 px` | Below = 4-col tablet tier; ≥ = 6-col desktop tier |
| `BASELINE_AVAILABLE_HEIGHT` | `900 px` | --pulse-scale anchor (1080p minus typical chrome) |
| `SCALE_FLOOR` | `0.875` | Minimum --pulse-scale (compressed viewports) |
| `SCALE_CEILING` | `1.25` | Maximum --pulse-scale (large viewports → breathing room thereafter) |
| `TRANSITION_DURATION` | `300 ms` | Cell-height recomputation + tier transition timing |
| `TRANSITION_EASING` | `ease-out` | Settle-feel curve |

**Reference implementation**: `frontend/src/components/spaces/PulseSurface.tsx` + `PulseLayer.tsx` (post-Step-6 implementation; rendered against this section's formulas verbatim). Tests in `PulseSurface.test.tsx` cross-reference these constants — drift between docs + implementation is a defect.

### 13.4 Content Stream Visual Treatments

#### 13.4.1 Pinable Widget Pieces

Render with Pattern 2 chrome (locked in §12.5) at variant-determined size:
- Glance (1×1) — peripheral, single-data-point pieces
- Brief (2×1 or 2×2) — standard pieces, primary-content visible
- Detail (2×2 or 3×2) — work-surface pieces, primary work content
- Deep (3×2 or 4×2) — canvas-mounted pieces, full content rendering

Variant chosen by Pulse intelligence based on priority + viewport availability.

**Chrome-is-surface-responsibility convention (Phase W-4a Step 5 amendment, May 2026).** Pattern 2 chrome is the **surface's** responsibility, not the widget's. The surfaces that host pinable widgets (`PulsePiece` for Pulse, `WidgetWrapper` for dashboard surfaces, future `PinnedSection` widget pin renderer) apply Pattern 2 chrome at their own root. Widget renderer components MUST NOT apply Pattern 2 chrome at their root — doing so produces nested cards when the surface also applies chrome.

**Reference**: `frontend/src/components/spaces/PulsePiece.tsx` applies `rounded-[2px] bg-surface-elevated border border-border-subtle shadow-level-1` at its outer div. `frontend/src/components/widgets/WidgetWrapper.tsx:72` applies `rounded-md bg-surface-elevated shadow-level-1` at its outer div. Widget renderers (`VaultScheduleWidget`, `LineStatusWidget`, `TodayWidget`, `AnomaliesWidget`, etc.) have only content layout (`flex flex-col h-full p-4 gap-3`) at their root — no chrome.

**Pre-Step-5**: PulsePiece's docstring claimed widget renderers carry their own Pattern 2 chrome. That assumption was wrong — only `WidgetWrapper` applied chrome (dashboard surface), and Pulse pieces rendered without any chrome at all. Step 5 corrects: PulsePiece applies Pattern 2 chrome at its root + AnomalyIntelligenceStream's previously-duplicated chrome moved up to PulsePiece (single source of truth, no nested cards). Widget renderers stay chrome-less. Future surfaces hosting widgets follow the same pattern.

**Surface-specific widget compaction (Phase W-4a Step 2/3 amendment, refined Step 6).** Pinable widgets may have surface-specific compact rendering. Pulse (`pulse_grid`) honors grid cell size constraints. Dashboard surfaces (`dashboard_grid`) render full Brief content with rows.

**Phase W-4a Step 6 amendment — container queries canonical for Pulse density.** Inside Pulse, density shifts respond to actual cell size, not a static surface label. Widgets that opt into density-tier rendering use `@container piece (...)` to switch between three densities:

- **Default** — assumes `cell_height ≥ 120 px`. Full Brief content (rows, descriptive copy, etc.).
- **Compact** — fits `cell_height` 80–120 px. Header + footer only (the anomalies Pulse-compact pattern from Step 2 D becomes this density tier).
- **Ultra-compact** — fits `cell_height` 60–80 px. Single-line dense rendering (icon + count + CTA inline).

The container query targets the cell, not the page:

```css
@container piece (max-height: 100px) {
  .anomalies-widget-pulse-compact { /* compact rendering */ }
}
@container piece (max-height: 80px) {
  .anomalies-widget-pulse-ultra-compact { /* single-line dense */ }
}
```

`PulsePiece` declares itself as a container (`container-type: size; container-name: piece`) so each piece's content responds to its cell size independently.

**Per-widget density tier opt-in.** Widgets opt INTO density tiers; they don't have to support all three. Most widgets render the same content at all densities (just smaller spacing/font via `--pulse-scale`). Widgets with structurally distinct compact modes (anomalies' "drop the rows" mode, line_status' "summary line only" mode) declare their compact + ultra-compact rendering explicitly via `@container` queries. Widgets without explicit declarations fall back to default rendering at all cell sizes (and may overflow if cell is small — surfaced as a defect through CI tests + visual review).

**Workspace-core widget exemption.** Workspace-core widgets per §12.6 (e.g. `vault_schedule` Detail) preserve their workspace shape per §13.3.2.1. They MAY NOT aggressively compact — the kanban frame IS the cognitive affordance. When a workspace-core widget can't fit its minimum content in the cell allocated, the canonical fallback is **scroll within piece** (the widget's own `overflow-y: auto`). Workspace-core widgets do not opt into ultra-compact density.

**Surface prop for non-Pulse surfaces.** The `surface` prop (`pulse_grid` | `dashboard_grid` | `focus_canvas` | `focus_stack` | `spaces_pin`) stays on the widget renderer signature for non-Pulse surfaces. Sidebar pins (`spaces_pin`) and dashboard widgets use `surface` to select rendering. Pulse-grid rendering is now driven by container queries (which inspect actual cell size, not surface label); the `surface="pulse_grid"` prop remains for explicit identification + back-compat with Step 2 D rendering.

**Reference**: `anomalies` widget Brief variant.

| Density | Cell height range | Content |
|---|---|---|
| Default (`@container piece (min-height: 121px)`) | ≥ 121 px | Full 4-row list with per-row Acknowledge action + "View all N →" footer |
| Compact (`@container piece (max-height: 120px) (min-height: 81px)`) | 81–120 px | Header (count + critical breakdown + count badge) + footer ("Investigate N →"). Body/rows skipped. |
| Ultra-compact (`@container piece (max-height: 80px)`) | ≤ 80 px | Single-line: icon + "N anomalies" + critical badge + "Investigate →" inline. |

Pulse cell sizes derived from §13.3.4 viewport-fit math; widgets respond automatically.

**Pattern**: opt into density tiers when intrinsic content varies meaningfully across cell sizes. Most widgets won't need this — they render uniform content with `--pulse-scale` typography. Density tiers are for widgets like anomalies / line_status / today / briefing where the small-cell rendering is structurally different from the large-cell rendering.

**Pre-Step-6 Pattern (preserved as `surface=pulse_grid` fallback)**: Step 2 D's `surface === "pulse_grid"` branch in widget renderers stays as the explicit-fallback path. Container queries are canonical; `surface` prop is the back-compat path for older renderers + the explicit-identification path (e.g., for tests asserting "this rendering came from Pulse"). When both mechanisms apply, container queries win (more accurate to actual cell size).

#### 13.4.2 Intelligence Stream Pieces

Render with similar Pattern 2 chrome but with intelligence-stream-specific affordances:
- Smart email surfacing pieces show source email metadata (subject, sender, original date) plus contextual relevance reason ("you committed to follow up on this 3 weeks ago")
- Daily briefing pieces show synthesized text in friendly typography (slightly larger reading-text size; brass accent on key entities)
- Coordination summary pieces show cross-tenant context with tenant-color accent
- Anomaly intelligence pieces show synthesis above raw anomaly count
- Conflict detection pieces show conflicting items with terracotta connection indicator

Intelligence streams are visually distinct from pinable widgets via:
- Slightly more prose/text vs structured data
- Reasoning-context chrome ("because..." or "given..." subtle text)
- Brass thread accents at piece edges (signaling composed-by-intelligence)

This subtle distinction signals "this is intelligent content" without dominating chrome. User can tell Pulse pieces apart but the surface reads coherently.

#### 13.4.3 Agency-Dictated Error Surface (Phase W-4a Step 6, May 2026)

When a widget renderer is unavailable (registered but not in the renderer registry, or registered but throws at render time), the error-surface treatment depends on **who composed the surface**: platform or user.

**Platform-composed surfaces (silent filter + log)**:

- **Pulse** (`pulse_grid`) — composition engine plans the surface. If a widget can't render, the platform's choice is silently overridden. The slot disappears from the layout entirely; layer compacts to remaining items via tetris repacking. `console.warn("[pulse] missing widget renderer; skipping piece", {component_key, layer, item_id})` fires for observability. RUM integration captures the warn (post-September). Users never see misconfigurations they didn't author.

- **Future platform-composed surfaces** (briefing summaries, default standard-Spaces dashboards if platform-seeded) follow the same pattern.

**User-composed surfaces (visible placeholder)**:

- **`PinnedSection`** (sidebar pins) — user explicitly pinned the widget. If broken, they SHOULD see the broken state — they own the configuration. `MissingWidgetEmptyState` renders in place with the offending `widget_id` surfaced for QA observability + user transparency.

- **Custom Spaces dashboards** (Phase W-5+) — user added the widget to their dashboard. `MissingWidgetEmptyState` renders in place.

- **Future user-composed surfaces** (saved-view-as-widget instances on user's surfaces, etc.) follow the same pattern.

**Why agency dictates the treatment**: composition agency = error-surface agency. If the platform composed and made a wrong choice, the platform should clean up silently — surfacing the platform's wrong choice TO the user is poor UX (they didn't ask for it). If the user composed and made a wrong choice, the user should see the consequence — surfacing it gives them feedback to fix or remove.

**CI parity test mandatory.** Every backend `widget_id` declared in `app/services/widgets/widget_registry.py::WIDGET_DEFINITIONS` must have a corresponding frontend renderer registered via `registerWidgetRenderer(widget_id, Component)`. A vitest test imports all widget-registration modules + asserts every backend widget_id resolves to a registered renderer (not the fallback). The CI parity test fails loudly when a backend declaration has no frontend implementation — surfaces backend/frontend drift before it reaches production.

The CI test does NOT cover renderers throwing at render time (e.g., AncillaryPoolPin throws when called outside `SchedulingFocusDataProvider`). That class of failure is observed via `console.warn` from the platform-composed-surface filter at runtime.

**Reference implementations**:
- `frontend/src/components/focus/canvas/widget-renderers.ts::getWidgetRenderer` — fallback split: `widgetType === undefined` → MockSavedViewWidget (legacy/test); `widgetType` set-but-not-registered → `MissingWidgetEmptyState`. (Step 5)
- `PulseLayer` filter (Step 6 implementation) — items where the renderer resolves to `MissingWidgetEmptyState` are filtered from `visibleItems` + `console.warn` fires.
- `PinnedSection` (Step 5 unchanged) — user pinned the widget; placeholder visible.
- CI parity test: `frontend/src/__tests__/widget-renderer-parity.test.ts` (Step 6 — new file).

### 13.5 Signal Collection Chrome

Pulse Tier 2 intelligence requires dismiss + navigation tracking. Chrome supports this with subtle affordances:

#### 13.5.1 Dismiss Affordances

Each Pulse content piece has dismiss affordance:
- Subtle X icon top-right of piece (visible on hover, otherwise low-contrast)
- Dismiss action records signal (user dismissed this content type at this time of day)
- Confirmation: piece animates out smoothly
- Re-surface logic: dismissed content stays out for a calibrated window (next morning, next week, etc.)
- "Restore dismissed" affordance in Pulse footer (rarely-used escape hatch)

#### 13.5.2 Navigation Tracking

Click-through from any Pulse piece records signal:
- What user clicked
- Where it navigated to
- Time of navigation
- Time spent on Pulse before navigating

No visible chrome for navigation tracking — invisible signal collection.

#### 13.5.3 Engagement Indicators (Tier 2+)

When Tier 2 algorithms ship post-September, subtle engagement indicators may surface:
- "Frequently used" markers on consistently-engaged content
- "New for you" markers on content surfaced based on recent behavior shift
- Calibrated to feel adaptive, not surveillance-y

Specific chrome TBD when Tier 2 ships.

### 13.6 Onboarding Visual Treatment

Onboarding flow captures work areas + responsibilities with care:

#### 13.6.1 Work Area Multi-select

Multi-select cards for work areas:
- Each work area as visual card (icon + label + brief description)
- Cards arrange in responsive grid
- Selection state: brass border + filled background
- Multiple selections allowed (encouraged by phrasing)
- Save-and-continue requires at least one selection
- Adjustable post-onboarding via Settings Space

#### 13.6.2 Responsibilities Description

Free-text input for responsibilities:
- Multi-line text area (calibrated for ~3-5 sentence response)
- Placeholder text models good response: "Tell us about your day-to-day. What do you do, what do you watch out for, what do you wish you had better visibility into?"
- Auto-save as user types
- Skippable but encouraged ("This helps Bridgeable understand what to surface for you")
- Adjustable post-onboarding via Settings Space

### 13.7 Visual Coherence Discipline

Across Space types, visual coherence is maintained:
- Same brass accent color across Pulse and standard dashboards
- Same widget chrome (Pattern 1 / Pattern 2) across surfaces
- Same typography (Fraunces display + Geist body + Geist Mono numerals)
- Same iconography (Lucide)
- Same dark/light mode treatment

Distinctions between Space types are intentional but subtle. User moving between Home Pulse and a custom Space should feel continuity ("same platform") with awareness ("different mode").

### 13.8 Reference Implementations

Phase W-4a (April 2026) shipped the Home Pulse infrastructure end-to-end. The references below are locked against that build and serve as calibration anchors for subsequent component refinement and post-September iteration. Three additional references — **My Stuff Space** (Phase W-4b+), **Custom Space template** (Phase W-5), and the **full Onboarding flow** including the multi-select work-area card grid (deferred until the standalone onboarding visual lands) — will be added as those phases ship.

#### 13.8.1 Home Pulse — Sunnycrest dispatcher (canonical composition)

The reference for §13.3 Tetris Composition + §13.4 Content Stream Visual Treatments is the Sunnycrest dispatcher Pulse surface. Two states are locked (the platform must render both coherently).

**State A — User without `work_areas` set (vertical-default fallback per D4):**
- `metadata.vertical_default_applied = true`
- `PulseFirstLoginBanner` renders at the top of `PulseSurface` per §13.6
- Operational layer composes the `manufacturing` vertical-default set: `vault_schedule` Detail (2×2) + `line_status` Brief (2×1) + `scheduling.ancillary-pool` Brief (2×1) + `today` Glance (1×1) + `urn_catalog_status` Glance (only when the `urn_sales` extension is active)
- Anomaly + Activity layers render their advisory text in italic when empty
- Brass-thread divider above the Operational layer per §13.3.2 — 1px solid terracotta accent at 30% alpha

**State B — User with canonical Sunnycrest dispatcher `work_areas` set:**
- `work_areas = ["Production Scheduling", "Delivery Scheduling", "Inventory Management"]`
- `responsibilities_description` populated with operator-narrative text (e.g., *"I dispatch vault deliveries, coordinate ancillary pickups, and watch inventory levels for upcoming pours."*)
- `metadata.vertical_default_applied = false`
- `PulseFirstLoginBanner` is suppressed
- Operational layer matches the same canonical D5 composition: `vault_schedule` Detail (2×2, primary work surface) + `scheduling.ancillary-pool` Brief (2×1) + `line_status` Brief (2×1) + `today` Glance (1×1)
- Personal layer surfaces the `approvals_waiting` stream when the user has pending approvals; otherwise renders an empty advisory
- Anomaly intelligence stream synthesizes prose when the tenant has unresolved `AgentAnomaly` rows; brass-thread accents at piece edges per §13.4.2

The composition emerges from the work-area-to-widget mapping in `backend/app/services/pulse/operational_layer_service.py` — the canonical reference for the §3.26.3.1 work-area vocabulary.

#### 13.8.2 PulseSurface tetris grid

`frontend/src/components/spaces/PulseSurface.tsx` + `PulseLayer.tsx` implement §13.3.1. The locked grid contract:
- Custom CSS Grid: `grid-cols-[repeat(auto-fit,minmax(160px,1fr))] auto-rows-[80px] gap-3`
- Pieces consume cells via inline `gridColumn: span {cols}` + `gridRow: span {rows}` derived from each `LayerItem.cols / .rows` (sized by the composition engine, not the renderer)
- Per-layer padding via `space-y-4` between layers — breathing-room composition per §13.3.1
- Empty layers (`pieces.length === 0`) render a single italic advisory line (`pulse-layer-advisory` slot) when the layer service emits one; otherwise the layer returns `null` so it doesn't reserve vertical space

#### 13.8.3 Operational layer brass-thread divider

`PulseLayer` applies `border-t border-accent/30 pt-4 mt-2` ONLY when `layer === "operational"`. Visual contract:
- 1px solid border using the platform terracotta accent token at 30% alpha
- 16px top padding + 8px top margin separating the divider from the layer above
- Subtle: passes the **cover-with-hand test** — covering the line with a hand should not change the user's perception of layered composition; the divider reinforces an already-readable hierarchy rather than carrying it
- Single-value across light + dark mode per Aesthetic Arc Session 2 (no asymmetric tokenization)

The divider is the only chrome marker between layers. Personal / Anomaly / Activity layers blend through positioning + sizing per §13.3.2.

#### 13.8.4 PulsePiece — two content primitives

`PulsePiece.tsx` dispatches by `LayerItem.kind`:
- `kind="widget"` → routes through the widget renderer registry (`getWidgetRenderer`) with `surface="pulse_grid"` and the item's `variant_id` + `config`. Pattern 2 chrome inherited from §12.5.
- `kind="stream"` → renders the matching `IntelligenceStream` content via the stream renderer registry; `AnomalyIntelligenceStream` is the Phase W-4a reference implementation per §13.4.2.

Dismiss chrome (X icon, top-right, opacity-0 default → group-hover:opacity-100) per §13.5.1 and click navigation tracking per §13.5.2 are wired uniformly across both primitives.

#### 13.8.5 AnomalyIntelligenceStream — V1 reference for §13.4.2

`frontend/src/components/spaces/intelligence-streams/AnomalyIntelligenceStream.tsx` is the locked V1 reference for the intelligence-stream visual treatment:
- Pattern 2 chrome (`bg-surface-elevated rounded-[2px] border border-border-subtle`) + brass-thread top edge via `before:` pseudo-element (`before:h-px before:bg-accent`)
- `Sparkles` Lucide icon (terracotta) + `title` (display-weight) + `synthesized_text` (body, slightly larger reading-text size) per §13.4.2
- `referenced_items` rendered as a row of chips (top 5; remainder collapsed into a "+N more" indicator)
- Click dispatches `onReferencedItemClick` for the navigation signal collection contract

Future intelligence streams (smart email surfacing, daily briefing, cross-tenant coordination, conflict detection — Phase W-4b) extend the same chrome pattern with stream-specific affordances.

#### 13.8.6 PulseFirstLoginBanner — §13.6 onboarding surface

`PulseFirstLoginBanner.tsx` is the locked reference for the §13.6 onboarding affordance on the Pulse surface itself. Visual contract:
- Inline banner above all layers (NOT a tooltip — `OnboardingTouch` is the tooltip primitive; this banner shares the persistence hook `useOnboardingTouch("pulse_first_login_banner")` but renders as inline content)
- `bg-accent-subtle` (terracotta @ 10% alpha) + `border-accent/30`
- `Sparkles` icon + heading *"Personalize your Pulse"* + body explainer + brass-filled CTA button rendering as a `<Link to="/onboarding/operator-profile" />` + dismiss X
- Suppressed in two cases: (1) `metadata.vertical_default_applied === false` (user has work_areas set), (2) the onboarding-touch flag is already dismissed
- Dismissal persists server-side via `useOnboardingTouch` — cross-device, cross-session

The full onboarding visual (multi-select work-area card grid + responsibilities textarea per §13.6.1 / §13.6.2) lands when the dedicated `/onboarding/operator-profile` route ships its visual; only the editor API surface (`PATCH /api/v1/operator-profile`) is locked in Phase W-4a.

#### 13.8.7 Signal collection chrome

The dismiss chrome on `PulsePiece` and the navigation signal collection on click-through are the locked reference for §13.5. Visual + behavioral contract:
- Dismiss X positioned top-right, `opacity-0 group-hover:opacity-100` so chrome stays low-contrast at rest per §13.5.1
- Click on dismiss → fire-and-forget `POST /api/v1/pulse/signals/dismiss` with `{component_key, layer, time_of_day, work_areas_at_dismiss}`; piece animates to `opacity-0 scale-95` over 200ms before unmount
- Click on the piece body (or descendant `<a>` link) → fire-and-forget `POST /api/v1/pulse/signals/navigate` with `{from_component_key, to_route, dwell_time_seconds, layer}`; `dwell_time_seconds` computed client-side as `(Date.now() - pulseLoadedAt) / 1000`
- Both signals persist with the standardized JSONB metadata shapes locked in the `r61_user_work_areas_pulse_signals` migration; Tier 2 algorithms post-September will pattern-match against them

No visible chrome carries the navigation tracking — invisible signal collection per §13.5.2.

#### 13.8.8 Empty-layer advisory pattern

When a layer has no items, the layer service may emit an `advisory` string. `PulseLayer` renders it in italic `text-content-muted` via `text-body-sm` typography — the layer otherwise renders no grid container, no chrome. Locked exemplar copy:
- Anomaly empty: *"All clear — nothing needs attention right now."*
- Activity empty: *"Quiet day so far."*
- Personal empty: layer service returns `null` (layer is omitted entirely rather than rendering an advisory) — the empty Personal state does not warrant a copy slot.

Future layers added to Pulse follow the same advisory contract: a brief one-line italic note, no chrome, only when the empty state is informative.

Future references for §13.8 will land here as Phase W-4b (intelligence streams beyond Anomaly), W-5 (My Stuff + Custom Spaces), and the standalone onboarding visual ship.

### 13.9 Cross-references

- **Section 11 Pattern 1 + Pattern 2**: chrome treatments shared across Pulse + standard Spaces.
- **Section 12 (Widget Library Architecture)**: pinable widget catalog + variant + surface declarations consumed by Pulse composition engine.
- **Section 12.5**: surface composition rules (`pulse_grid` is the surface declaration consulted by Pulse's intelligent selection).
- **Section 12.6a**: Widget Interactivity Discipline applies inside Pulse — bounded interactions per piece; heavy decisions route to Focus.
- **Section 12.10**: reference implementations (the 14 canonical widgets) compose into Pulse via §13.4.1 sizing rules.
- **BRIDGEABLE_MASTER.md §3.26**: parent canon for Spaces taxonomy + Pulse architecture + onboarding model + implementation sequencing.
- **PLATFORM_INTERACTION_MODEL.md** "Tony Stark / Jarvis interaction model": Pulse is the most direct realization of the summon/arrange/park/dismiss interaction primitives at platform scale.
- **AESTHETIC_ARC.md** Spaces and Pulse Architecture Canon Session entry: arc context.

---

*End of DESIGN_LANGUAGE.md v1.0.*
