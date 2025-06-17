import os
from dotenv import load_dotenv
from agno.document.base import Document
from agno.knowledge.document import DocumentKnowledgeBase
from agno.agent import Agent
from agno.vectordb.mongodb import MongoDb
from agno.storage.mongodb import MongoDbStorage
from rich.pretty import pprint
import asyncio
from agno.models.groq import Groq
from textwrap import dedent
from agno.tools.tavily import TavilyTools
from agno.knowledge.docx import DocxKnowledgeBase
from collections import defaultdict
from pathlib import Path
from agno.models.openai import OpenAIChat
from deep_crawler import crawl_website_for_documents
from download import download_documents_async
from utils.web import get_website_name_from_url
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.knowledge.combined import CombinedKnowledgeBase
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
import pickle
from bson.binary import Binary, USER_DEFINED_SUBTYPE
from bson.codec_options import TypeCodec, TypeRegistry, CodecOptions
import numpy as np


# Import logger
from utils.logger import get_logger

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()
logger.info("Loaded environment variables from .env file.")


def numpy_array_encoder(o):
    if isinstance(o, np.ndarray):
        return o.tolist()  # Convert to list for BSON serialization
    raise TypeError(repr(o) + " is not JSON serializable")  # Or BSON serializable


def get_mongodb(collection_name: str, db_url: str, database: str) -> MongoDb:
    """
    Initialize and return a MongoDb instance for vector storage.
    Uses environment variables for configuration.
    """
    return MongoDb(
        embedder=SentenceTransformerEmbedder(
            dimensions=768, id="sentence-transformers/all-mpnet-base-v2"
        ),
        collection_name=collection_name,
        db_url=db_url,
        database=database,
        wait_until_index_ready_in_seconds=30,
        wait_after_insert_in_seconds=30,
    )


async def download_specific_document_type(
    doc_urls: list[str], file_extensions: list[str], base_download_dir: Path
) -> dict[str, Path]:
    """
    Downloads documents of specified file types from a list of URLs and returns
    a map of document types to their respective download directory paths.

    Args:
        doc_urls: A list of URLs to potentially download documents from.
        file_extensions: A list of file extensions to filter for (e.g., ["docx", "pdf"]).
        base_download_dir: The base directory where subdirectories for each file type
                           will be created for downloads.

    Returns:
        A dictionary mapping document type (e.g., "docx") to its download Path.
        Directories are created for all specified types, even if no files are downloaded.
    """

    # Normalize file extensions: ensure they start with a dot and are lowercase
    normalized_extensions = [
        f".{ext.lower()}" if not ext.startswith(".") else ext.lower()
        for ext in file_extensions
    ]

    # Initialize the dictionary to store paths to created directories
    # and to group links by their respective file type
    download_paths: dict[str, Path] = {}
    grouped_links = defaultdict(list)  # Using defaultdict for convenience

    # First, create all target directories and populate download_paths
    for ext_with_dot in normalized_extensions:
        type_name = ext_with_dot[1:]  # e.g., "docx", "pdf"
        path_type_dir = base_download_dir / type_name
        path_type_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Ensured directory exists for {type_name.upper()} files: {path_type_dir}"
        )
        download_paths[type_name] = path_type_dir

    # Now, filter and group the URLs
    if doc_urls:
        for url in doc_urls:
            url_lower = url.lower()
            for ext_with_dot in normalized_extensions:
                if url_lower.endswith(ext_with_dot):
                    grouped_links[ext_with_dot].append(url)
                    break  # Assuming a URL belongs to only one of the specified types

    # Finally, perform downloads for found links
    for ext_with_dot in normalized_extensions:
        type_name = ext_with_dot[1:]
        links = grouped_links[
            ext_with_dot
        ]  # Will be an empty list if no links found for this type
        path_type_dir = download_paths[type_name]  # Retrieve the path created earlier

        if links:
            logger.info(
                f"Found {len(links)} {type_name.upper()} links for download to {path_type_dir}: {links}"
            )
            await download_documents_async(links, path_type_dir)
        else:
            logger.info(f"No {type_name.upper()} links found to download.")

    return download_paths


