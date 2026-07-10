import os
import sys

# `pytest authoring/` (per CLAUDE.md dev commands) runs with cwd at the noid
# root, not inside authoring/ — without this, `config.settings` isn't on
# sys.path and Django never initializes.
sys.path.insert(0, os.path.dirname(__file__))
