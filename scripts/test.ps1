$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\apps\api"
python -m pytest
Pop-Location

Push-Location "$PSScriptRoot\..\apps\workflow"
python -m pytest
Pop-Location
