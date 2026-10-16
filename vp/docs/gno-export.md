# Export as gnō-

*Export gnō-* (in Case settings) downloads the case as a `.gno` file: the
activity written as a **gnō- narrative**, meant for people to read, review
and discuss. gnō- is the platform's narrative language. Its specification is
`gno/README.md` in the platform repository.

The export goes one way only. The file is **not** imported back and the
player never runs it. To move a case between authors or servers, use
*Export JSON* instead.

The file is valid gnō- with a few vp conventions on top: `>>` lines, `>`
prompts and a data layer. They are defined here, in vp, and are not part of
the gnō- specification.

## The pieces

| In the case | In the `.gno` file |
|---|---|
| Step | A scene: `# <step name>: <case in focus>`. The scenario is `Case N` for steps about a case (explain, transfer, assessment, interview) and the activity title otherwise. The first scene is marked `(Start)`, the last `(End)`. |
| Literal message | Tutor dialog: `-- @tutor: …`, the exact words the student reads. Each paragraph is its own dialog line. |
| Case card | `>> card <field> — <card name>`, then the vignette as plain prose. |
| Generated element | `@tutor writes — <label>`, then its prompt as a `>` block. |
| Interaction | `@tutor converses — <label>`, or `@patient` in an interview or with a Patient strategy, then its prompt as a `>` block. |
| Side information, strategies | `>> uses <field> — <label>`, `>> strategy <key> — <name> (<moment>)`. Their texts are in the data layer. |
| Other bindings | `>> provides <field>`, `>> adds the phase sentence — …`, `>> note — …`, `>> review materials — …` |
| How a step ends | Diverts, one per way out, all to the next scene (see below). |
| Settings, agent prompts, strategy prompts, side-information texts | The data layer, after `===== Data =====`. |

**Every prompt is a `>` block**, in the scenes and in the data layer alike.
`{{fields}}` are left as written.

### Diverts

A step that ends with an interaction gets one divert per way the
interaction can end:

```gno
* The student has recalled the main concepts of the knowledge text. -> Narrative Construction
* After 6 student turns -> Narrative Construction
* The student says “I’m done” -> Narrative Construction
```

That is the author's *Ends when…* condition (when set), the turn limit, and
the student's "I'm done" (when allowed). A step without an interaction gets
`* The student answers -> …`, because the player waits for one reply. If an
interaction is followed by more elements, its endings are written inline
(`>> ends — …`) and the scene ends with `* Continue -> …`.

### Escaping

A line of the author's text that would look like gnō- structure is escaped
with a backslash. That covers lines starting with `#`, `*`, `--`, `>` or
`=====`, and `@name` anywhere (`\@name`). Scene names never contain a colon:
`Part 1: recall` becomes `Part 1 – recall`. When two steps share a name,
the second gets a number, so every divert points at exactly one scene.

### The data layer

The data layer follows the last scene and has four sections:

- **Settings**: title, student level, progress bar, reply language and script.
- **Agents**: the tutor and patient personas and the guardrails.
- **Strategies**: the instructions of the strategies the case uses.
- **Side information**: knowledge texts and expert explanations.

Its headings have no colon and its lists use `-`. That way a gnō- editor
never reads them as scenes or diverts, and shows the layer as plain text of
the last scene.

## Example

Here is part of a new case from the placeholder script *Recall → Explain →
Transfer*:

```gno
# Welcome & case 1: Sample activity (Start)

-- @tutor: Welcome! In this activity you will work through a clinical case with a virtual tutor. You can ask for feedback at any time. Ready to start?

>> adds the phase sentence — This activity has three phases: Knowledge Activation, Narrative Construction and Reasoning Transfer.

>> card case1.vignette — Case 1

A 45-year-old patient presents with fatigue.

-- @tutor: How would you explain this patient’s presentation?

* The student answers -> Knowledge Activation


# Narrative Construction: Case 1

@tutor writes — Phase introduction

> Announce {{phase.name}} and invite the student to explain the case in their own words. One or two sentences.

-- @tutor: Explain the patient’s presentation in your own words.

@tutor converses — Case discussion
>> uses case1.expert — Expert explanation of case 1
>> strategy hints — Hints first (per turn)

> Discuss {{case1.vignette}} with the student and compare each answer with {{case1.expert}}, one missing point at a time, without giving the whole explanation. Allow up to {{level.hints}} hints per point.

* The student has explained the main points of the expert explanation, in their own words. -> Reasoning Transfer
* After 8 student turns -> Reasoning Transfer
* The student says “I’m done” -> Reasoning Transfer

…

===== Data =====

## Settings

- Title — Sample activity
- Student level — Beginner (4 hints, pass mark 60%)
- Progress bar — shown
- Replies in the student’s language — yes
- Script — Recall → Explain → Transfer

## Agents

### @tutor — persona

> You are a friendly tutor helping students practise clinical reasoning on virtual patient cases. You guide with questions rather than handing out answers.

…

## Side information

### case1.expert — Expert explanation of case 1

_Expert explanation of case 1: the hidden evaluator compares the student’s answers with it._

…
```

The exporter is `vp/server/vp_studio/gnoexport.py`, a pure Python module
with no Django imports.
