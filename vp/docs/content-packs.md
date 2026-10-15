# Content Packs

A content pack holds VP Studio's pedagogical content:

- the **script templates** offered when a case is created;
- the **default elements** each step type starts with (labels, prompts, side information, strategies);
- the **strategy catalogue**;
- the instructions the **assistant** and the **preview** use when they call the LLM.

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
  "step_defaults": { ... },
  "assist": { ... },
  "preview": { ... }
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
| `instruction` | Sent to the LLM. It stays on the server and is never sent to the editor. |

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
 "strategies": [{"key": "hints", "moment": "per turn"}]}
```

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

### preview

```json
{"system": "…", "generated": "…", "interaction": "…", "final_feedback": "…"}
```

These are used by the preview's **Generate sample** buttons. The
`interaction` instruction must ask for one turn per line, prefixed with
`STUDENT:`, `TUTOR:` or `PATIENT:`. The editor parses that format.
