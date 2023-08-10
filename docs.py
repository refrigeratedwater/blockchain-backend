from docx import Document

class Docs:
    def __init__(self, file):
        self.file = file
        self.metadata: dict[str, str] = self.get_metadata()
        
    def get_metadata(self) -> dict[str, str]:
        document = Document(self.file)
        meta = document.core_properties
        return {
            "author": meta.author,
            "created": meta.created.isoformat() if meta.created else None,
            "last_modified_by": meta.last_modified_by,
            "title": meta.title,
            "version": meta.version,
            "name": self.file.filename,
        }