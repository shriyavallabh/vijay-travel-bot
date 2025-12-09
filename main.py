"""
Agentic Graph RAG WhatsApp Bot for Travel Business
Main FastAPI application integrating:
- Knowledge Graph (NetworkX)
- Hybrid Retriever (BM25 + Vector)
- Reranker (LLM)
- Agent with Travel Tools
- Session-Based Conversational Memory (LangChain)
- Voice Support (Whisper)
"""
import os
import hmac
import hashlib
import httpx
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "ragbot_verify_123")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATA_DIR = os.getenv("DATA_DIR", "data")
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "").split(",")
ALLOWED_NUMBERS = [n.strip() for n in ALLOWED_NUMBERS if n.strip()]

# Global instances
agent = None
rag_chain = None  # LangChain ConversationalRAGChain with session memory
voice_handler = None  # For Whisper voice transcription


def generate_appsecret_proof(access_token: str, app_secret: str) -> str:
    """Generate appsecret_proof for Meta API authentication"""
    return hmac.new(
        app_secret.encode('utf-8'),
        access_token.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def send_whatsapp_message(to: str, message: str):
    """Send a message via WhatsApp Business API"""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    # Generate appsecret_proof
    proof = generate_appsecret_proof(WHATSAPP_ACCESS_TOKEN, FB_APP_SECRET)

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Split long messages
    max_length = 4000
    messages = [message[i:i+max_length] for i in range(0, len(message), max_length)]

    async with httpx.AsyncClient() as client:
        for msg in messages:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": msg}
            }

            response = await client.post(
                f"{url}?appsecret_proof={proof}",
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                print(f"Error sending message: {response.status_code} - {response.text}")


def initialize_agent():
    """Initialize the RAG agent with all components including LangChain session memory and voice"""
    global agent, rag_chain, voice_handler

    print("\n" + "="*60)
    print("INITIALIZING TRAVEL RAG SYSTEM")
    print("WITH LANGCHAIN SESSION MEMORY + VOICE")
    print("="*60)

    # Import components
    from ingest import create_knowledge_graph
    from retriever import create_retriever_from_directory
    from agent import SimpleAgent
    from rag_chain import create_conversational_rag_chain, get_all_sessions
    from transcriber import create_voice_handler

    # Check for data directory
    if not os.path.exists(DATA_DIR):
        print(f"WARNING: Data directory not found: {DATA_DIR}")
        print("Creating empty knowledge graph...")
        from knowledge_graph import TravelKnowledgeGraph
        kg = TravelKnowledgeGraph()
    else:
        print(f"\n[1/5] Loading Knowledge Graph from {DATA_DIR}...")
        kg = create_knowledge_graph(DATA_DIR)

    print(f"\n[2/5] Building Hybrid Retriever...")
    try:
        retriever = create_retriever_from_directory(DATA_DIR, OPENAI_API_KEY)
    except Exception as e:
        print(f"Warning: Could not create retriever: {e}")
        retriever = None

    print(f"\n[3/5] Initializing Agent with Travel Tools...")
    agent = SimpleAgent(kg, retriever, OPENAI_API_KEY)

    print(f"\n[4/5] Setting up LangChain Session Memory (RunnableWithMessageHistory)...")
    print("       - Session store: In-memory dict (keyed by phone number)")
    print("       - History-aware retrieval: contextualize_q_chain")
    print("       - Max turns per session: 5")
    rag_chain = create_conversational_rag_chain(
        agent=agent,
        openai_api_key=OPENAI_API_KEY,
        model="gpt-4o-mini",
        max_turns=5
    )

    print(f"\n[5/5] Initializing Whisper Voice Handler...")
    voice_handler = create_voice_handler(OPENAI_API_KEY, WHATSAPP_ACCESS_TOKEN, FB_APP_SECRET)

    # Print summary
    stats = kg.stats()
    print("\n" + "="*60)
    print("TRAVEL RAG SYSTEM READY")
    print("="*60)
    print(f"  Customers: {stats.get('customers', 0)}")
    print(f"  Bookings: {stats.get('bookings', 0)}")
    print(f"  Destinations: {stats.get('destinations', 0)}")
    print(f"  Hotels: {stats.get('hotels', 0)}")
    print(f"  Graph Nodes: {stats.get('total_nodes', 0)}")
    print(f"  Graph Edges: {stats.get('total_edges', 0)}")
    print(f"  Memory: LangChain RunnableWithMessageHistory")
    print(f"         - Session ID: WhatsApp phone number (wa_id)")
    print(f"         - Store: Global dict (replace with Redis in prod)")
    print(f"  Voice: OpenAI Whisper enabled")

    business = kg.get_business_summary()
    if business:
        print(f"\n  Business Summary:")
        print(f"    Total Customers: {business.get('total_customers', 0)}")
        print(f"    Total Revenue: Rs {business.get('total_revenue', 0):,.0f}")
        print(f"    Active Trips: {business.get('active_trips', 0)}")

    print("="*60 + "\n")

    return agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize on startup"""
    # Startup
    print("Starting up Travel RAG Bot...")
    initialize_agent()
    yield
    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Travel Business RAG WhatsApp Bot",
    description="Rajasthan Tours RAG system with Knowledge Graph, Hybrid Retrieval, and Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    global agent
    return {
        "status": "running",
        "system": "Travel RAG Bot",
        "version": "1.0.0",
        "agent_initialized": agent is not None,
        "components": {
            "knowledge_graph": True,
            "hybrid_retriever": True,
            "reranker": True,
            "agent": True,
            "voice": True
        }
    }


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Webhook verification for Meta WhatsApp"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        print(f"Webhook verified successfully!")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Handle incoming WhatsApp messages with LangChain session-based memory.

    Flow:
    1. Receive Webhook -> Extract wa_id (phone_number) as session_id
    2. Retrieve Chat History for session_id from store
    3. Reformulate Question using contextualize_q_chain
    4. Retrieve Documents -> Generate Answer via Agent
    5. Save UserMessage and AIMessage back to the store under session_id
    """
    global rag_chain, voice_handler

    try:
        body = await request.json()
        print(f"\n{'='*50}")
        print("INCOMING WEBHOOK")
        print(f"{'='*50}")

        # Extract message data
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # =====================================================================
        # VERBOSE LOGGING: Check for status updates (read receipts, etc.)
        # =====================================================================
        statuses = value.get("statuses", [])
        if statuses:
            for status in statuses:
                status_type = status.get("status", "unknown")
                recipient_id = status.get("recipient_id", "")
                timestamp = status.get("timestamp", "")
                message_id = status.get("id", "")

                print(f"[STATUS] {status_type.upper()}")
                print(f"         Recipient: {recipient_id}")
                print(f"         Message ID: {message_id}")
                print(f"         Timestamp: {timestamp}")

                if status_type == "read":
                    print(f"         -> Message was READ by {recipient_id}")
                elif status_type == "delivered":
                    print(f"         -> Message DELIVERED to {recipient_id}")
                elif status_type == "sent":
                    print(f"         -> Message SENT to {recipient_id}")
                elif status_type == "failed":
                    errors = status.get("errors", [])
                    print(f"         -> Message FAILED: {errors}")

            return {"status": "status_update_processed", "statuses": len(statuses)}

        # Check for message
        messages = value.get("messages", [])
        if not messages:
            return {"status": "no_message"}

        message = messages[0]

        # =====================================================================
        # STEP 1: Extract wa_id (Sender's Phone Number) as session_id
        # =====================================================================
        wa_id = message.get("from", "")  # Sender's WhatsApp phone number
        session_id = wa_id  # Use wa_id as session identifier for memory

        message_type = message.get("type", "")
        message_id = message.get("id", "")

        print(f"Session ID (wa_id): {session_id}")
        print(f"Message Type: {message_type}")

        # Check if number is allowed
        if ALLOWED_NUMBERS and session_id not in ALLOWED_NUMBERS:
            print(f"Unauthorized number: {session_id}")
            return {"status": "unauthorized"}

        # Handle different message types
        text = ""

        if message_type == "text":
            # Text message
            text = message.get("text", {}).get("body", "")
            print(f"Message: {text}")

        elif message_type == "audio":
            # Voice message - transcribe with Whisper
            audio_data = message.get("audio", {})
            media_id = audio_data.get("id", "")

            if not media_id:
                await send_whatsapp_message(session_id, "Could not process voice message.")
                return {"status": "no_media_id"}

            print(f"Voice message received (media_id: {media_id})")

            if voice_handler is None:
                await send_whatsapp_message(session_id, "Voice processing not available.")
                return {"status": "voice_not_ready"}

            # Transcribe voice
            text, error = await voice_handler.process_voice_message(media_id)

            if error:
                print(f"Transcription error: {error}")
                await send_whatsapp_message(
                    session_id,
                    f"Could not transcribe voice message. Please try again or send a text message."
                )
                return {"status": "transcription_error", "error": error}

            print(f"Transcribed: {text}")

            # Send acknowledgment that voice was received
            await send_whatsapp_message(session_id, f"I heard: \"{text}\"\n\nProcessing your question...")

        elif message_type == "interactive":
            # =====================================================================
            # BUTTON CLICK HANDLING: Process interactive messages (button clicks)
            # =====================================================================
            interactive_data = message.get("interactive", {})
            interactive_type = interactive_data.get("type", "")

            print(f"[INTERACTIVE] Type: {interactive_type}")
            print(f"[INTERACTIVE] Data: {interactive_data}")

            if interactive_type == "button_reply":
                # Handle quick reply button click
                button_reply = interactive_data.get("button_reply", {})
                button_id = button_reply.get("id", "")
                button_title = button_reply.get("title", "")

                print(f"[BUTTON CLICK] ID: {button_id}")
                print(f"[BUTTON CLICK] Title: {button_title}")

                # Check for GET_PLAN_DAY_{day_number} payload
                if button_id.startswith("GET_PLAN_DAY_"):
                    try:
                        day_number = int(button_id.replace("GET_PLAN_DAY_", ""))
                        print(f"[BUTTON CLICK] Detected Morning Nudge button for Day {day_number}")

                        # Generate synthetic prompt for agent
                        text = f"Please give me the detailed plan for Day {day_number}. Include all activities, timings, and video guides."
                        print(f"[SYNTHETIC PROMPT] {text}")

                    except ValueError:
                        text = "Please give me today's plan with video guides."
                else:
                    # Other button payloads
                    text = button_id

            elif interactive_type == "list_reply":
                # Handle list selection
                list_reply = interactive_data.get("list_reply", {})
                text = list_reply.get("id", "") or list_reply.get("title", "")
                print(f"[LIST REPLY] {text}")
            else:
                text = ""
                print(f"[INTERACTIVE] Unknown interactive type: {interactive_type}")

        else:
            # Unsupported message type
            await send_whatsapp_message(
                session_id,
                "I can process text, voice, and button clicks. Please send me a question about your trip or booking."
            )
            return {"status": "unsupported_message_type"}

        if not text:
            return {"status": "empty_message"}

        # Check if RAG chain is initialized
        if rag_chain is None:
            await send_whatsapp_message(
                session_id,
                "System is still initializing. Please try again in a moment."
            )
            return {"status": "agent_not_ready"}

        # =====================================================================
        # STEPS 2-5: Process with LangChain RAG Chain (session memory)
        # =====================================================================
        print(f"\nProcessing with LangChain RAG Chain (session: {session_id})...")
        try:
            response = rag_chain.invoke(session_id, text)
            print(f"\nAgent Response:\n{response[:200]}...")
        except Exception as e:
            print(f"RAG Chain error: {e}")
            import traceback
            traceback.print_exc()
            response = f"I encountered an error processing your request. Please try rephrasing your question."

        # Send response
        await send_whatsapp_message(session_id, response)

        print(f"\n{'='*50}")
        print("RESPONSE SENT")
        print(f"{'='*50}\n")

        return {"status": "success", "message_id": message_id, "session_id": session_id}

    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@app.get("/stats")
async def get_stats():
    """Get system statistics including session memory info"""
    global agent, rag_chain

    if agent is None:
        return {"error": "Agent not initialized"}

    from rag_chain import get_all_sessions

    kg_stats = agent.agent.kg.stats()
    business = agent.agent.kg.get_business_summary()
    sessions = get_all_sessions()

    return {
        "knowledge_graph": kg_stats,
        "business_summary": business,
        "retriever": agent.agent.retriever.stats() if agent.agent.retriever else None,
        "memory": {
            "type": "LangChain RunnableWithMessageHistory",
            "store": "In-memory dict (keyed by phone number)",
            "active_sessions": len(sessions),
            "sessions": sessions
        }
    }


@app.get("/sessions")
async def get_sessions():
    """Get all active conversation sessions"""
    from rag_chain import get_all_sessions, store

    sessions = get_all_sessions()
    session_details = {}

    for session_id, msg_count in sessions.items():
        if session_id in store:
            history = store[session_id]
            session_details[session_id] = {
                "message_count": msg_count,
                "messages": [
                    {"role": msg.type, "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content}
                    for msg in history.messages
                ]
            }

    return {
        "total_sessions": len(sessions),
        "sessions": session_details
    }


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a specific session"""
    from rag_chain import clear_session as clear_session_func

    result = clear_session_func(session_id)
    if result:
        return {"status": "cleared", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")


@app.get("/customers")
async def list_customers():
    """List all customers"""
    global agent

    if agent is None:
        return {"error": "Agent not initialized"}

    customers = agent.agent.kg.get_all_customers()
    return {
        "total": len(customers),
        "customers": customers
    }


@app.get("/customer/{name}")
async def get_customer(name: str):
    """Get specific customer details"""
    global agent

    if agent is None:
        return {"error": "Agent not initialized"}

    result = agent.agent.kg.find_customer(name)
    if result:
        return result
    else:
        raise HTTPException(status_code=404, detail=f"Customer '{name}' not found")


@app.get("/active-travelers")
async def get_active_travelers():
    """Get customers currently on trip"""
    global agent

    if agent is None:
        return {"error": "Agent not initialized"}

    travelers = agent.agent.kg.get_active_travelers()
    return {
        "total": len(travelers),
        "travelers": [
            {
                "name": t.get("name"),
                "current_day": t.get("trip_progress", {}).get("current_day"),
                "location": t.get("trip_progress", {}).get("current_location"),
                "hotel": t.get("trip_progress", {}).get("current_hotel")
            }
            for t in travelers
        ]
    }


@app.get("/upcoming-travelers")
async def get_upcoming_travelers():
    """Get customers with upcoming trips"""
    global agent

    if agent is None:
        return {"error": "Agent not initialized"}

    travelers = agent.agent.kg.get_upcoming_travelers()
    return {
        "total": len(travelers),
        "travelers": [
            {
                "name": t.get("name"),
                "start_date": t.get("booking", {}).get("travel_start_date")
            }
            for t in travelers
        ]
    }


@app.post("/query")
async def query_agent(request: Request):
    """
    Direct API endpoint to query the agent with optional session memory.

    Body:
    - question: The question to ask
    - session_id: Optional session ID for conversation memory (default: "api_user")
    """
    global agent, rag_chain

    if agent is None:
        return {"error": "Agent not initialized"}

    body = await request.json()
    question = body.get("question", "")
    session_id = body.get("session_id", "api_user")

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Use the RAG chain with memory if available
    if rag_chain is not None:
        response = rag_chain.invoke(session_id, question)
    else:
        response = agent.query(question)

    return {
        "question": question,
        "response": response,
        "session_id": session_id
    }


@app.post("/reload")
async def reload_data():
    """Reload data and reinitialize agent"""
    global agent
    agent = initialize_agent()
    return {"status": "reloaded", "stats": agent.agent.kg.stats()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
