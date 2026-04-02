#!/bin/bash
set -e

SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"

cat << 'EOF' > "$SERVICE_DIR/jarvis.service"
[Unit]
Description=J.A.R.V.I.S. Background Assistant
After=default.target

[Service]
Type=simple
WorkingDirectory=/home/vishesh/My Stuff/BCS-2025-26/Inter-IIT/Google Agent
ExecStart=/bin/bash "/home/vishesh/My Stuff/BCS-2025-26/Inter-IIT/Google Agent/start_jarvis.sh"
Restart=always
RestartSec=5
# Adjust these depending on your audio subsystem (pipewire vs pulseaudio)
Environment="XDG_RUNTIME_DIR=/run/user/%U" "JARVIS_SERVICE_ACTIVE=1"

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable jarvis.service
# Try to start lingering automatically, but warn if it fails
loginctl enable-linger "$USER" || echo "Note: Run 'sudo loginctl enable-linger $USER' if you want it to run without logging in."

echo "J.A.R.V.I.S. service has been created and enabled for the user."
echo "You can start it manually with: systemctl --user start jarvis"
echo "You can view logs with: journalctl --user -u jarvis -f"
