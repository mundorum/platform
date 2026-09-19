# gnō-

This document describes the `.gno` narrative format and the editor's Player
behavior. For how the editor application itself is built (stack, views,
persistence, parsing pipeline), see [`docs/architecture.md`](docs/architecture.md).

## Narrative

A narrative is the complete description of an interactive story: everything contained in a single `.gno` file. A narrative is composed of one or more scenarios, each grouping one or more scenes.

## Scene

A scene is the basic organizational unit of a narrative. A scene is a complete unit of presentation; it can represent, for example, a scenario, a focus inside a scenario, a state in the narrative, etc. Each scene is distinctively presented, one at a time.

Scenes are initiated and identified by markdown headers, followed by a colon and the name of the scenario it is situated in. Example:

~~~gno
# Scene A: Scenario X
~~~

Several scenes can occur in the same scenario.

## Scene Description

Inside a scene, one can write a Markdown text, that will be presented inside the scene.

## Diverts

Diverts are transitions from the current scene to another. It starts with a markdown bullet (asterisk) followed by a transition label, an arrow (`->`) and the target scene. Example:

~~~gno
* Label -> Target Scene
~~~

## Entities

Entities are the characters, objects, or other elements referenced within a scene. They are identified with an `@` prefix followed by an identifier, and can appear in three forms.

Alone on its own line, optionally followed by words describing its state:

~~~gno
@prince right sad
~~~

