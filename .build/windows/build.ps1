param(
    [Parameter(Mandatory=$true,
        HelpMessage="Where to find open-cravat. A pypi name or path to repositry"
    )]
    [string]$PipTarget,
    [Parameter(Mandatory=$true,
        HelpMessage="The version to embed in the built package."
    )]
    [string]$CravatVersion,
    [Parameter(Mandatory=$false,
        HelpMessage="Remove installation target directory before running"
        )]
        [switch]$Clean,
    [Parameter(Mandatory=$false,
        HelpMessage="Force download of python"
        )]
        [switch]$ForceDownload,
    [Parameter(Mandatory=$false,
        HelpMessage="Build with InnoSetup"
        )]
        [switch]$Build
    )

# Change to "C:\Program Files\OpenCRAVAT" for prod run
$baseDir="C:\Program Files\OpenCRAVAT"

# To update python version, get new url from https://www.python.org/downloads/windows/
# You will also have to change other hardcoded paths that include the python version
$pyEmbedUrl="https://www.python.org/ftp/python/3.10.8/python-3.10.8-embed-amd64.zip"
$pyEmbedArchive="python.zip"
$getPipUrl="https://bootstrap.pypa.io/get-pip.py"
$getPipPath="get-pip.py"

$pythonDir="$baseDir\python"
$_pthPath="$pythonDir\python310._pth"
$binDir="$baseDir\bin"

$batPath="$PSScriptRoot\OpenCRAVAT.bat"
$icoPath="$PSScriptRoot\logo.ico"

$ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$issPath="./OpenCRAVAT.iss"

if (Test-Path -Path $baseDir) {
    if ($Clean) {
        Remove-Item -Recurse $baseDir
    } else {
        Write-Output "Delete directory $baseDir to continue. Or use -Clean"
        Exit
    }
}

if ($ForceDownload -Or -Not( Test-Path -Path $pyEmbedArchive -PathType Leaf)) {
    Invoke-WebRequest -Uri $pyEmbedUrl -OutFile $pyEmbedArchive
}
if ($ForceDownload -Or -Not( Test-Path -Path $getPipPath -PathType Leaf)) {
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath
}

# Extract python
New-Item -ItemType Directory -Path $baseDir
Expand-Archive -Path $pyEmbedArchive -DestinationPath $pythonDir

# https://dev.to/fpim/setting-up-python-s-windows-embeddable-distribution-properly-1081
# https://mcpmag.com/articles/2018/08/08/replace-text-with-powershell.aspx
((Get-Content -Path $_pthPath -Raw) -Replace '#import','import') | Set-Content -Path $_pthPath

# Install pip
& $pythonDir\python.exe $getPipPath --no-warn-script-location

# Install oc
& $pythonDir\python.exe -m pip install $PipTarget --no-warn-script-location --upgrade

# Make bin, add executables
New-Item -ItemType Directory -Path $binDir
Copy-Item -Path $pythonDir\Scripts\oc.exe -Destination $binDir
Copy-Item -Path $batPath -Destination $binDir

if (-Not(Test-Path -Path $binDir/oc.exe -PathType Leaf)) {
    Write-Output "FAILED: No oc.exe in $binDir"
    Exit
}

# Copy icon
Copy-Item -Path $icoPath -Destination $baseDir

Write-Output ""
Write-Output "Finished setup for version $CravatVersion"

if ($Build) {
    $installerName="OpenCRAVAT-$CravatVersion"
    & $ISCC /Qp /F$installerName /DVersion=$CravatVersion $issPath
    Write-Output ""
    Write-Output "Installer created"
    Write-Output "$pwd\Output\$installerName.exe"
}
