# Command Line Usage

**Note:** Relative paths are not recommended as it is unclear what the current working directory might be especially when Sublime Text is already running. Use absolute paths for better transparency and reliability.

### Windows
```subl --command "sbs_compare_files {\"A\":\"file1\", \"B\":\"file2\"}"```  
Requires additional escaping of backslashes in file paths.

**compare.ps1**  
_Usage: .\compare.ps1 file1.txt file2.txt_
```
param (
    [string]$File1,
    [string]$File2
)

$AbsoluteFile1 = (Resolve-Path -Path $File1).Path
$AbsoluteFile2 = (Resolve-Path -Path $File2).Path

subl --command "sbs_compare_files {\"A\":\"$AbsoluteFile1\", \"B\":\"$AbsoluteFile2\"}"
```

**compare.bat**  
_Usage: compare.bat file1.txt file2.txt_
```
set file1=%~1
for %%I in (%file1%) do set file1=%%~fI
set file1=%file1:\=\\%
set file2=%~2
for %%I in (%file2%) do set file2=%%~fI
set file2=%file2:\=\\%
subl --command "sbs_compare_files {\"A\":\"%file1%\", \"B\":\"%file2%\"}"
```

---

### Linux/OSX
```subl --command "sbs_compare_files {\"A\":\"file1\", \"B\":\"file2\"}"```  
Untested on OSX, but should be the same as Linux.

**compare.sh**  
_Usage: compare.sh file1.txt file2.txt_
```
#!/bin/sh
file1=$(readlink -f "$1")
file2=$(readlink -f "$2")
subl --command "sbs_compare_files {\"A\":\"$file1\", \"B\":\"$file2\"}"
```
