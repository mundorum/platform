# gnō-

This document describes the `.gno` narrative format and the editor's Player
behavior. For how the editor application itself is built (stack, views,
persistence, parsing pipeline), see [`docs/architecture.md`](docs/architecture.md).
For a step-by-step tutorial on designing a scenario's graphic presentation,
see [`docs/scenario-tutorial.md`](docs/scenario-tutorial.md) (in Portuguese:
[`docs/scenario-tutorial.pt-BR.md`](docs/scenario-tutorial.pt-BR.md)).

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

### Groups

Two or more entities joined with `+` act together, in any of the three forms:

~~~gno
@king + @queen right happy
-- @king + @queen: Welcome, friends!
The @king + @queen bow.
~~~

The order doesn't matter: `@queen + @king` is the same group. A group's state applies to every member. In the graphic Player, a group can have images of its own (see [Graphic play](#graphic-play)).

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

A back button, shown beside the continue button once the reader is past a scene's first pause, steps back to the previous screen (a graphic design can supply its own with `action_regress`, see below). The `Restart` button at the top of the Player starts the narrative over from its `(Start)` scene at any time.

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

1. *State → image.* The label sets defined for the entity in **Presentation → Entity** are compared with the labels written after it, and the image sharing the most labels is used. On a tie, the first one defined wins. Given `@king happy left` and images labeled `happy` and `sad`, the `happy` image is used, since `left` isn't one of its labels. A label made of several words (`very happy`) must appear as such. If no label matches (or none is written), the entity's image with no labels is used; if every image has labels, the first one defined is used.
2. *Label → anchor.* Of the labels that weren't used as a state, the first one that names an anchor ID in the SVG says where the entity stands; its image is fitted into that anchor's box. An entity with no anchor label (and none from before) isn't drawn.

Later mentions update what they say something about: `@king sad` changes the image and keeps the position, `@king right` moves the king and keeps the image. `@king ->` removes the entity. Labels, anchor IDs and text-area IDs are compared ignoring case and accents.

**Groups.** Entities joined in **Presentation → Entity**, by typing them with `+` in *Add entity* (for example `@king + @queen`, or `@king + @queen + @jester` for more), can have images of their own, which are used only where the narrative writes the members joined, in any order (`@king + @queen right` or `@queen + @king right`). The Presentation tab shows a group with its members in the order they were typed. Their labels work as for a single entity. While the group is on stage, it is drawn as one image and the members' own images are hidden. The group stands at the anchor it names; if it names none, it stands where its first placed member already is. `@king + @queen ->` removes the group together with its members.

Mentioning a member alone (`-- @king: …`, `@king sad`, or `@king ->`), in the same beat or after a pause, *splits* the group: from then on, each member is on stage on its own.

1. A member mentioned alone takes that mention and its labels, as usual (`@king ->` makes it leave).
2. A member not mentioned alone stays on stage until it leaves explicitly. Its image is the one best matching the labels the group was given (`@king + @queen happy` → the queen's `happy` image). If none matches, its image with no labels is used, or else its first image. It stands where it stood before the group formed, or else where the group stands.

For example, after `@king + @queen middle happy` and a pause, `-- @king: Hello.` shows the king and the queen apart, each in a `happy` image if they have one. A group with no images of its own is the same as mentioning each member with the same labels.

**IDs: entity and text pairs.** In **Presentation → Scenarios**, a text area and an entity can have the same ID: together they play the same role, the text area showing the text and the entity being its picture (a button, a speech bubble). In the exported SVG, the text area's id gets the suffix `_text` (`action_1` and `action_1_text`, `speech` and `speech_text`); typing the suffix yourself, or the former `_label`, makes no difference. Designs made before this are converted when they are opened: their text areas get the suffix (`action_1_label` becomes `action_1_text`, `speech` becomes `speech_text`).

**Speech.** Text is shown in the SVG's text areas, replaced at every pause like the text view:

| What | Goes to text area | Otherwise |
|---|---|---|
| Free text (outside any dialog) | `_.speech` | `speech` |
| A dialog of `@king` | `king.speech` | `speech` |
| A dialog of `@king + @queen` | `speech` | the first member's own area (`king.speech`) |

When dialogs share a `speech` area (and, always, for a group) they are prefixed with the speaker's name. Text with no area to go to isn't shown, and a speech area with nothing to show at the current pause is hidden, like an unused choice. An entity with the same ID as a speech area (`speech`, `_.speech`, `king.speech`), such as a speech bubble, is shown only while its text area has something to show.

**Actions.** Items with these IDs are the controls. Each can be an entity, a text area, or both (a pair), and both behave the same:

| ID | Behavior |
|---|---|
| `action_proceed` | Visible and clickable while the scene is paused; continues. A text area shows its own text ("Continue"). |
| `action_regress` | Visible and clickable once past the first beat; steps back to the previous beat. A text area shows its own text. |
| `action_N` | Choice N (the Nth `* Label -> Target` of the scene); clickable while the choices are on offer, goes to its target. A text area is filled with the choice's label. |

**Stacks.** Items can be put into *stacks*, which place them the way a CSS flexbox does: a vertical stack lines its items up top to bottom, a horizontal one left to right, and stacks can contain other stacks. Each item keeps its own size, and the stack decides its position from three settings: where the run sits along the direction (start, center, end or spread out), how each item is aligned across it, and the gap between items. Items hidden at the current pause take no room, so the rest close up. A stack with nothing visible is hidden as well. Hidden items are an empty speech area, a choice not on offer, an inactive control, or an anchor with no one on it. For example, a vertical stack aligned to the bottom, holding the `speech` text area and then the `action_N` text areas, shows the speech right at the bottom while there are no choices, and moves it up above them when the choices appear.

**Item groups.** Items can also be put into *groups*, which keep them together exactly where they were placed: a speech area over a speech-bubble image behind it, for instance. A group has no area of its own (it is just the items in it); it moves as one, and a stack places it like any other item, its items following along. A group is hidden while every item in it that can be hidden is (an empty speech area, a choice not on offer, …), and its plain images go with it; so the bubble shows only while there is speech. A group holding plain images only is always shown. Inside a group, items are drawn back to front in the group's order.

Items go into a stack or group in either of two ways in **Presentation → Scenarios**:

1. Select the stack or group (or create one with **New group**), press **Insert items**, and click the items, on the canvas or in the hierarchy.
2. In the sidebar's *hierarchy* (the design's stacks and groups with the items they hold, nested as they are), Shift- or Ctrl-click several items and group or stack them with the buttons at its top, or drag items onto a group or stack. Dragging them onto empty space in the hierarchy takes them out again.

In the hierarchy, the arrows on a row move it up or down among its neighbours: at the top level and in a group that changes the drawing order (higher rows are behind lower ones), in a stack the placing order. The trash button on a row deletes that item, and the one at the top deletes all the selected items; deleting a group or stack keeps the items it held, which take its place.

Controls that don't apply right now are hidden. If the design lacks a control, the Player's regular button stands in for it (a continue button without `action_proceed`, a choice button for each choice without an `action_N` entity or text area), so a scene can never get stuck; `Space` always continues.

## Side panels

Every side panel can be resized by dragging its inner edge: the left navigation, the Editor's preview, the Graph's scene panel, the Scenarios sidebar and the Player's entity panel. Double-clicking an edge restores the default width. The widths are remembered in this browser.

## Browser Storage (Save / Load)

The `Save` and `Load` buttons keep named narratives in the browser's `localStorage`, under the key prefix `gno-narrative-v2:<name>`. Each entry is a JSON bundle: the narrative source, the graph layout (`_graph.yaml` equivalent), and the presentation setup (`_presentation.yaml` equivalent — image libraries, entity/image associations, declared entities, scenario designs). Scenario SVGs aren't stored separately here; the scenario design data is what `Download` renders them from, so keeping one copy avoids the two ever drifting apart.

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

