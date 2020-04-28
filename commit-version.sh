#!/usr/bin/env sh

set -eu

if [ $# -ne 1 ]; then
    printf 'Usage: %s VERSION\n' "$0"
    exit 1
fi

version=$1

sed -i "s/__version__ = .*/__version__ = \"$version\"/" sansio_lsp_client/__init__.py
poetry version "$version"

git add sansio_lsp_client/__init__.py pyproject.toml
git commit -v
git tag "v$version"
