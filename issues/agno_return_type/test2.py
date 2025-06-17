
from agno.tools.reasoning import ReasoningTools
from agno.knowledge.url import UrlKnowledge
from agno.embedder.openai import OpenAIEmbedder
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.agent import AgentKnowledge
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.agent import Agent, RunResponse  # noqa
from agno.vectordb.mongodb import MongoDb
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
print("Loaded environment variables from .env file.")

embeddings = SentenceTransformerEmbedder().get_embedding(
    "The quick brown fox jumps over the lazy dog."
)

# Print the embeddings and their dimensions
print(f"Embeddings: {embeddings[:5]}")
print(f"Dimensions: {len(embeddings)}")

# Load Agno documentation in a knowledge base
knowledge = UrlKnowledge(
    urls=["https://docs.agno.com/introduction/agents.md"],
    vector_db=MongoDb(
        embedder=SentenceTransformerEmbedder(
        ),
        collection_name=os.getenv(
            "MONGO_COLLECTION_TEST", "issue_test"
        ),
        db_url=os.getenv("MONGO_CONNECTION_STRING"),
        database=os.getenv("MONGO_DB", "AI_Worflows"),
        wait_until_index_ready_in_seconds=30,
        wait_after_insert_in_seconds=30,
    )
)

agent = Agent(
    name="Agno Assist",
    instructions=[
        "Use tables to display data.",
        "Include sources in your response.",
        "Search your knowledge before answering the question.",
        "Only include the output in your response. No other text.",
    ],
    knowledge=knowledge,
    tools=[ReasoningTools(add_instructions=True)],
    add_datetime_to_instructions=True,
    markdown=True,
)

if __name__ == "__main__":
    # Load the knowledge base, comment out after first run
    # Set recreate to True to recreate the knowledge base if needed
    agent.knowledge.load(recreate=True)
    agent.print_response(
        "What are Agents?",
        stream=True,
        show_full_reasoning=True,
        stream_intermediate_steps=True,
    )