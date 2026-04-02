# J.A.R.V.I.S.

A conversational assistant that integrates with Gmail, Google Drive, Google Calendar, and IITK Webmail using Google APIs, MCP (Model Context Protocol), and the Gemini Live API. J.A.R.V.I.S. acts as an autonomous background daemon, providing real-time voice interactions, managing personal tasks, and maintaining a continuously learning user persona.

## Features

- **Real-Time Voice Assistant**: Powered by the Gemini 3.1 Flash Live API, enabling blazing fast conversational audio input and output.
- **Always-On Background Mode**: Runs persistently as a systemd service, waking up to the keyword "Jarvis" via Vosk framework.
- **Gmail & IITK Mail Integration**: Read, search, filter, and send emails across multiple accounts safely.
- **Google Drive & Calendar**: Retrieve context, download files, and automatically book meetings or deadlines without leaving the voice interface.
- **Living Persona Engine**: Quietly learns your preferences, routines, classes, and communication style by reflecting on past conversations, building a local `user_persona.json`.
- **Short-Term Memory Storage**: Remembers the context of conversations even if the system is restarted or crashes.
- **Local Notepad Toolkit**: Create to-do lists, save contacts, and manage scratchpad notes locally.
- **System Control Tools**: Control Volume, Brightness, and play YouTube audio autonomously.

## Directory Structure

```
.env
.gitignore
live_audio.py         <- Main entry block for Gemini Live API and Voice
mcp_server.py         <- MCP Tool server exposing all APIs to Gemini
notepad.py            <- Service module for the Local Notepad
short_term_memory.py  <- Persistent conversation context memory buffer
user_persona.py       <- Persona extraction and learning module
README.md

services/
	 calender.py
	 drive.py
	 mail.py
	 iitk_mail.py
	 web_search.py

Temporary/
	 downloaded_file0.pdf
```

## Setup

1. **Clone the repository**  
	```sh
	git clone https://github.com/vishesh-kumar-singh/Google-Agent.git
	cd "Google Agent"
	```

2. **Install dependencies**  
	- Python 3.12+
	- Required packages:
	  ```sh
	  pip install -r requirements.txt
	  ```

3. **Google API Credentials**  
	- You must generate your own OAuth credentials to connect J.A.R.V.I.S to your personal Gmail and Calendar.
	- Go to the [Google Cloud Console](https://console.cloud.google.com/).
	- Create a new project, and enable the **Gmail API**, **Google Drive API**, and **Google Calendar API**.
	- Navigate to **APIs & Services > Credentials**, click **Create Credentials > OAuth client ID** (Choose "Desktop app").
	- Download the JSON file and rename it entirely to `credentials.json`.
	- Place your OAuth credentials in the project root as `credentials.json`.
	- On first run, it will open your browser to authenticate; tokens are saved locally in `token.json`.

4. **Environment Variables**
	- Ensure you have a `.env` file with `GEMINI_API_KEY`, `IITK_EMAIL`, etc. setup.

## Usage

Start the main live audio interface:
```sh
python live_audio.py
```
J.A.R.V.I.S. is immediately available in active audio-listening mode.

## Running as a Background Daemon (J.A.R.V.I.S. Mode)

To have J.A.R.V.I.S. run continuously in the background when you turn on your PC, an automated setup script is provided.

1. Ensure the setup script is executable: `chmod +x setup_jarvis_service.sh`
2. Run the deployment script: `./setup_jarvis_service.sh`
3. Manually trigger the service once: `systemctl --user start jarvis`
4. Check activity logs and audio events: `journalctl --user -u jarvis -f`

## Privacy & Local Files

J.A.R.V.I.S maintains learning parameters entirely locally without uploading to unified cloud networks:
- `user_persona.json`: Personal knowledge and preferences learned from interacting.
	- **Dynamic Overwrites**: State vectors (Name, Scheduling patterns, Mood preference) are directly overwritten with corrected up-to-date data.
	- **Cumulative Appends**: Arrays (Hobbies, Music tastes) are naturally appended to, guaranteeing J.A.R.V.I.S handles long-tail data securely without completely dumping historical favorites.
- `jarvis_notes.json`: Your local notes and to-dos.
- `conversation_context.json`: Short term memory logs.

## Current Status

The application is continually evolving into a true, ambient J.A.R.V.I.S ecosystem.
