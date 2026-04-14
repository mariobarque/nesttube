# Pi setup guide — run these commands on your Raspberry Pi

# 1. Clone / copy the project
#    (replace with your actual copy method — USB stick, scp, git clone, etc.)
#    scp -r ./NestTube pi@raspberrypi.local:/home/pi/nesttube

# 2. Create a Python virtual environment and install dependencies
cd /home/pi/nesttube
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 3. Copy env file and fill in your YouTube API key
cp .env.example .env
nano .env          # set YOUTUBE_API_KEY and SECRET_KEY; leave ADMIN_PASSCODE_HASH blank
                   # the Admin Panel will let you create the passcode on first visit

# 4. Install the systemd service
sudo cp setup/nesttube.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nesttube
sudo systemctl start nesttube

# 5. Make kiosk script executable
chmod +x setup/start_kiosk.sh

# 6. Auto-start Chromium kiosk on desktop login
#    Create an autostart entry (LXDE / Raspberry Pi OS Desktop):
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/kiosk.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=NestTube Kiosk
Exec=/home/pi/nesttube/setup/start_kiosk.sh
EOF

# 7. (Optional) Set hostname for easy admin access from other devices
sudo hostnamectl set-hostname nesttube
# Then access admin panel from your phone at: http://nesttube.local/admin
