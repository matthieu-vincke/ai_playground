from urllib.parse import urlparse

def get_website_name_from_url(url: str) -> str:
    """
    Extracts the main website name from a given URL.

    Args:
        url (str): The input URL.

    Returns:
        str: The extracted website name (e.g., "gluegang").
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    # Remove "www." if present and split by "." to get the name
    if domain.startswith("www."):
        domain = domain[4:]
    name_parts = domain.split('.')
    if name_parts:
        return name_parts[0]
    return ""