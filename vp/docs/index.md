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
| Simple mode editor | Teachers with no prompt-engineering background | In development |
| Advanced mode editor | Instructional designers | Planned |
| Player | Students, and authors via "Try it" | Planned |

## Concepts

A **case** (one activity) is an ordered list of **steps** (welcome, knowledge
activation, case explanation, assessment, transfer to a new case, patient
interview, reflection, final feedback, or custom). Each step holds ordered
**elements**:

| Kind | Author writes | Student sees |
|------|---------------|--------------|
| Literal | The exact text | That text |
| Generated | A prompt with `{{fields}}` | Text the LLM writes when the session runs |
| Interaction | An agent prompt with an exit condition | A multi-turn conversation |

Elements can carry hidden **side information** (expert explanation, hidden
findings, rubric, ...) and reusable **strategies** (feedback style, patient
persona, final-feedback format, gamification).

## Code

| Path | What |
|------|------|
| `vp/server/vp_studio/` | Django app (label `vp`, tables `vp_*`) |
| `vp/web/` | Frontend (Vue 3 from CDN, no build step) |

## Activity content

The public repository ships **neutral placeholder** templates, prompts and
strategy texts. A deployment loads its real content from a private fixture
with the following command (arrives with Simple mode):

```bash
python manage.py load_vp_content <path>
```
