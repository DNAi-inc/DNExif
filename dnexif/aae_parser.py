# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
AAE (Apple Adjustments) file metadata parser

This module handles reading metadata from AAE (Apple Adjustments) files.
AAE files are PLIST-based XML files that contain photo editing adjustments.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path
from xml.etree import ElementTree as ET

from dnexif.exceptions import MetadataReadError


class AAParser:
    """
    Parser for AAE (Apple Adjustments) metadata.
    
    AAE files are PLIST-based XML files that contain photo editing adjustments
    and metadata from Apple Photos app.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize AAE parser.
        
        Args:
            file_path: Path to AAE file
            file_data: AAE file data bytes
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
        Parse AAE metadata.
        
        Returns:
            Dictionary of AAE metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid AAE file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'AAE'
            metadata['File:FileTypeExtension'] = 'aae'
            metadata['File:MIMEType'] = 'application/x-apple-aae'
            
            # AAE files are XML PLIST files
            # Try to decode as UTF-8
            try:
                aae_text = file_data.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                # Try other encodings
                try:
                    aae_text = file_data.decode('utf-16', errors='ignore')
                except UnicodeDecodeError:
                    aae_text = file_data.decode('latin-1', errors='ignore')
            
            # Check if it's a PLIST file
            if not (aae_text.startswith('<?xml') or aae_text.startswith('<plist')):
                # Not a valid AAE file
                return metadata
            
            metadata['AAE:Format'] = 'PLIST XML'
            metadata['AAE:Present'] = 'Yes'
            
            # Parse PLIST XML
            try:
                # Remove XML declaration and DTD if present for cleaner parsing
                plist_text = aae_text
                if '<?xml' in plist_text:
                    # Remove XML declaration
                    plist_text = plist_text.split('?>', 1)[1] if '?>' in plist_text else plist_text
                if '<!DOCTYPE' in plist_text:
                    # Remove DTD
                    dtd_start = plist_text.find('<!DOCTYPE')
                    dtd_end = plist_text.find('>', dtd_start)
                    if dtd_end > dtd_start:
                        plist_text = plist_text[:dtd_start] + plist_text[dtd_end+1:]
                
                root = ET.fromstring(plist_text.strip())
                
                # Extract PLIST metadata
                metadata['AAE:PLIST:RootType'] = root.tag.replace('{', '').replace('}', '').split('}')[-1]
                
                # Extract key-value pairs from dict elements
                if root.tag.endswith('dict'):
                    self._extract_plist_dict(root, metadata, 'AAE')
                
                # Extract array elements
                elif root.tag.endswith('array'):
                    array_items = []
                    for child in root:
                        item_text = child.text if child.text else ''
                        if item_text.strip():
                            array_items.append(item_text.strip())
                    if array_items:
                        metadata['AAE:PLIST:ArrayItems'] = array_items
                        metadata['AAE:PLIST:ArrayCount'] = len(array_items)
                
                # Extract string values
                elif root.tag.endswith('string'):
                    if root.text:
                        metadata['AAE:PLIST:StringValue'] = root.text.strip()
                
                # Store raw PLIST XML (truncate if too long)
                if len(aae_text) <= 10000:  # Store up to 10KB
                    metadata['AAE:PLIST:Data'] = aae_text
                else:
                    metadata['AAE:PLIST:Data'] = aae_text[:10000] + '...'
                    metadata['AAE:PLIST:Truncated'] = 'Yes'
                
                metadata['AAE:PLIST:Size'] = len(file_data)
                
            except ET.ParseError as e:
                # PLIST parsing failed, but still mark as present
                metadata['AAE:PLIST:ParseError'] = str(e)
                metadata['AAE:PLIST:Data'] = aae_text[:1000]  # Store first 1KB
            except Exception as e:
                # Other parsing errors
                metadata['AAE:Error'] = str(e)
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse AAE metadata: {str(e)}")
        
        return metadata
    
    def _extract_plist_dict(self, dict_elem, metadata: Dict[str, Any], prefix: str) -> None:
        """
        Extract key-value pairs from PLIST dict element.
        
        Args:
            dict_elem: XML element representing a PLIST dict
            metadata: Metadata dictionary to update
            prefix: Prefix for metadata keys
        """
        try:
            # PLIST dict structure: <key>keyname</key><value>value</value> pairs
            children = list(dict_elem)
            i = 0
            while i < len(children) - 1:
                key_elem = children[i]
                value_elem = children[i + 1]
                
                if key_elem.tag.endswith('key') and key_elem.text:
                    key_name = key_elem.text.strip()
                    # Sanitize key name for metadata tag
                    tag_key = key_name.replace(' ', '').replace('-', '').replace(':', '')
                    
                    # Extract value based on value element type
                    if value_elem.tag.endswith('string'):
                        value = value_elem.text if value_elem.text else ''
                        if value.strip():
                            metadata[f'{prefix}:{tag_key}'] = value.strip()
                    elif value_elem.tag.endswith('integer'):
                        try:
                            value = int(value_elem.text) if value_elem.text else 0
                            metadata[f'{prefix}:{tag_key}'] = value
                        except ValueError:
                            pass
                    elif value_elem.tag.endswith('real'):
                        try:
                            value = float(value_elem.text) if value_elem.text else 0.0
                            metadata[f'{prefix}:{tag_key}'] = value
                        except ValueError:
                            pass
                    elif value_elem.tag.endswith('true'):
                        metadata[f'{prefix}:{tag_key}'] = True
                    elif value_elem.tag.endswith('false'):
                        metadata[f'{prefix}:{tag_key}'] = False
                    elif value_elem.tag.endswith('dict'):
                        # Nested dict - extract recursively
                        nested_prefix = f'{prefix}:{tag_key}'
                        self._extract_plist_dict(value_elem, metadata, nested_prefix)
                    elif value_elem.tag.endswith('array'):
                        # Array - extract items
                        array_items = []
                        for item in value_elem:
                            if item.text:
                                array_items.append(item.text.strip())
                        if array_items:
                            metadata[f'{prefix}:{tag_key}'] = array_items
                    elif value_elem.tag.endswith('data'):
                        # Binary data - store as base64 or hex
                        if value_elem.text:
                            # PLIST data elements are base64 encoded
                            metadata[f'{prefix}:{tag_key}:Data'] = value_elem.text.strip()
                            metadata[f'{prefix}:{tag_key}:DataType'] = 'Base64'
                
                i += 2  # Move to next key-value pair
        except Exception:
            pass

