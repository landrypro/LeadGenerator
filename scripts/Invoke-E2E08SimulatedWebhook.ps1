[CmdletBinding()]
param(
    [string]$WslDistribution = 'Ubuntu-24.04',
    [Parameter(Mandatory)]
    [ValidateLength(1, 128)]
    [string]$FormId,
    [ValidateLength(1, 128)]
    [string]$LeadId = 'E2E08-LEAD-001'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$workspaceWsl = (& wsl -d $WslDistribution -- wslpath -a $workspace).Trim()
if ($LASTEXITCODE -ne 0 -or -not $workspaceWsl) {
    throw "Impossible de résoudre le répertoire WSL pour $workspace."
}
if ($workspaceWsl -match "[\r\n']") {
    throw 'Le chemin de travail WSL contient un caractère non pris en charge.'
}

function Invoke-WslBash {
    param([Parameter(Mandatory)][string]$Script)

    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& wsl -d $WslDistribution -- bash -lc "printf '%s' $encoded | base64 -d | bash" 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    $output | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
        throw "L'envoi du webhook E2E-08 a échoué (code $exitCode)."
    }
}

$formIdEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($FormId))
$leadIdEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($LeadId))

Invoke-WslBash -Script @"
set -euo pipefail
cd '$workspaceWsl'

form_id="`$(printf '%s' '$formIdEncoded' | base64 -d)"
lead_id="`$(printf '%s' '$leadIdEncoded' | base64 -d)"

docker compose --profile runtime exec -T \
  -e "E2E08_FORM_ID=`$form_id" \
  -e "E2E08_LEAD_ID=`$lead_id" \
  api python - <<'PY'
import asyncio
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.config import Settings

settings = Settings.from_env()
body = json.dumps(
    {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "form_id": os.environ["E2E08_FORM_ID"],
                            "leadgen_id": os.environ["E2E08_LEAD_ID"],
                            "created_time": int(datetime.now(UTC).timestamp()),
                        }
                    }
                ]
            }
        ]
    },
    separators=(",", ":"),
).encode()
signature = "sha256=" + hmac.new(
    settings.meta_webhook_app_secret.encode(), body, hashlib.sha256
).hexdigest()


async def active_binding_exists() -> bool:
    """Diagnose the local fixture without exposing a form id or a secret."""
    form_fingerprint = hmac.new(
        settings.meta_reference_hmac_key.encode(),
        os.environ["E2E08_FORM_ID"].encode(),
        hashlib.sha256,
    ).hexdigest()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            return bool(
                await connection.scalar(
                    text(
                        "SELECT EXISTS("
                        "SELECT 1 FROM app_private.resolve_meta_lead_binding(:fingerprint)"
                        ")"
                    ),
                    {"fingerprint": form_fingerprint},
                )
            )
    finally:
        await engine.dispose()


request = Request(
    "http://127.0.0.1:8000/webhooks/meta/leadgen",
    data=body,
    headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    method="POST",
)
try:
    with urlopen(request, timeout=10) as response:
        print(f"E2E08_WEBHOOK=PASS status={response.status}")
except HTTPError as error:
    print(f"E2E08_WEBHOOK=FAILED status={error.code}")
    if error.code == 403:
        try:
            active = asyncio.run(active_binding_exists())
            diagnostic = "ACTIVE_BINDING_FOUND" if active else "NO_ACTIVE_BINDING"
            print(f"E2E08_WEBHOOK_DIAGNOSTIC={diagnostic}")
        except Exception:
            print("E2E08_WEBHOOK_DIAGNOSTIC=UNAVAILABLE")
    raise
PY
"@
