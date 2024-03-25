# Build OpenCRAVAT Windows Installer

## Steps
1. Set [powershell execution policy](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.2) to `RemoteSigned`. Example command is: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned`
2. Check paths in `setup-files.ps1` and run it as Administrator using PowerShell. For production runs `$baseDir` must be `C:\Program Files\OpenCRAVAT`. Also ensure that pip is installing the correct python
3. Open `OpenCRAVAT.iss` using [InnoSetup](https://jrsoftware.org/isinfo.php) and compile the installer
4. Copy the installer from `Output/mysetup.exe` to your desired destination and filename
5. Delete "C:\Program Files\OpenCRAVAT", and install using the installer to test.open