# gnō- Architecture

`gno/` is a **single-file, single-page application**: everything — markup, CSS,
and application code — lives in [`editor.html`](../editor.html). There is no
build step, no bundler, and no package.json; the file is opened directly in a
browser. This is a deliberate scope choice, not a placeholder: `gno/` is
isolated from the rest of the platform (see the root `CLAUDE.md`) and doesn't
share tooling or code with `backend/`/`frontend/` or `noid/`.

For the *narrative format itself* (scenes, entities, dialogs, diverts,
Player pause rules), see [`../README.md`](../README.md). This document covers
how the editor application that reads/writes that format is built.

## Stack

| Concern | Choice | How it's loaded |
|---|---|---|
| UI framework | Vue 3 (Composition-ish `createApp` with `ref`/`reactive`/`computed`/`watch`) | `unpkg.com/vue@3/dist/vue.global.prod.js` |
| Markdown rendering | `marked` | cdnjs |
| Zip read/write (Download / Upload) | `JSZip` | cdnjs |
| YAML read/write (`_graph.yaml`, `_presentation.yaml`) | `js-yaml` | cdnjs |
| Icons | Tabler Icons webfont | jsdelivr |
| Fonts | Lora / Outfit / JetBrains Mono | Google Fonts |

All libraries are pulled from CDNs via `<script>`/`<link>` tags at the top of
`editor.html` — no local `node_modules`. This mirrors the "no build step"
constraint but is otherwise independent from the CSS design-token system
shared with the rest of the platform (`--c-*` custom properties), which `gno/`
also follows even though it doesn't import `assets/tokens.css` from
`frontend/`.

## File layout inside `editor.html`

1. `<head>` — the favicon (an inline SVG `data:` URI of the app-tile icon from
   `design/icons/gno-icon-tile.svg`, so the file stays self-contained),
   font/icon links, then a single `<style>` block defining the
   `--c-*`/`--font-*` custom properties (light palette in `:root`, dark
   palette under `@media (prefers-color-scheme: dark)`) and all component CSS.
2. `<body>` — the Vue template: topbar, left nav (`#nav-panel`), and
   `#main-area` containing four mutually-exclusive view panels toggled by
   `view === '...'` (`editor`, `graph`, `presentation`, `player`).
3. A single trailing `<script>` block containing:
   - Free (non-Vue) functions: the `.gno` parser, entity analyzer, Markdown
     preview renderer, syntax highlighter, graph layout, catalog parsers, and
     scenario-SVG (de)serialization.
   - One `createApp({ ... })` call holding all reactive state and the methods
     the template binds to, mounted to `#app`.

There is no component decomposition — the whole UI is one Vue root instance
with template `v-if`/`v-show` blocks per view. Given the file's size (~4200
lines), when making changes prefer `grep -n` for the section comments (each
major function is preceded by a comment explaining its *why*) over reading
the file top to bottom.

## Resizable side panels

Each side panel has a `.panel-splitter` on its inner edge (the left
navigation's sits absolutely at the left of `#main-area`). `startPanelResize`
tracks the pointer on `window` and writes `panelWidths` (`nav`, `preview` —
`null` means half and half with the source —, `scenarioSide`,
`playerEntities`), clamped by `PANEL_LIMITS`; double-click resets one. While
dragging, `#app.resizing` turns off the grid transition and pointer events
elsewhere. Widths are a per-browser convenience in their own `localStorage`
key (`gno-panel-widths`), not part of the narrative bundle. The Graph's scene
panel keeps its own older handle (`onPanelResizeDown`, `nodePanelWidth`).

## The four views

The editor is one Vue app with a `view` ref switching between four panels;
all four share the same in-memory narrative (`source`, the raw `.gno` text)
and its derived state.

### Editor
Split pane: a plain `<textarea>` for the raw `.gno` source, with a read-only
`<pre>` overlay behind it (`highlightGno`) providing the colored-token
syntax highlighting, plus a live preview pane rendered by `renderGno`
(`.gno` → HTML via `marked`, with scene headings, diverts, and `@entity`
mentions substituted into styled spans first).

### Graph
A node-per-scene diagram. `layoutGraphNodes` auto-arranges scenes into
left-to-right topological columns (BFS from root scenes, orphans handled
separately); `layoutGraphEdges` draws cubic-bezier divert arrows between
nodes based on their *final* rendered position. Nodes can be dragged; a
dragged position, a chosen color, and a free-text annotation are stored per
scene **title** in `nodeMeta` (title, not id, so the graph survives scene
reordering/renumbering). `nodeMeta` round-trips through the session
autosave and the downloadable `_graph.yaml`, but is **not** part of named
browser-storage saves or the `.gno` file itself — it's presentation
metadata, not narrative content.

### Presentation
Three sub-tabs building the visual/staging layer on top of the narrative,
all persisted together as `_presentation.yaml`:
- **Image Libraries** — external image catalogs registered by URL. A
  catalog can be gnō's own simple list (`gno-catalog.yaml`, or its restricted
  Markdown twin `gno-catalog.md` — a bullet list of `* ![id](path)` items),
  an IIIF Collection, or a schema.org `ImageGallery`; `detectAndParseCatalog`
  sniffs the format (`.md` by extension) and `resolveCatalogUrls` treats a
  bare directory URL as "fetch `gno-catalog.yaml` inside it, else
  `gno-catalog.md`" (`fetchCatalog`).
