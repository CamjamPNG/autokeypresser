$ErrorActionPreference = 'Stop'
$packageArgs = @{
  packageName   = 'autokeypresser'
  fileType      = 'exe'
  url64bit      = 'https://github.com/CamjamPNG/autokeypresser/releases/download/v2.0/AutoKeyPresser-Setup.exe'
  checksum64    = '363335852B5ACAAFBB920DD38A17755C8741C471B1EB3C0B8D6494429CFD4FA5'
  checksumType64 = 'sha256'
  silentArgs    = '/VERYSILENT /NORESTART'
  validExitCodes = @(0)
}
Install-ChocolateyPackage @packageArgs
