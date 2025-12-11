# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
GPX (GPS Exchange Format) file metadata parser

This module handles reading metadata from GPX files.
GPX files are XML-based GPS track log files.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from dnexif.exceptions import MetadataReadError


class GPXParser:
    """
    Parser for GPX (GPS Exchange Format) metadata.
    
    GPX files are XML-based GPS track log files.
    Structure:
    - GPX root element with version and creator
    - Waypoints (wpt elements)
    - Tracks (trk elements) with track segments (trkseg) and track points (trkpt)
    - Routes (rte elements) with route points (rtept)
    """
    
    # GPX namespaces
    GPX_NAMESPACES = {
        'gpx': 'http://www.topografix.com/GPX/1/1',
        'gpx10': 'http://www.topografix.com/GPX/1/0',
    }
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize GPX parser.
        
        Args:
            file_path: Path to GPX file
            file_data: GPX file data bytes
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
        Parse GPX metadata.
        
        Returns:
            Dictionary of GPX metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid GPX file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'GPX'
            metadata['File:FileTypeExtension'] = 'gpx'
            metadata['File:MIMEType'] = 'application/gpx+xml'
            
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
                raise MetadataReadError("Invalid GPX file: XML parse error")
            
            # Extract namespace
            ns_uri = None
            if root.tag.startswith('{'):
                ns_uri = root.tag.split('}')[0][1:]
            else:
                # Try common namespaces
                for prefix, uri in self.GPX_NAMESPACES.items():
                    if uri in xml_content:
                        ns_uri = uri
                        break
            
            # Build namespace dictionary for ElementTree
            namespaces = {}
            if ns_uri:
                namespaces['gpx'] = ns_uri
            
            # Extract GPX version
            version = root.get('version')
            if version:
                metadata['GPX:Version'] = version
            
            # Extract creator
            creator = root.get('creator')
            if creator:
                metadata['GPX:Creator'] = creator
            
            # Extract time - handle namespace properly
            time_elem = None
            if ns_uri:
                time_elem = root.find(f'.//{{{ns_uri}}}time', namespaces)
            if time_elem is None:
                time_elem = root.find('.//time')
            if time_elem is not None and time_elem.text:
                metadata['GPX:Time'] = time_elem.text
                try:
                    dt = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                    metadata['GPX:DateTime'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                except Exception:
                    pass
            
            # Extract bounds - handle namespace properly
            bounds = None
            if ns_uri:
                bounds = root.find(f'.//{{{ns_uri}}}bounds', namespaces)
            if bounds is None:
                bounds = root.find('.//bounds')
            if bounds is not None:
                minlat = bounds.get('minlat')
                minlon = bounds.get('minlon')
                maxlat = bounds.get('maxlat')
                maxlon = bounds.get('maxlon')
                if minlat and minlon and maxlat and maxlon:
                    metadata['GPX:Bounds:MinLatitude'] = float(minlat)
                    metadata['GPX:Bounds:MinLongitude'] = float(minlon)
                    metadata['GPX:Bounds:MaxLatitude'] = float(maxlat)
                    metadata['GPX:Bounds:MaxLongitude'] = float(maxlon)
            
            # Count waypoints - handle namespace properly
            waypoints = []
            if ns_uri:
                waypoints = root.findall(f'.//{{{ns_uri}}}wpt', namespaces)
            if not waypoints:
                waypoints = root.findall('.//wpt')
            if waypoints:
                metadata['GPX:WaypointCount'] = len(waypoints)
                for i, wpt in enumerate(waypoints[:20], 1):  # Limit to 20 waypoints
                    wpt_metadata = self._parse_waypoint(wpt, i, ns_uri)
                    if wpt_metadata:
                        metadata.update(wpt_metadata)
            
            # Count tracks - handle namespace properly
            tracks = []
            if ns_uri:
                tracks = root.findall(f'.//{{{ns_uri}}}trk', namespaces)
            if not tracks:
                tracks = root.findall('.//trk')
            if tracks:
                metadata['GPX:TrackCount'] = len(tracks)
                track_point_count = 0
                for i, trk in enumerate(tracks[:10], 1):  # Limit to 10 tracks
                    trk_metadata = self._parse_track(trk, i, ns_uri)
                    if trk_metadata:
                        metadata.update(trk_metadata)
                        # Count track points - handle namespace properly
                        trkpts = []
                        if ns_uri:
                            trkpts = trk.findall(f'.//{{{ns_uri}}}trkpt', namespaces)
                        if not trkpts:
                            trkpts = trk.findall('.//trkpt')
                        track_point_count += len(trkpts)
                
                if track_point_count > 0:
                    metadata['GPX:TrackPointCount'] = track_point_count
            
            # Count routes - handle namespace properly
            routes = []
            if ns_uri:
                routes = root.findall(f'.//{{{ns_uri}}}rte', namespaces)
            if not routes:
                routes = root.findall('.//rte')
            if routes:
                metadata['GPX:RouteCount'] = len(routes)
                route_point_count = 0
                for i, rte in enumerate(routes[:10], 1):  # Limit to 10 routes
                    rte_metadata = self._parse_route(rte, i, ns_uri)
                    if rte_metadata:
                        metadata.update(rte_metadata)
                        # Count route points - handle namespace properly
                        rtepts = []
                        if ns_uri:
                            rtepts = rte.findall(f'.//{{{ns_uri}}}rtept', namespaces)
                        if not rtepts:
                            rtepts = rte.findall('.//rtept')
                        route_point_count += len(rtepts)
                
                if route_point_count > 0:
                    metadata['GPX:RoutePointCount'] = route_point_count
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse GPX metadata: {str(e)}")
    
    def _parse_waypoint(self, wpt: ET.Element, index: int, ns_uri: Optional[str]) -> Dict[str, Any]:
        """
        Parse waypoint element.
        
        Args:
            wpt: Waypoint XML element
            index: Waypoint index
            ns_uri: Namespace URI string
            
        Returns:
            Dictionary of waypoint metadata
        """
        metadata = {}
        
        try:
            prefix = f'GPX:Waypoint{index}'
            
            # Build namespaces dict
            namespaces = {}
            if ns_uri:
                namespaces['gpx'] = ns_uri
            
            # Extract coordinates
            lat = wpt.get('lat')
            lon = wpt.get('lon')
            if lat and lon:
                metadata[f'{prefix}:Latitude'] = float(lat)
                metadata[f'{prefix}:Longitude'] = float(lon)
            
            # Extract elevation - handle namespace properly
            ele_elem = None
            if ns_uri:
                ele_elem = wpt.find(f'.//{{{ns_uri}}}ele', namespaces)
            if ele_elem is None:
                ele_elem = wpt.find('.//ele')
            if ele_elem is not None and ele_elem.text:
                metadata[f'{prefix}:Elevation'] = float(ele_elem.text)
            
            # Extract name - handle namespace properly
            name_elem = None
            if ns_uri:
                name_elem = wpt.find(f'.//{{{ns_uri}}}name', namespaces)
            if name_elem is None:
                name_elem = wpt.find('.//name')
            if name_elem is not None and name_elem.text:
                metadata[f'{prefix}:Name'] = name_elem.text
            
            # Extract description - handle namespace properly
            desc_elem = None
            if ns_uri:
                desc_elem = wpt.find(f'.//{{{ns_uri}}}desc', namespaces)
            if desc_elem is None:
                desc_elem = wpt.find('.//desc')
            if desc_elem is not None and desc_elem.text:
                metadata[f'{prefix}:Description'] = desc_elem.text
            
            # Extract comment - handle namespace properly
            cmt_elem = None
            if ns_uri:
                cmt_elem = wpt.find(f'.//{{{ns_uri}}}cmt', namespaces)
            if cmt_elem is None:
                cmt_elem = wpt.find('.//cmt')
            if cmt_elem is not None and cmt_elem.text:
                metadata[f'{prefix}:Comment'] = cmt_elem.text
            
            # Extract time - handle namespace properly
            time_elem = None
            if ns_uri:
                time_elem = wpt.find(f'.//{{{ns_uri}}}time', namespaces)
            if time_elem is None:
                time_elem = wpt.find('.//time')
            if time_elem is not None and time_elem.text:
                metadata[f'{prefix}:Time'] = time_elem.text
            
            # Extract symbol - handle namespace properly
            sym_elem = None
            if ns_uri:
                sym_elem = wpt.find(f'.//{{{ns_uri}}}sym', namespaces)
            if sym_elem is None:
                sym_elem = wpt.find('.//sym')
            if sym_elem is not None and sym_elem.text:
                metadata[f'{prefix}:Symbol'] = sym_elem.text
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_track(self, trk: ET.Element, index: int, ns_uri: Optional[str]) -> Dict[str, Any]:
        """
        Parse track element.
        
        Args:
            trk: Track XML element
            index: Track index
            ns_uri: Namespace URI string
            
        Returns:
            Dictionary of track metadata
        """
        metadata = {}
        
        try:
            prefix = f'GPX:Track{index}'
            
            # Build namespaces dict
            namespaces = {}
            if ns_uri:
                namespaces['gpx'] = ns_uri
            
            # Extract name - handle namespace properly
            name_elem = None
            if ns_uri:
                name_elem = trk.find(f'.//{{{ns_uri}}}name', namespaces)
            if name_elem is None:
                name_elem = trk.find('.//name')
            if name_elem is not None and name_elem.text:
                metadata[f'{prefix}:Name'] = name_elem.text
            
            # Extract description - handle namespace properly
            desc_elem = None
            if ns_uri:
                desc_elem = trk.find(f'.//{{{ns_uri}}}desc', namespaces)
            if desc_elem is None:
                desc_elem = trk.find('.//desc')
            if desc_elem is not None and desc_elem.text:
                metadata[f'{prefix}:Description'] = desc_elem.text
            
            # Extract comment - handle namespace properly
            cmt_elem = None
            if ns_uri:
                cmt_elem = trk.find(f'.//{{{ns_uri}}}cmt', namespaces)
            if cmt_elem is None:
                cmt_elem = trk.find('.//cmt')
            if cmt_elem is not None and cmt_elem.text:
                metadata[f'{prefix}:Comment'] = cmt_elem.text
            
            # Count track segments - handle namespace properly
            trksegs = []
            if ns_uri:
                trksegs = trk.findall(f'.//{{{ns_uri}}}trkseg', namespaces)
            if not trksegs:
                trksegs = trk.findall('.//trkseg')
            if trksegs:
                metadata[f'{prefix}:SegmentCount'] = len(trksegs)
            
            # Count track points - handle namespace properly
            trkpts = []
            if ns_uri:
                trkpts = trk.findall(f'.//{{{ns_uri}}}trkpt', namespaces)
            if not trkpts:
                trkpts = trk.findall('.//trkpt')
            if trkpts:
                metadata[f'{prefix}:PointCount'] = len(trkpts)
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_route(self, rte: ET.Element, index: int, ns_uri: Optional[str]) -> Dict[str, Any]:
        """
        Parse route element.
        
        Args:
            rte: Route XML element
            index: Route index
            ns_uri: Namespace URI string
            
        Returns:
            Dictionary of route metadata
        """
        metadata = {}
        
        try:
            prefix = f'GPX:Route{index}'
            
            # Build namespaces dict
            namespaces = {}
            if ns_uri:
                namespaces['gpx'] = ns_uri
            
            # Extract name - handle namespace properly
            name_elem = None
            if ns_uri:
                name_elem = rte.find(f'.//{{{ns_uri}}}name', namespaces)
            if name_elem is None:
                name_elem = rte.find('.//name')
            if name_elem is not None and name_elem.text:
                metadata[f'{prefix}:Name'] = name_elem.text
            
            # Extract description - handle namespace properly
            desc_elem = None
            if ns_uri:
                desc_elem = rte.find(f'.//{{{ns_uri}}}desc', namespaces)
            if desc_elem is None:
                desc_elem = rte.find('.//desc')
            if desc_elem is not None and desc_elem.text:
                metadata[f'{prefix}:Description'] = desc_elem.text
            
            # Extract comment - handle namespace properly
            cmt_elem = None
            if ns_uri:
                cmt_elem = rte.find(f'.//{{{ns_uri}}}cmt', namespaces)
            if cmt_elem is None:
                cmt_elem = rte.find('.//cmt')
            if cmt_elem is not None and cmt_elem.text:
                metadata[f'{prefix}:Comment'] = cmt_elem.text
            
            # Count route points - handle namespace properly
            rtepts = []
            if ns_uri:
                rtepts = rte.findall(f'.//{{{ns_uri}}}rtept', namespaces)
            if not rtepts:
                rtepts = rte.findall('.//rtept')
            if rtepts:
                metadata[f'{prefix}:PointCount'] = len(rtepts)
        
        except Exception:
            pass
        
        return metadata

