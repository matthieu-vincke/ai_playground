import os
import json
from typing import List, Optional, Dict

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.mongodb import MongoDbStorage
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.newspaper4k import Newspaper4kTools
from pydantic import BaseModel, ValidationError
from agno.utils.log import logger
from agno.models.groq import Groq
from agno.workflow import RunResponse  # Added this import

from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv("MONGO_CONNECTION_STRING")

class Article(BaseModel):
    title: str
    summary: str
    reference_links: List[str]

class Articles(BaseModel):
    articles: List[Article]

class HackerNewsTeam(Team):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_state = {
            "hn_stories": {},
            "web_search_results": {},
            "article_contents": {}
        }

    def get_cached_hn_stories(self, query: str) -> Optional[List[dict]]:
        logger.info(f"Checking cached HackerNews stories for query: {query}")
        return self.session_state['hn_stories'].get(query)

    def add_hn_stories_to_cache(self, query: str, stories: List[str]):
        logger.info(f"Caching HackerNews stories for query: {query}")
        self.session_state['hn_stories'][query] = stories

    def get_cached_web_search(self, story: str) -> Optional[List[str]]:
        logger.info(f"Checking cached web search results for story: {story}")
        return self.session_state['web_search_results'].get(story)

    def add_web_search_to_cache(self, story: str, search_results: List[str]):
        logger.info(f"Caching web search results for story: {story}")
        self.session_state['web_search_results'][story] = search_results

    def get_cached_article_content(self, url: str) -> Optional[str]:
        logger.info(f"Checking cached article content for URL: {url}")
        return self.session_state['article_contents'].get(url)

    def add_article_content_to_cache(self, url: str, content: str):
        logger.info(f"Caching article content for URL: {url}")
        self.session_state['article_contents'][url] = content

    def run(
        self, 
        query: str, 
        use_hn_cache: bool = True, 
        use_web_search_cache: bool = True,
        use_article_cache: bool = True,
        num_stories: int = 2
    ):
        logger.info(f"Running HackerNews Team for query: {query}")

        # Check cached HackerNews stories if cache is enabled
        if use_hn_cache:
            cached_stories = self.get_cached_hn_stories(query)
            if cached_stories:
                logger.info("Using cached HackerNews stories")
                return self._process_cached_stories(cached_stories)

        try:
            # Fetch HackerNews stories
            hn_results = self.members[0].run(query)
            
            # Extract actual stories from RunResponse
            if isinstance(hn_results, RunResponse):
                hn_stories = hn_results.content
            else:
                hn_stories = hn_results

            # Ensure hn_stories is a list
            if not isinstance(hn_stories, list):
                hn_stories = [str(hn_stories)]
            
            # Cache HackerNews stories
            self.add_hn_stories_to_cache(query, hn_stories)

            # For each story, do web search with caching
            processed_articles = []
            for story in hn_stories[:num_stories]:
                # Check web search cache if enabled
                web_links = None
                if use_web_search_cache:
                    web_links = self.get_cached_web_search(story)
                
                # If no cached web search results, perform web search
                if not web_links:
                    web_search_results = self.members[1].run(story)
                    
                    # Extract links from web search results
                    if isinstance(web_search_results, RunResponse):
                        web_links = web_search_results.content
                    else:
                        web_links = web_search_results
                    
                    # Ensure web_links is a list
                    if not isinstance(web_links, list):
                        web_links = [str(web_links)]
                    
                    # Cache web search results if caching is enabled
                    if use_web_search_cache:
                        self.add_web_search_to_cache(story, web_links)

                # Read articles
                article_contents = []
                for link in web_links:
                    # Check article cache if enabled
                    article_content = None
                    if use_article_cache:
                        article_content = self.get_cached_article_content(link)
                    
                    # If no cached article content, read the article
                    if not article_content:
                        article_result = self.members[2].run(link)
                        
                        # Extract content from RunResponse if needed
                        if isinstance(article_result, RunResponse):
                            article_content = article_result.content
                        else:
                            article_content = article_result

                        # Cache article content if caching is enabled
                        if use_article_cache:
                            self.add_article_content_to_cache(link, article_content)

                    article_contents.append(article_content)

                # Create Article object
                processed_article = Article(
                    title=story,
                    summary=" ".join([str(content) for content in article_contents]),
                    reference_links=web_links
                )
                processed_articles.append(processed_article)

            return Articles(articles=processed_articles)

        except Exception as e:
            logger.error(f"Error in HackerNews Team run: {e}")
            raise

    def _process_cached_stories(self, cached_stories):
        """Process cached stories to maintain the same interface."""
        try:
            processed_articles = [
                Article(
                    title=story,
                    summary="Cached story summary",
                    reference_links=[]
                ) for story in cached_stories
            ]
            return Articles(articles=processed_articles)
        except Exception as e:
            logger.error(f"Error processing cached stories: {e}")
            raise

hn_researcher = Agent(
    name="HackerNews Researcher",
    model=Groq(
        id="qwen-qwq-32b"
    ), 
    #model=OpenAIChat("gpt-4o"),
    role="Gets top stories from hackernews.",
    tools=[HackerNewsTools()],
)

web_searcher = Agent(
    name="Web Searcher",
    model=Groq(
        id="qwen-qwq-32b"
    ), 
    #model=OpenAIChat("gpt-4o"),
    role="Searches the web for information on a topic",
    tools=[DuckDuckGoTools()],
    add_datetime_to_instructions=True,
)

article_reader = Agent(
    name="Article Reader",
    model=Groq(
        id="qwen-qwq-32b"
    ), 
    role="Reads articles from URLs.",
    tools=[Newspaper4kTools()],
)

hn_team = HackerNewsTeam(
    name="HackerNews Team",
    mode="coordinate",
    model=Groq(
        id="qwen-qwq-32b"
    ), 
    #model=OpenAIChat("gpt-4o"),
    members=[hn_researcher, web_searcher, article_reader],
    storage=MongoDbStorage(
        collection_name="team_sessions", db_url=db_url, db_name="agno"
    ),
    instructions=[
        "First, search hackernews for what the user is asking about.",
        "Then, ask the web searcher to search for each story to get more information.",
        "Then, ask the article reader to read the links for the stories to get more information.",
        "Finally, provide a thoughtful and engaging summary.",
    ],
    response_model=Articles,
    show_tool_calls=True,
    markdown=True,
    debug_mode=True,
    show_members_responses=True,
)

try:
    reports = hn_team.run(
        "Write an article about the top 2 stories on hackernews",
        use_hn_cache=True,
        use_web_search_cache=True,
        use_article_cache=True
    )
    
    print("Raw response:", reports)
    
    # Correctly access the content
    for report in reports.articles:
        print(f"Title: {report.title}")
        print(f"Summary: {report.summary}")
        print(f"Reference Links: {report.reference_links}")
        print("---")

except Exception as e:
    print(f"An error occurred: {e}")