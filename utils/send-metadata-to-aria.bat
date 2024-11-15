@echo off
::conda activate fandango
echo.
echo #############################################################
echo #################### Welcome to Fandango! ###################
echo #############################################################
echo.
echo Let's specify the project parameters to generate metadata and send it to ARIA API...
echo.


:: Enter "Project name"
echo _____________________________________
echo.
echo - Project name:
echo       This name will be only stored as a reference in fandango database, it can be any name, for instance, original project name or project id.
echo.
:projectname
set /p pname=  Please, enter project name: 
if "%pname%"=="" (
    echo    Empty project name was provided, please enter a valid project name. Examples: covid-19-2022, 124532
    goto projectname
)
echo.
echo -----------------^> Project name, %pname%


:: Enter "Project id from LOGS"
echo _____________________________________
echo.
echo - LOGS id: 
echo       Project id from LOGS.
echo.
:logsid
set /p logs= Please, enter project id from LOGS: 
if "%logs%"=="" (
    echo    Empty project id was provided, please enter a valid project id from LOGS. Examples: 227, 129
    goto logsid
)
echo.
echo  -----------------^> Project id from LOGS, %logs%


:: Enter "Library excel path"
echo _____________________________________
echo.
echo - Library excel path: 
echo         Path where is stored the excel file with library information for this project.
echo.
:libraryexcelpath
set /p excelpath= Please, enter library excel path: 
if "%excelpath%"=="" (
    echo    Empty excel path id was provided, please enter a valid library excel path. Example: C:\data\covid19_2024\library.xlsx
    goto libraryexcelpath
)
echo.
echo -----------------^> Library excel path, %excelpath%


:: Enter "ARIA visit id"
echo _____________________________________
echo.
echo - ARIA visit id: 
echo         Visit id created by ARIA to which this project data acquisition is associated. You can find this information in the ARIA platform.
echo.
:ariavisitid
set /p visitid= Please, enter ARIA visit id: 
if "%visitid%"=="" (
    echo    Empty ARIA visit id was provided, please enter a valid ARIA visit id. Example: 32
    goto ariavisitid
)
echo.
echo -----------------^> ARIA visit id, %visitid%

echo _____________________________________
echo.
echo Entering info ...
echo.
::timeout /t 5
ping 127.0.0.1 -n 1 >nul

:: Review info
:review
echo #############################################################
echo Please review the entered information:
echo Project name: %pname%
echo LOGS id: %logs%
echo Library excel path: %excelpath%
echo ARIA visit id: %visitid%
echo #############################################################
echo.
echo Enter C to continue with these details.
echo Enter R to re-enter the information.
echo.

:choice
set /p choice=Your choice (C to continue, R to re-enter): 
if /i "%choice%"=="R" goto reenter
if /i "%choice%"=="C" goto continue
echo Invalid choice. Please enter C or R.
goto choice


:: Reenter info
:reenter
echo.
echo Re-entering the information...
echo.
:reenterp
set /p pname= Please, enter project name: 
if "%pname%"=="" (
    echo    Empty project name was provided, please enter a valid project name. Examples: covid-19-2022, 124532
    goto reenterp
)
:reenterl
set /p logs= Please, enter project id from LOGS: 
if "%logs%"=="" (
    echo    Empty project id was provided, please enter a valid project id from LOGS. Examples: 227, 129
    goto reenterl
)
:reentere
set /p excelpath= Please, enter library excel path: 
if "%excelpath%"=="" (
    echo    Empty excel path id was provided, please enter a valid library excel path. Example: C:\data\covid19_2024\library.xlsx
    goto reentere
)
:reenterv
set /p visitid= Please, enter ARIA visit id: 
if "%visitid%"=="" (
    echo    Empty ARIA visit id was provided, please enter a valid ARIA visit id. Example: 32
    goto reenterv
)
echo _____________________________________
echo.
echo Entering info ...
ping 127.0.0.1 -n 1 >nul
echo.
goto review

:: Continue with fandango commands
:continue
echo.
echo Continuing with the script...
echo.
ping 127.0.0.1 -n 1 >nul

:: create-project
echo Creating entry in fandango database for project %pname% ... 
fandango create-project --name %pname% > send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while creating entry in fandango database for project. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)

:: link-project
echo Linking project %pname% to the fandango-nmr-guf plugin ...
fandango link-project --name %pname% --plugin fandanGO-nmr-guf >> send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while linking project to fandango-nmr-guf plugin. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)


:: action generate-experiment-metadata
echo Generating experiment metadata from LOGS using LOGS id %logs% ...
fandango execute --action generate-experiment-metadata --name %pname% --logs-project-id %logs% >> send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while generating experiment metadata from LOGS. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)


:: action generate-library-from-excel
echo Generating library metadata JSON from excel file %excelpath% ...
fandango execute --action generate-library-from-excel --name %pname% --input %excelpath% >> send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while generating library metadata JSON from excel file. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)

:: action generate-library-metadata
echo Filtering experiment metadata with library metadata ...
fandango execute --action generate-library-metadata --name %pname% >> send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while filtering exmperiment metadata with library metadata. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)


:: action send-metadata
echo Sending final metadata files to ARIA API using visit id %visitid%
fandango execute --action send-metadata --name %pname% --visit-id %visitid% >> send-metadata-output.log 2>&1
if not %ERRORLEVEL% equ 0 (
    echo Error while sending metadata to ARIA API. Exiting with error code %ERRORLEVEL%...
    echo See send-metadata-output.log file for more details.
    exit /b %ERRORLEVEL%
)


echo All commands completed successfully!
echo Press Enter to exit.
pause