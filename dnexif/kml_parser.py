# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
KML (Keyhole Markup Language) file metadata parser

This module handles reading metadata from KML files.
KML files are XML-based Google Earth files.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from dnexif.exceptions import MetadataReadError


class KMLParser:
    """
    Parser for KML (Keyhole Markup Language) metadata.
    
    KML files are XML-based Google Earth files.
    Structure:
    - KML root element with namespace
    - Document/Folder elements containing placemarks
    - Placemark elements with name, description, coordinates, etc.
    - Style elements for visualization
    """
    
    # KML namespaces
    KML_NAMESPACES = {
        'kml': 'http://www.opengis.net/kml/2.2',
        'kml22': 'http://www.opengis.net/kml/2.2',
        'gx': 'http://www.google.com/kml/ext/2.2',
    }
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize KML parser.
        
        Args:
            file_path: Path to KML file
            file_data: KML file data bytes
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
        Parse KML metadata.
        
        Returns:
            Dictionary of KML metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid KML file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'KML'
            metadata['File:FileTypeExtension'] = 'kml'
            metadata['File:MIMEType'] = 'application/vnd.google-earth.kml+xml'
            
            # Try to decode as UTF-8
            try:
                xml_content = file_data.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    xml_content = file_data.decode('utf-16-le')
                except UnicodeDecodeError:
                    xml_content = file_data.decode('latin-1', errors='ignore')
            
            # Parse XML
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                raise MetadataReadError("Invalid KML file: XML parse error")
            
            # Extract namespace
            ns = {}
            if root.tag.startswith('{'):
                ns_uri = root.tag.split('}')[0][1:]
                ns['kml'] = ns_uri
            else:
                # Try common namespaces
                for prefix, uri in self.KML_NAMESPACES.items():
                    if uri in xml_content:
                        ns['kml'] = uri
                        break
            
            # Extract Document element - handle namespace properly
            document = None
            if ns and 'kml' in ns:
                document = root.find(f'.//{{{ns["kml"]}}}Document')
            if document is None:
                document = root.find('.//Document')
            if document is None:
                document = root  # Use root if no Document element
            
            # Extract document name - handle namespace properly
            name_elem = None
            if ns and 'kml' in ns:
                name_elem = document.find(f'.//{{{ns["kml"]}}}name')
            if name_elem is None:
                name_elem = document.find('.//name')
            if name_elem is not None and name_elem.text:
                metadata['KML:Document:Name'] = name_elem.text
            
            # Extract document description - handle namespace properly
            desc_elem = None
            if ns and 'kml' in ns:
                desc_elem = document.find(f'.//{{{ns["kml"]}}}description')
            if desc_elem is None:
                desc_elem = document.find('.//description')
            if desc_elem is not None and desc_elem.text:
                metadata['KML:Document:Description'] = desc_elem.text
            
            # Count placemarks - handle namespace properly
            placemarks = []
            if ns and 'kml' in ns:
                placemarks = root.findall(f'.//{{{ns["kml"]}}}Placemark')
            if not placemarks:
                placemarks = root.findall('.//Placemark')
            
            if placemarks:
                metadata['KML:PlacemarkCount'] = len(placemarks)
                for i, pm in enumerate(placemarks[:20], 1):  # Limit to 20 placemarks
                    pm_metadata = self._parse_placemark(pm, i, ns)
                    if pm_metadata:
                        metadata.update(pm_metadata)
            
            # Count folders - handle namespace properly
            folders = []
            if ns and 'kml' in ns:
                folders = root.findall(f'.//{{{ns["kml"]}}}Folder')
            if not folders:
                folders = root.findall('.//Folder')
            
            if folders:
                metadata['KML:FolderCount'] = len(folders)
            
            # Count styles - handle namespace properly
            styles = []
            if ns and 'kml' in ns:
                styles = root.findall(f'.//{{{ns["kml"]}}}Style')
            if not styles:
                styles = root.findall('.//Style')
            
            if styles:
                metadata['KML:StyleCount'] = len(styles)
            
            # Count ground overlays - handle namespace properly
            overlays = []
            if ns and 'kml' in ns:
                overlays = root.findall(f'.//{{{ns["kml"]}}}GroundOverlay')
            if not overlays:
                overlays = root.findall('.//GroundOverlay')
            
            if overlays:
                metadata['KML:GroundOverlayCount'] = len(overlays)
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse KML metadata: {str(e)}")
    
    def _parse_placemark(self, pm: ET.Element, index: int, ns: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse placemark element.
        
        Args:
            pm: Placemark XML element
            index: Placemark index
            ns: Namespace dictionary
            
        Returns:
            Dictionary of placemark metadata
        """
        metadata = {}
        
        try:
            prefix = f'KML:Placemark{index}'
            
            # Extract name - handle namespace properly
            name_elem = None
            if ns and 'kml' in ns:
                name_elem = pm.find(f'.//{{{ns["kml"]}}}name')
            if name_elem is None:
                name_elem = pm.find('.//name')
            if name_elem is not None and name_elem.text:
                metadata[f'{prefix}:Name'] = name_elem.text
            
            # Extract description - handle namespace properly
            desc_elem = None
            if ns and 'kml' in ns:
                desc_elem = pm.find(f'.//{{{ns["kml"]}}}description')
            if desc_elem is None:
                desc_elem = pm.find('.//description')
            if desc_elem is not None and desc_elem.text:
                metadata[f'{prefix}:Description'] = desc_elem.text
            
            # Extract coordinates from Point - handle namespace properly
            point = None
            if ns and 'kml' in ns:
                point = pm.find(f'.//{{{ns["kml"]}}}Point')
            if point is None:
                point = pm.find('.//Point')
            
            if point is not None:
                coords_elem = None
                if ns and 'kml' in ns:
                    coords_elem = point.find(f'.//{{{ns["kml"]}}}coordinates')
                if coords_elem is None:
                    coords_elem = point.find('.//coordinates')
                
                if coords_elem is not None and coords_elem.text:
                    coords = coords_elem.text.strip().split(',')
                    if len(coords) >= 2:
                        try:
                            lon = float(coords[0])
                            lat = float(coords[1])
                            metadata[f'{prefix}:Longitude'] = lon
                            metadata[f'{prefix}:Latitude'] = lat
                            if len(coords) >= 3 and coords[2]:
                                metadata[f'{prefix}:Altitude'] = float(coords[2])
                        except (ValueError, IndexError):
                            pass
            
            # Extract time - handle namespace properly
            time_elem = None
            if ns and 'kml' in ns:
                time_elem = pm.find(f'.//{{{ns["kml"]}}}TimeStamp/{{{ns["kml"]}}}when')
            if time_elem is None:
                time_elem = pm.find('.//TimeStamp/when')
            if time_elem is None:
                if ns and 'kml' in ns:
                    time_elem = pm.find(f'.//{{{ns["kml"]}}}when')
                if time_elem is None:
                    time_elem = pm.find('.//when')
            
            if time_elem is not None and time_elem.text:
                metadata[f'{prefix}:Time'] = time_elem.text
                try:
                    dt = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                    metadata[f'{prefix}:DateTime'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                except Exception:
                    pass
            
            # Extract style URL - handle namespace properly
            style_elem = None
            if ns and 'kml' in ns:
                style_elem = pm.find(f'.//{{{ns["kml"]}}}styleUrl')
            if style_elem is None:
                style_elem = pm.find('.//styleUrl')
            if style_elem is not None and style_elem.text:
                metadata[f'{prefix}:StyleURL'] = style_elem.text
        
        except Exception:
            pass
        
        return metadata

