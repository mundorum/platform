---
title: noid
---

# noid

noid composes and executes **n-o-id scenes**: directed graphs of Python
components connected by publish/subscribe edges. Scenes are authored in a web
editor on the platform's shared server (mounted at `/noid/`) and packaged as
zip files; a separate processing machine runs them and returns their results,
the two communicating over HTTPS.

## Documentation

<ul class="doclist">
  <li><a href="docs/architecture.html">Architecture</a>
    <span>The two-machine model, data flows and technology choices.</span></li>
  <li><a href="docs/scene-package.html">Scene package</a>
    <span>The platform's extensions to the zip format of a scene.</span></li>
  <li><a href="docs/api.html">API reference</a>
    <span>Endpoints of noid authoring and processing.</span></li>
  <li><a href="docs/dev-setup.html">Development tasks</a>
    <span>noid-specific development tasks.</span></li>
</ul>

## Shared server

noid runs on the platform's shared server, together with VP Studio.

<ul class="doclist">
  <li><a href="../docs/architecture.html">Platform architecture</a>
    <span>How the subprojects share the server, database and sign-in.</span></li>
  <li><a href="../docs/dev-setup.html">Development setup</a>
    <span>Running the shared server and noid's processing server locally.</span></li>
  <li><a href="../docs/deployment.html">Docker deployment</a>
    <span>Deploying the platform with Docker Compose.</span></li>
</ul>
