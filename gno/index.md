---
title: gnō-
---

# gnō-

gnō- is a language for interactive narratives and an editor to write and play
them. A narrative is a single Markdown-based `.gno` text: scenes grouped into
scenarios, entities, dialogs, states, and diverts that lead from one scene to
another. The editor shows the narrative as a graph and plays it in a Player,
optionally over a graphic presentation of each scenario drawn as SVG. It is a
single-page application that runs entirely in your browser: narratives are
kept in the browser's storage or downloaded as zip packages.

<div class="actions">
  <a class="btn primary" href="authoring/"><i class="ti ti-pencil"></i> Open the editor</a>
</div>

## Documentation

<ul class="doclist">
  <li><a href="README.html">The gnō- narrative format and Player</a>
    <span>Scenes, diverts, entities, states, dialogs, and how the Player presents them.</span></li>
  <li><a href="docs/syntax.html">Syntax reference</a>
    <span>Every structure of the <code>.gno</code> text, with EBNF-Lite rules and examples.</span></li>
  <li><a href="docs/scenario-svg.html">Scenario SVG</a>
    <span>The SVG files that hold a scenario's graphic design: elements, <code>data-gno-*</code> attributes and role IDs.</span></li>
  <li><a href="docs/scenario-tutorial.html">Tutorial: building a scenario presentation</a>
    <span>Step by step, from a blank SVG to a scenario played by the Player.
    Also <a href="docs/scenario-tutorial.pt-BR.html">em português</a>.</span></li>
  <li><a href="docs/versions.html">Versions journal</a>
    <span>What changed in each version of the language and its formats.</span></li>
  <li><a href="docs/architecture.html">Editor architecture</a>
    <span>How the single-file editor is built: stack, views, persistence and parsing pipeline.</span></li>
</ul>
