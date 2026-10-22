vbs_code = '''CreateObject("WScript.Shell").Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\\Users\\w\\.openclaw\\watchdog.ps1""", 0, False
'''
with open(r'C:\Users\w\.openclaw\watchdog.vbs', 'w', encoding='utf-8') as f:
    f.write(vbs_code)
print("SUCCESS: watchdog.vbs created.")
