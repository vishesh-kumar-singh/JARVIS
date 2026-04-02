"""
MCP (Model Context Protocol) Server for J.A.R.V.I.S.

This file defines the suite of tools exposed to the Gemini 3.1 Flash Live API.
By wrapping generic Google APIs (Gmail, Calendar, Drive), System Controls (volume, 
brightness, browser), and local modules (Notepad, IITK Mail) into `FastMCP` tools, 
we allow the LLM to autonomously call these functions during live audio conversations.

Note: IO-bound blocking functions are wrapped in `asyncio.to_thread` to prevent 
starving the live audio event loop, preventing audio stutter and timeouts.
"""
from mcp.server.fastmcp import FastMCP
from typing import List
from OAuth import Authenticate
from services.calender import GoogleCalendar, parse_datetime_to_iso
from services.mail import Gmail
from services.iitk_mail import IITKMail
from services.drive import GoogleDrive
from services.web_search import WebSearch, scrape_page
from notepad import Notepad
from datetime import datetime, timedelta
import pytz
import asyncio

# Initialize Google Services
creds = Authenticate()
mail_service = Gmail(creds)
iitk_mail_service = IITKMail()
drive_service = GoogleDrive(creds)
calendar_service = GoogleCalendar(creds)
notepad_service = Notepad()

# Initialize MCP Server
mcp = FastMCP("GoogleAgentTools")

@mcp.tool()
async def gmail_send(to: str, subject: str, body: str) -> str:
    """
    CRITICAL RESTRICTION: NEVER CALL THIS TOOL WITHOUT EXPLICIT VERBAL PERMISSION FROM THE USER FIRST.
    If you are autonomously checking emails, DO NOT REPLY TO THEM.
    Send an email using Gmail
    """
    return str(await asyncio.to_thread(mail_service.send_mail, to, subject, body))

@mcp.tool()
async def gmail_search(query: str, results: int = 5) -> str:
    """Search Gmail inbox and return semantically relevant emails"""
    return str(await asyncio.to_thread(mail_service.search, query, results=results, rag=True))

@mcp.tool()
async def gmail_unread(results: int = 5) -> str:
    """Fetch unread Gmail messages"""
    return str(await asyncio.to_thread(mail_service.unread, max_results=results))

@mcp.tool()
async def iitk_mail_send(to: str, subject: str, body: str) -> str:
    """
    CRITICAL RESTRICTION: NEVER CALL THIS TOOL WITHOUT EXPLICIT VERBAL PERMISSION FROM THE USER FIRST.
    If you are autonomously checking emails, DO NOT REPLY TO THEM.
    Send an email using IITK Webmail (IMAP/SMTP)
    """
    return str(await asyncio.to_thread(iitk_mail_service.send_mail, to, subject, body))

@mcp.tool()
async def iitk_mail_unread(results: int = 5) -> str:
    """Fetch recent unread IITK Webmail messages (last 48 hours only)"""
    return str(await asyncio.to_thread(iitk_mail_service.unread, max_results=results))

@mcp.tool()
async def iitk_mail_search(query: str, results: int = 5) -> str:
    """Search the ENTIRE IITK inbox (read + unread) for emails matching a keyword query. Use this when the user asks to find or search for specific emails."""
    return str(await asyncio.to_thread(iitk_mail_service.search, query, max_results=results))

@mcp.tool()
async def drive_search(query: str, keywords: List[str], max_results: int = 5) -> str:
    """Search Google Drive for files related to list of keywords and retrieve content through RAG for a given query"""
    return str(await asyncio.to_thread(drive_service.get_results, query, keywords, max_results=max_results))

@mcp.tool()
async def calendar_search(query: str, max_results: int = 5) -> str:
    """Search Google Calendar events for a given query"""
    return str(await asyncio.to_thread(calendar_service.search_events, query, max_results=max_results))

@mcp.tool()
async def calendar_upcoming(max_results: int = 10) -> str:
    """Get upcoming events"""
    return str(await asyncio.to_thread(calendar_service.upcoming_events, max_results=max_results))