At the start of a dialog line (see [Dialogs](#dialogs)), optionally followed by state words:

~~~gno
-- @king left happy: Hello everybody!
~~~

In the middle of ordinary text, with no state:

~~~gno
The @king enters the room.
~~~

## States

Words that immediately follow an entity — either standalone or at the start of a dialog — describe its state, such as its position or mood. States are free-form text with no fixed vocabulary; they end at the end of the line or, in a dialog, at the colon. Example:

~~~gno
@prince right sad
~~~

Here `right sad` is the state of `@prince`: positioned on the right, in a sad mood.

## Dialogs

A dialog is text spoken by an entity. It always starts with a double dash (`--`), followed by the entity (with an optional state), a colon, and the dialog text:

~~~gno
-- @king left happy: Hello everybody!
~~~

Several dialog lines can follow one another directly:

~~~gno
-- @prince right angry: You are always happy and the kingdom is falling apart!
-- @friend middle: My friend is right.
~~~

Dialog text can also start on the line(s) following the colon, continuing until a blank line:

~~~gno
-- @king:
Oh my son, you are an angry boy!
Why?
~~~

## Player

The `Player` tab in the editor lets you step through a narrative as a reader would, one pause at a time.

### Start and End scenes

Exactly one scene should be marked `(Start)` — in parentheses, right after the scenario name in the heading. The player begins there:

~~~gno
# The Council Chamber: Castle (Start)
~~~

One scene should likewise be marked `(End)`. When the player reaches it and finishes presenting it, the narrative ends:

~~~gno
# The Aftermath: Castle (End)
~~~

If no scene is marked `(Start)`, the player falls back to the first scene in the file.

### Pauses

While playing a scene, the player reveals its content a little at a time, clearing the screen at each pause so only the newly-revealed text and dialogs are shown (not a growing transcript). It stops at each pause to show a "continue" icon (or button); pressing `space` also advances. A pause happens in two situations:

1. **After a dialog.** Once a single dialog line, or an unbroken run of consecutive dialog lines (a *dialog set*), has been shown, the player pauses before continuing — **unless** nothing but the scene's diverts follow that dialog. In that case there's no pause: the dialog stays on screen together with the divert options, since offering the diverts is already a wait for the reader to pick one.
2. **At a lone `--` line.** A line containing only `--` forces a pause at that point. The `--` itself is never shown to the reader — it is a pure pause marker.

Plain prose, standalone entity lines (`@princess right curious`), and inline mentions do **not** cause a pause by themselves; they simply accumulate into whatever is shown at the next pause.

At the end of a scene, once its last bit of content is on screen, the scene's diverts appear right alongside it. For an `(End)` scene, that same moment shows that the narrative is finished instead of a divert list.

### Entities on stage

The Player shows a separate panel — independent of the narrative text — listing which entities are currently "on stage" in the scene and their state, updated as the scene is revealed.

- An entity becomes present in this panel the moment it's first mentioned, in any of the three forms (standalone, dialog, or inline).
- It stays present, keeping whatever state it was last given, even as the scene moves on to other content — until either the scene ends or it's explicitly marked as having left.
- A standalone line whose entire state is the symbol `->` — e.g. `@guard ->` — marks that entity as having exited: it's removed from the panel from that point on. Being a symbol rather than a word, it reads the same regardless of the narrative's language. An entity that's mentioned again after leaving simply becomes present again.
- Each entity appears only once in the panel, showing its most recent state — not a history of every state it's had.
- The panel is scoped to the current scene: it always starts empty when a new scene begins.

For example, given this scene:

~~~gno
# The Garden: Castle

The castle garden is bright and cold.

--

The fountain has things moving under its waters.

@princess right curious

The @princess kneels beside the fountain, sketching the koi beneath the surface.

-- @guard middle formal: Princess, your father asks for you in the council chamber.
-- @princess right curious: Did he say why?

-- @guard middle formal: Only that it concerns the northern villages.

@princess right worried

* Return to the council chamber -> The Council Chamber
~~~

the player shows the following screens in turn (`<pause>` marks the point where the reader must continue; each screen below replaces the previous one rather than piling up):

~~~gno
# The Garden: Castle

The castle garden is bright and cold.

<pause>
~~~

~~~gno
The fountain has things moving under its waters.

@princess right curious

The @princess kneels beside the fountain, sketching the koi beneath the surface.

-- @guard middle formal: Princess, your father asks for you in the council chamber.
-- @princess right curious: Did he say why?

<pause>
~~~

~~~gno
-- @guard middle formal: Only that it concerns the northern villages.

<pause>
~~~

~~~gno
@princess right worried

* Return to the council chamber -> The Council Chamber
~~~

Note that the two consecutive `-- @guard` / `-- @princess` lines form a single dialog set and share one pause, while the later lone `-- @guard` line gets its own. The final screen needs no pause of its own — the divert button is already there waiting to be picked.

### Graphic play

When the current scene's scenario has a design in **Presentation → Scenarios**, the Player plays it graphically by default: the scenario's SVG is loaded and the scene is acted out on it, instead of printed as text. The `Graphic` / `Text` switch at the top of the Player picks between the two; a scenario with no design always plays as text. The pauses, `(Start)`/`(End)` scenes and diverts work exactly as described above — only the presentation changes.

**Entities.** When an entity enters, its image is placed on the SVG. Its labels (the words after `@id`) are read in two steps:

1. *State → image.* The label sets defined for the entity in **Presentation → Entity** are compared with the labels written after it, and the image sharing the most labels is used. On a tie, the first one defined wins. Given `@king happy left` and images labeled `happy` and `sad`, the `happy` image is used, since `left` isn't one of its labels. A label made of several words (`very happy`) must appear as such. If the entity has no matching label at all it gets its first image.
2. *Label → anchor.* Of the labels that weren't used as a state, the first one that names an anchor ID in the SVG says where the entity stands; its image is fitted into that anchor's box. An entity with no anchor label (and none from before) isn't drawn.

Later mentions update what they say something about: `@king sad` changes the image and keeps the position, `@king right` moves the king and keeps the image. `@king ->` removes the entity. Labels, anchor IDs and text-area IDs are compared ignoring case and accents.

**Speech.** Text is shown in the SVG's text areas, replaced at every pause like the text view:

| What | Goes to text area | Otherwise |
|---|---|---|
| Free text (outside any dialog) | `_.speech` | `speech` |
| A dialog of `@king` | `king.speech` | `speech` |

When dialogs share a `speech` area they are prefixed with the speaker's name. Text with no area to go to isn't shown.

**Actions.** Items with these IDs are the controls:

| ID | Kind | Behavior |
|---|---|---|
| `action_proceed` | entity | Visible and clickable while the scene is paused; continues. |
| `action_regress` | entity | Visible and clickable once past the first beat; steps back to the previous beat. |
| `action_N` | entity | Choice N (the Nth `* Label -> Target` of the scene); clickable while the choices are on offer, goes to its target. |
| `action_N_label` | text area | Filled with choice N's label; clickable like `action_N`. (`action_N_text` is accepted as well.) |

Controls that don't apply right now are hidden. If the design lacks a control, the Player's regular button stands in for it (a continue button without `action_proceed`, a choice button for each choice without `action_N` / `action_N_label`), so a scene can never get stuck; `Space` always continues.

## Browser Storage (Save / Load)

The `Save` and `Load` buttons keep named narratives in the browser's `localStorage`, under the key prefix `gno-narrative-v2:<name>`. Each entry is a JSON bundle: the narrative source, the graph layout (`_graph.yaml` equivalent), and the presentation setup (`_presentation.yaml` equivalent — image libraries, entity/image associations, scenario designs). Scenario SVGs aren't stored separately here; the scenario design data is what `Download` renders them from, so keeping one copy avoids the two ever drifting apart.

### Migrating narratives saved before this format (v1)

Versions prior to this one stored only the raw narrative text, under the key prefix `gno-narrative:<name>` (no `-v2`). That format is incompatible with the current app and is **not** read automatically — v1 saves stay exactly where they are in `localStorage` (nothing is deleted), they just no longer appear in the `Load` menu. To bring one forward:

1. Open the browser's DevTools console on this page.
2. Run `localStorage.getItem('gno-narrative:<name>')` (with the narrative's saved name) to get its raw text, or list every old entry at once:
   ```js
   Object.keys(localStorage)
     .filter(k => k.startsWith('gno-narrative:'))
     .forEach(k => console.log(k, '=>', localStorage.getItem(k)));
   ```
3. Copy the text into a new `.gno` file and use `Upload` to bring it into the editor (or paste it directly into the editor pane).
4. Use `Save` under the same (or a new) name — this writes it under the new `gno-narrative-v2:` prefix as a full bundle. Graph layout and presentation setup start empty, since v1 saves never had any.
5. Once confirmed, the old `gno-narrative:<name>` entry can be removed with `localStorage.removeItem('gno-narrative:<name>')` — optional, since the app never reads or writes that prefix anymore.

