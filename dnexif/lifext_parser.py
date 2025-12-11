# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Leica LIFEXT (Leica Image File Extended) metadata parser

This module handles reading metadata from Leica LIFEXT files.
LIFEXT files are XML-based metadata files used by Leica software.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class LIFEXTParser:
    """
    Parser for Leica LIFEXT (Leica Image File Extended) metadata.
    
    LIFEXT files are UTF-16 LE XML files containing Leica-specific metadata.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize LIFEXT parser.
        
        Args:
            file_path: Path to LIFEXT file
            file_data: LIFEXT file data bytes
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
        Parse LIFEXT metadata.
        
        Returns:
            Dictionary of LIFEXT metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 4:
                raise MetadataReadError("Invalid LIFEXT file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'LIFEXT'
            metadata['File:FileTypeExtension'] = 'lifext'
            metadata['File:MIMEType'] = 'application/xml'
            metadata['Leica:Format'] = 'LIFEXT'
            metadata['Leica:FormatType'] = 'UTF-16 LE XML'
            
            # Look for XML start (UTF-16 LE: 3c 00 = '<')
            # LIFEXT files may have a binary header before the XML
            xml_start = file_data.find(b'\x3c\x00')
            if xml_start >= 0:
                # Found XML start, skip binary header
                xml_data = file_data[xml_start:]
                metadata['Leica:XMLOffset'] = xml_start
            else:
                # Try checking if it starts directly with XML
                xml_data = file_data
                xml_start = 0
            
            # Check if it's UTF-16 LE XML
            if xml_data[:2] == b'\x3c\x00':
                # Decode as UTF-16 LE
                # For very large files, read larger portion but still limit to avoid memory issues
                max_xml_size = 50 * 1024 * 1024  # 50MB max (increased for better parsing)
                xml_data_to_parse = xml_data[:max_xml_size] if len(xml_data) > max_xml_size else xml_data
                
                try:
                    xml_text = xml_data_to_parse.decode('utf-16-le', errors='ignore')
                    metadata['Leica:HasXML'] = True
                    if len(xml_data) > max_xml_size:
                        metadata['Leica:XMLTruncated'] = True
                        metadata['Leica:XMLSize'] = len(xml_data)
                    
                    # Parse XML - use iterparse for large files
                    try:
                        # Try full parse first (for smaller files)
                        if len(xml_text) < 5 * 1024 * 1024:  # 5MB
                            root = ET.fromstring(xml_text)
                            metadata['Leica:XMLRootElement'] = root.tag
                            
                            # Extract root attributes
                            if root.attrib:
                                for key, value in root.attrib.items():
                                    metadata[f'Leica:XMLRoot:{key}'] = value
                            
                            # Extract child elements recursively
                            self._extract_xml_elements(root, metadata, prefix='Leica:XML', max_elements=5000)
                            
                            # Extract text content if present
                            if root.text and root.text.strip():
                                metadata['Leica:XMLContent'] = root.text.strip()
                        else:
                            # For large files, use iterparse
                            import io
                            xml_stream = io.BytesIO(xml_data_to_parse)
                            context = ET.iterparse(xml_stream, events=('start', 'end'))
                            element_count = 0
                            max_elements_to_extract = 5000
                            
                            for event, elem in context:
                                if element_count >= max_elements_to_extract:
                                    break
                                
                                if event == 'start':
                                    # Extract attributes
                                    if elem.attrib:
                                        clean_tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                                        for key, value in elem.attrib.items():
                                            tag_name = f'Leica:XML:{clean_tag}:{key}'
                                            if len(metadata) < max_elements_to_extract:
                                                metadata[tag_name] = value
                                                element_count += 1
                                
                                elif event == 'end':
                                    # Extract text content
                                    if elem.text and elem.text.strip():
                                        clean_tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                                        tag_name = f'Leica:XML:{clean_tag}'
                                        text_value = elem.text.strip()
                                        if len(text_value) > 1000:
                                            text_value = text_value[:1000] + '...'
                                        
                                        if len(metadata) < max_elements_to_extract:
                                            if tag_name not in metadata:
                                                metadata[tag_name] = text_value
                                            element_count += 1
                                    
                                    # Clear element to free memory
                                    elem.clear()
                            
                            # Get root element from first start event
                            xml_stream.seek(0)
                            try:
                                root = ET.parse(xml_stream).getroot()
                                metadata['Leica:XMLRootElement'] = root.tag.split('}')[-1] if '}' in root.tag else root.tag
                                if root.attrib:
                                    for key, value in root.attrib.items():
                                        metadata[f'Leica:XMLRoot:{key}'] = value
                            except:
                                pass
                        
                    except ET.ParseError as e:
                        metadata['Leica:XMLError'] = f"XML parse error: {str(e)}"
                        # Still store raw XML text preview
                        metadata['Leica:XMLText'] = xml_text[:2000]  # First 2000 chars
                        
                        # Try to extract some metadata from XML text even if parsing fails
                        import re
                        # Extract element names and attributes from XML text
                        element_pattern = r'<([^/>\s]+)([^>]*)>'
                        matches = re.findall(element_pattern, xml_text[:100000])  # First 100KB
                        for elem_name, attrs in matches[:100]:  # Limit to 100 elements
                            clean_name = elem_name.split('}')[-1] if '}' in elem_name else elem_name
                            metadata[f'Leica:XMLElement:{clean_name}'] = 'Present'
                            
                            # Extract attributes
                            attr_pattern = r'(\w+)="([^"]*)"'
                            attr_matches = re.findall(attr_pattern, attrs)
                            for attr_name, attr_value in attr_matches[:5]:  # Limit attributes per element
                                if len(metadata) < 5000:
                                    metadata[f'Leica:XMLElement:{clean_name}:{attr_name}'] = attr_value
                        
                except UnicodeDecodeError:
                    # Try UTF-16 BE
                    try:
                        xml_text = xml_data_to_parse.decode('utf-16-be', errors='ignore')
                        metadata['Leica:HasXML'] = True
                        metadata['Leica:FormatType'] = 'UTF-16 BE XML'
                        
                        root = ET.fromstring(xml_text)
                        metadata['Leica:XMLRootElement'] = root.tag
                        
                        if root.attrib:
                            for key, value in root.attrib.items():
                                metadata[f'Leica:XMLRoot:{key}'] = value
                        
                        self._extract_xml_elements(root, metadata, prefix='Leica:XML')
                        
                        if root.text and root.text.strip():
                            metadata['Leica:XMLContent'] = root.text.strip()
                            
                    except (UnicodeDecodeError, ET.ParseError):
                        metadata['Leica:HasXML'] = False
                        metadata['Leica:FormatType'] = 'Unknown'
                        # Store raw XML preview
                        try:
                            preview = xml_data_to_parse[:1000].decode('utf-16-le', errors='ignore')
                            metadata['Leica:XMLPreview'] = preview[:500]
                        except:
                            pass
            else:
                # Try regular UTF-8 XML
                try:
                    xml_text = file_data.decode('utf-8')
                    if xml_text.strip().startswith('<'):
                        metadata['Leica:HasXML'] = True
                        metadata['Leica:FormatType'] = 'UTF-8 XML'
                        
                        root = ET.fromstring(xml_text)
                        metadata['Leica:XMLRootElement'] = root.tag
                        
                        if root.attrib:
                            for key, value in root.attrib.items():
                                metadata[f'Leica:XMLRoot:{key}'] = value
                        
                        self._extract_xml_elements(root, metadata, prefix='Leica:XML')
                        
                        if root.text and root.text.strip():
                            metadata['Leica:XMLContent'] = root.text.strip()
                    else:
                        metadata['Leica:HasXML'] = False
                except (UnicodeDecodeError, ET.ParseError):
                    metadata['Leica:HasXML'] = False
            
            return metadata
            
        except Exception as exc:
            raise MetadataReadError(f"Failed to parse LIFEXT metadata: {exc}") from exc
    
    def _extract_xml_elements(self, element: ET.Element, metadata: Dict[str, Any], prefix: str = 'Leica:XML', depth: int = 0, max_depth: int = 10) -> None:
        """
        Recursively extract XML elements and attributes.
        
        Args:
            element: XML element to process
            metadata: Metadata dictionary to update
            prefix: Tag name prefix
            depth: Current recursion depth
            max_depth: Maximum recursion depth
        """
        if depth > max_depth:
            return
        
        # Extract element attributes
        if element.attrib:
            for key, value in element.attrib.items():
                tag_name = f'{prefix}:{element.tag}:{key}'
                metadata[tag_name] = value
        
        # Extract element text content
        if element.text and element.text.strip():
            tag_name = f'{prefix}:{element.tag}'
            if tag_name not in metadata:
                metadata[tag_name] = element.text.strip()
            else:
                # If tag already exists, append to it
                existing = metadata[tag_name]
                if isinstance(existing, str):
                    metadata[tag_name] = [existing, element.text.strip()]
                elif isinstance(existing, list):
                    existing.append(element.text.strip())
        
        # Process child elements
        child_count = 0
        for child in element:
            child_count += 1
            child_prefix = f'{prefix}:{element.tag}'
            self._extract_xml_elements(child, metadata, prefix=child_prefix, depth=depth + 1, max_depth=max_depth)
        
        # Store child count
        if child_count > 0:
            metadata[f'{prefix}:{element.tag}:ChildCount'] = child_count

