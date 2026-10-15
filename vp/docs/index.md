# VP Studio

VP Studio lets educators author **virtual patient (VP) activities**: a
scripted sequence of steps in which an LLM tutor (and optionally an LLM
patient) guides a student through clinical cases. Students play the activity
in a chat-style player.

It runs on the platform's shared server at `/vp/`, with the shared sign-in
and the [LLM gateway](../../docs/llm-gateway.md).

## Status

| Part | For | State |
|------|-----|-------|
| Simple mode editor | Teachers with no prompt-engineering background | Available |
| Advanced mode editor | Instructional designers | Planned (the toggle is disabled) |
| Player and "Try it" | Students, and authors testing a case | Planned (placeholder screen) |

## Concepts

A **case** (one activity) is an ordered list of **steps**: welcome, knowledge
activation, case explanation, assessment, transfer to a new case, patient
interview, reflection, final feedback, or a custom step. Each step holds
ordered **elements**:

| Kind | Author writes | Student sees |
|------|---------------|--------------|
| Literal | The exact text | That text |
| Generated | A prompt with `{{fields}}` | Text the LLM writes when the session runs |
| Interaction | An agent prompt with an exit condition | A multi-turn conversation |

Elements can carry hidden **side information** (expert explanation, hidden
findings, rubric, …) and reusable **strategies** (feedback style, patient
persona, final-feedback format, gamification).

## Simple mode at a glance

- **New case** opens a gallery: start from scratch (Welcome + Final feedback)
  or from a script template. *Your cases* lists your existing cases.
- **Steps** can be added, moved, renamed and removed. The script rules are
  enforced: Welcome first, Final feedback last, transfers and assessments
  after "Explain case 1", single steps at most once. An option that would
  break a rule is shown disabled, with the reason.
- **Fields.** The prompt editor highlights `{{fields}}` as you type:
  - known fields in amber;
  - unknown fields in red;
  - fields that refer to something not available yet at that step (a later
    step's answer, for example) also in red.

  *Insert field* lists what each step can use. Renaming a custom step
  rewrites every `{{…answer}}` that points to it.
- **Assistant** buttons (wand, stethoscope) ask the LLM to write a text, a
  vignette or a prompt, or an expert explanation from the knowledge text.
  The result replaces the text; the toast offers **Undo**.
- **Preview** shows what the student sees in the open step. **Generate
  sample** asks the LLM for an example of a generated text or interaction.
  Samples are cached per prompt, strategies and level.
- **Save** (Ctrl+S) stores the case. **Publish** first checks the readiness
  requirements (title, every text and side information filled, no
  unknown or forward fields), then freezes a published copy.

## Activity content

The public repository ships **neutral placeholder** templates, prompts and
strategies. A deployment loads its own with `manage.py load_vp_content`; see
[Content packs](content-packs.md).

## Code

| Path | What |
|------|------|
| `vp/server/vp_studio/casedoc.py` | Case rules (sequencing, fields, readiness, structure). Pure Python. |
| `vp/server/vp_studio/content.py` | Content-pack validation, new-case building. Pure Python. |
| `vp/server/vp_studio/services.py` | Assistant calls, preview samples, publishing |
| `vp/server/vp_studio/views.py` | API under `/vp/api/` |
| `vp/web/static/js/casemodel.js` | The same rules as `casedoc.py`, in the browser |
| `vp/web/static/js/studio.js` | The editor (Vue 3 from a CDN, no build step) |

API (all require the sign-in token):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/vp/api/content/` | Active content pack (without server-only instructions) |
| `GET/POST` | `/vp/api/cases/` | List / create your cases |
| `GET/PUT/DELETE` | `/vp/api/cases/{id}/` | Read / save (send `base_revision` to detect concurrent edits → 409) / delete |
| `POST` | `/vp/api/cases/{id}/publish/` | Publish, or `400` with `problems` |
| `POST` | `/vp/api/assist/` | `{mode, document, step, element, side?, instruction?}` → `{text}` |
| `POST` | `/vp/api/preview-sample/` | `{document, step, element, refresh?}` → `{kind, text \| turns, cached}` |
