# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Parser for JSON files.

Extracts JSON-specific metadata like structure information, key count, and content analysis.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json

from dnexif.exceptions import MetadataReadError


class JSONParser:
    """
    Parser for JSON file metadata.
    
    Extracts:
    - JSON structure information (object count, array count, key count)
    - Content analysis (depth, size)
    - File metadata (already handled by _add_file_tags)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize JSON parser.
        
        Args:
            file_path: Path to JSON file
            file_data: JSON file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def _analyze_json_structure(self, obj: Any, depth: int = 0) -> Dict[str, int]:
        """
        Recursively analyze JSON structure.
        
        Args:
            obj: JSON object to analyze
            depth: Current depth level
            
        Returns:
            Dictionary with structure statistics
        """
        stats = {
            'max_depth': depth,
            'object_count': 0,
            'array_count': 0,
            'key_count': 0,
            'string_count': 0,
            'number_count': 0,
            'boolean_count': 0,
            'null_count': 0,
        }
        
        if isinstance(obj, dict):
            stats['object_count'] = 1
            stats['key_count'] = len(obj)
            for key, value in obj.items():
                nested_stats = self._analyze_json_structure(value, depth + 1)
                stats['max_depth'] = max(stats['max_depth'], nested_stats['max_depth'])
                stats['object_count'] += nested_stats['object_count']
                stats['array_count'] += nested_stats['array_count']
                stats['key_count'] += nested_stats['key_count']
                stats['string_count'] += nested_stats['string_count']
                stats['number_count'] += nested_stats['number_count']
                stats['boolean_count'] += nested_stats['boolean_count']
                stats['null_count'] += nested_stats['null_count']
        elif isinstance(obj, list):
            stats['array_count'] = 1
            for item in obj:
                nested_stats = self._analyze_json_structure(item, depth + 1)
                stats['max_depth'] = max(stats['max_depth'], nested_stats['max_depth'])
                stats['object_count'] += nested_stats['object_count']
                stats['array_count'] += nested_stats['array_count']
                stats['key_count'] += nested_stats['key_count']
                stats['string_count'] += nested_stats['string_count']
                stats['number_count'] += nested_stats['number_count']
                stats['boolean_count'] += nested_stats['boolean_count']
                stats['null_count'] += nested_stats['null_count']
        elif isinstance(obj, str):
            stats['string_count'] = 1
        elif isinstance(obj, (int, float)):
            stats['number_count'] = 1
        elif isinstance(obj, bool):
            stats['boolean_count'] = 1
        elif obj is None:
            stats['null_count'] = 1
        
        return stats
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse JSON file metadata.
        
        Returns:
            Dictionary of JSON metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if not file_data:
                raise MetadataReadError("Invalid JSON file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'JSON'
            metadata['File:FileTypeExtension'] = 'json'
            metadata['File:MIMEType'] = 'application/json'
            
            # Try to decode as UTF-8
            try:
                text = file_data.decode('utf-8')
                metadata['JSON:Encoding'] = 'utf-8'
            except UnicodeDecodeError:
                # Try other encodings
                for enc in ['latin-1', 'cp1252', 'us-ascii']:
                    try:
                        text = file_data.decode(enc)
                        metadata['JSON:Encoding'] = enc
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = file_data.decode('utf-8', errors='ignore')
                    metadata['JSON:Encoding'] = 'utf-8'
            
            # Parse JSON
            try:
                json_obj = json.loads(text)
                metadata['JSON:IsValid'] = True
                
                # Analyze structure
                stats = self._analyze_json_structure(json_obj)
                metadata['JSON:MaxDepth'] = stats['max_depth']
                metadata['JSON:ObjectCount'] = stats['object_count']
                metadata['JSON:ArrayCount'] = stats['array_count']
                metadata['JSON:KeyCount'] = stats['key_count']
                metadata['JSON:StringCount'] = stats['string_count']
                metadata['JSON:NumberCount'] = stats['number_count']
                metadata['JSON:BooleanCount'] = stats['boolean_count']
                metadata['JSON:NullCount'] = stats['null_count']
                
                # Determine root type
                if isinstance(json_obj, dict):
                    metadata['JSON:RootType'] = 'object'
                    metadata['JSON:RootKeyCount'] = len(json_obj)
                elif isinstance(json_obj, list):
                    metadata['JSON:RootType'] = 'array'
                    metadata['JSON:RootElementCount'] = len(json_obj)
                else:
                    metadata['JSON:RootType'] = type(json_obj).__name__
                
            except json.JSONDecodeError as e:
                metadata['JSON:IsValid'] = False
                metadata['JSON:ParseError'] = str(e)
                metadata['JSON:ParseErrorLine'] = getattr(e, 'lineno', None)
                metadata['JSON:ParseErrorColumn'] = getattr(e, 'colno', None)
            
            # Character and byte counts
            metadata['JSON:CharacterCount'] = len(text)
            metadata['JSON:ByteCount'] = len(file_data)
            
            # Line count
            line_count = text.count('\n')
            if text and not text.endswith('\n'):
                line_count += 1
            metadata['JSON:LineCount'] = line_count
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse JSON file metadata: {str(e)}")

