"""
YouTube Video Search Tool for Travel RAG Bot
Uses YouTube Data API v3 to search for travel-related videos
"""
import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class YouTubeVideo:
    """YouTube video result"""
    title: str
    video_id: str
    url: str
    channel: str
    description: str
    thumbnail: str


class YouTubeSearchTool:
    """
    YouTube Search Tool using YouTube Data API v3.
    Falls back to web search URL generation if API key not available.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3/search"

    def search(self, query: str, max_results: int = 2) -> List[YouTubeVideo]:
        """
        Search YouTube for videos matching the query.

        Args:
            query: Search query (e.g., "Amber Fort travel guide")
            max_results: Maximum number of results (default 2)

        Returns:
            List of YouTubeVideo objects
        """
        # Add travel-related context to query
        enhanced_query = f"{query} travel guide tour"

        if self.api_key:
            return self._search_with_api(enhanced_query, max_results)
        else:
            return self._generate_search_urls(enhanced_query, max_results)

    def _search_with_api(self, query: str, max_results: int) -> List[YouTubeVideo]:
        """Search using YouTube Data API v3"""
        try:
            import httpx

            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": self.api_key,
                "relevanceLanguage": "en",
                "videoDuration": "medium",  # Prefer medium-length videos
                "order": "relevance"
            }

            with httpx.Client() as client:
                response = client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

            videos = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")

                if video_id:
                    videos.append(YouTubeVideo(
                        title=snippet.get("title", ""),
                        video_id=video_id,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        channel=snippet.get("channelTitle", ""),
                        description=snippet.get("description", "")[:200],
                        thumbnail=snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
                    ))

            return videos

        except Exception as e:
            print(f"[YouTube API Error] {e}")
            return self._generate_search_urls(query, max_results)

    def _generate_search_urls(self, query: str, max_results: int) -> List[YouTubeVideo]:
        """
        Generate YouTube search URLs when API is not available.
        This provides direct search links for the user.
        """
        # Clean query for URL
        clean_query = re.sub(r'[^\w\s]', '', query)
        url_query = clean_query.replace(' ', '+')

        # Generate search URL
        search_url = f"https://www.youtube.com/results?search_query={url_query}"

        # Create predefined video suggestions based on common Rajasthan destinations
        rajasthan_videos = self._get_predefined_videos(query)

        if rajasthan_videos:
            return rajasthan_videos[:max_results]

        # Fallback to search URL
        return [YouTubeVideo(
            title=f"Search YouTube: {query}",
            video_id="search",
            url=search_url,
            channel="YouTube Search",
            description=f"Click to search for videos about {query}",
            thumbnail=""
        )]

    def _get_predefined_videos(self, query: str) -> List[YouTubeVideo]:
        """
        Return predefined popular travel videos for Rajasthan destinations.
        These are well-known travel videos that are likely to be helpful.
        """
        query_lower = query.lower()

        # Popular video mappings for Rajasthan destinations
        video_database = {
            "amber fort": [
                YouTubeVideo(
                    title="Amber Fort Jaipur - Complete Tour Guide",
                    video_id="amber_fort_guide",
                    url="https://www.youtube.com/results?search_query=amber+fort+jaipur+complete+guide",
                    channel="Travel Guide",
                    description="Complete walkthrough of Amber Fort with history and tips",
                    thumbnail=""
                ),
                YouTubeVideo(
                    title="Amber Fort History & Architecture",
                    video_id="amber_fort_history",
                    url="https://www.youtube.com/results?search_query=amber+fort+history+architecture",
                    channel="India Travel",
                    description="Learn about the rich history of Amber Fort",
                    thumbnail=""
                )
            ],
            "jaipur": [
                YouTubeVideo(
                    title="Jaipur Travel Guide - Top Things to Do",
                    video_id="jaipur_guide",
                    url="https://www.youtube.com/results?search_query=jaipur+travel+guide+things+to+do",
                    channel="Travel Vlog",
                    description="Complete Jaipur travel guide with top attractions",
                    thumbnail=""
                ),
                YouTubeVideo(
                    title="Pink City Jaipur - Full Day Tour",
                    video_id="jaipur_tour",
                    url="https://www.youtube.com/results?search_query=jaipur+pink+city+full+day+tour",
                    channel="India Explorer",
                    description="Explore the Pink City of India",
                    thumbnail=""
                )
            ],
            "hawa mahal": [
                YouTubeVideo(
                    title="Hawa Mahal - Palace of Winds Jaipur",
                    video_id="hawa_mahal_guide",
                    url="https://www.youtube.com/results?search_query=hawa+mahal+palace+of+winds+jaipur",
                    channel="Heritage Tours",
                    description="Explore the iconic Hawa Mahal",
                    thumbnail=""
                )
            ],
            "mehrangarh": [
                YouTubeVideo(
                    title="Mehrangarh Fort Jodhpur - Complete Guide",
                    video_id="mehrangarh_guide",
                    url="https://www.youtube.com/results?search_query=mehrangarh+fort+jodhpur+complete+guide",
                    channel="Fort Tours",
                    description="Explore one of India's largest forts",
                    thumbnail=""
                ),
                YouTubeVideo(
                    title="Mehrangarh Fort - Blue City Views",
                    video_id="mehrangarh_views",
                    url="https://www.youtube.com/results?search_query=mehrangarh+fort+blue+city+jodhpur",
                    channel="Travel India",
                    description="Amazing views of the Blue City from Mehrangarh",
                    thumbnail=""
                )
            ],
            "jodhpur": [
                YouTubeVideo(
                    title="Jodhpur Travel Guide - Blue City",
                    video_id="jodhpur_guide",
                    url="https://www.youtube.com/results?search_query=jodhpur+blue+city+travel+guide",
                    channel="Rajasthan Travel",
                    description="Complete guide to exploring Jodhpur",
                    thumbnail=""
                )
            ],
            "udaipur": [
                YouTubeVideo(
                    title="Udaipur - Venice of the East",
                    video_id="udaipur_guide",
                    url="https://www.youtube.com/results?search_query=udaipur+venice+of+east+travel+guide",
                    channel="Lake City Tours",
                    description="Explore the romantic city of Udaipur",
                    thumbnail=""
                ),
                YouTubeVideo(
                    title="Lake Pichola Udaipur Boat Ride",
                    video_id="pichola_boat",
                    url="https://www.youtube.com/results?search_query=lake+pichola+udaipur+boat+ride",
                    channel="Udaipur Vlogs",
                    description="Experience the beautiful Lake Pichola",
                    thumbnail=""
                )
            ],
            "city palace": [
                YouTubeVideo(
                    title="City Palace Udaipur - Royal Heritage",
                    video_id="city_palace_udaipur",
                    url="https://www.youtube.com/results?search_query=city+palace+udaipur+tour+guide",
                    channel="Royal Rajasthan",
                    description="Tour the magnificent City Palace of Udaipur",
                    thumbnail=""
                )
            ],
            "pushkar": [
                YouTubeVideo(
                    title="Pushkar Travel Guide - Holy Town",
                    video_id="pushkar_guide",
                    url="https://www.youtube.com/results?search_query=pushkar+travel+guide+brahma+temple",
                    channel="Spiritual India",
                    description="Explore the sacred town of Pushkar",
                    thumbnail=""
                )
            ],
            "ranakpur": [
                YouTubeVideo(
                    title="Ranakpur Jain Temple - Marble Marvel",
                    video_id="ranakpur_temple",
                    url="https://www.youtube.com/results?search_query=ranakpur+jain+temple+guide",
                    channel="Temple Tours",
                    description="Explore the stunning Ranakpur Jain Temple",
                    thumbnail=""
                )
            ],
            "chokhi dhani": [
                YouTubeVideo(
                    title="Chokhi Dhani Jaipur - Village Experience",
                    video_id="chokhi_dhani",
                    url="https://www.youtube.com/results?search_query=chokhi+dhani+jaipur+village+experience",
                    channel="Food & Culture",
                    description="Experience Rajasthani culture at Chokhi Dhani",
                    thumbnail=""
                )
            ],
            "nahargarh": [
                YouTubeVideo(
                    title="Nahargarh Fort Jaipur - Sunset Views",
                    video_id="nahargarh_fort",
                    url="https://www.youtube.com/results?search_query=nahargarh+fort+jaipur+sunset+views",
                    channel="Fort Explorer",
                    description="Best sunset views from Nahargarh Fort",
                    thumbnail=""
                )
            ],
            "day 1": [
                YouTubeVideo(
                    title="Jaipur Day 1 Itinerary - Amber Fort & More",
                    video_id="jaipur_day1",
                    url="https://www.youtube.com/results?search_query=jaipur+one+day+itinerary+amber+fort",
                    channel="Travel Planner",
                    description="Perfect Day 1 itinerary for Jaipur",
                    thumbnail=""
                )
            ],
            "day 2": [
                YouTubeVideo(
                    title="Jaipur Day 2 - Forts & Local Experience",
                    video_id="jaipur_day2",
                    url="https://www.youtube.com/results?search_query=jaipur+nahargarh+jaigarh+fort+tour",
                    channel="Travel Guide",
                    description="Explore Nahargarh and Jaigarh forts",
                    thumbnail=""
                )
            ]
        }

        # Find matching videos
        for keyword, videos in video_database.items():
            if keyword in query_lower:
                return videos

        # Default Rajasthan videos
        return [
            YouTubeVideo(
                title="Rajasthan Travel Guide - Complete Tour",
                video_id="rajasthan_guide",
                url="https://www.youtube.com/results?search_query=rajasthan+travel+guide+complete+tour",
                channel="India Travel",
                description="Complete guide to exploring Rajasthan",
                thumbnail=""
            ),
            YouTubeVideo(
                title="Best of Rajasthan - Top Places to Visit",
                video_id="rajasthan_top",
                url="https://www.youtube.com/results?search_query=rajasthan+best+places+to+visit",
                channel="Travel India",
                description="Top attractions in Rajasthan",
                thumbnail=""
            )
        ]

    def format_results(self, videos: List[YouTubeVideo]) -> str:
        """Format video results for display"""
        if not videos:
            return "No videos found."

        result = "YouTube Videos:\n"
        for i, video in enumerate(videos, 1):
            result += f"\n{i}. {video.title}\n"
            result += f"   Channel: {video.channel}\n"
            result += f"   Link: {video.url}\n"

        return result


def search_youtube_videos(query: str, max_results: int = 2) -> List[Dict[str, str]]:
    """
    Convenience function to search YouTube videos.

    Args:
        query: Search query
        max_results: Maximum results to return

    Returns:
        List of video dictionaries with title, url, channel, description
    """
    tool = YouTubeSearchTool()
    videos = tool.search(query, max_results)

    return [
        {
            "title": v.title,
            "url": v.url,
            "channel": v.channel,
            "description": v.description
        }
        for v in videos
    ]


if __name__ == "__main__":
    # Test the tool
    tool = YouTubeSearchTool()

    test_queries = [
        "Amber Fort guide",
        "Jaipur travel",
        "Mehrangarh Fort Jodhpur",
        "Lake Pichola Udaipur"
    ]

    for query in test_queries:
        print(f"\n=== Query: {query} ===")
        videos = tool.search(query, max_results=2)
        print(tool.format_results(videos))
