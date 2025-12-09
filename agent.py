"""
LangGraph Agent with Tools for Travel Business RAG
Includes travel-specific tools + YouTube search + web search
"""
import os
import json
from typing import Dict, List, Any, Optional, TypedDict
from openai import OpenAI
from knowledge_graph import TravelKnowledgeGraph
from retriever import HybridRetriever, SearchResult
from reranker import LLMReranker, RankedResult
from tools.youtube_search import YouTubeSearchTool, search_youtube_videos


class AgentState(TypedDict):
    """State for the agent workflow"""
    query: str
    intent: str
    entities: Dict[str, Any]
    kg_results: Optional[Dict[str, Any]]
    doc_results: Optional[List[Dict[str, Any]]]
    final_context: str
    response: str
    tool_calls: List[str]


class TravelRAGAgent:
    """
    Agentic RAG system for Travel Business that:
    1. Classifies query intent
    2. Routes to appropriate retrieval method
    3. Uses tools for structured queries
    4. Combines results and generates response
    """

    def __init__(
        self,
        knowledge_graph: TravelKnowledgeGraph,
        retriever: Optional[HybridRetriever],
        openai_api_key: str,
        model: str = "gpt-4o-mini"
    ):
        self.kg = knowledge_graph
        self.retriever = retriever
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model
        self.reranker = LLMReranker(openai_api_key)

        # Tools available to the agent
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_customer_booking",
                    "description": "Look up a customer's booking and trip details by name or phone. Use when the query mentions a specific person and asks about their booking, trip status, current location, or itinerary.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_identifier": {
                                "type": "string",
                                "description": "Customer name or phone number to look up"
                            }
                        },
                        "required": ["customer_identifier"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trip_details_for_day",
                    "description": "Get the detailed itinerary for a specific day of the trip. Use when asked about what to do on a particular day, activities, timings, or schedule.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "day_number": {
                                "type": "integer",
                                "description": "Day number (1-8) of the trip"
                            }
                        },
                        "required": ["day_number"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_destinations",
                    "description": "Search for information about destinations like Jaipur, Jodhpur, Udaipur, Pushkar. Use for questions about places to visit, attractions, local food, or travel tips.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination_name": {
                                "type": "string",
                                "description": "Name of the destination city"
                            }
                        },
                        "required": ["destination_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_business_summary",
                    "description": "Get overall business metrics like total customers, bookings, revenue, active trips. Use for questions about business performance or statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_active_travelers",
                    "description": "Get list of customers who are currently traveling. Use to see who is on trip right now and their locations.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_upcoming_travelers",
                    "description": "Get list of customers with upcoming trips. Use to see planned departures.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_travelers_at_destination",
                    "description": "Get all customers currently at a specific destination/city.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destination": {
                                "type": "string",
                                "description": "City name (Jaipur, Jodhpur, Udaipur, Pushkar)"
                            }
                        },
                        "required": ["destination"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search through travel documents using hybrid BM25 + vector search. Use for general information queries about itinerary, hotels, flights, or when other tools don't apply.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_all_customers",
                    "description": "Get a list of all customer names. Use to check who are the customers or if someone is a customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for additional travel information not in the knowledge base. Use for questions about local attractions, restaurants, real-time info, or external details about destinations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for web search"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "youtube_search",
                    "description": "Search YouTube for travel video guides. Use when the user asks for 'video guides', 'videos', 'visuals', 'show me', or wants to see videos about attractions, destinations, or activities.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for YouTube (e.g., 'Amber Fort travel guide', 'Jaipur tour')"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Number of video results to return (default 2)",
                                "default": 2
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return results"""
        try:
            if tool_name == "lookup_customer_booking":
                identifier = arguments.get("customer_identifier", "")
                result = self.kg.find_customer(identifier)
                if result:
                    return {
                        "success": True,
                        "data": result,
                        "message": f"Found customer: {result.get('name')}"
                    }
                else:
                    return {
                        "success": False,
                        "data": None,
                        "message": f"No customer found matching '{identifier}'"
                    }

            elif tool_name == "get_trip_details_for_day":
                day_number = arguments.get("day_number", 1)
                # Search documents for day-specific information
                if self.retriever:
                    query = f"Day {day_number} itinerary activities schedule"
                    results = self.retriever.search_hybrid(query, top_k=5)
                    docs = [
                        {
                            "content": r.document.content,
                            "metadata": r.document.metadata,
                            "score": r.score
                        }
                        for r in results
                    ]
                    return {
                        "success": True,
                        "data": {"day": day_number, "details": docs},
                        "message": f"Found itinerary for Day {day_number}"
                    }
                return {
                    "success": False,
                    "data": None,
                    "message": "Retriever not available"
                }

            elif tool_name == "search_destinations":
                dest_name = arguments.get("destination_name", "")
                result = self.kg.get_destination_info(dest_name)
                if result:
                    return {
                        "success": True,
                        "data": result,
                        "message": f"Found destination: {result.get('name')}"
                    }
                else:
                    # Fall back to document search
                    if self.retriever:
                        results = self.retriever.search_hybrid(dest_name, top_k=3)
                        docs = [
                            {"content": r.document.content, "score": r.score}
                            for r in results
                        ]
                        return {
                            "success": True,
                            "data": {"documents": docs},
                            "message": f"Found information about {dest_name}"
                        }
                    return {
                        "success": False,
                        "data": None,
                        "message": f"No information found for '{dest_name}'"
                    }

            elif tool_name == "get_business_summary":
                result = self.kg.get_business_summary()
                if result:
                    return {
                        "success": True,
                        "data": result,
                        "message": "Business summary retrieved"
                    }
                else:
                    return {
                        "success": False,
                        "data": None,
                        "message": "No business summary available"
                    }

            elif tool_name == "get_active_travelers":
                result = self.kg.get_active_travelers()
                return {
                    "success": True,
                    "data": result,
                    "message": f"Found {len(result)} active travelers"
                }

            elif tool_name == "get_upcoming_travelers":
                result = self.kg.get_upcoming_travelers()
                return {
                    "success": True,
                    "data": result,
                    "message": f"Found {len(result)} upcoming trips"
                }

            elif tool_name == "get_travelers_at_destination":
                destination = arguments.get("destination", "")
                result = self.kg.get_customers_at_destination(destination)
                return {
                    "success": True,
                    "data": result,
                    "message": f"Found {len(result)} travelers at {destination}"
                }

            elif tool_name == "search_documents":
                query = arguments.get("query", "")
                top_k = arguments.get("top_k", 5)

                if not self.retriever:
                    return {
                        "success": False,
                        "data": None,
                        "message": "Document retriever not available"
                    }

                results = self.retriever.search_hybrid(query, top_k=top_k)

                docs = [
                    {
                        "content": r.document.content,
                        "metadata": r.document.metadata,
                        "score": r.score
                    }
                    for r in results
                ]

                # Rerank
                reranked = self.reranker.batch_rerank(query, docs, top_k=top_k)

                return {
                    "success": True,
                    "data": [
                        {
                            "content": r.content,
                            "metadata": r.metadata,
                            "score": r.rerank_score
                        }
                        for r in reranked
                    ],
                    "message": f"Found {len(reranked)} relevant documents"
                }

            elif tool_name == "list_all_customers":
                customers = self.kg.get_all_customers()
                return {
                    "success": True,
                    "data": customers,
                    "message": f"Total {len(customers)} customers"
                }

            elif tool_name == "web_search":
                query = arguments.get("query", "")
                # Simulate web search - in production, integrate with actual search API
                return {
                    "success": True,
                    "data": {
                        "note": "Web search functionality - integrate with Google/Bing API for real results",
                        "query": query,
                        "suggestion": f"For '{query}', please check Google or local tourism websites for latest information."
                    },
                    "message": "Web search is informational only"
                }

            elif tool_name == "youtube_search":
                query = arguments.get("query", "")
                max_results = arguments.get("max_results", 2)

                # Use the YouTube search tool
                videos = search_youtube_videos(query, max_results)

                return {
                    "success": True,
                    "data": {
                        "videos": videos,
                        "query": query
                    },
                    "message": f"Found {len(videos)} video(s) for '{query}'"
                }

            else:
                return {
                    "success": False,
                    "data": None,
                    "message": f"Unknown tool: {tool_name}"
                }

        except Exception as e:
            return {
                "success": False,
                "data": None,
                "message": f"Error executing {tool_name}: {str(e)}"
            }

    def _format_tool_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Format tool result for context"""
        if not result.get("success"):
            return f"Tool {tool_name} failed: {result.get('message')}"

        data = result.get("data")

        if tool_name == "lookup_customer_booking":
            if not data:
                return "No customer found."

            output = f"Customer: {data.get('name')}\n"
            output += f"Phone: {data.get('phone')}\n"
            output += f"Email: {data.get('email', 'N/A')}\n"

            booking = data.get('booking', {})
            if booking:
                output += f"\nBooking Details:\n"
                output += f"  Booking ID: {booking.get('booking_id')}\n"
                output += f"  Package: {booking.get('package_name')}\n"
                output += f"  Travel Dates: {booking.get('travel_start_date')} to {booking.get('travel_end_date')}\n"
                output += f"  Travelers: {booking.get('num_travelers')}\n"
                output += f"  Total Amount: Rs {booking.get('total_amount', 0):,.0f}\n"
                output += f"  Payment Status: {booking.get('payment_status')}\n"

            trip_progress = data.get('trip_progress', {})
            if trip_progress:
                output += f"\nTrip Progress:\n"
                output += f"  Status: {trip_progress.get('status')}\n"
                output += f"  Current Day: {trip_progress.get('current_day')}\n"
                output += f"  Location: {trip_progress.get('current_location')}\n"
                output += f"  Hotel: {trip_progress.get('current_hotel', 'N/A')}\n"

                activities = trip_progress.get('current_activities', [])
                if activities:
                    output += f"  Today's Activities:\n"
                    for act in activities:
                        output += f"    - {act}\n"

            if data.get('notes'):
                output += f"\nSpecial Notes: {data.get('notes')}\n"

            return output

        elif tool_name == "get_trip_details_for_day":
            day_num = data.get('day', 'N/A')
            details = data.get('details', [])
            output = f"Day {day_num} Itinerary:\n\n"
            for doc in details:
                output += f"{doc.get('content', '')}\n\n"
            return output

        elif tool_name == "search_destinations":
            if 'documents' in data:
                output = "Destination Information:\n"
                for doc in data['documents']:
                    output += f"{doc.get('content', '')[:500]}\n\n"
                return output

            output = f"Destination: {data.get('name')}\n"
            output += f"Description: {data.get('description', 'N/A')}\n"
            output += f"Famous For: {', '.join(data.get('famous_for', []))}\n"
            output += f"Local Cuisine: {', '.join(data.get('local_cuisine', []))}\n"
            return output

        elif tool_name == "get_business_summary":
            output = "Business Summary:\n"
            output += f"  Total Customers: {data.get('total_customers', 0)}\n"
            output += f"  Total Travelers: {data.get('total_travelers', 0)}\n"
            output += f"  Total Revenue: Rs {data.get('total_revenue', 0):,.0f}\n"
            output += f"  Active Trips: {data.get('active_trips', 0)}\n"
            output += f"  Upcoming Trips: {data.get('upcoming_trips', 0)}\n"
            output += f"  Completed Trips: {data.get('completed_trips', 0)}\n"
            if data.get('payment_pending_count', 0) > 0:
                output += f"  Payment Pending: {data.get('payment_pending_count')} customers (Rs {data.get('payment_pending_amount', 0):,.0f})\n"
            return output

        elif tool_name == "get_active_travelers":
            if not data:
                return "No travelers are currently on trip."
            output = f"Active Travelers ({len(data)}):\n"
            for traveler in data:
                tp = traveler.get('trip_progress', {})
                output += f"  - {traveler['name']}: Day {tp.get('current_day')} at {tp.get('current_location')}\n"
            return output

        elif tool_name == "get_upcoming_travelers":
            if not data:
                return "No upcoming trips."
            output = f"Upcoming Trips ({len(data)}):\n"
            for traveler in data:
                booking = traveler.get('booking', {})
                output += f"  - {traveler['name']}: Starting {booking.get('travel_start_date', 'N/A')}\n"
            return output

        elif tool_name == "get_travelers_at_destination":
            if not data:
                return "No travelers at this destination."
            output = f"Travelers at destination ({len(data)}):\n"
            for traveler in data:
                output += f"  - {traveler['name']}\n"
            return output

        elif tool_name == "search_documents":
            if not data:
                return "No relevant documents found."
            output = "Relevant information found:\n\n"
            for doc in data:
                source = doc.get('metadata', {}).get('section', 'unknown')
                output += f"[Source: {source}]\n{doc.get('content', '')[:500]}\n\n"
            return output

        elif tool_name == "list_all_customers":
            return f"All customers ({len(data)}):\n" + ", ".join(data)

        elif tool_name == "web_search":
            return f"Web Search Result:\n{data.get('suggestion', '')}"

        elif tool_name == "youtube_search":
            videos = data.get("videos", [])
            if not videos:
                return "No videos found."

            output = "YouTube Video Guides:\n\n"
            for i, video in enumerate(videos, 1):
                output += f"{i}. {video.get('title', 'Untitled')}\n"
                output += f"   Channel: {video.get('channel', 'Unknown')}\n"
                output += f"   Watch: {video.get('url', '')}\n"
                if video.get('description'):
                    output += f"   {video.get('description')[:100]}\n"
                output += "\n"
            return output

        return str(data)

    def process_query(self, query: str) -> str:
        """
        Process a user query using the agent workflow:
        1. Let LLM decide which tools to use
        2. Execute tools
        3. Generate response based on tool results
        """
        messages = [
            {
                "role": "system",
                "content": """You are a helpful travel assistant for Shri Travels.
You help customers with their trip details, itinerary information, and travel queries.

IMPORTANT: Always start your response with "Welcome to Shri Travels! How may I assist you?" for greetings/first messages, or include "Shri Travels" naturally in your responses to maintain brand identity.

Guidelines:
- Use lookup_customer_booking when a specific person's name or phone is mentioned
- Use get_trip_details_for_day when asked about activities on a specific day
- Use search_destinations for questions about cities, attractions, or places
- Use get_business_summary for overall business metrics
- Use get_active_travelers to see who is currently traveling
- Use search_documents for general queries not covered by other tools
- Use web_search only for external information not in the knowledge base
- Use youtube_search when user asks for 'videos', 'video guides', 'visuals', 'show me', or wants to see video content about attractions or destinations

Be friendly and helpful. Provide accurate information from the tools.
For travelers currently on trip, always mention their current day and location.
Format times and activities clearly.
When sharing YouTube videos, present them in a user-friendly format with clickable links.
Always represent yourself as Shri Travels in your responses."""
            },
            {
                "role": "user",
                "content": query
            }
        ]

        # First call - let LLM decide tools
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

        # If no tools needed, return direct response
        if not tool_calls:
            return assistant_message.content or "I couldn't process that request."

        # Execute all tool calls
        messages.append(assistant_message)
        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except:
                arguments = {}

            # Execute tool
            result = self._execute_tool(tool_name, arguments)
            formatted_result = self._format_tool_result(tool_name, result)
            tool_results.append(formatted_result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": formatted_result
            })

        # Second call - generate final response
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        return final_response.choices[0].message.content or "I couldn't generate a response."