@mcp.tool()
async def calendar_create(summary: str, start: str, end: str = None, timezone: str = "Asia/Kolkata") -> str:
    """
    Create a new calendar event using natural language dates.
    
    start: natural language start time, e.g., "8th Sep 2025 at 23:30"
    end: optional natural language end time; if not provided, defaults to 1 hour after start
    timezone: e.g., "Asia/Kolkata"
    """
    # Parse start datetime to ISO
    start_iso = parse_datetime_to_iso(start, timezone)

    # Parse end datetime
    if end:
        end_iso = parse_datetime_to_iso(end, timezone)
    else:
        # Default: 1 hour after start
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = start_dt + timedelta(hours=1)
        end_iso = end_dt.isoformat()

    return str(await asyncio.to_thread(calendar_service.create_event, summary, start_iso, end_iso, timezone))

@mcp.tool()
async def calendar_delete(summary: str, days_ahead: int = 30) -> str:
    """Delete an event by summary text (first match)"""
    return str(await asyncio.to_thread(calendar_service.delete_event, summary, days_ahead=days_ahead))

@mcp.tool()
async def note_add(content: str, category: str = "general") -> str:
    """Save a note, todo item, phone number, or reminder. Category can be: general, todo, contact, reminder, shopping, idea."""
    return str(await asyncio.to_thread(notepad_service.add_note, content, category))

@mcp.tool()
async def note_list(category: str = "") -> str:
    """List all saved notes, optionally filtered by category (e.g. todo, contact, reminder)."""
    cat = category if category else None
    return str(await asyncio.to_thread(notepad_service.list_notes, cat))

@mcp.tool()
async def note_search(query: str) -> str:
    """Search through saved notes by keyword."""
    return str(await asyncio.to_thread(notepad_service.search_notes, query))

@mcp.tool()
async def note_done(note_id: int) -> str:
    """Mark a todo/note as completed by its ID number."""
    return str(await asyncio.to_thread(notepad_service.mark_done, note_id))

@mcp.tool()
async def note_delete(note_id: int) -> str:
    """Delete a note by its ID number."""
    return str(await asyncio.to_thread(notepad_service.delete_note, note_id))

@mcp.tool()
async def web_search(query: str) -> str:
    """Performs websearch and returns top 5 page title, content and url"""
    return str(await asyncio.to_thread(WebSearch, query=query))

@mcp.tool()
async def scrapper(url: str) -> str:
    """Scrapes the whole webpage for a given url, can be used with a web search tool to get url then scrape whole page if required"""
    return str(await asyncio.to_thread(scrape_page, url=url))

