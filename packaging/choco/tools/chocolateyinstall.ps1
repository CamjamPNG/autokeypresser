$ErrorActionPreference = 'Stop'
$packageArgs = @{
  packageName   = 'autokeypresser'
  fileType      = 'exe'
  url64bit      = 'https://github.com/CamjamPNG/autokeypresser/releases/download/v1.5/AutoKeyPresser-Setup.exe'
  checksum64    = 'REPLACE_WITH_RELEASE_SHA256'
  checksumType64 = 'sha256'
  silentArgs    = '/VERYSILENT /NORESTART'
  validExitCodes = @(0)
}
Install-ChocolateyPackage @packageArgs