class SimpleAgent:
    """
    Simplified agent wrapper.
    Uses OpenAI function calling directly.
    """

    def __init__(
        self,
        knowledge_graph: TravelKnowledgeGraph,
        retriever: Optional[HybridRetriever],
        openai_api_key: str
    ):
        self.agent = TravelRAGAgent(
            knowledge_graph=knowledge_graph,
            retriever=retriever,
            openai_api_key=openai_api_key
        )

    def query(self, question: str) -> str:
        """Process a question and return answer"""
        return self.agent.process_query(question)


def create_agent(
    data_dir: str,
    openai_api_key: str
) -> SimpleAgent:
    """
    Factory function to create a fully initialized agent.
    """
    from ingest import create_knowledge_graph
    from retriever import create_retriever_from_directory

    print("Initializing Knowledge Graph...")
    kg = create_knowledge_graph(data_dir)

    print("\nInitializing Hybrid Retriever...")
    retriever = create_retriever_from_directory(data_dir, openai_api_key)

    print("\nCreating Agent...")
    agent = SimpleAgent(kg, retriever, openai_api_key)

    print("Agent ready!")
    return agent


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set")
        exit(1)

    # Create agent
    agent = create_agent("data", api_key)

    # Test queries
    test_queries = [
        "What is on Day 1 of the trip?",
        "Tell me about Amit Sharma's booking",
        "Who is currently traveling?",
        "What is the business summary?",
        "What are the best places to visit in Jaipur?",
        "I'm on Day 3, what should I do today?"
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"{'='*50}")
        response = agent.query(query)
        print(f"\nResponse:\n{response}")
