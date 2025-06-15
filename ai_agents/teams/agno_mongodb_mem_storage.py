import os
import json

from typing import List

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.mongodb import MongoDbStorage
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.newspaper4k import Newspaper4kTools
from pydantic import BaseModel, ValidationError

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# MongoDB connection settings
db_url = os.getenv("MONGO_CONNECTION_STRING")


class Article(BaseModel):
    title: str
    summary: str
    reference_links: List[str]

class Articles(BaseModel):
    articles: List[Article]

hn_researcher = Agent(
    name="HackerNews Researcher",
    model=OpenAIChat("gpt-4o"),
    role="Gets top stories from hackernews.",
    tools=[HackerNewsTools()],
)

web_searcher = Agent(
    name="Web Searcher",
    model=OpenAIChat("gpt-4o"),
    role="Searches the web for information on a topic",
    tools=[DuckDuckGoTools()],
    add_datetime_to_instructions=True,
)

article_reader = Agent(
    name="Article Reader",
    role="Reads articles from URLs.",
    tools=[Newspaper4kTools()],
)


hn_team = Team(
    name="HackerNews Team",
    mode="coordinate",
    model=OpenAIChat("gpt-4o"),
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
        "Write an article about the top 2 stories on hackernews"
    )

    print("Raw response:", reports)
    
    # Correctly access the content
    for report in reports.content.articles:
        print("---")
        print(f"Title: {report.title}")
        print(f"Summary: {report.summary}")
        print(f"Reference Links: {report.reference_links}")
        print("---")

except Exception as e:
    print(f"An error occurred: {e}")