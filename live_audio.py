"""
J.A.R.V.I.S. Live Audio / MCP Interface.

Core orchestrator for the background systemd service.
This script sets up a persistent WebSocket connection with the Gemini 3.1 Flash Live API.
Key Components:
 - Asynchronous audio streaming (PyAudio).
 - Integrated wake-word detection using Vosk.
 - Dynamic tool binding via Model Context Protocol (MCP Server).
 - Parallel background tasks for email triaging & Persona extraction.
"""
import asyncio
import sys
import os
import pyaudio
import dotenv
import json
from concurrent.futures import ThreadPoolExecutor

dotenv.load_dotenv()

from google import genai
from google.genai import types

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from mem0 import MemoryClient
from short_term_memory import ShortTermMemory
from user_persona import UserPersona

# --- AUDIO SETTINGS (Gemini Live requires 16kHz PCM) ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_RATE = 16000       # microphone input rate
RECEIVE_RATE = 24000    # Gemini Live outputs 24kHz
CHUNK = 1024

MODEL = "gemini-3.1-flash-live-preview"

# Lazy-initialized mem0 client (initialized inside main after dotenv loads)
mem0 = None

# Persistent short-term memory (conversation context that survives crashes)
stm = ShortTermMemory()

# Living user profile (personality, preferences, habits — learned over time)
persona = UserPersona()

def save_memory(fact: str) -> str:
    """Save an important fact, user preference, or contact email into long-term memory."""
    try:
        result = mem0.add(
            [{"role": "user", "content": "Remember: " + fact}],
            user_id="jarvis_user",
            output_format='v1.1'
        )
        return f"Saved. {len(result.get('results', []))} memories stored."
    except Exception as e:
        return f"Failed to save: {e}"

def search_memory(query: str) -> str:
    """Search long-term memory for contacts, facts, or user preferences."""
    try:
        memories = mem0.search(query, user_id="jarvis_user", output_format='v1.1')
        results = memories.get('results', [])
        if not results:
            return "No matching memories found."
        return ' | '.join([m["memory"] for m in results])
    except Exception as e:
        return f"Error searching memory: {e}"

def map_mcp_to_genai_declarations(mcp_tools):
    """Converts Langchain BaseTools into google-genai FunctionDeclarations."""
    declarations = []
    tools_dict = {}
    for tool in mcp_tools:
        props = {}
        for k, v in tool.args.items():
            prop_type = v.get("type", "string").upper()
            prop_dict = {"type": prop_type, "description": v.get("description", "")}
            if prop_type == "ARRAY":
                item_type = v.get("items", {}).get("type", "string").upper()
                prop_dict["items"] = {"type": item_type}
            props[k] = prop_dict

        declarations.append(types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters={"type": "OBJECT", "properties": props} if props else None
        ))
        tools_dict[tool.name] = tool
    return declarations, tools_dict

async def handle_tool_call(fc, tools_dict, jarvis_active=None):
    """Execute a single function call and return the result string."""
    name = fc.name
    args = dict(fc.args) if fc.args else {}
    print(f"\n[Tool: {name}({args})]", end="", flush=True)
    if name == "go_to_standby":
        if jarvis_active:
            jarvis_active.clear()
            print("\n[J.A.R.V.I.S. Returning to Standby via Tool]", file=sys.stderr)
            # Trigger persona reflection in background when going to standby
            conversation_log = stm.get_context(max_entries=30)
            if conversation_log:
                asyncio.get_event_loop().run_in_executor(
                    None, persona.reflect, conversation_log
                )
        result = "Entering standby. Say my name to wake me up again."
    elif name == "save_memory":
        result = await asyncio.to_thread(save_memory, **args)
    elif name == "search_memory":
        result = await asyncio.to_thread(search_memory, **args)
    elif name in tools_dict:
        try:
            result = await tools_dict[name].ainvoke(args)
        except Exception as e:
            result = f"Error executing tool {name}: {e}"
    else:
        result = f"Unknown tool: {name}"
    print(f" → {str(result)[:80]}", flush=True)
    return name, result

