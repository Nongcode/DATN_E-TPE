$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force fixtures | Out-Null
venv\Scripts\python.exe -X utf8 manage.py dumpdata auth.user store --natural-foreign --natural-primary --indent 2 --output fixtures\initial_data.json

Write-Host "Exported current database to fixtures\initial_data.json"