- **Entity** — associates narrative `@id`s with one or more library images
  (`entityAssociations`). Entities the narrative never mentions (scenery,
  props) can be declared with the "Add entity" field; those ids live in
  `extraEntities` (`extra_entities:` in `_presentation.yaml`) because, unlike
  narrative entities, nothing in the text would bring them back on reload.
  They appear in the Scenarios palette like any other entity and can be
  removed again; narrative entities can't (the text defines them).
  *Groups* (`@king + @queen`) are entities too, keyed by `entityGroupKey`
  (members sorted, joined with ` + `), so a group's images live in
  `entityAssociations` like any entity's. They come from the narrative
  (`analyzeEntities` reads the joined form) or from typing them with `+` in
  "Add entity" (`normalizeEntityRef`, spaces around `+` optional, any number
  of members). Resolution goes by key, but a group is *shown* in the order it
  was written (`entityWrittenRef`): `extraEntities` keeps the typed form
  (re-typing a declared group in another order replaces it), occurrences carry
  `written`, and the app's `entityLabel(key)` picks the typed form first, then
  the narrative's first one. The Editor preview and the text Player show
  each occurrence as written (`entityBlockHtml` uses `occ.written`; the
  roster lists a group's members in written order).
- **Scenarios** — a small SVG design canvas per scenario
  (`buildScenarioSvg`/`parseScenarioSvg`), downloaded as one `.svg` file per
  scenario inside the export zip.
  - *Canvas:* its size, which the background always fills, is set by dragging
    the bottom-right corner or by typing width/height.
  - *Modes:* the toolbar's mode decides what a press on the canvas does
    (`placeMode`). With no mode selected, items are locked in place. **Edit**
    selects, moves and resizes them; it is the only mode in which items take
    the pointer (`.scenario-svg.editing`) and the inspector shows a
    selection. **Place: Text** / **Place: Vertical stack** / **Place:
    Horizontal stack** draw a new text area or stack, and then switch to Edit
    with it selected. Entities are added by dragging a tile from the palette,
    in any mode.
  - *Items:* entities, text areas and stacks are placed on it; anchors are
    made from entities (see below). Every item
    has an ID, edited in the sidebar inspector after placement. Text areas
    and the other items have separate IDs, so a text area and an entity can
    share one and play a role as a pair (`action_1`, `speech`). Internally
    `svgId` stays unique: a text area's always carries `TEXT_ID_SUFFIX`
    (`_text`); `itemRoleId` gives the authored ID, `roleSvgId(kind, id)` the
    svgId for a typed one (dropping a typed `_text`/`_label`), and
    `migrateTextIds` (run by `sanitizeScenarioDesigns` and
    `parseScenarioSvg`) suffixes text areas of older designs, renaming
    `action_N_label` to `action_N_text`. The UI always shows `itemRoleId`.
    New anchors, text areas and stacks start as `anchor_n` /
    `text_n` / `layout_n` (lowest free `n` from 1); entities start as their entity id. The
    inspector suggests IDs for entities and text areas: first the action and
    speech IDs the other sort uses without a partner, then `action_n`,
    `action_proceed`, `action_regress`, `speech`, `_.speech`,
    `entity.speech`.
  - *Moving and resizing:* every item can be moved by dragging it or by typing
    its X/Y in the inspector. The X/Y fields always show the top-left corner,
    including for anchors, whose stored x/y is their center. The canvas
    and every item can be resized by dragging a corner handle or typing
    width/height. Holding Shift while dragging, or the lock
    toggle beside the inputs (one for the canvas, one for items), keeps the
    current proportion.
  - *Anchors* are made by placing an entity, sizing it while its image is
    still visible, then using the inspector's "Convert to anchor" button: the
    image is dropped and the footprint (size, and position as its center) is
    kept. The ID becomes the next `anchor_n` unless the user had already
    renamed it. Anchors are drawn as a dashed rectangle of the image's footprint and exported as a `<g>` with
    `data-gno-width`/`data-gno-height` (36×36 if absent, e.g. in older
    files). Their x/y is their center, so they grow around it when resized.
    The conversion is one-way.
  - *Text areas* are drawn by dragging in "Place: Text" mode and exported as a
    `<foreignObject>` wrapping an HTML `<div>`, since SVG `<text>` cannot wrap
    lines; text, font, size and color are set in the inspector.
  - *Stacks* (`kind: 'layout'`) are flexbox-like: a box, a `direction`
    (`column` | `row`), `justify`, `align`, `gap`, and an ordered list of
    child ids (`children`), which may include other stacks. The layout
    itself is the pure `layoutBoxes`. While designing, every child counts as
    visible, and a deep watcher (`relayoutDesign`) writes the positions back
    into the children, so the canvas, the inspector and the exported SVG
    agree. A child is selected but not dragged, and its X/Y fields are
    disabled. Items are added with the inspector's "Insert items" (click
    items on the canvas), reordered or removed from its list, or taken out
    from the child's own inspector. Renaming or removing an item updates the
    lists that reference it (`renameLayoutRefs`). A stack is exported as an
    empty `<g data-gno-layout="column|row">` whose settings and child ids
    are in `data-gno-*` attributes. The children stay flat in the SVG's
    z-order.
  - *Groups* (`kind: 'group'`, `cleanGroup`) are the other container:
    `children`, with no area and no placement rule of their own. Their box is
    always the union of their children's (`fitGroups`, run after each
    relayout, inner groups first), which is what a stack sizes them by; it is
    only drawn, as a frame around the items. "New group" makes an empty one
    and starts inserting into it. Children keep their
    absolute x/y; moving the group (drag or X/Y) moves them along
    (`translateItem`), and when a stack places the group, `layoutBoxes`
    shifts them by the group's displacement. Stacks and groups nest freely
    (`isContainer`); an item sits in at most one container. A group's
    `children` are back to front and mirror the design's z-order: inserting
    files the item by its z-index, and reordering permutes the children's
    slots in `items` (`moveLayoutChild`). Inserting also grows the box to
    Visibility in play:
    a group is shown while any child that can hide (anything but a plain,
    non-action entity image, `isDecorItem`) is, else everything inside it is
    hidden (`layoutBoxes` returns that set as `hidden`). Exported as an empty
    `<g data-gno-group data-gno-children=…>`.
  - *Hierarchy:* the sidebar lists the design as a tree (`designTree`):
    top-level items in z-order, containers with their children indented.
    A row selects its item (switching to Edit), or inserts it while a
    container is collecting items. Shift/Ctrl/Cmd-click builds a multiple
    selection (`treeSelection`; the last one picked is the inspector's
    `selectedItemId`, and a canvas selection resets it). `wrapTreeSelection`
    puts it into a new group (children in z-order) or stack (children in
    their order along its direction, box = their union), which takes their
    place in their container when they all shared one. Rows are draggable
    (HTML5 DnD, `treeDrag`): dropped on a container they go in through
    `insertIntoLayout` (no cycles), dropped on empty space in the panel they
    go to the top level.
  - *Wide editor:* a toolbar button lifts the whole workspace (toolbar,
    canvas, sidebar) into a fixed full-window layer (`.scenario-workspace.wide`),
    hiding the app's top bar, navigation and the 900px page column. Esc (or
    the same button) leaves it. It is a layout switch only — the canvas is
    still shown at 1:1, so a large background scrolls inside it.

