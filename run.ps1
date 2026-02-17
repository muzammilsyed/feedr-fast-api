# Run backend - use 0.0.0.0 so physical devices on the same network can connect
# http://localhost:8000 works from this computer
# http://YOUR_IP:8000 works from your phone (e.g. http://192.168.0.27:8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
