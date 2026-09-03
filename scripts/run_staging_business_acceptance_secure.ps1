param(
    [Parameter(Mandatory = $true)]
    [string]$StagingApiOrigin,

    [ValidateRange(1, 120)]
    [double]$Timeout = 90,

    [switch]$HandshakeOnly
)

$ErrorActionPreference = 'Stop'
$rsa = $null
$plainBytes = $null
$exitCode = 1
$stage = 'initialize'

try {
    $stage = 'create_key'
    $rsa = [System.Security.Cryptography.RSACryptoServiceProvider]::new(2048)
    $stage = 'export_public_key'
    $publicParameters = $rsa.ExportParameters($false)
    $publicModulus = [Convert]::ToBase64String($publicParameters.Modulus)
    $publicExponent = [Convert]::ToBase64String($publicParameters.Exponent)
    $stage = 'emit_public_key'
    Write-Output "STAGING_ACCEPTANCE_PUBLIC_KEY=$publicModulus`:$publicExponent"
    $stage = 'receive_ciphertext'

    $encryptedLine = [Console]::ReadLine()
    if ([string]::IsNullOrWhiteSpace($encryptedLine) -or $encryptedLine.Length -gt 2048) {
        throw [System.InvalidOperationException]::new('encrypted credential input is missing or oversized')
    }

    $cipherBytes = [Convert]::FromBase64String($encryptedLine)
    $stage = 'decrypt'
    $plainBytes = $rsa.Decrypt($cipherBytes, $true)
    $stage = 'parse_credentials'
    $credentialJson = [System.Text.Encoding]::UTF8.GetString($plainBytes)
    $credentials = $credentialJson | ConvertFrom-Json

    $adminPassword = [string]$credentials.admin_password
    $adminInvite = [string]$credentials.admin_invite_code
    $customerInvite = [string]$credentials.customer_invite_code
    if (
        [string]::IsNullOrWhiteSpace($adminPassword) -or
        [string]::IsNullOrWhiteSpace($adminInvite) -or
        [string]::IsNullOrWhiteSpace($customerInvite) -or
        $adminPassword.Length -gt 200 -or
        $adminInvite.Length -gt 200 -or
        $customerInvite.Length -gt 200 -or
        $adminInvite -ceq $customerInvite
    ) {
        throw [System.InvalidOperationException]::new('decrypted staging credentials are invalid')
    }
    $stage = 'credentials_validated'

    if ($HandshakeOnly) {
        Write-Output 'secure credential handoff: PASS'
        $exitCode = 0
    }
    else {
        $env:STAGING_API_ORIGIN = $StagingApiOrigin
        $env:ADMIN_PASSWORD = $adminPassword
        $env:ADMIN_INVITE_CODE = $adminInvite
        $env:CUSTOMER_INVITE_CODE = $customerInvite

        $python = Join-Path $PSScriptRoot '..\backend\.venv\Scripts\python.exe'
        $acceptanceScript = Join-Path $PSScriptRoot 'check_staging_business_flows.py'
        & $python $acceptanceScript --timeout $Timeout
        $exitCode = $LASTEXITCODE
    }
}
catch {
    Write-Output (
        "secure staging acceptance failed: stage=$stage " +
        "error_type=$($_.Exception.GetType().Name) " +
        "line=$($_.InvocationInfo.ScriptLineNumber)"
    )
    $exitCode = 1
}
finally {
    $env:ADMIN_PASSWORD = $null
    $env:ADMIN_INVITE_CODE = $null
    $env:CUSTOMER_INVITE_CODE = $null
    if ($null -ne $plainBytes) {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
    if ($null -ne $rsa) {
        $rsa.Dispose()
    }
}

exit $exitCode
