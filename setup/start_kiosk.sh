#!/usr/bin/env bash
# Launches Chromium in kiosk mode pointed at the local NestTube server.
# Typically called from ~/.config/autostart/kiosk.desktop (LXDE)
# or from a systemd service that runs after nesttube.service.

# Wait for the backend to be ready (up to 30 s)
for i in $(seq 1 30); do
    curl -s http://localhost:8000/ > /dev/null && break
    sleep 1
done

# Disable screen saver / screen blanking
xset s off
xset s noblank
xset -dpms

# Unclutter hides the mouse cursor after 1 s of inactivity
unclutter -idle 1 &

chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --no-first-run \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required \
    "http://localhost:8000"
