# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
SVG metadata writer

This module provides metadata writing for SVG files.
SVG metadata is stored in XML elements.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.xmp_writer import XMPWriter


class SVGWriter:
    """
    Writer for SVG metadata.
    
    SVG files can contain metadata in:
    - <metadata> elements (RDF/DC)
    - <title> and <desc> elements
    - Custom metadata elements
    """
    
    def __init__(self):
        """Initialize SVG writer."""
        self.xmp_writer = XMPWriter()
    
    def write_svg(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to SVG file.
        
        Args:
            file_path: Path to input SVG file
            metadata: Dictionary of metadata to write
            output_path: Path to output SVG file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                svg_data = f.read()
            
            # Decode to string
            try:
                svg_str = svg_data.decode('utf-8')
            except UnicodeDecodeError:
                svg_str = svg_data.decode('latin-1', errors='ignore')
            
            # Parse XML
            try:
                root = ET.fromstring(svg_str)
            except ET.ParseError:
                # Try to fix common XML issues
                svg_str = svg_str.replace('&', '&amp;')
                root = ET.fromstring(svg_str)
            
            # Separate metadata by type
            svg_metadata = {}
            xmp_metadata = {}
            rdf_metadata = {}
            
            for key, value in metadata.items():
                if key.startswith('SVG:'):
                    svg_metadata[key[4:]] = value
                elif key.startswith('XMP:'):
                    xmp_metadata[key] = value
                elif key.startswith('RDF:') or key.startswith('DC:'):
                    rdf_metadata[key] = value
                else:
                    # Default to SVG for unknown prefixes
                    svg_metadata[key] = value

            artist_value = metadata.get('EXIF:Artist') or metadata.get('Artist')
            if artist_value and 'XMP:Creator' not in xmp_metadata:
                xmp_metadata['XMP:Creator'] = artist_value
            if artist_value and 'DC:Creator' not in rdf_metadata:
                rdf_metadata['DC:Creator'] = artist_value

            # Bridge common XMP tags into core SVG fields so round-trip reads succeed
            if 'XMP:Title' in xmp_metadata:
                svg_metadata['Title'] = xmp_metadata['XMP:Title']
            if 'XMP:Description' in xmp_metadata and 'Description' not in svg_metadata:
                svg_metadata['Description'] = xmp_metadata['XMP:Description']
            
            # Update title
            if 'Title' in svg_metadata:
                title_elem = root.find('.//{http://www.w3.org/2000/svg}title')
                if title_elem is None:
                    title_elem = root.find('.//title')
                if title_elem is None:
                    # Create title element
                    title_elem = ET.Element('title')
                    root.insert(0, title_elem)
                title_elem.text = str(svg_metadata['Title'])
            
            # Update description
            if 'Description' in svg_metadata:
                desc_elem = root.find('.//{http://www.w3.org/2000/svg}desc')
                if desc_elem is None:
                    desc_elem = root.find('.//desc')
                if desc_elem is None:
                    # Create desc element
                    desc_elem = ET.Element('desc')
                    if root.find('.//title') is not None:
                        root.insert(1, desc_elem)
                    else:
                        root.insert(0, desc_elem)
                desc_elem.text = str(svg_metadata['Description'])
            
            # Write XMP/RDF metadata
            if xmp_metadata or rdf_metadata:
                # Find or create metadata element
                metadata_elem = root.find('.//{http://www.w3.org/2000/svg}metadata')
                if metadata_elem is None:
                    metadata_elem = root.find('.//metadata')
                if metadata_elem is None:
                    # Create metadata element
                    metadata_elem = ET.Element('metadata')
                    # Insert after desc or title
                    insert_pos = 0
                    for i, child in enumerate(root):
                        if child.tag.endswith('title') or child.tag.endswith('desc'):
                            insert_pos = i + 1
                    root.insert(insert_pos, metadata_elem)
                
                # Add RDF description
                rdf_ns = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                         'dc': 'http://purl.org/dc/elements/1.1/',
                         'xmp': 'http://ns.adobe.com/xap/1.0/'}
                
                rdf_elem = metadata_elem.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
                if rdf_elem is None:
                    rdf_elem = ET.Element('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
                    metadata_elem.append(rdf_elem)
                
                # Add XMP packet if XMP metadata present
                if xmp_metadata:
                    xmp_packet = self.xmp_writer.build_xmp_packet(xmp_metadata)
                    if isinstance(xmp_packet, bytes):
                        xmp_text = xmp_packet.decode('utf-8', errors='ignore')
                    else:
                        xmp_text = str(xmp_packet)
                    existing_text = metadata_elem.text or ''
                    metadata_elem.text = existing_text + xmp_text
                
                # Add DC elements if RDF metadata present
                if rdf_metadata:
                    desc_elem = rdf_elem.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
                    if desc_elem is None:
                        desc_elem = ET.Element('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
                        rdf_elem.append(desc_elem)
                    
                    for key, value in rdf_metadata.items():
                        if key.startswith('DC:'):
                            dc_tag = key[3:].lower()
                            dc_elem = ET.SubElement(desc_elem, f'{{http://purl.org/dc/elements/1.1/}}{dc_tag}')
                            dc_elem.text = str(value)
            
            # Write output file
            ET.register_namespace('', 'http://www.w3.org/2000/svg')
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write SVG metadata: {str(e)}")
