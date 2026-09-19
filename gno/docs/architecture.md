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

1. `<head>` — font/icon links, then a single `<style>` block defining the
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
  catalog can be gnō's own simple YAML list, an IIIF Collection, or a
  schema.org `ImageGallery`; `detectAndParseCatalog` sniffs the format and
  `resolveCatalogUrl` treats a bare directory URL as "fetch gnō's default
  catalog filename inside it."
- **Entity** — associates narrative `@id`s with one or more library images
  (`entityAssociations`). Entities the narrative never mentions (scenery,
  props) can be declared with the "Add entity" field; those ids live in
  `extraEntities` (`extra_entities:` in `_presentation.yaml`) because, unlike
  narrative entities, nothing in the text would bring them back on reload.
  They appear in the Scenarios palette like any other entity and can be
  removed again; narrative entities can't (the text defines them).
- **Scenarios** — a small SVG design canvas per scenario
  (`buildScenarioSvg`/`parseScenarioSvg`), downloaded as one `.svg` file per
  scenario inside the export zip.
  - *Canvas:* its size, which the background always fills, is set by dragging
    the bottom-right corner or by typing width/height.
  - *Items:* entities and text areas are placed on it ("Place: Entity" drags
    a tile from the palette, "Place: Text" drags out an area); anchors are
    made from entities (see below). Every item
    has an ID, unique within the scenario, edited in the sidebar inspector
    after placement. New anchors and text areas start as `anchor_n` /
    `text_n` (lowest free `n` from 1); entities start as their entity id. The
    inspector offers suggested IDs for all kinds (`action_n`,
    `action_n_label`, `action_proceed`, `action_regress`), plus `speech`,
    `_.speech` and `entity.speech` for text areas.
  - *Resizing:* the canvas and every item can be resized by dragging a corner
    handle or typing width/height. Holding Shift while dragging, or the lock
    toggle beside the inputs (one for the canvas, one for items), keeps the
    current proportion.
  - *Anchors* are made by placing an entity, sizing it while its image is
    still visible, then using the inspector's "Convert to anchor" button: the
    image is dropped and the footprint (size, and position as its center) is
    kept. The ID becomes the next `anchor_n` unless the user had already
    renamed it. Anchors are drawn as an ellipse and exported as a `<g>` with
    `data-gno-width`/`data-gno-height` (36×36 if absent, e.g. in older
    files). Their x/y is their center, so they grow around it when resized.
    The conversion is one-way.
  - *Text areas* are drawn by dragging in "Place: Text" mode and exported as a
    `<foreignObject>` wrapping an HTML `<div>`, since SVG `<text>` cannot wrap
    lines; text, font, size and color are set in the inspector.
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
match, first on ties) → `routeSpeech` assigns speech to text areas →
`buildPlayerStage` walks the design in its own z-order and emits drawable
layers, with `action_*` items turned into click targets. Entity images come
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
