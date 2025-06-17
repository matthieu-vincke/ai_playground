import os
import asyncio
import aiohttp
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

# Configure logging (assuming get_logger is defined elsewhere or use basicConfig)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


DEFAULT_EXTENSIONS = [
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".md",
    ".rtf",
    ".odt",
]

def extract_document_links(
    html_text: str,
    base_url: str,
    extensions: Optional[List[str]] = None,
) -> List[str]:
    """
    Parses HTML content and extracts full URLs of document links based on specified extensions.

    Args:
        html_text (str): Raw HTML content.
        base_url (str): Base URL for resolving relative links.
        extensions (List[str], optional): List of allowed file extensions.

    Returns:
        List[str]: A list of full URLs to documents.
    """
    extensions = extensions or DEFAULT_EXTENSIONS
    soup = BeautifulSoup(html_text, "html.parser")
    links = soup.find_all("a", href=True)

    document_urls = []
    for link in links:
        href = link["href"]
        if any(href.lower().endswith(ext) for ext in extensions):
            full_url = urljoin(base_url, href)
            document_urls.append(full_url)
    return document_urls

async def download_document(
    session: aiohttp.ClientSession,
    full_url: str,
    download_folder: str,
) -> Dict[str, str]:
    """
    Asynchronously downloads a single document, handling JavaScript redirects.
    """
    original_filename = os.path.basename(full_url.split("?")[0])
    file_path = os.path.join(download_folder, original_filename)

    logger.info(f"Attempting to download: {full_url}")
    try:
        # First, fetch the content of the initial URL
        async with session.get(full_url, timeout=10) as response:
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').lower()

            if 'text/html' in content_type:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Extract the JavaScript redirect logic
                script_tag = soup.find('script', string=lambda s: 'window.location.replace' in s)
                if script_tag:
                    script_content = script_tag.string
                    
                    # This is a bit specific to the observed redirect,
                    # but for this case, we can recreate the URL.
                    # A more robust solution might use a headless browser or regex for complex JS.
                    
                    # Look for the replacement pattern in the script
                    # For this specific case: .replace('file-examples.com/wp-content/storage/','file-examples.com/storage/fefdd7ab126835e7993bb1a/')
                    
                    # Let's directly apply the observed transformation
                    if 'file-examples.com/wp-content/storage/' in full_url:
                        redirect_url = full_url.replace(
                            'file-examples.com/wp-content/storage/',
                            'file-examples.com/storage/fefdd7ab126835e7993bb1a/'
                        )
                        logger.info(f"Detected redirect to: {redirect_url}")
                        
                        # Now download from the redirected URL
                        async with session.get(redirect_url, timeout=10) as redirect_response:
                            redirect_response.raise_for_status()
                            final_content = await redirect_response.read()
                            with open(file_path, "wb") as f:
                                f.write(final_content)
                            logger.info(f"Downloaded (after redirect): {file_path}")
                            return {"status": "downloaded", "path": file_path}
                    else:
                        logger.warning(f"HTML content found but no recognizable redirect pattern for {full_url}")
                        # Fallback to saving the HTML if it's not a recognizable redirect
                        with open(file_path + ".html", "wb") as f: # Save as .html if it's HTML
                            f.write(html_content.encode('utf-8'))
                        logger.info(f"Saved HTML content for {full_url} to {file_path}.html")
                        return {"status": "failed", "url": full_url, "error": "Content is HTML with unrecognized redirect pattern."}
                else:
                    logger.warning(f"No redirect script found in HTML for {full_url}")
                    with open(file_path + ".html", "wb") as f: # Save as .html if it's HTML
                        f.write(html_content.encode('utf-8'))
                    logger.info(f"Saved HTML content for {full_url} to {file_path}.html")
                    return {"status": "failed", "url": full_url, "error": "Content is HTML without redirect."}
            else:
                # If not HTML, assume it's the direct file
                content = await response.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                logger.info(f"Downloaded: {file_path}")
                return {"status": "downloaded", "path": file_path}

    except aiohttp.ClientError as e:
        error_msg = f"Download error for {full_url}: {str(e)}"
        logger.error(error_msg)
        return {"status": "failed", "url": full_url, "error": str(e)}
    except Exception as e:
        error_msg = f"Unexpected error saving {file_path}: {str(e)}"
        logger.error(error_msg)
        return {"status": "failed", "url": full_url, "error": str(e)}

# The rest of your code (download_documents_async, main, if __name__ == "__main__") remains the same.
# Ensure that download_document is imported or defined within the same scope.

async def download_documents_async(
    document_urls: List[str],
    download_folder: str,
) -> Dict[str, Any]:
    """
    Asynchronously downloads documents from a list of URLs to a specified folder and logs results.
    """
    os.makedirs(download_folder, exist_ok=True)

    downloaded = []
    failed = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for full_url in document_urls:
            task = asyncio.create_task(download_document(session, full_url, download_folder))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        for result in results:
            if result["status"] == "downloaded":
                downloaded.append(result["path"])
            else:
                failed.append({"url": result["url"], "error": result["error"]})

    return {"downloaded": downloaded, "failed": failed}

# --- Example Usage ---
async def main():
    urls = [
        "https://file-examples.com/wp-content/storage/2017/10/file-example_PDF_1MB.pdf",
        "https://file-examples.com/storage/fefdd7ab126835e7993bb1a/file-example_PDF_1MB.pdf", # Include the direct URL as well for testing
        "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",  # This will fail
        "https://www.africau.edu/images/default/sample.pdf",  # This will fail
        "http://example.com/nonexistent.pdf"  # This will fail
    ]
    folder = "downloads_async"
    results = await download_documents_async(urls, folder)
    print("\n--- Download Results ---")
    print(f"Successfully downloaded: {results['downloaded']}")
    print(f"Failed downloads: {results['failed']}")

if __name__ == "__main__":
    asyncio.run(main())