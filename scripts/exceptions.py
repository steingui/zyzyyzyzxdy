class InvalidDOMError(Exception):
    """Raised when the page DOM does not match the expected structure (e.g., missing stats table)."""
    pass
