# gnō versions journal

This journal lists, for each version of the gnō language, what changed since
the previous version. It covers only the formats a narrative is written in:

- **GNO language**: the `.gno` narrative text, its syntax and what it means;
- **Presentation format**: the presentation YAML and the scenario SVGs;
- **Graph format**: the graph layout YAML.

Changes to the editor itself (panels, views, buttons) are not listed. A
narrative's version is recorded in its manifest (see `../README.md`,
"Versions"); a narrative of an older version is converted when it is opened.
Each topic below says what the converter does about it.

Newest version first.

## 1.1 (under development, from 1)

### GNO language

- **Start and end markers** are symbols: `(*)` and `(**)` replace `(Start)`
  and `(End)`. *Converted.*
- **Entity exit** is `@entity =>`, replacing `@entity ->`. *Converted.*
- **Entity diverts** (new): `@entity -> Scene`, optionally with state words
  before the arrow (`@door left open -> Scene`). While the entity is on stage,
  clicking it takes the divert. *Lines of this form gave the entity state
  words in version 1; they are listed to check.*
- **Subscenes** (new): the arrow `~>` opens its target over the current scene
  instead of replacing it, for choices (`* Label ~> Scene`) and entities
  (`@entity ~> Scene`). Going back (`action_regress`) closes the subscene; a
  `->` divert taken inside a subscene closes every open subscene. *Choices
  with `~>` were plain text in version 1; they are listed to check.*
- **Entity options** (new): choices indented (two spaces or more, or a tab)
  on the lines right under a standalone entity line are that entity's
  options, offered while it is on stage, when the reader clicks it or points
  at it, instead of at the scene's end. Diverts are now scene-centric (the
  choices) or entity-centric (entity diverts and options). An option can
  also use `=>`, which goes to the target taking the entity along, on stage
  there from the start with the states it had. A later options block, or an
  entity divert, replaces an entity's options. *Indented choices under an
  entity line were text in version 1; they are listed to check.*

### Presentation format

- **Subscene placement** (new role IDs): an item named `subscene.<scenario>`
  (spaces written as `_`), or plain `subscene`, gives the box a subscene is
  fitted into. A text area or an anchor is an invisible box; an entity with
  the same ID is a frame shown only while the subscene is open. *Items
  already named so are listed to check.*
- **Entity option IDs** (new role IDs): `<entity>.action_N`, the entity's
  name without `@` (`Lucinda.action_1`, text area `Lucinda.action_1_text`),
  shows the entity's Nth option while its options are open; a group's
  options use its first member as written. *Items already named so are
  listed to check.*
- **Player settings** (new `player` key in the presentation YAML):
  `entity_options: click | hover`, how the reader opens an entity's options;
  `click` when absent. *Nothing to convert.*
- **Text area IDs always end in `_text`** in the scenario designs. Version 1
  also read text areas named without it (`speech`, `action_N_label`) and
  renamed them as it opened them; 1.1 reads only the suffixed form.
  *Converted.*
- **Anchors are named by their `id` alone.** Version 1 also read an anchor
  `<g>` with no `id`, by its `data-gno-anchor` marker, and an anchor of a
  browser save with no ID, by its former `label`. *Converted.*
- **No `version` key** in the presentation YAML: the version now lives in the
  narrative's manifest (`manifest.json` in the zip). *Nothing to convert: an
  old key is ignored.*

### Graph format

- **No `version` key** in the graph YAML, for the same reason. *Nothing to
  convert: an old key is ignored.*

## 1 (baseline)

The language as it was before versions were recorded: any narrative without
a manifest is version 1. Its last state is the one in commit `b318d1b`
(`git show b318d1b:gno/README.md`).