@mcp.tool()
async def open_browser(url: str) -> str:
    """Open a URL in the default web browser (useful for playing YouTube songs, opening links, etc.)"""
    import webbrowser
    import subprocess
    import sys
    import os
    import pwd
    import time
    
    # 1. Build a strict graphical environment for systemd background services
    env = os.environ.copy()
    if sys.platform.startswith('linux'):
        try:
            uid = os.getuid()
            user_name = pwd.getpwuid(uid).pw_name
            
            # XDG_RUNTIME_DIR is strictly required for modern browsers/Wayland/DBUS
            if 'XDG_RUNTIME_DIR' not in env:
                env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
            if 'DISPLAY' not in env:
                env['DISPLAY'] = ':0'
            if 'DBUS_SESSION_BUS_ADDRESS' not in env:
                env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path=/run/user/{uid}/bus'
            if 'XAUTHORITY' not in env:
                env['XAUTHORITY'] = f'/home/{user_name}/.Xauthority'
            if 'WAYLAND_DISPLAY' not in env:
                env['WAYLAND_DISPLAY'] = 'wayland-0'
        except Exception:
            pass

    try:
        if sys.platform.startswith('linux'):
            brave_commands = [
                ['brave-browser', url],
                ['brave', url],
                ['flatpak', 'run', 'com.brave.Browser', url],
                ['snap', 'run', 'brave', url]
            ]
            
            for cmd in brave_commands:
                try:
                    # Pass the explicit graphical environment to the subprocess
                    process = subprocess.Popen(
                        cmd, 
                        env=env,
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                    
                    # Wait a tiny fraction of a second to ensure it didn't immediately crash due to display issues
                    time.sleep(0.3)
                    if process.poll() is not None and process.returncode != 0:
                        continue # Process crashed instantly, try the next command in the list
                        
                    return f"Opened {url} in Brave browser."
                except FileNotFoundError:
                    continue # Command not found, try the next one
                    
            raise Exception("All Brave commands either failed or crashed on launch.")
            
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-a', 'Brave Browser', url])
            return f"Opened {url} in browser."
            
        elif sys.platform == 'win32':
            subprocess.Popen(['cmd', '/c', 'start', 'brave', url])
            return f"Opened {url} in browser."
            
    except Exception as e:
        print(f"Specific browser launch failed: {e}. Falling back to default.")
        
    # Fallback to builtin webbrowser
    os.environ.update(env) # Update global env just in case
    success = await asyncio.to_thread(webbrowser.open, url)
    if success:
        return f"Opened {url} in default browser."
        
    return f"Failed to open {url} in browser."


@mcp.tool()
async def play_youtube_video(video_topic: str) -> str:
    """Search for any video or song on YouTube and automatically play the top result in the browser."""
    import urllib.request
    import urllib.parse
    import re
    import webbrowser
    import subprocess
    import sys
    import os
    import pwd
    import time

    try:
        # 1. FIX YOUTUBE SEARCH: Use headers and a better Regex for modern YouTube
        query_string = urllib.parse.urlencode({"search_query": video_topic})
        req = urllib.request.Request(
            "https://www.youtube.com/results?" + query_string,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        format_url = urllib.request.urlopen(req)
        html_content = format_url.read().decode()
        
        # YouTube hides IDs in ytInitialData now, not in standard watch?v= hrefs
        search_results = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html_content)
        
        # Remove duplicates while keeping order
        unique_results = list(dict.fromkeys(search_results))
        
        if not unique_results:
            return f"Could not find any YouTube videos for '{video_topic}'."
            
        url = "https://www.youtube.com/watch?v=" + unique_results[0]
        
        # 2. Build the strict graphical environment
        env = os.environ.copy()
        if sys.platform.startswith('linux'):
            try:
                uid = os.getuid()
                user_name = pwd.getpwuid(uid).pw_name
                
                if 'XDG_RUNTIME_DIR' not in env:
                    env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
                if 'DISPLAY' not in env:
                    env['DISPLAY'] = ':0'
                if 'DBUS_SESSION_BUS_ADDRESS' not in env:
                    env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path=/run/user/{uid}/bus'
                if 'XAUTHORITY' not in env:
                    env['XAUTHORITY'] = f'/home/{user_name}/.Xauthority'
                if 'WAYLAND_DISPLAY' not in env:
                    env['WAYLAND_DISPLAY'] = 'wayland-0'
            except Exception:
                pass

        try:
            if sys.platform.startswith('linux'):
                brave_commands = [
                    ['brave-browser', url],
                    ['brave', url],
                    ['flatpak', 'run', 'com.brave.Browser', url],
                    ['snap', 'run', 'brave', url]
                ]
                
                for cmd in brave_commands:
                    try:
                        process = subprocess.Popen(
                            cmd, 
                            env=env,
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL
                        )
                        
                        # Wait a tiny fraction of a second to ensure it doesn't crash instantly
                        time.sleep(0.3)
                        if process.poll() is not None and process.returncode != 0:
                            continue 
                            
                        return f"Playing '{video_topic}' on Brave: {url}"
                    except FileNotFoundError:
                        continue
                        
                raise Exception("All Brave executables failed.")
                
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', '-a', 'Brave Browser', url])
                return f"Playing '{video_topic}' on Brave: {url}"
                
            elif sys.platform == 'win32':
                subprocess.Popen(['cmd', '/c', 'start', 'brave', url])
                return f"Playing '{video_topic}' on Brave: {url}"
                
        except Exception as e:
            print(f"Specific browser launch failed: {e}. Falling back to default.")

        os.environ.update(env)
        await asyncio.to_thread(webbrowser.open, url)
        return f"Playing '{video_topic}' on default YouTube: {url}"
        
    except Exception as e:
        return f"Failed to play '{video_topic}' on YouTube. Error: {e}"

@mcp.tool()
async def system_command(command: str) -> str:
    """Execute a bash system command (useful for volume control, shutdown, reboot, running scripts, opening apps)"""
    import subprocess
    try:
        result = await asyncio.to_thread(
            subprocess.run, 
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        out = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        if not out:
            out = "No output."
        return f"Command executed (Return code: {result.returncode}). Output:\n{out[:2000]}"
    except Exception as e:
        return f"Error executing command: {e}"

if __name__ == "__main__":
    mcp.run()
