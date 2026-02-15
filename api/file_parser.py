# api/file_parser.py

class FileAction:
    def __init__(self, path, content):
        self.path = path
        self.content = content

    def to_dict(self):
        return {"path": self.path, "content": self.content}

def parse_multi_file_response(response_text):
    """
    Placeholder for parsing multi-file responses.
    In a real implementation, this would parse the BEGIN_FILE/END_FILE markers
    and extract file paths and content.
    """
    return []

def extract_clean_text(text):
    """
    Placeholder for extracting clean text.
    In a real implementation, this would remove any watermarks or unwanted text.
    """
    return text