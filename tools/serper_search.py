"""
Serper API Tool for Travel RAG Bot
Provides real-time Google search results for web, images, videos, and news
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
    snippet: str
    position: int = 0


@dataclass
class VideoResult:
    """Video search result"""
    title: str
    url: str
    channel: str
    duration: str
    thumbnail: str


class SerperSearchTool:
    """
    Serper API integration for real-time Google search.
    Supports web search, video search, image search, and news.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")
        self.base_url = "https://google.serper.dev"

    def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """
        Search the web using Serper API (Google results).

        Args:
            query: Search query string
            num_results: Number of results to return (max 10)

        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            return self._fallback_response(query)

        try:
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": query,
                "num": min(num_results, 10),
                "gl": "in",  # India for travel-relevant results
                "hl": "en"
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            results = []
            organic = data.get("organic", [])

            for i, item in enumerate(organic[:num_results], 1):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i
                ))

            return results

        except httpx.HTTPStatusError as e:
            print(f"[Serper API Error] HTTP {e.response.status_code}: {e}")
            return self._fallback_response(query)
        except Exception as e:
            print(f"[Serper Error] {e}")
            return self._fallback_response(query)

    def search_videos(self, query: str, num_results: int = 3) -> List[VideoResult]:
        """
        Search for YouTube videos using Serper API.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            List of VideoResult objects
        """
        if not self.api_key:
            return self._fallback_video_response(query)

        try:
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": query,
                "num": min(num_results, 10)
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.base_url}/videos",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            results = []
            videos = data.get("videos", [])

            for item in videos[:num_results]:
                results.append(VideoResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    channel=item.get("channel", ""),
                    duration=item.get("duration", ""),
                    thumbnail=item.get("imageUrl", "")
                ))

            return results

        except Exception as e:
            print(f"[Serper Video Error] {e}")
            return self._fallback_video_response(query)

    def search_images(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search for images using Serper API.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            List of image dictionaries
        """
        if not self.api_key:
            return []

        try:
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": query,
                "num": min(num_results, 10)
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.base_url}/images",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            results = []
            images = data.get("images", [])

            for item in images[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "image_url": item.get("imageUrl", ""),
                    "source": item.get("source", "")
                })

            return results

        except Exception as e:
            print(f"[Serper Image Error] {e}")
            return []

    def _fallback_response(self, query: str) -> List[SearchResult]:
        """Fallback when API is not available"""
        return [SearchResult(
            title=f"Search results for: {query}",
            url=f"https://www.google.com/search?q={query.replace(' ', '+')}",
            snippet=f"SERPER_API_KEY not configured. Click to search manually for '{query}'",
            position=1
        )]

    def _fallback_video_response(self, query: str) -> List[VideoResult]:
        """Fallback for video search when API is not available"""
        return [VideoResult(
            title=f"Search YouTube: {query}",
            url=f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            channel="YouTube Search",
            duration="",
            thumbnail=""
        )]

    def format_web_results(self, results: List[SearchResult]) -> str:
        """Format web search results for display"""
        if not results:
            return "No search results found."

        output = "Web Search Results:\n\n"
        for result in results:
            output += f"{result.position}. {result.title}\n"
            if result.snippet:
                output += f"   {result.snippet[:200]}{'...' if len(result.snippet) > 200 else ''}\n"
            output += f"   Link: {result.url}\n\n"

        return output

    def format_video_results(self, results: List[VideoResult]) -> str:
        """Format video search results for display"""
        if not results:
            return "No videos found."

        output = "YouTube Videos:\n\n"
        for i, video in enumerate(results, 1):
            output += f"{i}. {video.title}\n"
            output += f"   Channel: {video.channel}\n"
            if video.duration:
                output += f"   Duration: {video.duration}\n"
            output += f"   Watch: {video.url}\n\n"

        return output


def search_web(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Convenience function to search the web.

    Args:
        query: Search query
        num_results: Number of results

    Returns:
        List of result dictionaries
    """
    tool = SerperSearchTool()
    results = tool.search(query, num_results)

    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "position": r.position
        }
        for r in results
    ]


def search_youtube(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    """
    Convenience function to search YouTube videos.

    Args:
        query: Search query
        num_results: Number of results

    Returns:
        List of video dictionaries
    """
    tool = SerperSearchTool()
    results = tool.search_videos(query, num_results)

    return [
        {
            "title": v.title,
            "url": v.url,
            "channel": v.channel,
            "duration": v.duration,
            "thumbnail": v.thumbnail
        }
        for v in results
    ]


if __name__ == "__main__":
    # Test the tool
    tool = SerperSearchTool()

    print("=== Web Search Test ===")
    web_results = tool.search("best restaurants in Jaipur", num_results=3)
    print(tool.format_web_results(web_results))

    print("\n=== Video Search Test ===")
    video_results = tool.search_videos("Amber Fort travel guide", num_results=3)
    print(tool.format_video_results(video_results))
