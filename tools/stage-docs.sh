#!/usr/bin/env bash
# Assemble the documentation site from docs/ (platform), noid/docs/ and
# vp/docs/ into build/docs-site/, ready for `mkdocs build|serve`.
#
# In the repository the folders link to each other with repo-relative paths
# (../noid/docs/x.md, ../../docs/x.md) so links work when browsing on GitHub;
# this script rewrites them for the single site tree:
#   docs/*.md        → site/          ../noid/docs/ → noid/   ../vp/docs/ → vp/
#   noid/docs/*.md   → site/noid/     ../../docs/   → ../
#   vp/docs/*.md     → site/vp/       ../../docs/   → ../
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/docs-site"

rm -rf "$OUT"
mkdir -p "$OUT/docs/noid" "$OUT/docs/vp"

cp -r "$ROOT/docs/." "$OUT/docs/"
# noid/docs/internal/ is gitignored (private notes) — never publish it
rsync -a --exclude 'internal/' "$ROOT/noid/docs/" "$OUT/docs/noid/"
cp -r "$ROOT/vp/docs/." "$OUT/docs/vp/"
cp "$ROOT/mkdocs.yml" "$OUT/mkdocs.yml"

find "$OUT/docs" -maxdepth 1 -name '*.md' -exec sed -i \
  -e 's#\.\./noid/docs/#noid/#g' -e 's#\.\./vp/docs/#vp/#g' {} +
find "$OUT/docs/noid" "$OUT/docs/vp" -name '*.md' -exec sed -i \
  -e 's#\.\./\.\./docs/#../#g' {} +

echo "Staged docs in $OUT"
