# Content Packs

A content pack holds VP Studio's pedagogical content:

- the **script templates** offered when a case is created;
- the **default elements** each step type starts with (labels, prompts, side information, strategies);
- the **strategy catalogue**;
- the **agent prompts** (tutor persona, patient persona, guardrails) new cases start with;
- the instructions the **assistant**, the **authoring assistant**, the **preview** and the **player** use when they call the LLM.

Code and content are kept apart on purpose. The public repository ships only
neutral placeholder content (`vp/server/vp_studio/content/placeholder.json`).
A deployment loads its own pack, kept wherever its authors choose (for example
a private repository), with:

```bash
python manage.py load_vp_content path/to/pack.json --check   # validate only
python manage.py load_vp_content path/to/pack.json           # validate and activate
```

Loading a pack makes it the active one. Earlier packs stay in the database as
inactive history (visible in `/admin/`). With no pack loaded, the placeholder
applies. A pack only affects cases **created** after it is loaded: an
existing case keeps the texts it was created with.

## Format

A pack is one JSON file:

```json
{
  "format": 1,
  "name": "My institution's content",
  "default_template": "explain_only",
  "templates": [ ... ],
  "strategies": [ ... ],
  "agents": { ... },
  "step_defaults": { ... },
  "runtime": { ... },
  "assist": { ... },
  "preview": { ... },
  "authoring": { ... }
}
```

`load_vp_content` validates every rule below and names the first problem it
finds.

### templates

```json
{"id": "explain_only", "name": "Explain", "description": "One case discussion.",
 "steps": ["explain"]}
```

`steps` lists the steps **between** Welcome and Final feedback, which every
case has. The full sequence must follow the script rules:

- `know`, `explain` and `interview` appear at most once;
- `assess` and `transfer` come after `explain`.

Available step types: `know`, `explain`, `assess`, `transfer`, `interview`,
`reflect`, `custom`. `default_template` must name one of the templates.

### strategies

```json
{"key": "hints", "name": "Hints first", "category": "Feedback", "icon": "ti ti-bulb",
 "moment": "per turn", "description": "Shown to authors in the picker.",
 "instruction": "What the agent is told at runtime.",
 "preview_label": "Optional: final-feedback card label in the preview"}
```

