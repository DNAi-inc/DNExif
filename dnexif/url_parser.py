# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Windows .URL file metadata parser

This module handles reading metadata from Windows .URL shortcut files.
Windows .URL files are INI-format files that contain URL shortcuts.

Copyright 2025 DNAi inc.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class URLParser:
    """
    Parser for Windows .URL shortcut files.
    
    Windows .URL files are INI-format files with sections and key-value pairs.
    Common sections:
    - [InternetShortcut]
    - [DEFAULT]
    
    Common properties:
    - URL= (the target URL)
    - IconFile= (icon file path)
    - IconIndex= (icon index)
    - Modified= (modification date/time)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize URL parser.
        
        Args:
            file_path: Path to .URL file
            file_data: .URL file data bytes
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
        Parse Windows .URL file metadata.
        
        Returns:
            Dictionary of URL metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid .URL file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'URL'
            metadata['File:FileTypeExtension'] = 'url'
            metadata['File:MIMEType'] = 'application/x-mswinurl'
            
            # Try to decode as various encodings
            url_text = None
            for encoding in ['utf-8', 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252']:
                try:
                    url_text = file_data.decode(encoding, errors='strict')
                    metadata['URL:Encoding'] = encoding
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if url_text is None:
                # Fallback to UTF-8 with errors='replace'
                url_text = file_data.decode('utf-8', errors='replace')
                metadata['URL:Encoding'] = 'utf-8 (fallback)'
            
            # Parse INI format
            ini_data = self._parse_ini(url_text)
            if ini_data:
                metadata.update(ini_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse .URL metadata: {str(e)}")
    
    def _parse_ini(self, text: str) -> Dict[str, Any]:
        """
        Parse INI-format text.
        
        Args:
            text: INI-format text
            
        Returns:
            Dictionary of parsed INI data
        """
        metadata = {}
        
        try:
            # Split into lines
            lines = text.split('\n')
            
            current_section = None
            
            for line in lines:
                # Remove leading/trailing whitespace
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check for section header [SectionName]
                section_match = re.match(r'^\[(.+)\]$', line)
                if section_match:
                    current_section = section_match.group(1)
                    metadata[f'URL:Section:{current_section}'] = True
                    continue
                
                # Check for key=value pair
                if '=' in line:
                    # Split on first '=' only
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        # Store with section prefix if in a section
                        if current_section:
                            tag_key = f'URL:{current_section}:{key}'
                        else:
                            tag_key = f'URL:{key}'
                        
                        # Store value
                        metadata[tag_key] = value
                        
                        # Also store common properties without section prefix for easier access
                        if key.upper() == 'URL':
                            metadata['URL:URL'] = value
                        elif key.upper() == 'ICONFILE':
                            metadata['URL:IconFile'] = value
                        elif key.upper() == 'ICONINDEX':
                            try:
                                metadata['URL:IconIndex'] = int(value)
                            except ValueError:
                                metadata['URL:IconIndex'] = value
                        elif key.upper() == 'MODIFIED':
                            metadata['URL:Modified'] = value
                        elif key.upper() == 'WORKINGDIRECTORY' or key.upper() == 'WORKINGDIR':
                            metadata['URL:WorkingDirectory'] = value
                        elif key.upper() == 'HOTKEY':
                            metadata['URL:HotKey'] = value
            
            # Extract primary URL if available
            if 'URL:URL' in metadata:
                metadata['URL:TargetURL'] = metadata['URL:URL']
            
            # Extract icon information
            if 'URL:IconFile' in metadata:
                icon_file = metadata['URL:IconFile']
                metadata['URL:HasIcon'] = True
                metadata['URL:IconPath'] = icon_file
                
                # Extract icon index
                if 'URL:IconIndex' in metadata:
                    metadata['URL:IconIndex'] = metadata['URL:IconIndex']
            
            # Extract modification date
            if 'URL:Modified' in metadata:
                modified_str = metadata['URL:Modified']
                # Try to parse as date/time
                # Windows .URL files use various date formats
                metadata['URL:ModifiedDate'] = modified_str
            
        except Exception:
            pass
        
        return metadata

