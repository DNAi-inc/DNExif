# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
SVG (Scalable Vector Graphics) metadata parser

This module handles reading metadata from SVG files.
SVG metadata is stored in XML elements.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Iterable
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class SVGParser:
    """
    Parser for SVG metadata.
    
    SVG files can contain metadata in:
    - <metadata> elements (RDF/DC)
    - <title> and <desc> elements
    - Custom metadata elements
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize SVG parser.
        
        Args:
            file_path: Path to SVG file
            file_data: SVG file data bytes
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
        Parse SVG metadata.
        
        Returns:
            Dictionary of SVG metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            # Decode to string
            try:
                svg_str = file_data.decode('utf-8')
            except UnicodeDecodeError:
                svg_str = file_data.decode('latin-1', errors='ignore')
            
            # Parse XML
            try:
                root = ET.fromstring(svg_str)
            except ET.ParseError:
                # Try to fix common XML issues
                svg_str = svg_str.replace('&', '&amp;')
                root = ET.fromstring(svg_str)
            
            metadata = {}
            
            # Extract title
            title_elem = root.find('.//{http://www.w3.org/2000/svg}title')
            if title_elem is None:
                title_elem = root.find('.//title')
            if title_elem is not None and title_elem.text:
                self._store_with_alias(metadata, 'SVG:Title', title_elem.text.strip(), ['XMP:Title'])
            
            # Extract description
            desc_elem = root.find('.//{http://www.w3.org/2000/svg}desc')
            if desc_elem is None:
                desc_elem = root.find('.//desc')
            if desc_elem is not None and desc_elem.text:
                metadata['SVG:Description'] = desc_elem.text.strip()
            
            # Extract metadata element (RDF/DC)
            metadata_elem = root.find('.//{http://www.w3.org/2000/svg}metadata')
            if metadata_elem is None:
                metadata_elem = root.find('.//metadata')
            
            if metadata_elem is not None:
                # Parse RDF metadata if present
                rdf_desc = metadata_elem.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
                if rdf_desc is None:
                    rdf_desc = metadata_elem.find('.//Description')
                
                if rdf_desc is not None:
                    # Extract DC (Dublin Core) metadata
                    dc_namespaces = {
                        'dc': 'http://purl.org/dc/elements/1.1/',
                        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
                    }
                    
                    # Title
                    dc_title = rdf_desc.find('.//dc:title', dc_namespaces)
                    if dc_title is None:
                        dc_title = rdf_desc.find('.//title')
                    if dc_title is not None and dc_title.text:
                        self._store_with_alias(metadata, 'SVG:DCTitle', dc_title.text.strip(), ['XMP:Title'])
                    
                    # Creator
                    dc_creator = rdf_desc.find('.//dc:creator', dc_namespaces)
                    if dc_creator is None:
                        dc_creator = rdf_desc.find('.//creator')
                    if dc_creator is not None and dc_creator.text:
                        metadata['SVG:DCCreator'] = dc_creator.text.strip()
                    
                    # Subject
                    dc_subject = rdf_desc.find('.//dc:subject', dc_namespaces)
                    if dc_subject is not None and dc_subject.text:
                        metadata['SVG:DCSubject'] = dc_subject.text.strip()
                    
                    # Description
                    dc_description = rdf_desc.find('.//dc:description', dc_namespaces)
                    if dc_description is not None and dc_description.text:
                        metadata['SVG:DCDescription'] = dc_description.text.strip()
                    
                    # Date
                    dc_date = rdf_desc.find('.//dc:date', dc_namespaces)
                    if dc_date is not None and dc_date.text:
                        metadata['SVG:DCDate'] = dc_date.text.strip()
                    
                    # Rights
                    dc_rights = rdf_desc.find('.//dc:rights', dc_namespaces)
                    if dc_rights is not None and dc_rights.text:
                        metadata['SVG:DCRights'] = dc_rights.text.strip()
            
            # Extract SVG root element attributes
            if 'width' in root.attrib:
                width_val = root.attrib['width']
                metadata['SVG:Width'] = width_val
                metadata['SVG:ImageWidth'] = width_val
                # Also set File tag for composite tag calculation
                try:
                    # Remove units (px, pt, etc.) and extract numeric value
                    import re
                    width_match = re.search(r'([\d.]+)', width_val)
                    if width_match:
                        metadata['File:ImageWidth'] = int(float(width_match.group(1)))
                except (ValueError, TypeError):
                    pass
            
            if 'height' in root.attrib:
                height_val = root.attrib['height']
                metadata['SVG:Height'] = height_val
                metadata['SVG:ImageHeight'] = height_val
                # Also set File tag for composite tag calculation
                try:
                    # Remove units (px, pt, etc.) and extract numeric value
                    import re
                    height_match = re.search(r'([\d.]+)', height_val)
                    if height_match:
                        metadata['File:ImageHeight'] = int(float(height_match.group(1)))
                except (ValueError, TypeError):
                    pass
            
            if 'viewBox' in root.attrib:
                metadata['SVG:ViewBox'] = root.attrib['viewBox']
            
            # Extract SVG version
            if 'version' in root.attrib:
                metadata['SVG:SVGVersion'] = root.attrib['version']
            else:
                # Default SVG version if not specified
                metadata['SVG:SVGVersion'] = '1.1'
            
            # Extract baseProfile (SVG Tiny, SVG Basic, or full SVG)
            if 'baseProfile' in root.attrib:
                metadata['SVG:BaseProfile'] = root.attrib['baseProfile']
            
            # Extract xmlns (XML namespace)
            # SVG root element typically has xmlns="http://www.w3.org/2000/svg"
            xmlns_uri = root.tag.split('}')[0].strip('{') if '}' in root.tag else None
            if xmlns_uri:
                metadata['SVG:Xmlns'] = xmlns_uri
            elif 'xmlns' in root.attrib:
                metadata['SVG:Xmlns'] = root.attrib['xmlns']
            
            # Extract ID attribute
            if 'id' in root.attrib:
                metadata['SVG:ID'] = root.attrib['id']
            
            # Extract TitleId (ID of title element)
            title_elem = root.find('.//{http://www.w3.org/2000/svg}title')
            if title_elem is None:
                title_elem = root.find('.//title')
            if title_elem is not None and 'id' in title_elem.attrib:
                metadata['SVG:TitleId'] = title_elem.attrib['id']
            
            # If XMP Title still missing but SVG title present, mirror it
            if 'SVG:Title' in metadata and 'XMP:Title' not in metadata:
                metadata['XMP:Title'] = metadata['SVG:Title']
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse SVG metadata: {str(e)}")

    def _store_with_alias(self, metadata: Dict[str, Any], key: str, value: Any, aliases: Iterable[str]) -> None:
        """Store metadata value along with alias keys."""
        if value is None:
            return
        metadata[key] = value
        for alias in aliases:
            metadata[alias] = value

