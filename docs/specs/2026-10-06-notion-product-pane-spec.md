<!--
Export of the Notion page "Product Pane" (Bridgeable Modules database).
Page URL: https://app.notion.com/p/3ee727fa123c80e59e96c984e267af32
Page last edited: 2026-10-03T01:41:02Z
Exported: 2026-10-06 via the Notion connector, by the design-side chat.
Properties: Type=Pane, Status=Prototyped, Vertical=Universal,
Prototype=https://claude.ai/artifact/ErUUywB8tvGvwc4hhba6HK
The text below the marker is the page body as fetched.
-->
---BODY---
## PANE: Product
**Kind:** record pane · live data · compact density
**Reads:** products, product photos, price list items, stock, orders, personalization availability
**Opens with:** product name, any saved other name ("rough box"), a retired name, or a row in a product list. If more than one product matches, ask with a numbered pick.
**Works without AI** by name and alias lookup.
### Sections (in order)
1. **Header:** product photo at the top left; name, kind, made here / bought in, SKU beside it.
Tapping the photo opens it large with any other photos; office can add photos.
The first photo is the main one, also used on the spec sheet.
**Actions:** Order one, Send spec sheet, Catalog.
2. **Right now:** low stock, pending price change, none on hand (bought-in). One line each.
3. **Price:** one sentence: current, last changed, pending. Bought-in adds cost, supplier, margin.
4. **Specs:** one sentence: size, weight, lining.
5. **Stock:** one sentence: on hand, in production, due out this week.
6. **Pills:** Personalization · Recent orders · Price history · What Opas knows (other names, retired names, usually ordered with, substitute, lead time, truck).
Opening one scrolls it into view.
### Roles
- **Office:** everything.
- **Accounting:** no Order one.
- **Driver:** specs with weight and truck, Personalization. No price, stock or history.
**Presenting mode:** the photo shows large at the top. Keeps price and specs; hides cost, margin, stock, Right now, What Opas knows.
### Order one
Order one: starts an order with the vault filled in; personalization is pre-answered when the product offers none.
### Device notes
- **Desktop:** floating glass pane, drag by header; related panes open beside it.
- **iPad:** same, larger; sphere bottom center.
- **Phone:** full-width card above the sphere; related panes are cards to swipe between.
**Replaces:** the product page from the catalog prototype.
**Open questions:** which Right now items matter most.
