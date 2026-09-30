Option Explicit
Dim shell, fs, root, python
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
python = root & "\.venv-studio\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then python = "pythonw.exe"
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\studio.py" & Chr(34), 0, False
