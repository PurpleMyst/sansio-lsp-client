#!/usr/bin/env sh

set -eu

if [ $# -ne 1 ]; then
    printf 'Usage: %s VERSION\n' "$0"
    exit 1
fi

version=$1

sed -i "s/__version__ = .*/__version__ = \"$version\"/" tarts/__init__.py
poetry version "$version"

git add tarts/__init__.py pyproject.toml
git commit -v -m "chore: bump version"
git tag "v$version"