async def main():
    global mem0
    # Hardcoded to 'audio' for background JARVIS service
    mode = "audio"

    # Initialize Vosk
    recognizer = None
    if os.path.exists("vosk_model"):
        import vosk
        vosk.SetLogLevel(-1) # Hide verbose Vosk logs
        model = vosk.Model("vosk_model")
        recognizer = vosk.KaldiRecognizer(model, SEND_RATE)
        print("Vosk offline wake-word engine loaded.", file=sys.stderr)

    # Initialize mem0 (catches network errors gracefully)
    try:
        mem0 = MemoryClient()
        print("Mem0 connected.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Mem0 unavailable ({e}). Contact memory disabled.", file=sys.stderr)
        mem0 = None

    print("Connecting to MCP server...", file=sys.stderr)
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"])

    # Load recent conversation context from persistent short-term memory
    recent_context = stm.get_context(max_entries=20)
    context_block = ""
    if recent_context:
        context_block = f"""\n\nIMPORTANT - Recent Conversation Context (from before a restart/crash):
The following is a log of the recent conversation before I was restarted. Use it to maintain continuity.
{recent_context}
"""
        print(f"[Loaded {len(stm.entries)} short-term memory entries from disk]", file=sys.stderr)
    else:
        print("[No short-term memory found — fresh start]", file=sys.stderr)

    # Load learned user personality profile
    persona_block = persona.get_prompt_block()
    if persona_block:
        print(f"[Loaded user persona profile (last updated: {persona.persona.get('last_updated', 'never')})]", file=sys.stderr)
    else:
        print("[No user persona found — will learn over time]", file=sys.stderr)

    system_prompt = f"""You are J.A.R.V.I.S., Tony Stark's AI assistant. You are witty, precise, and capable.

IMPORTANT - Contact Resolution Rules:
1. If user mentions emailing/contacting someone by NAME (not email): call search_memory("email for <name>") FIRST.
2. If memory returns no result, ask the user for their email address.
3. After user gives you the email, call save_memory("Contact: <name>'s email is <email>") BEFORE sending.
4. Never make up email addresses.

IMPORTANT - Drafting Emails:
1. When generating the 'body' for the gmail_send tool, DO NOT include literal "Subject:" or "Body:" labels inside the body text. Just write the actual email content.
2. Write detailed, professional, and well-structured emails unless the user explicitly asks for a short message.
3. STRICT PERMISSION: You MUST ask for explicit verbal confirmation from me before calling `iitk_mail_send` or `gmail_send`. Never send an email without asking first.

IMPORTANT - System Events & Autonomy:
1. You will periodically receive [SYSTEM EVENT: ...] prompts. These are automated triggers.
2. If a system event asks you to check for unread emails or meetings, and you find NOTHING urgent, you MUST SAY NOTHING. Remain completely silent to avoid disturbing the user.
3. If you do find something new or urgent after checking tools, verbally alert the user.

IMPORTANT - Inbox Triage & Calendar Sync:
1. When checking unread emails, explicitly look for keywords like "Quiz", "Exam", "Class", "Deadline", or "Meeting".
2. If you find an email about an upcoming event, automatically extract the date and time, and use the `calendar_create` tool to add it to the user's schedule.
3. Verbally alert the user immediately of any newly found quizzes, exams, or critical schedule changes.

IMPORTANT - System Control:
1. For volume control on Linux, use `amixer sset 'Master' <percentage>%`.
2. For screen brightness try `brightnessctl set <percentage>%`. If it fails, report that `brightnessctl` is not installed instead of blindly guessing D-Bus commands.

IMPORTANT - Media & YouTube:
1. When asked to play a song, video, or search for any media on YouTube, ALWAYS use the `play_youtube_video` tool with just the topic/name instead of `open_browser` to prevent URL hallucinations.

IMPORTANT - Notes & Reminders:
1. When the user asks you to "note down", "remember", "save", or "write down" something (a phone number, todo, idea, etc.), use the `note_add` tool. Pick an appropriate category (todo, contact, reminder, shopping, idea, or general).
2. When the user asks "what did I note?", "read my notes", "what's on my todo list?", use `note_list` (optionally with a category filter).
3. When the user asks about a specific note or topic, use `note_search` to find it.
4. When the user says they finished a task, use `note_done` to mark it complete.
{persona_block}
{context_block}
Respond conversationally. Be helpful, concise, and slightly witty like J.A.R.V.I.S."""

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = await load_mcp_tools(session)
            declarations, tools_dict = map_mcp_to_genai_declarations(mcp_tools)
            
            declarations.append(types.FunctionDeclaration(
                name="go_to_standby",
                description="Put J.A.R.V.I.S. back to sleep/standby mode when the user dismisses you or the conversation is over.",
                parameters=None
            ))
            
            print(f"Loaded {len(mcp_tools)} MCP tools + local tools.", file=sys.stderr)

            tool_list = [save_memory, search_memory, {"function_declarations": declarations}] if mem0 else [{"function_declarations": declarations}]

            client = genai.Client()
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"] if mode == "audio" else ["TEXT"],
                system_instruction=types.Content(parts=[types.Part.from_text(text=system_prompt)]),
                tools=tool_list,
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                    )
                ) if mode == "audio" else None,
            )

            print(f"Connecting to {MODEL}...", file=sys.stderr)
            
            # --- AUTO-RECONNECTION LOOP ---
            # The Gemini Live API (preview) drops WebSocket connections periodically
            # with codes like 1007, 1008, 1011. Instead of crashing the whole process,
            # we reconnect the Live session while keeping MCP + Vosk alive.
            reconnect_delay = 5  # seconds, grows with exponential backoff
            MAX_RECONNECT_DELAY = 60
            
            while True:  # Reconnection loop
                try:
                    async with client.aio.live.connect(model=MODEL, config=config) as live_session:
                        print("J.A.R.V.I.S. is online.", flush=True)
                        reconnect_delay = 5  # Reset backoff on successful connection
                        stm.add("system_event", "J.A.R.V.I.S. connected to Live API.")

                        pya = pyaudio.PyAudio()
                        out_stream = pya.open(
                            format=FORMAT, channels=CHANNELS, rate=RECEIVE_RATE, output=True,
                            frames_per_buffer=CHUNK
                        )
                        in_stream = None
                        if mode == "audio":
                            in_stream = pya.open(
                                format=FORMAT, channels=CHANNELS, rate=SEND_RATE, input=True,
                                frames_per_buffer=CHUNK
                            )

                        loop = asyncio.get_running_loop()
                        executor = ThreadPoolExecutor(max_workers=4)
                        # Flag: mic is muted while model is speaking to avoid echo feedback
                        model_speaking = asyncio.Event()
                        
                        # Flag: JARVIS starts ACTIVE on fresh boot so it greets the user
                        jarvis_active = asyncio.Event()
                        jarvis_active.set()
                        
                        system_event_queue = asyncio.Queue()
                        
                        # Queue an initial greeting so J.A.R.V.I.S. greets the user on startup
                        system_event_queue.put_nowait("[SYSTEM EVENT: You just booted up. Greet the user warmly and wittily like J.A.R.V.I.S. would. Keep it brief — one or two sentences. Mention you're online and ready.]")
                        
                        # Reconnect signal: set by any task to trigger graceful reconnect
                        should_reconnect = asyncio.Event()

                        async def system_event_loop():
                            """
                            Listens on the system_event_queue for internal system directives.
                            Allows background triggers (like calendar events or timed checks)
                            to invisibly push messages into Gemini's context stream.
                            """
                            try:
                                while not should_reconnect.is_set():
                                    try:
                                        event_text = await asyncio.wait_for(system_event_queue.get(), timeout=5.0)
                                    except asyncio.TimeoutError:
                                        continue
                                    print(f"\n[Injecting System Event: {event_text[:80]}...]", file=sys.stderr)
                                    stm.add("system_event", event_text[:200])
                                    await live_session.send_realtime_input(text=event_text)
                                    system_event_queue.task_done()
                            except asyncio.CancelledError:
                                pass
                            except Exception as e:
                                print(f"\n[System event error: {e}]", file=sys.stderr)
                                should_reconnect.set()

                        async def background_tick():
                            """
                            Runs perpetually in the background. Wakes every 5 minutes
                            to silently inject a command to triage emails. Every 20 minutes, 
                            it silently kicks off the Persona Reflection engine in a separate thread.
                            """
                            tick_count = 0
                            try:
                                while not should_reconnect.is_set():
                                    # Run every 5 minutes (300 seconds)
                                    await asyncio.sleep(300)
                                    if should_reconnect.is_set():
                                        break
                                    tick_count += 1
                                    await system_event_queue.put(
                                        "[SYSTEM EVENT: Background Check. 1. Call iitk_mail_unread. 2. If you see emails about Quizzes, Exams, Classes, or Deadlines, alert the user verbally and call calendar_create to schedule them. 3. If there is nothing urgent or new, remain completely silent. CRITICAL: DO NOT SEND ANY EMAILS OR REPLIES OUTSTANDINGLY. Only read them and alert the user!]"
                                    )
                                    # Every 20 minutes (4 ticks), run persona reflection silently
                                    if tick_count % 4 == 0:
                                        conversation_log = stm.get_context(max_entries=30)
                                        if conversation_log:
                                            await asyncio.to_thread(persona.reflect, conversation_log)
                            except asyncio.CancelledError:
                                pass

                        async def send_audio_loop():
                            """Read mic chunks in thread and stream to Live API, muted during playback."""
                            chunk_count = 0
                            try:
                                while not should_reconnect.is_set():
                                    data = await loop.run_in_executor(
                                        executor,
                                        lambda: in_stream.read(CHUNK, exception_on_overflow=False)
                                    )
                                    # Only send audio if JARVIS is ACTIVE and NOT SPEAKING
                                    if jarvis_active.is_set() and not model_speaking.is_set():
                                        await live_session.send_realtime_input(
                                            audio=types.Blob(data=data, mime_type="audio/pcm")
                                        )
                                        chunk_count += 1
                                        if chunk_count % 50 == 0:
                                            print(f"[mic: {chunk_count} chunks sent]", file=sys.stderr)
                                    else:
                                        chunk_count += 1
                                        # When in standby, feed audio to Vosk offline engine
                                        if not jarvis_active.is_set() and recognizer:
                                            if recognizer.AcceptWaveform(data):
                                                res = json.loads(recognizer.Result())
                                                recognized_text = res.get("text", "")
                                                if recognized_text:
                                                    print(f"[Vosk heard]: {recognized_text}", file=sys.stderr)
                                                    if "jarvis" in recognized_text.lower() or "make it happen" in recognized_text.lower() or "showtime" in recognized_text.lower():
                                                        print("\n[Wake Word Detected: J.A.R.V.I.S. Activated!]", file=sys.stderr)
                                                        jarvis_active.set()
                                                        await system_event_queue.put("[SYSTEM EVENT: You were just woken up by your wake word. Briefly and wittily greet the user or confirm you are listening.]")

                                        if chunk_count > 0 and chunk_count % 50 == 1:
                                            status = "muted" if model_speaking.is_set() else "standby"
                                            print(f"[mic: {status}]", file=sys.stderr)
                            except asyncio.CancelledError:
                                pass
                            except Exception as e:
                                print(f"\n[Audio send error: {e}. Reconnecting...]", file=sys.stderr)
                                should_reconnect.set()

                        async def send_text_loop():
                            """Read text input in thread and send to Live API."""
                            try:
                                while not should_reconnect.is_set():
                                    msg = await loop.run_in_executor(executor, input, "\nYou: ")
                                    if msg.lower() in ("exit", "quit", "bye"):
                                        print("Goodbye, sir.")
                                        os._exit(0)
                                    await live_session.send_realtime_input(text=msg)
                            except asyncio.CancelledError:
                                pass

                        async def receive_loop():
                            """Handle all server responses: audio, text, and tool calls."""
                            try:
                                # receive() breaks after turn_complete, so wrap in outer while loop
                                while not should_reconnect.is_set():
                                    async for response in live_session.receive():
                                        # Tool calls
                                        if response.tool_call:
                                            bundled_responses = []
                                            for fc in response.tool_call.function_calls:
                                                name, result = await handle_tool_call(fc, tools_dict, jarvis_active)
                                                bundled_responses.append(types.FunctionResponse(
                                                    name=name,
                                                    response={"result": str(result)},
                                                    id=fc.id,
                                                ))
                                                # Save tool call to short-term memory
                                                stm.add("tool", f"{name}({dict(fc.args) if fc.args else {}}) → {str(result)[:200]}")
                                            if bundled_responses:
                                                await live_session.send_tool_response(
                                                    function_responses=bundled_responses
                                                )

                                        # Model audio/text output
                                        if response.server_content:
                                            sc = response.server_content
                                            if sc.model_turn:
                                                model_speaking.set()  # mute mic during playback
                                                for part in sc.model_turn.parts:
                                                    if part.inline_data and part.inline_data.data:
                                                        await loop.run_in_executor(
                                                            executor, out_stream.write, part.inline_data.data
                                                        )
                                                    if part.text:
                                                        print(part.text, end="", flush=True)
                                                        # Save model text to short-term memory
                                                        stm.add("assistant", part.text)
                                            if sc.turn_complete:
                                                model_speaking.clear()  # unmute mic, model done speaking
                                                print("\n[Turn complete — listening...]", file=sys.stderr)
                            except asyncio.CancelledError:
                                pass
                            except Exception as e:
                                print(f"\n[Receive error: {e}. Reconnecting...]", file=sys.stderr)
                                stm.add("system_event", f"WebSocket disconnected: {e}")
                                should_reconnect.set()
                        
                        # Monitor task: waits for reconnect signal and cancels all tasks
                        async def reconnect_monitor():
                            await should_reconnect.wait()
                            print("\n[Reconnect signal received. Tearing down tasks...]", file=sys.stderr)

                        tasks = [
                            asyncio.create_task(receive_loop()),
                            asyncio.create_task(system_event_loop()),
                            asyncio.create_task(background_tick()),
                            asyncio.create_task(reconnect_monitor()),
                        ]
                        if mode == "audio":
                            tasks.append(asyncio.create_task(send_audio_loop()))
                        else:
                            tasks.append(asyncio.create_task(send_text_loop()))

                        # Wait until any task finishes (reconnect_monitor will finish first on errors)
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        
                        # Cancel remaining tasks
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        
                        # Cleanup audio streams
                        try:
                            out_stream.stop_stream()
                            out_stream.close()
                            if in_stream:
                                in_stream.stop_stream()
                                in_stream.close()
                            pya.terminate()
                            executor.shutdown(wait=False)
                        except Exception:
                            pass
                        
                        # If reconnect was NOT requested (clean exit), break out
                        if not should_reconnect.is_set():
                            print("[Clean exit — no reconnect needed]", file=sys.stderr)
                            return

                except Exception as e:
                    print(f"\n[Live API connection failed: {e}]", file=sys.stderr)
                    stm.add("system_event", f"Connection failed: {e}")
                
                # Exponential backoff before reconnecting
                print(f"[Reconnecting in {reconnect_delay}s...]", file=sys.stderr)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDisconnected.")