### Player
Steps through the narrative as a reader would. `buildScenePlayback` splits
a scene's body into *beats* (pause points), per the rules documented in
`README.md` (a lone `--` line, or the end of a dialog/dialog-set unless
only diverts follow). Alongside beats it tracks which entities are "on
stage" — present since first mention, carrying their last-given state,
until an explicit `@entity ->` exit or the scene ends — rendered in a
separate panel independent of the narrative text itself.

*Graphic mode* plays the same beats on the scenario's designed SVG (rules in
`README.md`, "Graphic play"). It is on by default when `scenarioDesigns` has an
entry for the scene's scenario; `playerGraphic` is only the reader's
preference and `playerUseGraphic` the effective mode. The stage is not the
exported SVG file loaded into the DOM: it is drawn by the Player's own
`<svg>` from the live `scenarioDesigns` data (like the Scenarios canvas), so it
tracks edits to the design, the associations and the narrative without a
round-trip. The pipeline is a chain of pure functions:
`buildScenePlayback` additionally returns per-beat `events` (entity mentions)
and `speeches` (prose and dialogs, in order) → `foldStageFrames` replays the
events into who is on stage and where, using `pickEntityImage` (best label
match, first on ties); a member mentioned alone splits an on-stage group
(`splitGroupsOf`: each member re-enters with the image the group's last
labels pick for it, at its own earlier anchor or the group's, and the
mention then applies on top) → `routeSpeech` assigns speech to text areas (by their authored ID; an
entity sharing a speech area's ID, `isSpeechRole`, is shown only while that
area has speech, and both items of an `action_*` pair follow `actionRole`) →
`buildPlayerStage` first settles what each item shows at this moment (and so
which items are hidden), then runs `layoutBoxes` so stacks close up around
the hidden items, and finally emits drawable layers in the design's z-order,
with `action_*` items turned into click targets. Entity images come
from the live library catalogs (`findCatalogImage`), not from anything stored
in the design, so an entity is drawn only once its catalog has loaded. The
Vue template binds the SVG's `viewBox` through `v-bind="{viewBox: …}"`
because the template is parsed as HTML, which lowercases a `:viewBox` name.

