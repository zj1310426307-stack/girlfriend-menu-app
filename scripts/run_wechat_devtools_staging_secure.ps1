param(
    [switch]$HandshakeOnly,
    [switch]$ManualEntry,
    [switch]$PrepareRotation
)

$ErrorActionPreference = 'Stop'
$rsa = $null
$plainBytes = $null
$secureInvite = $null
$inviteBstr = [IntPtr]::Zero
$generatedInviteBytes = $null
$rotationClipboardOwned = $false
$exitCode = 1
$stage = 'initialize'

try {
    if ($ManualEntry -and $PrepareRotation) {
        throw [System.ArgumentException]::new('ManualEntry and PrepareRotation are mutually exclusive')
    }
    $stage = 'verify_staging_dist'
    $miniprogramRoot = Join-Path $PSScriptRoot '..\miniprogram'
    $stagingEnvPath = Join-Path $miniprogramRoot '.env.staging'
    $productionEnvPath = Join-Path $miniprogramRoot '.env.production'
    $distRoot = Join-Path $miniprogramRoot 'dist'
    $appJson = Join-Path $distRoot 'app.json'
    if (-not (Test-Path -LiteralPath $appJson -PathType Leaf)) {
        throw [System.InvalidOperationException]::new('staging dist is missing app.json')
    }

    $stagingOriginLine = Get-Content -LiteralPath $stagingEnvPath |
        Where-Object { $_ -match '^TARO_APP_API_ORIGIN=' } |
        Select-Object -First 1
    $productionOriginLine = Get-Content -LiteralPath $productionEnvPath |
        Where-Object { $_ -match '^TARO_APP_API_ORIGIN=' } |
        Select-Object -First 1
    $stagingOrigin = [string]($stagingOriginLine -replace '^TARO_APP_API_ORIGIN=', '')
    $productionOrigin = [string]($productionOriginLine -replace '^TARO_APP_API_ORIGIN=', '')
    if (
        [string]::IsNullOrWhiteSpace($stagingOrigin) -or
        -not $stagingOrigin.StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase) -or
        $stagingOrigin -ceq $productionOrigin
    ) {
        throw [System.InvalidOperationException]::new('staging API origin is unsafe')
    }
    $compiledOriginFound = Get-ChildItem -LiteralPath $distRoot -Recurse -File -Filter '*.js' |
        Select-String -SimpleMatch $stagingOrigin -Quiet
    if (-not $compiledOriginFound) {
        throw [System.InvalidOperationException]::new('compiled dist does not contain the staging API origin')
    }

    if ($PrepareRotation) {
        $stage = 'generate_rotation_invite'
        $generatedInviteBytes = [byte[]]::new(24)
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($generatedInviteBytes)
        $encodedInvite = [Convert]::ToBase64String($generatedInviteBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
        $customerInvite = "stgC_$encodedInvite"
        Set-Clipboard -Value $customerInvite
        $rotationClipboardOwned = $true
        Write-Output 'A new staging customer invite is copied to the clipboard; its value is hidden.'
        [void](Read-Host 'Paste it into Render, save/deploy, wait for Live, then press Enter')
        $currentClipboard = Get-Clipboard -Raw -ErrorAction SilentlyContinue
        if ([string]$currentClipboard -ceq $customerInvite) {
            Set-Clipboard -Value ''
            $rotationClipboardOwned = $false
        }
    }
    elseif ($ManualEntry) {
        $stage = 'receive_hidden_invite'
        $secureInvite = Read-Host 'Paste the current staging customer invite (input hidden)' -AsSecureString
        $inviteBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureInvite)
        $customerInvite = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($inviteBstr)
    }
    else {
        $stage = 'create_key'
        $rsa = [System.Security.Cryptography.RSACryptoServiceProvider]::new(2048)
        $publicParameters = $rsa.ExportParameters($false)
        $publicModulus = [Convert]::ToBase64String($publicParameters.Modulus)
        $publicExponent = [Convert]::ToBase64String($publicParameters.Exponent)
        Write-Output "WECHAT_SMOKE_PUBLIC_KEY=$publicModulus`:$publicExponent"
        $stage = 'receive_ciphertext'

        $encryptedLine = [Console]::ReadLine()
        if ([string]::IsNullOrWhiteSpace($encryptedLine) -or $encryptedLine.Length -gt 2048) {
            throw [System.InvalidOperationException]::new('encrypted invite input is missing or oversized')
        }

        $cipherBytes = [Convert]::FromBase64String($encryptedLine)
        $stage = 'decrypt'
        $plainBytes = $rsa.Decrypt($cipherBytes, $true)
        $credentialJson = [System.Text.Encoding]::UTF8.GetString($plainBytes)
        $credentials = $credentialJson | ConvertFrom-Json
        $customerInvite = [string]$credentials.customer_invite_code
    }
    $stage = 'validate_invite'
    if ([string]::IsNullOrWhiteSpace($customerInvite) -or $customerInvite.Length -gt 200) {
        throw [System.InvalidOperationException]::new('decrypted staging invite is invalid')
    }

    if ($HandshakeOnly) {
        Write-Output 'secure WeChat smoke handoff: PASS'
        $exitCode = 0
    }
    else {
        $env:WECHAT_SMOKE_CUSTOMER_INVITE_CODE = $customerInvite
        Push-Location $miniprogramRoot
        try {
            & npm.cmd run test:smoke
            $exitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
}
catch {
    Write-Output (
        "secure WeChat staging smoke failed: stage=$stage " +
        "error_type=$($_.Exception.GetType().Name) " +
        "line=$($_.InvocationInfo.ScriptLineNumber)"
    )
    $exitCode = 1
}
finally {
    $env:WECHAT_SMOKE_CUSTOMER_INVITE_CODE = $null
    if ($rotationClipboardOwned) {
        $currentClipboard = Get-Clipboard -Raw -ErrorAction SilentlyContinue
        if ([string]$currentClipboard -ceq $customerInvite) {
            Set-Clipboard -Value ''
        }
    }
    if ($null -ne $generatedInviteBytes) {
        [Array]::Clear($generatedInviteBytes, 0, $generatedInviteBytes.Length)
    }
    if ($inviteBstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($inviteBstr)
    }
    if ($null -ne $secureInvite) {
        $secureInvite.Dispose()
    }
    if ($null -ne $plainBytes) {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
    if ($null -ne $rsa) {
        $rsa.Dispose()
    }
}

exit $exitCode
