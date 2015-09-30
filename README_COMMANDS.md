# Command Line Usage

### Windows
```subl --command "sbs_compare_files {\"A\":\"file1\", \"B\":\"file2\"}"```  
Requires additional escaping of backslashes in file paths.

**compare.bat**  
_Usage: compare.bat file1.txt file2.txt_
```
set file1=%~1
set file1=%file1:\=\\%
set file2=%~2
set file2=%file2:\=\\%
subl --command "sbs_compare_files {\"A\":\"%file1%\", \"B\":\"%file2%\"}"
```

---

### Linux/OSX
```subl --command 'sbs_compare_files {"A":"file1", "B":"file2"}'```  
Untested on OSX, but should be the same as Linux.

**compare.sh**  
_Usage: compare.sh file1.txt file2.txt_
```
#!/bin/sh
eval subl3 --command \'sbs_compare_files {\"A\":\"$1\", \"B\":\"$2\"}\'
```