## Persistence model

Three independent mechanisms share the same underlying bundle shape
(narrative source + graph layout + presentation setup):

| Mechanism | Trigger | Shape |
|---|---|---|
| Session autosave | Debounced (~600ms) on every edit, flushed immediately on tab hide/close | One `localStorage` draft key; restores work after a reload even without an explicit Save |
| Named save (Save/Load buttons) | Explicit user action | One JSON blob per name in `localStorage`, prefix `gno-narrative-v2:<name>` (see migration notes in `README.md` for the pre-v2 format) |
| Download / Upload | Explicit user action | A `.zip` containing `<name>.gno` + `<name>_graph.yaml` + `<name>_presentation.yaml` + one `scene/*.svg` per scenario design |

Named saves and the session draft keep `scenario_designs` as live data (the
same structure `buildScenarioSvg` renders from) rather than pre-rendered
SVG, so the two representations can never drift apart; only the downloadable
zip materializes the SVGs, as files meant to be viewed outside the app.
Uploading a single `.gno`/`.md`/`.txt` file (not a zip) loads narrative text
only and clears graph/presentation state, since there's nothing else to
restore it from.

## Parsing pipeline

`source` (raw text) flows through a small set of pure functions, each
independent and re-run reactively as the user types:

1. `parseGno(source)` — splits the text into scenes by `# Title: Scenario
   (Start|End)?` headings, extracting each scene's body and its trailing
   divert list (`* Label -> Target`).
2. `analyzeEntities(source)` — regex-based detection of the three `@entity`
   forms (standalone, dialog-leading, inline), using Unicode letter/number
   classes so accented ids are matched in full.
3. `renderGno(source, scenes, entities)` — produces the live preview HTML,
   substituting scene headings/diverts/entity mentions with styled spans
   before handing the rest of each line to `marked`.
4. `highlightGno(source, entities)` — tokenizes each line for the editor's
   syntax-highlight overlay.
5. `buildScenePlayback(scene, ...)` — (Player-only) turns one scene's body
   into the beat/pause sequence described above, plus the entity events and
   speech the graphic mode consumes (`foldStageFrames`, `routeSpeech`,
   `buildPlayerStage`).

None of these functions depend on Vue; they operate on plain strings/arrays
and are called from computed properties inside the app.
