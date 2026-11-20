# gnō Syntax

This document describes the syntax of the gnō narrative language, version
1.1: every structure an author can write in a `.gno` file, what it is for,
how it is written, and examples. What the Player does with each structure
(screens, the stage, graphic play) is described in the
[README](../README.md); the files that hold the scenarios' graphic design, in
the [scenario SVG reference](scenario-svg.md); what changed from one version
of the language to the next, in the [versions journal](versions.md).

A `.gno` file is Markdown. gnō adds a few kinds of line to it (scene
headings, entity lines, dialogs, pauses and diverts) and leaves every other
line to Markdown.

- [Notation](#notation)
- [Narrative](#narrative)
- [Scene](#scene): [scene heading](#scene-heading), [start and end markers](#start-and-end-markers)
- [Scene content](#scene-content): [text](#text), [pause](#pause)
- [Entities](#entities): [entity reference](#entity-reference), [group](#group), [standalone entity](#standalone-entity), [exit](#exit), [inline mention](#inline-mention), [dialog](#dialog)
- [Diverts](#diverts): [arrows](#arrows), [choice](#choice), [entity divert](#entity-divert)
- [How a line is read](#how-a-line-is-read)
- [Grammar at a glance](#grammar-at-a-glance)
- [Complete example](#complete-example)

## Notation

Each structure is described by a small grammar written in a minimal subset
of Extended BNF:

| Notation | Meaning |
|---|---|
| `a = …` | the rule that defines `a` |
| `"…"` | written exactly as shown |
| `a b` | `a` followed by `b` |
| `a \| b` | either `a` or `b` |
| `[ a ]` | `a` is optional |
| `{ a }` | `a` repeated zero or more times |
| `<…>` | a description in words, where a rule would say less than the words do |

Spaces between the items of a rule may be written or left out. A quoted
space, `" "`, means at least one space is required at that point. Rules that
build a single word (such as `entity-id`) allow no spaces inside.

Each rule comes with a concrete example on the line below it, marked `▸`:

```text
choice = "*" " " label arrow target
         ▸ * Examine the patient -> Examination Room
```

Each structure is then shown in use, in examples written as they would
appear in a `.gno` file.

## Narrative

A narrative is a complete interactive story, written in a single `.gno`
file. It is a sequence of scenes. Each scene takes place in a scenario (a
place or setting), and several scenes can share the same scenario.

```text
narrative = { preamble-line } scene { scene }
            ▸ # Emergency Room: Hospital (*)
              …
              # Examination Room: Hospital
              …
scene     = scene-heading { scene-line }
            ▸ # Emergency Room: Hospital (*)
              The waiting room is crowded.
              * Examine the patient -> Examination Room
```

Lines before the first scene heading (the preamble) belong to no scene. The
Player never shows them, so they can hold notes for the author.

```gno
Draft of the zombie emergency case. Notes for the author only.

# Emergency Room: Hospital (*)

The waiting room is crowded and noisy.

* Examine the patient -> Examination Room

# Examination Room: Hospital (**)

The patient lies down, pale and silent.
```

## Scene

### Scene heading

A scene is the basic unit of a narrative: one moment of the story,
presented to the reader on its own, one scene at a time. A scene can stand
for a place, a focus inside a place, or a state of the story. The scene
heading starts a scene and gives its title and its scenario. The scene runs
until the next scene heading.

```text
scene-heading = level " " title ":" scenario [ marker ]
                ▸ # Emergency Room: Hospital
level         = "#" | "##" | "###" | "####" | "#####" | "######"
                ▸ ##
title         = <text without ":">
                ▸ Emergency Room
scenario      = <text>
                ▸ Hospital
```

- The **title** names the scene. Diverts reach a scene by its title,
  ignoring case; the scenario is not part of the name. Give every scene a
  title of its own: if two scenes share a title, diverts reach the first
  one.
- The **scenario** groups scenes. Scenes of the same scenario share its
  graphic design (**Presentation → Scenarios**).
- The heading **level** makes no difference: all scenes are at the same
  level, with no hierarchy between them.
- A Markdown heading **without a colon** is not a scene heading: it stays a
  heading inside the scene's text. A heading **with a colon** always starts
  a new scene.

```gno
# Emergency Room: Hospital

## Zombie Treatment: Hospital

# Waiting Room: Hospital

### Symptoms
```

The first three lines start scenes, two of them in the same scenario,
`Hospital`. `### Symptoms` has no colon: it is a heading inside the
`Waiting Room` scene.

### Start and end markers

The markers tell the Player where the narrative begins and where it ends.
They are written in parentheses at the end of a scene heading, after the
scenario. Being symbols rather than words, they read the same whatever the
narrative's language.

```text
marker = "(*)" | "(**)"
         ▸ (*)
```

- `(*)` marks the **start** scene. Exactly one scene should carry it. If no
  scene does, the narrative starts at the first scene of the file.
- `(**)` marks the **end** scene. When the Player has presented it, the
  narrative is finished: no choices are offered.
- Spaces inside the parentheses are allowed: `( * )`.

```gno
# Emergency Room: Hospital (*)

# Zombie Treatment: Hospital (**)
```

## Scene content

```text
scene-line = choice | pause | dialog | entity-divert | entity-line | exit
           | text-line | <blank line>
             ▸ -- @Lucinda: Hey doctor, you must come here.
```

Each kind of line is described below. How the editor decides which kind a
line is, when it could be more than one, is summed up in
[How a line is read](#how-a-line-is-read).

### Text

Text is everything the reader reads outside dialogs: the description of the
scene, the narration of what happens. It is written in Markdown
(GitHub-flavored): paragraphs, emphasis, lists, links, images, block quotes
and so on. Entities mentioned in the text are
[inline mentions](#inline-mention).

```text
text-line = <a Markdown line that is no other gnō structure>
            ▸ The patient is a *man*, 55 years old, rather fat.
```

Blank lines separate paragraphs, as in Markdown, and also end a dialog's
text (see [Dialog](#dialog)).

```gno
# Emergency Room: Hospital (*)

The waiting room is crowded and noisy. In a corner, a man,
55 years old, rather fat, holds his left arm.

> The night shift has been quiet. Until now.
```

### Pause

A pause splits a scene into beats. The Player shows a scene one beat at a
time: it stops at each pause and waits for the reader to continue. Each new
beat replaces the previous one on screen.

```text
pause = "--"
        ▸ --
```

- A pause is a line with only `--` (spaces around it are allowed). The
  Player never shows it.
- Dialogs pause on their own: after a dialog, or a run of consecutive
  dialogs, the Player pauses unless only the scene's choices follow. There
  is no need to write `--` after a dialog.
- `---` (three dashes) is a Markdown horizontal rule, not a pause.

```gno
The waiting room is crowded and noisy.

--

A nurse runs toward you, holding a chart.
```

The reader first sees the waiting room, continues, and then sees the nurse.

## Entities

Entities are the characters, objects or other elements present in a scene.
They are written with an `@` before their identifier, in three forms: alone
on a line ([standalone entity](#standalone-entity)), at the start of a
[dialog](#dialog), or inside text ([inline mention](#inline-mention)). An
entity is on stage from the moment it is first mentioned, in any form,
until it [exits](#exit) or the scene ends.

### Entity reference

An entity reference names one entity, or a [group](#group) of entities
acting together.

```text
entity    = entity-id { "+" entity-id }
            ▸ @Lucinda
entity-id = "@" id-char { id-char }
            ▸ @Dr_Lima
id-char   = <letter> | <digit> | "_" | "'" | "-"
            ▸ é
```

- Letters can be of any alphabet, with accents: `@enfermeira`, `@médico`.
- The Player shows an entity without the `@`, with underscores as spaces:
  `@Dr_Lima` is shown as "Dr Lima".
- Write an entity the same way everywhere it appears.
- `'` and `-` belong to the identifier: in `@Lucinda's chart`, the entity is
  `@Lucinda's`, not `@Lucinda`. Write `the chart of @Lucinda` instead.

### Group

A group is two or more entities acting together, such as two nurses
standing side by side or speaking in unison. In graphic play, a group can
have images of its own.

```text
group = entity-id "+" entity-id { "+" entity-id }
        ▸ @Lucinda + @Jacinto
```

- A group can be used wherever an entity can: standalone, in a dialog or in
  text.
- The order doesn't matter: `@Jacinto + @Lucinda` is the same group. An
  entity repeated in a group counts once.
- A state given to the group applies to every member.
- Mentioning a member alone afterwards splits the group: from then on, each
  member is on stage on its own (see the [README](../README.md#graphic-play)).

```gno
@Lucinda + @Jacinto right ready

-- @Lucinda + @Jacinto: Ready, doctor!

The @Lucinda + @Jacinto lift the patient onto the bed.
```

### Standalone entity

A standalone entity line brings an entity on stage, or changes its state,
without saying anything. The state describes the entity at that point: its
position, its mood, its posture. In graphic play, the state words choose
the entity's image and the anchor it stands at.

```text
entity-line = entity { " " state-word }
              ▸ @Lucinda right concerned
state-word  = <a word without ":" or "@">
              ▸ concerned
```

- The entity and its state take the whole line.
- States are free-form words, with no fixed vocabulary. An entity with no
  state words just enters the stage.
- A new state replaces the previous one.
- Any line that starts with an entity and contains no `:` or `@` after it
  is a standalone entity line. `@Lucinda runs to the door.` gives Lucinda
  the state `runs to the door.`. To write that sentence as text, start the
  line with something else: `Nurse @Lucinda runs to the door.`

```gno
@Lucinda

@Lucinda left concerned

@patient right pale sweating
```

### Exit

An exit takes an entity off stage, from that point of the scene on.

```text
exit = entity " " "=>"
       ▸ @Lucinda =>
```

- `=>` must be the whole state: `@Lucinda =>` exits, `@Lucinda left =>` does
  not.
- An entity mentioned again after its exit comes back on stage.
- A group's exit takes the group and all its members off stage.
- Being a symbol rather than a word, it reads the same whatever the
  narrative's language.

```gno
-- @Lucinda: I will get the lab results.

@Lucinda =>
```

### Inline mention

An inline mention refers to an entity inside the text. It brings the entity
on stage, if it isn't already, without changing its state.

```text
mention-line = { <text> } entity { <text> | entity }
               ▸ Nurse @Lucinda hands the chart to @Dr_Lima.
```

- A line can mention several entities.
- In the Player, the mention is shown as the entity's name: `@Dr_Lima`
  becomes "Dr Lima".
- A line that starts with an entity and has no `:` or `@` after it is a
  [standalone entity](#standalone-entity), not a mention.
- A line that starts with `*` (a choice, a list item, or text in italics) is
  not searched for mentions.

```gno
Nurse @Lucinda checks the pulse of the @patient, then looks at @Dr_Lima.
```

### Dialog

A dialog is text spoken by an entity, or by a group speaking in unison. It
can also set the speaker's state, as a standalone entity line does.

```text
dialog      = "--" entity { state-word } ":" [ <text> ] { speech-line }
              ▸ -- @Lucinda left concerned: Hey doctor, you must come here.
speech-line = <a line that is not blank and not a dialog>
              ▸ His skin is getting greener by the minute.
```

- The speech can start after the colon, on the same line, or on the next
  line, and it continues over the following lines until a blank line or the
  next dialog. The lines are joined into one paragraph, which can use inline
  Markdown (emphasis, links).
- Leave a blank line after a dialog that spans several lines. Without it,
  the next line, even a `--` pause, becomes part of the speech.
- Dialogs written on consecutive lines form a dialog set: the Player shows
  them together and pauses once, after the last one.

```gno
-- @Lucinda left concerned: Hey doctor, you must come here.
-- @patient right pale: I... I don't feel well.

-- @Lucinda:
He arrived ten minutes ago.
His skin is getting *greener* by the minute.

-- @Lucinda + @Jacinto: Ready, doctor!
```

The first two dialogs form a dialog set and share one pause. The third one
spans two lines and is shown as one paragraph.

## Diverts

Diverts are transitions from the current scene to another. There are two
kinds: [choices](#choice), offered to the reader at the end of the scene,
and [entity diverts](#entity-divert), taken by clicking an entity while it
is on stage. Both are written with an arrow followed by the target scene.

### Arrows

The arrow says how the target scene is presented.

```text
arrow  = "->" | "~>"
         ▸ ~>
target = <the title of a scene>
         ▸ Examination Room
```

- `->` **goes** to the target: the target scene replaces the current one.
  Taken inside a subscene, it closes every open subscene.
- `~>` opens the target as a **subscene**: the target is played over the
  current scene, which stays frozen and dimmed underneath. Going back
  closes the subscene and returns to the scene underneath, exactly where it
  was left. A subscene can open further subscenes.
- The target is the title of a scene, compared ignoring case (see
  [Scene heading](#scene-heading)).
- `=>` is not an arrow: it is an [exit](#exit).

### Choice

A choice is an option offered to the reader: a label and the scene it leads
to.

```text
choice = "*" " " label arrow target
         ▸ * Examine the patient -> Examination Room
label  = <text without an arrow>
         ▸ Examine the patient
```

- The choice takes the whole line, starting with `*` and a space, as a
  Markdown list item does.
- Choices can be written anywhere in the scene, but the Player always offers
  them at its end, in the order written. They are numbered from 1 in that
  order (in graphic play, choice N is shown by `action_N`).
- A line starting with `*` that has no arrow is an ordinary Markdown list
  item.
- An `(**)` scene offers no choices: the narrative ends there.

```gno
* Examine the patient -> Examination Room
* Call Dr. Lima -> Doctors' Lounge
* Read the triage notes ~> Triage Notes
```

The third choice opens `Triage Notes` as a subscene over the current scene.

### Entity divert

An entity divert attaches a divert to an entity. While the entity is on
stage, the reader can click it to take the divert, at any point of the
scene rather than only at its end. The line also brings the entity on
stage, as a [standalone entity](#standalone-entity) line does, and can give
it a state.

```text
entity-divert = entity { " " state-word } " " arrow target
                ▸ @xray_film left ~> X-Ray
```

- The arrow needs a space before it, since `-` can be part of an
  identifier: `@door->Garden` is not a divert.
- The entity keeps its divert through later mentions, until it exits or the
  scene ends.
- Entity diverts are not numbered among the choices.
- Where the entity has no image to click (the text Player, or an entity not
  drawn), the Player shows a button for it.

```gno
@xray_film left ~> X-Ray

@door -> Corridor
```

## How a line is read

A line could sometimes fit more than one structure. The editor reads each
line of a scene as the first of these that fits:

| # | The line is | Read as |
|---|---|---|
| 1 | a heading (`#` to `######`) with a colon | [scene heading](#scene-heading) |
| 2 | `*`, a space, a label, an arrow and a target | [choice](#choice) |
| 3 | blank | end of a dialog's speech; paragraph break |
| 4 | only `--` | [pause](#pause) |
| 5 | `--` followed by an entity | [dialog](#dialog), with the speech lines after it |
| 6 | an entity, state words, a space, an arrow and a target | [entity divert](#entity-divert) |
| 7 | an entity followed by `=>` | [exit](#exit) |
| 8 | an entity followed only by words without `:` or `@` | [standalone entity](#standalone-entity) |
| 9 | anything else | [text](#text), with its `@` entities as [inline mentions](#inline-mention) (not on lines starting with `*`) |

## Grammar at a glance

```text
narrative     = { preamble-line } scene { scene }
scene         = scene-heading { scene-line }

scene-heading = level " " title ":" scenario [ marker ]
level         = "#" | "##" | "###" | "####" | "#####" | "######"
title         = <text without ":">
scenario      = <text>
marker        = "(*)" | "(**)"

scene-line    = choice | pause | dialog | entity-divert | entity-line | exit
              | text-line | <blank line>

text-line     = <a Markdown line that is no other gnō structure>
pause         = "--"

entity        = entity-id { "+" entity-id }
group         = entity-id "+" entity-id { "+" entity-id }
entity-id     = "@" id-char { id-char }
id-char       = <letter> | <digit> | "_" | "'" | "-"

entity-line   = entity { " " state-word }
state-word    = <a word without ":" or "@">
exit          = entity " " "=>"
mention-line  = { <text> } entity { <text> | entity }
dialog        = "--" entity { state-word } ":" [ <text> ] { speech-line }
speech-line   = <a line that is not blank and not a dialog>

arrow         = "->" | "~>"
target        = <the title of a scene>
choice        = "*" " " label arrow target
label         = <text without an arrow>
entity-divert = entity { " " state-word } " " arrow target
```

| Symbol | Where | Meaning |
|---|---|---|
| `#` … `:` | heading | scene title and scenario |
| `(*)` / `(**)` | end of a scene heading | start scene / end scene |
| `--` | alone on a line | pause |
| `--` | before an entity | dialog |
| `@` | before an identifier | entity |
| `+` | between entities | group |
| `:` | after a dialog's entity and state | start of the speech |
| `=>` | after an entity | exit |
| `->` | before a target | divert: go to the scene |
| `~>` | before a target | divert: open the scene as a subscene |
| `*` | start of a line with an arrow | choice |

## Complete example

```gno
Draft of the zombie emergency case. Notes for the author only.

# Emergency Room: Hospital (*)

The waiting room is crowded and noisy. In a corner, a man,
55 years old, rather fat, holds his left arm.

--

@Lucinda left concerned

-- @Lucinda left concerned: Hey doctor, you must come here.
-- @patient right pale: I... I don't feel well.

-- @Lucinda:
He arrived ten minutes ago.
His skin is getting *greener* by the minute.

@xray_film middle ~> X-Ray

* Examine the patient -> Examination Room
* Read the triage notes ~> Triage Notes

# Triage Notes: Hospital

*Bitten on the left arm at 2 a.m. Fever. Asks for brains.*

# X-Ray: Radiology

The film shows a perfectly normal chest.

# Examination Room: Hospital

Nurse @Lucinda helps the @patient onto the bed.

@patient middle lying

@Lucinda + @Jacinto right ready

-- @Lucinda + @Jacinto: Ready, doctor!

@Lucinda + @Jacinto =>

* Prescribe the zombie treatment -> Zombie Treatment

# Zombie Treatment: Hospital (**)

The color slowly comes back to the face of the @patient.

-- @patient middle relieved: Thank you, doctor. I no longer want brains.
```
