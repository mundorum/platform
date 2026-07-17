# gnō-

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

While playing a scene, the player reveals its content a little at a time, stopping at each pause to show a "continue" icon (or button); pressing `space` also advances. A pause happens in three situations:

1. **After a dialog.** Once a single dialog line, or an unbroken run of consecutive dialog lines (a *dialog set*), has been shown, the player pauses before continuing.
2. **At a lone `---` line.** A line containing only `---` forces a pause at that point. The `---` itself is never shown to the reader — it is a pure pause marker.
3. **At the end of a scene.** After all of a scene's content has been shown, the player pauses once more; advancing past this final pause reveals the scene's diverts, so the reader can pick where to go next, or — for an `(End)` scene — reveals that the narrative is finished.

Plain prose, standalone entity lines (`@princess right curious`), and inline mentions do **not** cause a pause by themselves; they simply accumulate into whatever is shown at the next pause.

For example, given this scene:

~~~gno
# The Garden: Castle

The castle garden is bright and cold.

---

The fountain has things moving under its waters.

@princess right curious

The @princess kneels beside the fountain, sketching the koi beneath the surface.

-- @guard middle formal: Princess, your father asks for you in the council chamber.
-- @princess right curious: Did he say why?

-- @guard middle formal: Only that it concerns the northern villages.

@princess right worried

* Return to the council chamber -> The Council Chamber
~~~

the player stops at the following points (`<pause>` marks are shown here only to illustrate — they are never part of the actual output):

~~~gno
# The Garden: Castle

The castle garden is bright and cold.

---

<pause>
The fountain has things moving under its waters.

@princess right curious

The @princess kneels beside the fountain, sketching the koi beneath the surface.

-- @guard middle formal: Princess, your father asks for you in the council chamber.
-- @princess right curious: Did he say why?

<pause>

-- @guard middle formal: Only that it concerns the northern villages.

<pause>

@princess right worried

* Return to the council chamber -> The Council Chamber

<pause waiting for the user to click>
~~~

Note that the two consecutive `-- @guard` / `-- @princess` lines form a single dialog set and share one pause, while the later lone `-- @guard` line gets its own.

