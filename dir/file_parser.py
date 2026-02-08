import re
from typing import List, Dict, Optional

class FileAction:
    def __init__(self, path: str, content: str):
        self.path = path
        self.content = content

    def to_dict(self):
        return {"path": self.path, "content": self.content}

def parse_multi_file_response(text: str) -> List[FileAction]:
    actions = []
    
    # XML-stijl: <file path="naam">content</file>
    xml_pattern = r'<file\s+path=["\'](.*?)["\']>(.*?)</file>'
    matches = re.finditer(xml_pattern, text, re.DOTALL)
    for match in matches:
        path = match.group(1).strip()
        content = match.group(2).strip()
        actions.append(FileAction(path, content))
    
    # Markdown-stijl: ```python # file: naam ... ```
    if not actions:
        markdown_pattern = r'```(?:\w+)?\s*\n(?:#|//)\s*file:\s*([^\n]+)\n(.*?)\n```'
        matches = re.finditer(markdown_pattern, text, re.DOTALL)
        for match in matches:
            path = match.group(1).strip()
            content = match.group(2).strip()
            actions.append(FileAction(path, content))
            
    return actions

def extract_clean_text(text: str) -> str:
    # Verwijder file tags voor een schone weergave in de chat
    text = re.sub(r'<file\s+path=["\'].*?["\']>.*?</file>', '[Bestand gegenereerd]', text, flags=re.DOTALL)
    return text.strip()
