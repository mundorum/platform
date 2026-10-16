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
| Player | Students (share link) and authors (**Try it**) | Available (minimal) |
| Advanced mode editor | Instructional designers | Planned (the toggle is disabled) |

## Concepts

A **case** (one activity) is an ordered list of **steps**: welcome, knowledge
activation, case explanation, assessment, transfer to a new case, patient
interview, reflection, final feedback, or a custom step. Each step holds
ordered **elements**:

| Kind | Author writes | Student sees |
|------|---------------|--------------|
| Literal | The exact text | That text |
| Generated | A prompt with `{{fields}}` | Text the LLM writes when the session runs |
| Interaction | An agent prompt, an end condition and a turn limit | A multi-turn conversation |

Elements can carry hidden **side information** (expert explanation, hidden
findings, rubric, …) and **strategies** (feedback style, patient
persona, final-feedback format, gamification), each with a timing: on start,
per turn or at end.

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
- **Interactions end** by any of three mechanisms:
  - **Ends when…** (optional): a condition the LLM checks after every
    student turn;
  - **Max turns** (required): a hard limit on student turns;
  - **"Students can say they're done"** (on by default): the player shows an
    *I'm done* button after the student's first reply.
- **Strategies** (the third toggle, beside Case settings and Element types)
  holds one editable prompt per agent and per strategy, stored with the
  case:
  - **Agents:** tutor persona, patient persona, guardrails;
  - **Strategies:** Feedback, Final feedback, Patient, Gamification.

  New cases start from the content pack's defaults; *Reset to default*
  restores one.
- **Assistant** buttons (wand, stethoscope) ask the LLM to write a text, a
  vignette or a prompt, or an expert explanation from the knowledge text.
  The result replaces the text; the toast offers **Undo**.
- **Preview** shows what the student sees in the open step. **Generate
  sample** asks the LLM for an example.
- **Save** (Ctrl+S) stores the case. **Publish** checks the readiness
  requirements, then freezes a published copy. Students always play the
  published copy; later edits reach them only when you publish again.

## The player

**Try it** (or the *Player* tab) plays the editor's current draft, including
unsaved changes. Grey trace notes show you:

- the turn count;
- each end-check result;
- the evaluator's counts;
- why each part ended.

Students never see these.

**Student link:** `/vp/play/<case id>/`. Copy it from the publish toast, the
*Your cases* list or the player's side panel. Any signed-in user (with a
pre-authorized Google account) who has the link can play the **published**
version. A student's progress is kept, and reopening the link resumes it.

How a case runs:

1. Steps run in order. A step with a phase shows its banner and, if
   enabled, the progress bar.
2. **Literal** elements are shown as written. The welcome message gets the
   phase sentence; *review materials* are followed by the case vignettes,
   expert explanations and knowledge text.
3. **Generated** elements are written by the tutor at that moment. An "on
   start" strategy (e.g. *reflection first*) makes the tutor ask its
   question first and wait for the reply.
4. **Interactions** are conversations with the tutor. The agent is the
   **patient** in an interview step, or when a Patient strategy is
   attached. The student speaks first when a literal question comes right
   before the interaction; otherwise the agent opens.

   After each student turn:
   1. a hidden **evaluator** compares the answers with the element's expert
      explanation, if it has one, and the tutor sees the result;
   2. the turn limit and the **Ends when…** condition are checked;
   3. the agent replies.

   "At end" strategies get a closing agent turn.
5. A step without an interaction (other than the final one) waits for one
   student answer at its end. A step's `{{…answer}}` is that answer, or the
   student's last message in the step's interaction.
6. **Request feedback** (side panel) asks the tutor for feedback on
   progress at any time.

## Activity content

The public repository ships **neutral placeholder** content: templates,
default elements, strategies, agent prompts and the player's instructions.
A deployment loads its own with `manage.py load_vp_content`; see
[Content packs](content-packs.md).

## Code

| Path | What |
|------|------|
| `vp/server/vp_studio/casedoc.py` | Case rules (sequencing, fields, readiness, structure). Pure Python. |
| `vp/server/vp_studio/content.py` | Content-pack validation, new-case building. Pure Python. |
| `vp/server/vp_studio/runtime.py` | The player's step machine. Pure Python; the LLM is injected. |
| `vp/server/vp_studio/services.py` | Assistant calls, preview samples, publishing, player sessions |
| `vp/server/vp_studio/views.py` | API under `/vp/api/` |
| `vp/web/static/js/casemodel.js` | The same rules as `casedoc.py`, in the browser |
| `vp/web/static/js/studio.js` | Editor and player (Vue 3 from a CDN, no build step) |

API (all require the sign-in token):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/vp/api/content/` | Active content pack (without the server-only instructions) |
| `GET/POST` | `/vp/api/cases/` | List / create your cases |
| `GET/PUT/DELETE` | `/vp/api/cases/{id}/` | Read / save (send `base_revision` to detect concurrent edits → 409) / delete |
| `POST` | `/vp/api/cases/{id}/publish/` | Publish, or `400` with `problems` |
| `POST` | `/vp/api/assist/` | `{mode, document, step, element, side?, instruction?}` → `{text}` |
| `POST` | `/vp/api/preview-sample/` | `{document, step, element, refresh?}` → `{kind, text \| turns, cached}` |
| `GET` | `/vp/api/play/{case}/` | Title and published state, for a student link |
| `POST` | `/vp/api/sessions/` | `{case, mode: "try" \| "play", document?, restart?}` → session (resumes the latest unless `restart`) |
| `GET` | `/vp/api/sessions/{id}/` | The session: `messages`, `waiting`, `can_finish`, `finished`, `phases` |
| `POST` | `/vp/api/sessions/{id}/reply/` | `{text}`: the student's message |
| `POST` | `/vp/api/sessions/{id}/done/` | The student ends the current interaction |
| `POST` | `/vp/api/sessions/{id}/feedback/` | Feedback on progress |

A session action runs all its LLM calls first and saves only if they
all succeed. On a provider error the session is unchanged, and the message
can be sent again.
