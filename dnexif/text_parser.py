# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Parser for plain text files (.txt, .log, etc.).

Extracts text-specific metadata like encoding, line count, word count, and newline type.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError

# Try to import chardet, but make it optional
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


class TextParser:
    """
    Parser for plain text file metadata.
    
    Extracts:
    - Text encoding (detected via chardet)
    - Line count
    - Word count
    - Newline type (CRLF, LF, CR)
    - Character count
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize text parser.
        
        Args:
            file_path: Path to text file
            file_data: Text file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse text file metadata.
        
        Returns:
            Dictionary of text metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if not file_data:
                raise MetadataReadError("Invalid text file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'TXT'
            metadata['File:FileTypeExtension'] = 'txt'
            metadata['File:MIMEType'] = 'text/plain'
            
            # Detect encoding
            text = None
            encoding = None
            
            if HAS_CHARDET:
                try:
                    detected = chardet.detect(file_data)
                    encoding = detected.get('encoding', 'unknown')
                    confidence = detected.get('confidence', 0.0)
                    
                    if encoding and confidence > 0.5:
                        metadata['TXT:Encoding'] = encoding
                        metadata['TXT:EncodingConfidence'] = confidence
                        try:
                            text = file_data.decode(encoding)
                            metadata['TXT:MIMEEncoding'] = encoding.lower()
                        except (UnicodeDecodeError, LookupError):
                            encoding = None
                except Exception:
                    pass
            
            # Try common encodings if chardet not available or failed
            if text is None:
                for enc in ['utf-8', 'us-ascii', 'latin-1', 'cp1252']:
                    try:
                        text = file_data.decode(enc)
                        encoding = enc
                        metadata['TXT:MIMEEncoding'] = enc.lower()
                        metadata['TXT:Encoding'] = enc
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                
                # If all fail, use utf-8 with errors='ignore'
                if text is None:
                    text = file_data.decode('utf-8', errors='ignore')
                    encoding = 'utf-8'
                    metadata['TXT:MIMEEncoding'] = 'utf-8'
                    metadata['TXT:Encoding'] = 'utf-8'
            
            # Count lines
            line_count = text.count('\n')
            if text and not text.endswith('\n'):
                line_count += 1  # Last line without newline
            metadata['TXT:LineCount'] = line_count
            
            # Detect newline type
            if '\r\n' in text:
                newline_type = 'Windows CRLF'
            elif '\r' in text:
                newline_type = 'Mac CR'
            elif '\n' in text:
                newline_type = 'Unix LF'
            else:
                newline_type = 'Unknown'
            metadata['TXT:Newlines'] = newline_type
            
            # Count words (split on whitespace)
            words = text.split()
            word_count = len(words)
            metadata['TXT:WordCount'] = word_count
            
            # Character count
            char_count = len(text)
            metadata['TXT:CharacterCount'] = char_count
            
            # Byte count
            byte_count = len(file_data)
            metadata['TXT:ByteCount'] = byte_count
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse text file metadata: {str(e)}")

