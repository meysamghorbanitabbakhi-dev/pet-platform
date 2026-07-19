#!/usr/bin/env bash
# Builds a reproducible release archive from a git ref (default: HEAD) via
# `git archive` -- packages exactly what git tracks, so there is no
# hand-maintained include/exclude list to drift from .gitignore, and the
# same commit always produces byte-identical output. PACKAGE_MANIFEST.md
# has long described what a backend release archive should and should not
# contain but noted plainly that "no packaging script currently enforces
# this list against a built archive -- treat it as intent, not verified
# build behavior, until one exists." This is that script: it builds the
# archive, then actually verifies the result instead of assuming it.
set -euo pipefail

ref="${1:-HEAD}"
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

backend_version=$(grep -m1 '^version' backend/pyproject.toml | sed -E 's/version = "(.*)"/\1/')
frontend_version=$(grep -m1 '"version"' frontend/pet-platform-frontend/package.json | sed -E 's/.*"version": *"([^"]+)".*/\1/')

if [ "$backend_version" != "$frontend_version" ]; then
  echo "ERROR: backend version ($backend_version) and frontend version ($frontend_version) disagree" >&2
  exit 1
fi

version="$backend_version"
commit_sha=$(git rev-parse --short "$ref")
archive_name="pet-platform-${version}-${commit_sha}"
out_dir="dist"
mkdir -p "$out_dir"
archive_path="$out_dir/${archive_name}.zip"

echo "+ building $archive_path from $ref (git archive, tracked files only)"
git archive --format=zip --prefix="${archive_name}/" -o "$archive_path" "$ref"

checksum=$(sha256sum "$archive_path" | awk '{print $1}')
echo "$checksum  ${archive_name}.zip" > "$out_dir/${archive_name}.sha256"

echo "+ verifying archive contents"
verify_dir=$(mktemp -d)
trap 'rm -rf "$verify_dir"' EXIT
unzip -q "$archive_path" -d "$verify_dir"

required_paths=(
  "${archive_name}/backend/app/main.py"
  "${archive_name}/backend/release-contract.json"
  "${archive_name}/backend/PACKAGE_MANIFEST.md"
  "${archive_name}/backend/migrations"
  "${archive_name}/backend/Dockerfile"
  "${archive_name}/frontend/pet-platform-frontend/package.json"
  "${archive_name}/frontend/pet-platform-frontend/src/app"
  "${archive_name}/docker-compose.yml"
)
for path in "${required_paths[@]}"; do
  if [ ! -e "$verify_dir/$path" ]; then
    echo "ERROR: expected path missing from archive: $path" >&2
    exit 1
  fi
done

# Sanity checks against PACKAGE_MANIFEST.md's exclusion list -- these should
# always pass by construction (git archive only ever includes tracked
# files, and these are all gitignored), so a failure here means something
# was force-added to git that should not have been.
excluded_patterns=(
  "*/node_modules/*"
  "*/.venv/*"
  "*/__pycache__/*"
  "*/.env"
  "*/.next/*"
)
for pattern in "${excluded_patterns[@]}"; do
  if find "$verify_dir" -path "$pattern" -print -quit | grep -q .; then
    echo "ERROR: archive unexpectedly contains files matching $pattern" >&2
    exit 1
  fi
done

file_count=$(find "$verify_dir/${archive_name}" -type f | wc -l)
archive_size=$(du -h "$archive_path" | cut -f1)

echo "{\"status\":\"ok\",\"archive\":\"$archive_path\",\"sha256\":\"$checksum\",\"version\":\"$version\",\"commit\":\"$commit_sha\",\"file_count\":$file_count,\"size\":\"$archive_size\"}"
