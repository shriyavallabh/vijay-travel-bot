"""
Brave Search API Tool for Travel RAG Bot
Provides real-time web search capabilities similar to Perplexity AI
"""
import os
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Web search result"""
    title: str
    url: str
    description: str
    age: Optional[str] = None


class BraveSearchTool:
    """
    Brave Search API integration for real-time web search.
    Provides privacy-focused search results from Brave's independent index.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.base_url = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query: str, count: int = 5, freshness: Optional[str] = None) -> List[SearchResult]:
        """
        Search the web using Brave Search API.

        Args:
            query: Search query string
            count: Number of results to return (max 20)
            freshness: Filter by freshness - 'pd' (past day), 'pw' (past week),
                      'pm' (past month), 'py' (past year), or None for all

        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            return self._fallback_response(query)

        try:
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key
            }

            params = {
                "q": query,
                "count": min(count, 20),
                "text_decorations": False,
                "search_lang": "en",
                "country": "in",  # India for travel-relevant results
            }

            if freshness:
                params["freshness"] = freshness

            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    self.base_url,
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()

            results = []
            web_results = data.get("web", {}).get("results", [])

            for item in web_results[:count]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    age=item.get("age", None)
                ))

            return results

        except httpx.HTTPStatusError as e:
            print(f"[Brave Search API Error] HTTP {e.response.status_code}: {e}")
            return self._fallback_response(query)
        except Exception as e:
            print(f"[Brave Search Error] {e}")
            return self._fallback_response(query)

    def _fallback_response(self, query: str) -> List[SearchResult]:
        """Fallback when API is not available"""
        return [SearchResult(
            title=f"Search results for: {query}",
            url=f"https://search.brave.com/search?q={query.replace(' ', '+')}",
            description=f"BRAVE_API_KEY not configured. Click to search manually for '{query}'",
            age=None
        )]

    def search_travel_info(self, destination: str, info_type: str = "general") -> List[SearchResult]:
        """
        Search for travel-specific information about a destination.

        Args:
            destination: Place name (e.g., "Jaipur", "Amber Fort")
            info_type: Type of info - 'general', 'restaurants', 'attractions',
                      'hotels', 'weather', 'tips'

        Returns:
            List of SearchResult objects
        """
        query_templates = {
            "general": f"{destination} travel guide 2024",
            "restaurants": f"best restaurants in {destination} local food",
            "attractions": f"top attractions things to do {destination}",
            "hotels": f"best hotels to stay {destination}",
            "weather": f"{destination} weather forecast travel",
            "tips": f"{destination} travel tips tourists"
        }

        query = query_templates.get(info_type, query_templates["general"])
        return self.search(query, count=5)

    def format_results(self, results: List[SearchResult], include_urls: bool = True) -> str:
        """
        Format search results for display/LLM consumption.

        Args:
            results: List of SearchResult objects
            include_urls: Whether to include URLs in output

        Returns:
            Formatted string of search results
        """
        if not results:
            return "No search results found."

        output = "Web Search Results:\n\n"

        for i, result in enumerate(results, 1):
            output += f"{i}. {result.title}\n"
            if result.description:
                output += f"   {result.description[:200]}{'...' if len(result.description) > 200 else ''}\n"
            if include_urls:
                output += f"   Link: {result.url}\n"
            if result.age:
                output += f"   ({result.age})\n"
            output += "\n"

        return output


def search_web(query: str, count: int = 5) -> List[Dict[str, str]]:
    """
    Convenience function to search the web.

    Args:
        query: Search query
        count: Number of results

    Returns:
        List of result dictionaries
    """
    tool = BraveSearchTool()
    results = tool.search(query, count)

    return [
        {
            "title": r.title,
            "url": r.url,
            "description": r.description,
            "age": r.age or ""
        }
        for r in results
    ]


def search_travel(destination: str, info_type: str = "general") -> List[Dict[str, str]]:
    """
    Convenience function for travel-specific searches.

    Args:
        destination: Place to search for
        info_type: Type of information needed

    Returns:
        List of result dictionaries
    """
    tool = BraveSearchTool()
    results = tool.search_travel_info(destination, info_type)

    return [
        {
            "title": r.title,
            "url": r.url,
            "description": r.description,
            "age": r.age or ""
        }
        for r in results
    ]


if __name__ == "__main__":
    # Test the tool
    tool = BraveSearchTool()

    test_queries = [
        "Amber Fort Jaipur visiting hours 2024",
        "best restaurants in Jodhpur",
        "Udaipur Lake Pichola boat ride timings"
    ]

    for query in test_queries:
        print(f"\n=== Query: {query} ===")
        results = tool.search(query, count=3)
        print(tool.format_results(results))
