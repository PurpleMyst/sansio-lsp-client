param([Parameter(Mandatory = $true)][string]$version);

$init = (Get-Content .\tarts\__init__.py) -replace "__version__ = .*", ('__version__ = "' + $version + '"')
Set-Content .\tarts\__init__.py $init
py -m poetry version "$version"

git add tarts/__init__.py pyproject.toml
git commit -v -m "chore: bump version"
git tag "v$version"