async def main(website_url: str, insert : bool = True, recreate: bool = False, skip_agent: bool = False):
    """
    Main asynchronous function to run the web crawling, indexing, and agent interaction.
    """
    logger.info("Starting web crawling process...")
    base_downloads_path = Path("downloads")
    base_downloads_path.mkdir(
        parents=True, exist_ok=True
    )  # Ensure the base directory exists
    documents = []
    doc_urls = []
    if recreate == True or insert == True:
        logger.info("Recreating the knowledge base index as requested.")
        crawl_resuls = await crawl_website_for_documents(
            website_url=website_url,
            metadata={"source": get_website_name_from_url(website_url)},
            max_depth=1,
            word_count_threshold=200,
            document_extensions=[".pdf", ".docx"],
        )
        documents = crawl_resuls["documents"]
        doc_urls = crawl_resuls["document_urls"]
        logger.info(
            f"Crawled {len(documents)} documents and found {len(doc_urls)} document URLs."
        )

    download_paths = await download_specific_document_type(
        doc_urls, ["docx", "pdf"], base_downloads_path
    )
    print("-" * 30)

    knowledge_base_pdf = PDFKnowledgeBase(
        path=download_paths["pdf"],
        # Table name: ai.pdf_documents
        # vector_db=get_mongodb(
        #     collection_name=os.getenv(
        #         "MONGO_COLLECTION_PDF", "crawl-store-query-pdf"
        #     ),
        #     db_url=os.getenv("MONGO_CONNECTION_STRING"),
        #     database=os.getenv("MONGO_DB", "AI_Worflows")
        # ),
    )

    knowledge_base_docs = DocxKnowledgeBase(
        path=download_paths["docx"],
        # Table name: ai.docx_documents
        # vector_db=get_mongodb(
        #     collection_name=os.getenv(
        #         "MONGO_COLLECTION_DOCX", "crawl-store-query-docx"
        #     ),
        #     db_url=os.getenv("MONGO_CONNECTION_STRING"),
        #     database=os.getenv("MONGO_DB", "AI_Worflows"),
        # ),
    )

    # Create a DocumentKnowledgeBase instance
    logger.info("Initializing DocumentKnowledgeBase...")
    knowledge_base_html = DocumentKnowledgeBase(
        documents=documents,
        # vector_db=get_mongodb(
        #     collection_name=os.getenv("MONGO_COLLECTION_HTML", "crawl-store-query"),
        #     db_url=os.getenv("MONGO_CONNECTION_STRING"),
        #     database=os.getenv("MONGO_DB", "AI_Worflows"),
        # ),
    )
    logger.info("DocumentKnowledgeBase initialized.")

    knowledge_base = CombinedKnowledgeBase(
        sources=[
            knowledge_base_html,
            knowledge_base_pdf,
            knowledge_base_docs,
        ],
        vector_db=get_mongodb(
            collection_name=os.getenv(
                "MONGO_COLLECTION_GLOBAL", "crawl-store-query-global"
            ),
            db_url=os.getenv("MONGO_CONNECTION_STRING"),
            database=os.getenv("MONGO_DB", "Web_Data"),
        ),
    )

    logger.info("CombinedKnowledgeBase initialized with HTML and PDF sources.")
    logger.info("Initializing Agent...")
    agent = Agent(
        # model=OpenAIChat(id="gpt-4.1-mini"),
        model=Groq(
            id="llama-3.3-70b-versatile"
        ),  # Response is OK, not as good as openAI
        knowledge=knowledge_base,
        # tools=[TavilyTools()],
        search_knowledge=True,
        session_id="crawl-store-query-session",
        storage=MongoDbStorage(
            # store sessions in the agent_sessions collection
            collection_name="agent_sessions",
            db_url=os.getenv("MONGO_CONNECTION_STRING"),
        ),
        # add_history_to_messages=True,
        # num_history_runs=3,
        description=dedent(
            """\
            You are the best AI Agent on the planet.
            Your writing style is:
            - Enthusiastic and inspiring
            - Creative and playful
            - Detailed and practical
            - Focused on joy and memorable experiences
        """
        ),
        instructions=dedent(
            """\
           Use your knowledge to reply to the queries
        """
        ),
        expected_output=dedent(
            """\
        A fantastic reply in markdown format:
        # {Whimsical request Title That Sparks Joy}
        ## Reponse
        {Complete detailed response}
        ---
        Response crafted by the best Agent on the planet
        Date: {current_date}
        """
        ),
        markdown=True,
        show_tool_calls=True,
        add_datetime_to_instructions=True,
    )
    logger.info("Agent initialized.")

    logger.info("Loading knowledge base (and potentially recreating index)...")
    agent.knowledge.load(
        recreate=recreate,
    )
    logger.info("Knowledge base loaded.")

    print("\n--- Agent is ready. Type your questions below (type 'exit' to quit) ---\n")

    if skip_agent == False:
        while True:
            user_input = input("You: ")
            if user_input.lower() in {"exit", "quit"}:
                # pprint(agent.get_messages_for_session())
                print("Exiting the conversation. Goodbye!")
                break
            try:
                agent.print_response(user_input)
            except Exception as e:
                print(f"Error during response generation: {e}")


if __name__ == "__main__":
    asyncio.run(main("https://www.agno.com/", insert=True, recreate=True, skip_agent=False)) 
    