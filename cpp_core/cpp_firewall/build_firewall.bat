@echo off
echo ==========================================
echo  Building C++ Layer-7 Firewall (DLL)
echo ==========================================
g++ -std=c++17 -O3 -Wall -shared hev_idps.cpp -o firewall.dll
if %errorlevel% neq 0 (
    echo [ERROR] Build failed! Check compiler.
) else (
    echo [SUCCESS] Build complete! firewall.dll is ready.
)
