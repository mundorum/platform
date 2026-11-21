---
title: VP Studio
---

# VP Studio

VP Studio lets educators author **virtual patient activities**: a scripted
sequence of steps in which an LLM tutor, and optionally an LLM patient, guides
a student through clinical cases. Authors build a case from ready-made steps
(knowledge activation, case explanation, assessment, patient interview,
reflection and more); students play it in a chat-style player. It runs on the
platform's shared server, at `/vp/`.

## Documentation

<ul class="doclist">
  <li><a href="docs/index.html">Overview</a>
    <span>Concepts, editor, player and API of VP Studio.</span></li>
  <li><a href="docs/content-packs.html">Content packs</a>
    <span>Script templates and the default elements of each step type.</span></li>
  <li><a href="docs/llm-case-authoring.html">Writing a case with an LLM</a>
    <span>A page meant to be given to a chat assistant, so it can help you build a case.</span></li>
  <li><a href="docs/gno-export.html">Export as gnō-</a>
    <span>How a case is written as a gnō- narrative for reading and review.</span></li>
  <li><a href="docs/slides/vp-authoring-v02.pdf">Authoring slides (v02, PDF)</a>
    <span>A presentation of activity authoring. Earlier edition: <a href="docs/slides/vp-authoring-v01.pdf">v01</a>.</span></li>
</ul>

## Shared server

VP Studio runs on the platform's shared server, together with noid.

<ul class="doclist">
  <li><a href="../docs/architecture.html">Platform architecture</a>
    <span>How the subprojects share the server, database and sign-in.</span></li>
  <li><a href="../docs/llm-gateway.html">LLM gateway</a>
    <span>Calling Groq, OpenRouter and Mistral, and where the keys live.</span></li>
  <li><a href="../docs/dev-setup.html">Development setup</a>
    <span>Running the shared server locally.</span></li>
  <li><a href="../docs/deployment.html">Docker deployment</a>
    <span>Deploying the platform with Docker Compose.</span></li>
</ul>
