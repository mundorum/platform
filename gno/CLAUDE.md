# gnō — CLAUDE.md

`gno/` is a standalone client-side app: everything is in `index.html` (see
`docs/architecture.md`). The narrative format and the Player are described in
`README.md`, and the changes between language versions in the versions
journal, `docs/versions.md`. It shares nothing with the rest of the platform.

## Language versions: always follow this protocol

The gnō language is versioned. **Every change to `gno/` must follow these
rules.** The current version is in `GNO_VERSION` (`index.html`, section
"LANGUAGE VERSIONS AND CONVERTERS"); what changed in each version is in the
versions journal, `docs/versions.md`.

### What a version is

1. **One version covers the whole narrative package:** the `.gno` text (its
   syntax and what it means), the graph layout YAML, the presentation YAML,
   the scenario SVGs, and the browser bundles that hold the same data
   (named saves and the autosave draft).
2. **The version is recorded only in the manifest:** `manifest.json` at the
   root of a zip, and the `manifest` field of a browser bundle. Never write
   a version into the YAML or SVG files. A package without a manifest is
   version 1.
3. **The app knows only the latest version.** The parser, the Player, the
   editor and the decoders handle only `GNO_VERSION`. Don't add
   backward-compatibility branches to them (no "the old form is still read"
   cases). Older forms are handled only by converters, which run when a
   package is opened, and the author is told what was converted.

### Starting a new version

Only the user starts a new version, and they will say so explicitly. Never
start one on your own, however large a change is: a version can span many
changes and commits. When the user starts version N (following version P):

1. Version P is finished. Its converter (the one ending at P) is frozen from
   now on.
2. Set `GNO_VERSION` to N.
3. Add a converter `{ from: P, to: N, bundle: convert_P_to_N }` at the end of
   `CONVERTERS`. It starts as a no-op that returns the package unchanged
   with no notes, so packages of version P already open in version N.
4. In the versions journal, `docs/versions.md`, add a section for version N
   at the top, marked "under development, from P", and remove that mark
   from P's section.

### While a version is under development

Any change that alters how a package is **written or read** must update the
current version's converter (the one ending at `GNO_VERSION`) in the same
change. That includes:

- syntax or meaning of the `.gno` text (markers, arrows, entity forms, pauses…)
- keys or structure of the graph or presentation YAML
- SVG markup, attributes or `data-gno-*` fields
- IDs or names that gain a role (such as `action_N` or `subscene`), and
  defaults that change how an existing narrative looks or plays

For such a change:

1. Rewrite what can be rewritten, so the old package keeps its meaning in
   the new version.
2. For lines or items that the old version read one way and the new one
   reads another, and that can't be rewritten without guessing, add a
   `Check …` note naming the line or item.
3. Record it in the versions journal (see below).
4. Update `DEMO_SOURCE` if it uses the changed form.

Changes that leave packages alone (editor UI, panels, the Graph view's
behaviour, performance) need no converter change. In your report on any
gno change, say whether the converter changed and why.

### The versions journal

`docs/versions.md` lists, for each version (newest first), what changed
since the previous one. **Update it in the same change whenever a change
affects the GNO language (the `.gno` text: syntax or meaning), the
presentation format (presentation YAML, scenario SVGs, item ID roles) or the
graph format (graph YAML).** Editor-only changes don't go in it.

- Add the topic under the current version's section, in the matching
  subsection: *GNO language*, *Presentation format* or *Graph format*.
- Keep it to a short bullet: the change in bold, one or two sentences on
  what it is, then in italics what the converter does about it
  (*Converted.*, *… listed to check.*, or *Nothing to convert.*).
- If a later change in the same version alters or reverses an earlier one,
  edit that bullet instead of adding another: the section describes the
  difference between the two versions, not the order of the commits.
- Never edit the section of a finished version, except to fix an error in
  it.

### The syntax and SVG references

`docs/syntax.md` describes the syntax of the `.gno` text for the current
version, structure by structure, with EBNF-Lite rules and examples. **Update
it in the same change whenever the syntax of the `.gno` text changes** (a new
or changed structure, symbol or rule for how a line is read).

`docs/scenario-svg.md` describes the scenario SVG files in the same way: their
elements, `data-gno-*` attributes and role IDs. **Update it in the same
change whenever how a scenario SVG is written or read changes** (an element,
an attribute, a role ID, or what the Player shows or hides).

When a new version starts, update the version number in the introduction of
both.

### How to write a converter

- It is a pure function. It carries **its own copies** of every pattern it
  matches. Never call the current parser or reuse its regexes: they will
  change in later versions, and the converter must keep doing exactly what
  it did.
- The `bundle` stage works on the decoded package
  `{ source, layout, presentation }`. Every way of opening a narrative
  arrives at this shape, so changes of meaning belong here.
- Add a `files` stage, which works on a zip's raw files before they are
  decoded, only when a version changes how something is written in the
  files and the current decoders can't read the old form. The `bundle` stage
  must then also accept data that the `files` stage has already brought up
  to date.
- Make it idempotent where possible: running it on already-converted
  content changes nothing.
- Notes are for the author: one per kind of change, with a count, plus one
  `Check …` note per doubtful line, giving its line number.
- Never change a finished version's converter. If one has a bug, tell the
  user and fix it only once they agree.

### Testing

Test each converter change in a headless browser (Chromium can load
`index.html` with a test script appended; keep harnesses outside the repo,
in the scratchpad). Cover a package of the previous version opened in each
way: a zip without a manifest, a zip with one, a bare `.gno`, a named
browser save and the autosave draft. Check the converted text, the notes,
and that opening a current package converts nothing.
