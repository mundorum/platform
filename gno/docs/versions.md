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

### Presentation format

- **Subscene placement** (new role IDs): an item named `subscene.<scenario>`
  (spaces written as `_`), or plain `subscene`, gives the box a subscene is
  fitted into. A text area or an anchor is an invisible box; an entity with
  the same ID is a frame shown only while the subscene is open. *Items
  already named so are listed to check.*
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
