# Start the DigiTrail FAQ assistant with the project virtualenv.
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m streamlit run src\app.py --server.port 8501
