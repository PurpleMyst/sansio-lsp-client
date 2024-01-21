param([Parameter(Mandatory = $true)][string]$version);

$init = (Get-Content .\sansio_lsp_client\__init__.py) -replace "__version__ = .*", ('__version__ = "' + $version + '"')
Set-Content .\sansio_lsp_client\__init__.py $init
py -m poetry version "$version"

git add sansio_lsp_client/__init__.py pyproject.toml
git commit -v -m "chore: bump version"
git tag "v$version"
