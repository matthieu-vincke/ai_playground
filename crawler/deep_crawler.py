import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from agno.document.base import Document
from crawl4ai.deep_crawling.filters import (
    FilterChain,
    ContentTypeFilter
)

from download import extract_document_links, download_documents_async
from utils.logger import get_logger

logger = get_logger(__name__)
today_str = datetime.now().strftime("%Y-%m-%d")


def hash_content(content: str) -> str:
    """
    Compute a SHA-256 hash of the given text content.

    This is used to identify and skip duplicate pages during the crawl.

    Parameters:
        content (str): The text content to hash.

    Returns:
        str: The SHA-256 hash of the input string.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def crawl_website_for_documents(
    website_url: str,
    metadata: Dict = None,
    max_depth: int = 5,
    word_count_threshold: int = 200,
    document_extensions: Optional[List[str]] = None, # New argument
) -> Dict[str, Any]: # Changed return type to Dict
    """
    Asynchronously crawls a website and returns a list of deduplicated, cleaned `Document` objects
    and a list of extracted document URLs.

    This function uses a BFS deep crawling strategy and filters out pages with low content or
    duplicate text. HTML content is converted to Markdown before being packaged as a agno
    `Document`.

    Parameters:
        website_url (str): The root URL to start crawling from.
        metadata (Dict, optional): Additional metadata to attach to each `Document`.
        max_depth (int, optional): Maximum link-following depth for the crawl. Default is 5.
        word_count_threshold (int, optional): Minimum number of words required to retain a page. Default is 200.
        document_extensions (List[str], optional): List of file extensions to extract document links.
                                                    E.g., [".pdf", ".docx"]. Defaults to DEFAULT_EXTENSIONS.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - "documents": List[Document]: A list of agno `Document` objects.
            - "document_urls": List[str]: A list of unique URLs to documents found on the website.

    Notes:
        - Duplicate documents (based on text hash) are skipped.
        - Empty or non-substantive pages are ignored.
        - Metadata includes crawl depth, source URL, and crawl date.
    """
    metadata = metadata or {}
    logger.info(f"Starting deep crawl of {website_url}")
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Initialize Markdown generator with options for cleaner output
    md_generator = DefaultMarkdownGenerator(
        options={
            "ignore_links": True,
            "ignore_images": True,
            "escape_html": False,
            "body_width": 80,
            "skip_internal_links": True,
            "include_sup_sub": True,
        }
    )

    allowed_data_types = [
        "text/html",
        "application/json",
        "text/plain",
        "application/xml",
        "text/xml",
        # Add other content types you want to include, but specifically exclude image types.
    ]

    # Create a filter chain to only allow specified content types
    filter_chain = FilterChain([
        ContentTypeFilter(allowed_types=allowed_data_types)
    ])

    # Configure the crawling run
    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=max_depth,
            include_external=False,
            filter_chain=filter_chain,

        ),
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
        word_count_threshold=word_count_threshold,
        scan_full_page=True,
        process_iframes=True,
        simulate_user=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
    )

    cleaned_docs = []
    seen_hashes = set()
    all_document_urls = set() # Use a set to store unique document URLs

    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(website_url, config=config)
        logger.info(f"Crawled {len(results)} pages")

        for result in results:
            text = result.markdown
            url = result.url
            html_content = result.html # Access raw HTML to extract document links

            # Extract document links from the current page's HTML
            if document_extensions:
                extracted_page_document_urls = extract_document_links(
                    html_content, url, document_extensions
                )
                all_document_urls.update(extracted_page_document_urls)


            if not text:
                logger.warning(f"Empty text skipped: {url}")
                continue

            content_hash = hash_content(text.strip())
            if content_hash in seen_hashes:
                logger.info(f"Duplicate content skipped: {url}")
                continue
            seen_hashes.add(content_hash)

            doc_metadata = {
                "source": url,
                "markdown": text,
                "depth": result.metadata.get("depth", 0),
                "website": website_url,
                "parsing_date": today_str,
            }
            doc_metadata.update(metadata)

            cleaned_docs.append(Document(content=text, meta_data=doc_metadata, name="GG"))

    logger.info(f"Returning {len(cleaned_docs)} documents and {len(all_document_urls)} document URLs")
    return {"documents": cleaned_docs, "document_urls": list(all_document_urls)}

if __name__ == "__main__":
    async def main():
        website_to_crawl = "https://docs.agno.com/" 
        download_dir = "downloaded_extracted_docs"
        
        # Example of crawling and extracting specific document types
        crawl_results = await crawl_website_for_documents(
            website_to_crawl,
            max_depth=1,
            document_extensions=[".pdf", ".xlsx"], # Specify extensions to look for
        )

        documents = crawl_results["documents"]
        extracted_doc_urls = crawl_results["document_urls"]

        print(f"\n--- Crawled Documents ({len(documents)}) ---")
        for i, doc in enumerate(documents[:3]): # Print details of first 3 documents
            print(f"Document {i+1} from {doc.meta_data.get('source')}:")
            print(f"  Content length: {len(doc.content)} characters")
            print(f"  Depth: {doc.meta_data.get('depth')}")
            print("-" * 20)

        print(f"\n--- Extracted Document URLs ({len(extracted_doc_urls)}) ---")
        for url in extracted_doc_urls[:5]: # Print first 5 extracted URLs
            print(url)

        # Optionally, download the extracted documents
        if extracted_doc_urls:
            print(f"\n--- Attempting to download extracted documents to {download_dir} ---")
            download_results = await download_documents_async(extracted_doc_urls, download_dir)
            print(f"Download Summary: {download_results}")
            
    # To run the async main function
    import asyncio
    asyncio.run(main())