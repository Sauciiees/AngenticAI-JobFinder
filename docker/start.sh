#!/bin/sh
# Starts a virtual screen for the visible browser windows (job-board sign-in, auto-apply, CAPTCHAs),
# shares it as a web page through noVNC, then runs the API and web app.
set -e

# 1. Virtual display that Playwright's non-headless Chromium draws on
Xvfb :99 -screen 0 1366x1000x24 -nolisten tcp &
sleep 1

# 2. VNC server for that display, reachable only from inside the container
if [ -n "$VNC_PASSWORD" ]; then
  x11vnc -display :99 -forever -shared -localhost -rfbport 5900 -passwd "$VNC_PASSWORD" -quiet &
else
  x11vnc -display :99 -forever -shared -localhost -rfbport 5900 -nopw -quiet &
fi

# 3. noVNC: the screen as a web page on port 6080 (docker-compose publishes it on 127.0.0.1 only)
websockify --web /usr/share/novnc 6080 localhost:5900 >/dev/null 2>&1 &

# 4. The app
exec uvicorn server:app --host 0.0.0.0 --port 8000
