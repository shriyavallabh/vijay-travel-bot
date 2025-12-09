"""
LangChain RAG Chain with Session-Based Conversational Memory
For Travel Business WhatsApp Bot

This module implements history-aware retrieval using:
- RunnableWithMessageHistory for session management
- Global dict store (keyed by phone number)
- Question reformulation for follow-up handling
"""
import os
from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI


# =============================================================================
# SESSION STORE
# In production, replace this dict with RedisChatMessageHistory or similar
# =============================================================================
store: Dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    Get or create chat history for a session.

    Args:
        session_id: The WhatsApp phone number (wa_id) of the user

    Returns:
        ChatMessageHistory instance for this session
    """
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
        print(f"[Memory] Created new session for: {session_id}")
    else:
        print(f"[Memory] Retrieved session for: {session_id} ({len(store[session_id].messages)} messages)")
    return store[session_id]


def clear_session(session_id: str) -> bool:
    """Clear chat history for a session"""
    if session_id in store:
        del store[session_id]
        print(f"[Memory] Cleared session for: {session_id}")
        return True
    return False


def get_all_sessions() -> Dict[str, int]:
    """Get all active sessions with message counts"""
    return {
        session_id: len(history.messages)
        for session_id, history in store.items()
    }


# =============================================================================
# CONTEXTUALIZE QUESTION CHAIN
# Reformulates follow-up questions into standalone questions
# =============================================================================

CONTEXTUALIZE_SYSTEM_PROMPT = """Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history.

Do NOT answer the question, just reformulate it if needed and otherwise return it as is.

Examples for a travel assistant context:
- If chat history mentions "Amit Sharma" and user asks "what is his current location?" -> "What is Amit Sharma's current location?"
- If user asks "tell me about Day 1" with no prior context -> "tell me about Day 1" (unchanged)
- If chat history discussed Jaipur and user asks "what are the best restaurants there?" -> "What are the best restaurants in Jaipur?"
- If user asks "what about tomorrow?" and they discussed Day 3 -> "What are the activities for Day 4?"
- If user says "recheck" after discussing a booking -> "Please recheck the booking details for [customer name]"
"""


def create_contextualize_chain(llm: ChatOpenAI):
    """
    Create a chain that reformulates questions based on chat history.

    This is CRUCIAL for handling follow-up questions like:
    - "what about tomorrow?" -> "What are the activities for Day 4?"
    - "where is he now?" -> "Where is Amit Sharma now?"
    """
    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", CONTEXTUALIZE_SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])

    return contextualize_prompt | llm | StrOutputParser()


# =============================================================================
# RAG CHAIN WITH MEMORY
# Combines question reformulation + retrieval + generation
# =============================================================================

RAG_SYSTEM_PROMPT = """You are a helpful travel assistant for Rajasthan Royal Heritage Tours.
You help customers with their trip details, itinerary, and travel queries.

Use the following retrieved context to answer the question. If you don't know the answer based on the context, say so clearly.

Guidelines:
- Be friendly and helpful
- Provide specific times, locations, and details when available
- If a customer is on an active trip, mention their current day and location
- For itinerary questions, include timings and activities
- Format information clearly with bullet points when appropriate
- Never make up booking or trip details

Context:
{context}
"""


class ConversationalRAGChain:
    """
    Conversational RAG chain that:
    1. Retrieves chat history for the session
    2. Reformulates the question using chat history
    3. Retrieves relevant documents
    4. Generates response
    5. Saves messages back to session store
    """

    def __init__(
        self,
        agent,  # SimpleAgent or TravelRAGAgent
        openai_api_key: str,
        model: str = "gpt-4o-mini",
        max_history_messages: int = 10  # Keep last 10 messages (5 turns)
    ):
        self.agent = agent
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0
        )
        self.max_history_messages = max_history_messages

        # Create the contextualize chain
        self.contextualize_chain = create_contextualize_chain(self.llm)

        # Create the main chain wrapped with message history
        self._setup_chain()

    def _setup_chain(self):
        """Setup the conversational chain with history"""

        # The core chain that processes queries
        def process_with_context(inputs: Dict[str, Any]) -> str:
            """Process the reformulated question through the agent"""
            question = inputs.get("input", "")
            chat_history = inputs.get("chat_history", [])

            # Reformulate question if there's chat history
            if chat_history:
                reformulated = self.contextualize_chain.invoke({
                    "input": question,
                    "chat_history": chat_history
                })
                print(f"[RAG Chain] Original: '{question}'")
                print(f"[RAG Chain] Reformulated: '{reformulated}'")
            else:
                reformulated = question
                print(f"[RAG Chain] Query (no history): '{question}'")

            # Process through the agent (which handles tools, retrieval, etc.)
            response = self.agent.query(reformulated)
            return response

        # Create the runnable
        self.chain = RunnableLambda(process_with_context)

        # Wrap with message history
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )

    def invoke(self, session_id: str, question: str) -> str:
        """
        Process a query with conversation history.

        Args:
            session_id: WhatsApp phone number (wa_id)
            question: User's question

        Returns:
            Agent's response
        """
        config = {"configurable": {"session_id": session_id}}

        try:
            response = self.chain_with_history.invoke(
                {"input": question},
                config=config
            )

            # Trim history if needed
            self._trim_history(session_id)

            return response

        except Exception as e:
            print(f"[RAG Chain] Error: {e}")
            import traceback
            traceback.print_exc()
            return f"I encountered an error processing your request. Please try rephrasing your question."

    def _trim_history(self, session_id: str):
        """Keep only the last max_history_messages"""
        if session_id in store:
            history = store[session_id]
            if len(history.messages) > self.max_history_messages:
                # Keep only the most recent messages
                history.messages = history.messages[-self.max_history_messages:]
                print(f"[Memory] Trimmed history for {session_id} to {len(history.messages)} messages")

    def get_history(self, session_id: str) -> List[BaseMessage]:
        """Get chat history for a session"""
        if session_id in store:
            return store[session_id].messages
        return []

    def clear_history(self, session_id: str):
        """Clear history for a session"""
        clear_session(session_id)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_conversational_rag_chain(
    agent,
    openai_api_key: str,
    model: str = "gpt-4o-mini",
    max_turns: int = 5
) -> ConversationalRAGChain:
    """
    Create a conversational RAG chain with session memory.

    Args:
        agent: The SimpleAgent with tools
        openai_api_key: OpenAI API key
        model: Model to use for contextualization
        max_turns: Max conversation turns to keep (1 turn = user + assistant)

    Returns:
        ConversationalRAGChain instance
    """
    return ConversationalRAGChain(
        agent=agent,
        openai_api_key=openai_api_key,
        model=model,
        max_history_messages=max_turns * 2  # Each turn has 2 messages
    )


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set")
        exit(1)

    # Test the contextualize chain directly
    llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)
    contextualize = create_contextualize_chain(llm)

    # Simulate a conversation
    test_session = "919999999999"

    # Add some history manually for testing
    history = get_session_history(test_session)
    history.add_user_message("Tell me about Amit Sharma's booking")
    history.add_ai_message("Amit Sharma has a booking from Dec 15-22, 2024. Currently on Day 3 in Pushkar.")

    # Test reformulation
    test_questions = [
        "what is his current location?",
        "what about tomorrow?",
        "What is on Day 1?",  # Should not change
    ]

    for q in test_questions:
        reformulated = contextualize.invoke({
            "input": q,
            "chat_history": history.messages
        })
        print(f"\nOriginal: {q}")
        print(f"Reformulated: {reformulated}")

    print(f"\nSession history: {get_all_sessions()}")