| Field | Notes |
|-------|-------|
| `category` | One of `Feedback`, `Final feedback`, `Patient`, `Gamification`. Each element kind accepts only some categories: literal → Gamification; generated → Final feedback, Gamification; interaction → Feedback, Patient, Gamification. Within Feedback, Final feedback and Patient an element holds one strategy at most; Gamification allows several. |
| `moment` | Default timing: `on start`, `per turn` or `at end`. Authors can change it per element. |
| `icon` | A [Tabler icon](https://tabler.io/icons) class. |
| `instruction` | Sent to the LLM. New cases copy it into the case, where authors can edit it (Strategies panel). |

### agents

```json
{"tutor_persona": "…", "patient_persona": "…", "guardrails": "…"}
```

These are copied into every new case, where authors can edit them in the
Strategies panel. The tutor persona and guardrails shape every tutor turn
and generated text. The patient persona shapes interviews and interactions
with a Patient strategy. They may use `{{fields}}`.

### step_defaults

One list per step type, covering **all** nine (`welcome`, `know`, `explain`,
`assess`, `transfer`, `interview`, `reflect`, `final`, `custom`); a list may
be empty. Each entry is an element:

```json
{"kind": "interaction", "label": "Case discussion",
 "text": "Discuss {{case{N}.vignette}} … End when …",
 "ref": "optional: makes the element's content a field",
 "card": "optional: render a literal as a case card with this heading",
 "note": "optional: fixed info line under the editor",
 "autoPhaseSentence": true,
 "isFinalFeedback": true,
 "sideInfo": [{"label": "Expert explanation of case {N}", "ref": "case{N}.expert", "text": "",
               "generateFromCase": "{N}"}],
 "strategies": [{"key": "hints", "moment": "per turn"}],
 "endsWhen": "interaction only: the end condition the LLM checks after each student turn",
 "maxTurns": 8,
 "allowStudentExit": true,
 "reviewMaterials": true}
```

- `maxTurns` (1–50) is **required** on interactions; `endsWhen` may be empty
  (turn limit only); `allowStudentExit` defaults to `true`.
- `reviewMaterials` on a literal makes the player append the case vignettes,
  expert explanations and knowledge text after it (typically in the final
  step).
- Side information with `generateFromCase` is an **expert explanation**:
  the player's hidden evaluator compares the student's answers with it.

- `kind` is `literal`, `generated` or `interaction`.
- In `transfer` defaults, `{N}` is replaced by the step's case number (2, 3, …) in every text, label, card and ref. `generateFromCase: "{N}"` becomes that number.
- Texts may use `{{fields}}`: content refs, step answers (`{{case1.answer}}`) and the system fields listed in the editor's *Insert field* tray.
- Leave case-specific material empty (`""`): vignettes, knowledge text, expert explanations, findings. Authors fill it in for each case; the readiness meter reminds them.

### assist

```json
{"system": "System prompt for every assistant call.",
 "modes": {"text": "…", "vignette": "…", "prompt": "…", "vprompt": "…", "expert": "…"}}
```

Each mode is the task description for one assistant button:

| Mode | Button |
|------|--------|
| `text` | write a literal text |
| `vignette` | write a case vignette |
| `prompt` | draft a generated or interaction prompt |
| `vprompt` | draft a prompt that generates a vignette |
| `expert` | "Generate from knowledge text" on an expert explanation |

The server appends the case context to every call: title, level, step,
element, existing text, available fields, strategies, and (for `expert`) the
knowledge text and vignette. It also appends the author's request.

### runtime

Server-only instructions used by the player:

```json
{"generated": "…", "exit_check": "…", "evaluator": "…", "progress_feedback": "…",
 "levels": {"beginner": "…", "intermediate": "…", "advanced": "…"}}
```

| Key | Used for |
|-----|----------|
| `generated` | wraps a generated element's prompt when the player writes it |
| `exit_check` | decides whether an interaction's **Ends when…** condition is met. Must ask for JSON `{"end": true\|false, "reason": "…"}` |
| `evaluator` | the hidden evaluator. Must ask for JSON `{"covered": [], "missing": [], "misconceptions": []}` |
| `progress_feedback` | the student's **Request feedback** button |
| `levels` | one sentence per student level, added to the tutor's instructions |

### preview

```json
{"system": "…", "generated": "…", "interaction": "…", "final_feedback": "…"}
```

These are used by the preview's **Generate sample** buttons. The
`interaction` instruction must ask for one turn per line, prefixed with
`STUDENT:`, `TUTOR:` or `PATIENT:`. The editor parses that format.

### authoring (optional)

Used by the **Authoring Assistant** (New case gallery), which drafts a case
from the author's vignette, the symptoms to explain and reference documents:

```json
{"template": "explain_transfer", "system": "…", "explanation": "…", "summary": "…",
 "summary_words": 400}
```

| Key | Used for |
|-----|----------|
| `template` | the script template the new case uses. Its steps must contain the `case1.vignette`, `case1.expert` and `knowledge` elements |
| `system` | system prompt for both calls |
| `explanation` | task for the explanation of the symptoms |
| `summary` | task for the summary of the documents |
| `summary_words` | the summary's word limit (the editor shows a word count against it) |

Each request puts the material first and the instruction last, so the
instruction isn't buried under long documents:

```
<documents>
<document name="file.pdf">…extracted text…</document>
</documents>

<vignette>…</vignette>          (explanation only)

<symptoms>…</symptoms>          (explanation only)

<explanation or summary instruction>
Length: at most <summary_words> words.   (summary only)
```

Instructions can refer to the material by these tag names.

The new case gets the vignette as case 1, the explanation as case 1's expert
explanation and the summary as the knowledge text.

A pack without this section uses the placeholder's instructions with the
pack's own template whose steps are `know`, `explain`, `transfer` (or its
`default_template` if it has none).

Staff can override all five keys from the assistant's settings panel, either
for everyone or for themselves (`AuthoringSettings`,
`/vp/api/authoring/settings/`, staff only). These overrides sit on top of the
pack. Loading a new pack keeps them. If the overridden `template` is no
longer offered, the pack's template is used instead. Settings identical to
what would apply anyway are not stored.
