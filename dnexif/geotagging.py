# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Geotagging features for DNExif

This module provides advanced geotagging capabilities including GPS track log
parsing (GPX, NMEA, KML) and time-synchronized geotagging.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import re
import csv
import json

from dnexif.core import DNExif
from dnexif.exceptions import MetadataWriteError


class GPSPoint:
    """Represents a GPS point with timestamp and coordinates."""
    
    def __init__(
        self,
        latitude: float,
        longitude: float,
        timestamp: datetime,
        altitude: Optional[float] = None,
        speed: Optional[float] = None,
        accuracy_horizontal: Optional[float] = None,
        direction: Optional[float] = None
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.timestamp = timestamp
        self.altitude = altitude
        self.speed = speed  # Speed in m/s
        self.accuracy_horizontal = accuracy_horizontal  # Horizontal accuracy in meters
        self.direction = direction  # Direction/bearing in degrees (0-360)
    
    def distance_to(self, other: 'GPSPoint') -> float:
        """Calculate distance to another GPS point in meters (Haversine formula)."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth radius in meters
        
        lat1 = radians(self.latitude)
        lat2 = radians(other.latitude)
        dlat = lat2 - lat1
        dlon = radians(other.longitude - self.longitude)
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c


class Geotagging:
    """
    Advanced geotagging features.
    
    Supports GPS track log parsing (GPX, NMEA, KML) and
    time-synchronized geotagging of images.
    """
    
    @staticmethod
    def parse_gpx(gpx_file: str) -> List[GPSPoint]:
        """
        Parse GPX (GPS Exchange Format) file.
        
        Args:
            gpx_file: Path to GPX file
            
        Returns:
            List of GPSPoint objects
        """
        points = []
        
        try:
            tree = ET.parse(gpx_file)
            root = tree.getroot()
            
            # Handle different GPX namespaces
            namespaces = {
                'gpx': 'http://www.topografix.com/GPX/1/1',
                'gpx10': 'http://www.topografix.com/GPX/1/0'
            }
            
            # Find all track points
            for trk in root.findall('.//gpx:trk', namespaces) or root.findall('.//trk'):
                for trkseg in trk.findall('.//gpx:trkseg', namespaces) or trk.findall('.//trkseg'):
                    for trkpt in trkseg.findall('.//gpx:trkpt', namespaces) or trkseg.findall('.//trkpt'):
                        lat = float(trkpt.get('lat', 0))
                        lon = float(trkpt.get('lon', 0))
                        
                        # Get timestamp
                        time_elem = trkpt.find('.//gpx:time', namespaces)
                        if time_elem is None:
                            time_elem = trkpt.find('.//time')
                        if time_elem is not None and time_elem.text is not None:
                            timestamp = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.now()
                        
                        # Get elevation
                        ele_elem = trkpt.find('.//gpx:ele', namespaces)
                        if ele_elem is None:
                            ele_elem = trkpt.find('.//ele')
                        altitude = float(ele_elem.text) if ele_elem is not None and ele_elem.text is not None else None
                        
                        # Get speed (OpenTracks extension)
                        speed = None
                        # Check for OpenTracks speed extension (namespace: http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1)
                        speed_elem = trkpt.find('.//{http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1}speed')
                        if speed_elem is None:
                            # Try without namespace
                            speed_elem = trkpt.find('.//speed')
                        if speed_elem is not None and speed_elem.text is not None:
                            try:
                                speed = float(speed_elem.text)  # Speed in m/s
                            except (ValueError, TypeError):
                                pass
                        
                        # Get accuracy_horizontal (OpenTracks extension)
                        accuracy_horizontal = None
                        # Check for OpenTracks accuracy extension
                        accuracy_elem = trkpt.find('.//{http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1}accuracy')
                        if accuracy_elem is None:
                            # Try without namespace
                            accuracy_elem = trkpt.find('.//accuracy')
                        if accuracy_elem is None:
                            # Try hdop (horizontal dilution of precision) as accuracy indicator
                            hdop_elem = trkpt.find('.//{http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1}hdop')
                            if hdop_elem is None:
                                hdop_elem = trkpt.find('.//hdop')
                            if hdop_elem is not None and hdop_elem.text is not None:
                                try:
                                    # Convert HDOP to approximate accuracy (HDOP * ~5 meters is typical)
                                    hdop = float(hdop_elem.text)
                                    accuracy_horizontal = hdop * 5.0  # Approximate conversion
                                except (ValueError, TypeError):
                                    pass
                        elif accuracy_elem.text is not None:
                            try:
                                accuracy_horizontal = float(accuracy_elem.text)  # Accuracy in meters
                            except (ValueError, TypeError):
                                pass
                        
                        points.append(GPSPoint(lat, lon, timestamp, altitude, speed, accuracy_horizontal))
            
            # Also check for waypoints
            for wpt in root.findall('.//gpx:wpt', namespaces) or root.findall('.//wpt'):
                lat = float(wpt.get('lat', 0))
                lon = float(wpt.get('lon', 0))
                
                time_elem = wpt.find('.//gpx:time', namespaces)
                if time_elem is None:
                    time_elem = wpt.find('.//time')
                if time_elem is not None and time_elem.text is not None:
                    timestamp = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.now()
                
                ele_elem = wpt.find('.//gpx:ele', namespaces)
                if ele_elem is None:
                    ele_elem = wpt.find('.//ele')
                altitude = float(ele_elem.text) if ele_elem is not None and ele_elem.text is not None else None
                
                points.append(GPSPoint(lat, lon, timestamp, altitude))
        
        except Exception as e:
            raise MetadataWriteError(f"Failed to parse GPX file: {str(e)}")
        
        return points
    
    @staticmethod
    def parse_nmea(nmea_file: str) -> List[GPSPoint]:
        """
        Parse NMEA (National Marine Electronics Association) file.
        
        Supports GPRMC and GPGGA sentences.
        
        Args:
            nmea_file: Path to NMEA file
            
        Returns:
            List of GPSPoint objects
        """
        points = []
        
        try:
            with open(nmea_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith('$'):
                        continue
                    
                    fields = line.split(',')
                    
                    if fields[0] == '$GPRMC' and len(fields) >= 12:
                        # Recommended Minimum Course
                        if fields[2] != 'A':  # Status must be 'A' (valid)
                            continue
                        
                        # Time
                        time_str = fields[1]
                        date_str = fields[9]
                        if len(time_str) >= 6 and len(date_str) >= 6:
                            # Handle milliseconds in time string (e.g., "120000.00")
                            time_clean = time_str.split('.')[0] if '.' in time_str else time_str
                            if len(time_clean) >= 6:
                                try:
                                    timestamp = datetime.strptime(
                                        f"{date_str} {time_clean}",
                                        "%d%m%y %H%M%S"
                                    )
                                except ValueError:
                                    continue
                            else:
                                continue
                        else:
                            continue
                        
                        # Latitude
                        lat_deg = float(fields[3][:2])
                        lat_min = float(fields[3][2:])
                        latitude = lat_deg + lat_min / 60.0
                        if fields[4] == 'S':
                            latitude = -latitude
                        
                        # Longitude
                        lon_deg = float(fields[5][:3])
                        lon_min = float(fields[5][3:])
                        longitude = lon_deg + lon_min / 60.0
                        if fields[6] == 'W':
                            longitude = -longitude
                        
                        points.append(GPSPoint(latitude, longitude, timestamp))
                    
                    elif fields[0] == '$GPGGA' and len(fields) >= 15:
                        # Global Positioning System Fix Data
                        if fields[6] == '0':  # Fix quality 0 = invalid
                            continue
                        
                        # Time
                        time_str = fields[1]
                        if len(time_str) >= 6:
                            # Use current date if not available
                            timestamp = datetime.now().replace(
                                hour=int(time_str[0:2]),
                                minute=int(time_str[2:4]),
                                second=int(time_str[4:6])
                            )
                        else:
                            continue
                        
                        # Latitude
                        lat_deg = float(fields[2][:2])
                        lat_min = float(fields[2][2:])
                        latitude = lat_deg + lat_min / 60.0
                        if fields[3] == 'S':
                            latitude = -latitude
                        
                        # Longitude
                        lon_deg = float(fields[4][:3])
                        lon_min = float(fields[4][3:])
                        longitude = lon_deg + lon_min / 60.0
                        if fields[5] == 'W':
                            longitude = -longitude
                        
                        # Altitude
                        altitude = None
                        if fields[9] and fields[9] != '':
                            altitude = float(fields[9])
                        
                        points.append(GPSPoint(latitude, longitude, timestamp, altitude))
        
        except Exception as e:
            raise MetadataWriteError(f"Failed to parse NMEA file: {str(e)}")
        
        return points
    
    @staticmethod
    def parse_kml(kml_file: str) -> List[GPSPoint]:
        """
        Parse KML (Keyhole Markup Language) file.
        
        Args:
            kml_file: Path to KML file
            
        Returns:
            List of GPSPoint objects
        """
        points = []
        
        try:
            tree = ET.parse(kml_file)
            root = tree.getroot()
            
            # Handle KML namespaces
            namespaces = {
                'kml': 'http://www.opengis.net/kml/2.2'
            }
            
            # Find all coordinates
            coord_elems = root.findall('.//kml:coordinates', namespaces)
            if not coord_elems:
                coord_elems = root.findall('.//coordinates')
            
            for coord_elem in coord_elems:
                if coord_elem.text:
                    coord_str = coord_elem.text.strip()
                    for coord_line in coord_str.split():
                        parts = coord_line.split(',')
                        if len(parts) >= 2:
                            longitude = float(parts[0])
                            latitude = float(parts[1])
                            altitude = float(parts[2]) if len(parts) >= 3 and parts[2] else None
                            
                            # Try to find timestamp - search in parent elements
                            timestamp = datetime.now()
                            parent = coord_elem
                            for _ in range(5):  # Search up to 5 levels up
                                when_elem = parent.find('.//kml:when', namespaces)
                                if when_elem is None:
                                    when_elem = parent.find('.//when')
                                if when_elem is not None and when_elem.text:
                                    try:
                                        timestamp = datetime.fromisoformat(when_elem.text.replace('Z', '+00:00'))
                                        break
                                    except:
                                        pass
                                # Move to parent
                                parent_list = list(parent)
                                if parent_list:
                                    parent = parent_list[0]
                                else:
                                    break
                            
                            points.append(GPSPoint(latitude, longitude, timestamp, altitude))
        
        except Exception as e:
            raise MetadataWriteError(f"Failed to parse KML file: {str(e)}")
        
        return points
    
    @staticmethod
    def parse_columbus_csv(csv_file: str) -> List[GPSPoint]:
        """
        Parse Columbus GPS logger CSV file.
        
        Columbus GPS loggers export CSV files with columns like:
        - Date, Time (or DateTime)
        - Latitude, Longitude
        - Altitude (optional)
        - Speed (optional)
        - Heading (optional)
        
        This parser is flexible and can handle various CSV formats with common column names.
        
        Args:
            csv_file: Path to Columbus GPS logger CSV file
            
        Returns:
            List of GPSPoint objects
        """
        points = []
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter (comma or semicolon)
                first_line = f.readline()
                f.seek(0)
                
                delimiter = ','
                if ';' in first_line and first_line.count(';') > first_line.count(','):
                    delimiter = ';'
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                # Normalize column names (case-insensitive, strip whitespace)
                fieldnames = [name.strip().lower() for name in reader.fieldnames or []]
                
                # Map common column name variations
                date_col = None
                time_col = None
                datetime_col = None
                lat_col = None
                lon_col = None
                alt_col = None
                direction_col = None
                
                for i, fieldname in enumerate(fieldnames):
                    fieldname_lower = fieldname.lower()
                    if 'date' in fieldname_lower and 'time' in fieldname_lower:
                        datetime_col = reader.fieldnames[i]
                    elif 'date' in fieldname_lower:
                        date_col = reader.fieldnames[i]
                    elif 'time' in fieldname_lower:
                        time_col = reader.fieldnames[i]
                    elif 'lat' in fieldname_lower:
                        lat_col = reader.fieldnames[i]
                    elif 'lon' in fieldname_lower or 'lng' in fieldname_lower:
                        lon_col = reader.fieldnames[i]
                    elif 'alt' in fieldname_lower or 'elevation' in fieldname_lower:
                        alt_col = reader.fieldnames[i]
                    elif 'direction' in fieldname_lower or 'bearing' in fieldname_lower or 'heading' in fieldname_lower or 'course' in fieldname_lower or 'ref' in fieldname_lower and 'direction' in fieldname_lower:
                        direction_col = reader.fieldnames[i]
                
                if not lat_col or not lon_col:
                    raise MetadataWriteError("CSV file must contain Latitude and Longitude columns")
                
                if not datetime_col and not (date_col and time_col):
                    raise MetadataWriteError("CSV file must contain DateTime or Date+Time columns")
                
                # Parse rows
                for row in reader:
                    try:
                        # Get latitude and longitude
                        lat_str = row.get(lat_col, '').strip()
                        lon_str = row.get(lon_col, '').strip()
                        
                        if not lat_str or not lon_str:
                            continue
                        
                        latitude = float(lat_str)
                        longitude = float(lon_str)
                        
                        # Validate coordinates
                        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                            continue
                        
                        # Parse timestamp
                        timestamp = None
                        if datetime_col:
                            dt_str = row.get(datetime_col, '').strip()
                            if dt_str:
                                # Try common datetime formats
                                for fmt in [
                                    '%Y-%m-%d %H:%M:%S',
                                    '%Y/%m/%d %H:%M:%S',
                                    '%d.%m.%Y %H:%M:%S',
                                    '%m/%d/%Y %H:%M:%S',
                                    '%Y-%m-%dT%H:%M:%S',
                                    '%Y-%m-%dT%H:%M:%SZ',
                                    '%Y-%m-%d %H:%M:%S.%f',
                                    '%Y-%m-%dT%H:%M:%S.%f',
                                    '%Y-%m-%dT%H:%M:%S.%fZ'
                                ]:
                                    try:
                                        timestamp = datetime.strptime(dt_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                        else:
                            date_str = row.get(date_col, '').strip()
                            time_str = row.get(time_col, '').strip()
                            
                            if date_str and time_str:
                                # Try common date/time formats
                                for date_fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y', '%m/%d/%Y']:
                                    for time_fmt in ['%H:%M:%S', '%H:%M:%S.%f', '%H:%M']:
                                        try:
                                            date_part = datetime.strptime(date_str, date_fmt).date()
                                            time_part = datetime.strptime(time_str, time_fmt).time()
                                            timestamp = datetime.combine(date_part, time_part)
                                            break
                                        except ValueError:
                                            continue
                                    if timestamp:
                                        break
                        
                        if not timestamp:
                            continue
                        
                        # Get altitude if available
                        altitude = None
                        if alt_col:
                            alt_str = row.get(alt_col, '').strip()
                            if alt_str:
                                try:
                                    altitude = float(alt_str)
                                except ValueError:
                                    pass
                        
                        # Get direction/bearing if available (reference direction column)
                        direction = None
                        if direction_col:
                            direction_str = row.get(direction_col, '').strip()
                            if direction_str:
                                try:
                                    direction = float(direction_str)
                                    # Normalize direction to 0-360 degrees
                                    if direction < 0:
                                        direction = direction + 360
                                    elif direction >= 360:
                                        direction = direction % 360
                                except ValueError:
                                    pass
                        
                        points.append(GPSPoint(latitude, longitude, timestamp, altitude, None, None, direction))
                        
                    except (ValueError, KeyError) as e:
                        # Skip invalid rows
                        continue
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to parse Columbus GPS logger CSV file: {str(e)}")
        
        return points
    
    @staticmethod
    def parse_google_takeout_json(json_file: str) -> List[GPSPoint]:
        """
        Parse Google Takeout JSON file (new format).
        
        Google Takeout exports location history in JSON format with structure like:
        {
          "locations": [
            {
              "timestampMs": "1234567890123",
              "latitudeE7": 1234567890,
              "longitudeE7": 1234567890,
              "accuracy": 20,
              "altitude": 100,
              ...
            }
          ]
        }
        
        Or JSON Lines format where each line is a JSON object.
        
        Args:
            json_file: Path to Google Takeout JSON file
            
        Returns:
            List of GPSPoint objects
        """
        points = []
        
        try:
            with open(json_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
                
                # Try to parse as JSON Lines format first (each line is a JSON object)
                if content.startswith('{') and '\n' in content:
                    # JSON Lines format
                    for line in content.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            # Handle single location object
                            if 'timestampMs' in data or 'timestamp' in data:
                                timestamp_ms = data.get('timestampMs') or data.get('timestamp')
                                if isinstance(timestamp_ms, str):
                                    timestamp_ms = int(timestamp_ms)
                                elif isinstance(timestamp_ms, int):
                                    pass
                                else:
                                    continue
                                
                                # Convert E7 coordinates (multiply by 1e-7)
                                lat_e7 = data.get('latitudeE7') or data.get('latitude')
                                lon_e7 = data.get('longitudeE7') or data.get('longitude')
                                
                                if lat_e7 is None or lon_e7 is None:
                                    continue
                                
                                # Handle E7 format (multiply by 1e-7) or regular format
                                if isinstance(lat_e7, int) and abs(lat_e7) > 1000:
                                    latitude = lat_e7 / 1e7
                                else:
                                    latitude = float(lat_e7)
                                
                                if isinstance(lon_e7, int) and abs(lon_e7) > 1000:
                                    longitude = lon_e7 / 1e7
                                else:
                                    longitude = float(lon_e7)
                                
                                # Validate coordinates
                                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                                    continue
                                
                                # Convert timestamp (milliseconds to datetime)
                                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
                                
                                # Get altitude if available
                                altitude = data.get('altitude') or data.get('altitudeMeters')
                                if altitude is not None:
                                    try:
                                        altitude = float(altitude)
                                    except (ValueError, TypeError):
                                        altitude = None
                                
                                points.append(GPSPoint(latitude, longitude, timestamp, altitude))
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
                else:
                    # Standard JSON format
                    data = json.loads(content)
                    
                    # Handle different JSON structures
                    locations = []
                    if 'locations' in data:
                        locations = data['locations']
                    elif isinstance(data, list):
                        locations = data
                    elif 'timelineObjects' in data:
                        # Alternative Google Takeout format
                        for obj in data['timelineObjects']:
                            if 'placeVisit' in obj:
                                place = obj['placeVisit']
                                if 'location' in place:
                                    loc = place['location']
                                    if 'latitudeE7' in loc and 'longitudeE7' in loc:
                                        locations.append({
                                            'latitudeE7': loc['latitudeE7'],
                                            'longitudeE7': loc['longitudeE7'],
                                            'timestampMs': place.get('duration', {}).get('startTimestampMs') or place.get('startTimestampMs')
                                        })
                            elif 'activitySegment' in obj:
                                segment = obj['activitySegment']
                                if 'waypointPath' in segment and 'waypoints' in segment['waypointPath']:
                                    for waypoint in segment['waypointPath']['waypoints']:
                                        if 'latE7' in waypoint and 'lngE7' in waypoint:
                                            locations.append({
                                                'latitudeE7': waypoint['latE7'],
                                                'longitudeE7': waypoint['lngE7'],
                                                'timestampMs': waypoint.get('timestampMs')
                                            })
                    
                    # Parse locations
                    for loc in locations:
                        try:
                            timestamp_ms = loc.get('timestampMs') or loc.get('timestamp')
                            if timestamp_ms is None:
                                continue
                            
                            if isinstance(timestamp_ms, str):
                                timestamp_ms = int(timestamp_ms)
                            elif not isinstance(timestamp_ms, int):
                                continue
                            
                            # Convert E7 coordinates (multiply by 1e-7) or regular format
                            lat_e7 = loc.get('latitudeE7') or loc.get('latitude') or loc.get('latE7')
                            lon_e7 = loc.get('longitudeE7') or loc.get('longitude') or loc.get('lngE7')
                            
                            if lat_e7 is None or lon_e7 is None:
                                continue
                            
                            # Handle E7 format (multiply by 1e-7) or regular format
                            if isinstance(lat_e7, int) and abs(lat_e7) > 1000:
                                latitude = lat_e7 / 1e7
                            else:
                                latitude = float(lat_e7)
                            
                            if isinstance(lon_e7, int) and abs(lon_e7) > 1000:
                                longitude = lon_e7 / 1e7
                            else:
                                longitude = float(lon_e7)
                            
                            # Validate coordinates
                            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                                continue
                            
                            # Convert timestamp (milliseconds to datetime)
                            timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
                            
                            # Get altitude if available
                            altitude = loc.get('altitude') or loc.get('altitudeMeters')
                            if altitude is not None:
                                try:
                                    altitude = float(altitude)
                                except (ValueError, TypeError):
                                    altitude = None
                            
                            points.append(GPSPoint(latitude, longitude, timestamp, altitude))
                            
                        except (ValueError, KeyError, TypeError) as e:
                            # Skip invalid entries
                            continue
                
        except json.JSONDecodeError as e:
            raise MetadataWriteError(f"Failed to parse Google Takeout JSON file: Invalid JSON format - {str(e)}")
        except Exception as e:
            raise MetadataWriteError(f"Failed to parse Google Takeout JSON file: {str(e)}")
        
        return points
    
    @staticmethod
    def geotag_from_track(
        image_file: str,
        track_file: str,
        time_offset: Optional[timedelta] = None,
        interpolate: bool = True,
        gps_hpos_err: Optional[float] = None,
        gps_quadrant: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Geotag an image from a GPS track log file.
        
        Args:
            image_file: Path to image file
            track_file: Path to GPS track log (GPX, NMEA, or KML)
            time_offset: Optional time offset to apply (for camera clock drift)
            interpolate: Whether to interpolate between GPS points
            
        Returns:
            Dictionary with geotagging results
        """
        # Parse track file based on extension
        track_path = Path(track_file)
        ext = track_path.suffix.lower()
        
        if ext == '.gpx':
            points = Geotagging.parse_gpx(track_file)
        elif ext == '.nmea' or ext == '.txt':
            points = Geotagging.parse_nmea(track_file)
        elif ext == '.kml':
            points = Geotagging.parse_kml(track_file)
        elif ext == '.csv':
            points = Geotagging.parse_columbus_csv(track_file)
        elif ext == '.json':
            points = Geotagging.parse_google_takeout_json(track_file)
        else:
            raise MetadataWriteError(f"Unsupported track file format: {ext}")
        
        if not points:
            raise MetadataWriteError("No GPS points found in track file")
        
        # Get image timestamp
        try:
            manager = DNExif(image_file)
            metadata = manager.get_all_metadata()
            
            # Try to get DateTimeOriginal
            dt_str = metadata.get('EXIF:DateTimeOriginal') or metadata.get('IFD0:DateTime')
            if not dt_str:
                raise MetadataWriteError("Image has no timestamp - cannot geotag")
            
            # Parse image timestamp
            image_dt = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
            
            # Apply time offset if provided
            if time_offset:
                image_dt = image_dt + time_offset
            
            # Find closest GPS point
            closest_point = None
            min_time_diff = None
            
            for point in points:
                time_diff = abs((point.timestamp - image_dt).total_seconds())
                if min_time_diff is None or time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_point = point
            
            if not closest_point:
                raise MetadataWriteError("Could not find matching GPS point")
            
            # Interpolate if requested and we have multiple points
            if interpolate and len(points) > 1:
                # Find points before and after image time
                before = None
                after = None
                
                for point in points:
                    if point.timestamp <= image_dt:
                        if before is None or point.timestamp > before.timestamp:
                            before = point
                    else:
                        if after is None or point.timestamp < after.timestamp:
                            after = point
                
                if before and after:
                    # Interpolate
                    total_time = (after.timestamp - before.timestamp).total_seconds()
                    image_time = (image_dt - before.timestamp).total_seconds()
                    ratio = image_time / total_time if total_time > 0 else 0
                    
                    latitude = before.latitude + (after.latitude - before.latitude) * ratio
                    longitude = before.longitude + (after.longitude - before.longitude) * ratio
                    altitude = None
                    if before.altitude is not None and after.altitude is not None:
                        altitude = before.altitude + (after.altitude - before.altitude) * ratio
                    
                    closest_point = GPSPoint(latitude, longitude, image_dt, altitude)
            
            # Geotag the image
            from dnexif.advanced_features import AdvancedFeatures
            result = AdvancedFeatures.geotag(
                image_file,
                closest_point.latitude,
                closest_point.longitude,
                closest_point.altitude
            )
            
            # Write GPSDOP and GPSMeasureMode if accuracy_horizontal (hdop/pdop) information exists
            if closest_point.accuracy_horizontal is not None:
                try:
                    manager = DNExif(image_file)
                    
                    # Convert accuracy_horizontal to HDOP (approximately accuracy / 5)
                    # HDOP is typically accuracy / 5 meters
                    hdop = closest_point.accuracy_horizontal / 5.0
                    
                    # Write GPSDOP (GPS Dilution of Precision)
                    # GPSDOP is typically HDOP for horizontal accuracy
                    manager.set_tag('GPS:GPSDOP', f"{hdop:.2f}")
                    
                    # Write GPSMeasureMode
                    # 2 = 2D measurement (no altitude), 3 = 3D measurement (with altitude)
                    if closest_point.altitude is not None:
                        manager.set_tag('GPS:GPSMeasureMode', '3')
                    else:
                        manager.set_tag('GPS:GPSMeasureMode', '2')
                    
                    manager.save()
                    result['gpsdop'] = hdop
                    result['gpsmeasuremode'] = '3' if closest_point.altitude is not None else '2'
                except Exception:
                    # If writing GPSDOP/GPSMeasureMode fails, continue without them
                    pass
            
            # Write GPSHPositioningError if GeoHPosErr option is provided
            if gps_hpos_err is not None:
                try:
                    manager = DNExif(image_file)
                    # GPSHPositioningError is stored in meters
                    manager.set_tag('GPS:GPSHPositioningError', f"{gps_hpos_err:.2f}")
                    manager.save()
                    result['gpshposerr'] = gps_hpos_err
                except Exception:
                    # If writing GPSHPositioningError fails, continue without it
                    pass
            
            # Write GPSQuadrant if GPSQuadrant option is provided
            if gps_quadrant is not None:
                try:
                    manager = DNExif(image_file)
                    # Validate quadrant value (N, S, E, W, NE, NW, SE, SW)
                    valid_quadrants = ['N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW']
                    quadrant_upper = gps_quadrant.upper()
                    if quadrant_upper in valid_quadrants:
                        # Store GPSQuadrant as a custom tag or use GPSImgDirectionRef if appropriate
                        # For now, store as a custom tag GPS:GPSQuadrant
                        manager.set_tag('GPS:GPSQuadrant', quadrant_upper)
                        manager.save()
                        result['gpsquadrant'] = quadrant_upper
                except Exception:
                    # If writing GPSQuadrant fails, continue without it
                    pass
            
            # Write GPSImgDirection if reference direction is available from CSV
            if closest_point.direction is not None:
                try:
                    manager = DNExif(image_file)
                    # GPSImgDirection is stored in degrees (0-360)
                    # GPSImgDirectionRef: 'M' = Magnetic North, 'T' = True North
                    manager.set_tag('GPS:GPSImgDirectionRef', 'T')  # Default to True North
                    manager.set_tag('GPS:GPSImgDirection', f"{closest_point.direction:.2f}")
                    manager.save()
                    result['gpsimgdirection'] = closest_point.direction
                except Exception:
                    # If writing GPSImgDirection fails, continue without it
                    pass
            
            result['time_offset'] = min_time_diff
            result['interpolated'] = interpolate and len(points) > 1
            
            return result
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to geotag from track: {str(e)}")
    
    @staticmethod
    def export_to_gpx(
        image_file: str,
        output_file: str
    ) -> None:
        """
        Export GPS coordinates from image to GPX file.
        
        Args:
            image_file: Path to image file
            output_file: Path to output GPX file
        """
        try:
            manager = DNExif(image_file)
            metadata = manager.get_all_metadata()
            
            # Get GPS coordinates
            lat_ref = metadata.get('GPS:GPSLatitudeRef')
            lat = metadata.get('GPS:GPSLatitude')
            lon_ref = metadata.get('GPS:GPSLongitudeRef')
            lon = metadata.get('GPS:GPSLongitude')
            alt = metadata.get('GPS:GPSAltitude')
            
            if not lat or not lon:
                raise MetadataWriteError("Image has no GPS coordinates")
            
            # Parse coordinates (format: "deg/1 min/1 sec/100")
            def parse_coord(coord_str, ref):
                parts = coord_str.split()
                deg = float(parts[0].split('/')[0]) / float(parts[0].split('/')[1])
                min_val = float(parts[1].split('/')[0]) / float(parts[1].split('/')[1])
                sec = float(parts[2].split('/')[0]) / float(parts[2].split('/')[1])
                coord = deg + min_val/60.0 + sec/3600.0
                if ref in ('S', 'W'):
                    coord = -coord
                return coord
            
            latitude = parse_coord(lat, lat_ref)
            longitude = parse_coord(lon, lon_ref)
            altitude = None
            if alt:
                altitude = float(alt.split('/')[0]) / float(alt.split('/')[1])
            
            # Get timestamp
            dt_str = metadata.get('EXIF:DateTimeOriginal') or metadata.get('IFD0:DateTime')
            timestamp = datetime.now()
            if dt_str:
                timestamp = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
            
            # Create GPX file
            gpx = ET.Element('gpx', version='1.1', xmlns='http://www.topografix.com/GPX/1/1')
            wpt = ET.SubElement(gpx, 'wpt', lat=str(latitude), lon=str(longitude))
            time_elem = ET.SubElement(wpt, 'time')
            time_elem.text = timestamp.isoformat()
            if altitude is not None:
                ele_elem = ET.SubElement(wpt, 'ele')
                ele_elem.text = str(altitude)
            
            tree = ET.ElementTree(gpx)
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
        
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to export to GPX: {str(e)}")
    
    @staticmethod
    def write_timed_gps_to_gpx(
        gps_points: List[GPSPoint],
        output_file: str,
        track_name: str = "GPS Track"
    ) -> None:
        """
        Write timed GPS points to GPX file.
        
        This is useful for exporting timed GPS data from videos (dashcam, drone, etc.)
        to GPX format for use in mapping applications.
        
        Args:
            gps_points: List of GPSPoint objects with timestamps
            output_file: Path to output GPX file
            track_name: Name for the track in GPX file
        """
        if not gps_points:
            raise MetadataWriteError("No GPS points provided")
        
        try:
            # Create GPX file structure
            gpx = ET.Element('gpx', version='1.1', xmlns='http://www.topografix.com/GPX/1/1')
            
            # Create track
            trk = ET.SubElement(gpx, 'trk')
            name_elem = ET.SubElement(trk, 'name')
            name_elem.text = track_name
            
            # Create track segment
            trkseg = ET.SubElement(trk, 'trkseg')
            
            # Add track points
            for point in gps_points:
                trkpt = ET.SubElement(trkseg, 'trkpt', lat=str(point.latitude), lon=str(point.longitude))
                
                # Add timestamp
                time_elem = ET.SubElement(trkpt, 'time')
                time_elem.text = point.timestamp.isoformat() + 'Z' if point.timestamp.tzinfo is None else point.timestamp.isoformat()
                
                # Add elevation if available
                if point.altitude is not None:
                    ele_elem = ET.SubElement(trkpt, 'ele')
                    ele_elem.text = str(point.altitude)
                
                # Add extensions for speed and accuracy if available
                if point.speed is not None or point.accuracy_horizontal is not None:
                    extensions = ET.SubElement(trkpt, 'extensions')
                    if point.speed is not None:
                        speed_elem = ET.SubElement(extensions, 'speed', xmlns='http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1')
                        speed_elem.text = str(point.speed)
                    if point.accuracy_horizontal is not None:
                        accuracy_elem = ET.SubElement(extensions, 'accuracy', xmlns='http://www.opentracksapp.com/xmlschemas/GpxExtensions/v1')
                        accuracy_elem.text = str(point.accuracy_horizontal)
            
            # Write GPX file
            tree = ET.ElementTree(gpx)
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write GPX file: {str(e)}")
    
    @staticmethod
    def write_timed_gps_to_kml(
        gps_points: List[GPSPoint],
        output_file: str,
        placemark_name: str = "GPS Track"
    ) -> None:
        """
        Write timed GPS points to KML file (Google Earth format).
        
        This is useful for exporting timed GPS data from videos (dashcam, drone, etc.)
        to KML format for viewing in Google Earth.
        
        Args:
            gps_points: List of GPSPoint objects with timestamps
            output_file: Path to output KML file
            placemark_name: Name for the placemark in KML file
        """
        if not gps_points:
            raise MetadataWriteError("No GPS points provided")
        
        try:
            # Create KML file structure
            kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
            document = ET.SubElement(kml, 'Document')
            
            name_elem = ET.SubElement(document, 'name')
            name_elem.text = placemark_name
            
            # Create placemark
            placemark = ET.SubElement(document, 'Placemark')
            pm_name = ET.SubElement(placemark, 'name')
            pm_name.text = placemark_name
            
            # Create LineString for track
            line_string = ET.SubElement(placemark, 'LineString')
            tessellate = ET.SubElement(line_string, 'tessellate')
            tessellate.text = '1'
            
            # Create coordinates string
            coordinates = []
            for point in gps_points:
                coord_str = f"{point.longitude},{point.latitude}"
                if point.altitude is not None:
                    coord_str += f",{point.altitude}"
                else:
                    coord_str += ",0"
                coordinates.append(coord_str)
            
            coord_elem = ET.SubElement(line_string, 'coordinates')
            coord_elem.text = ' '.join(coordinates)
            
            # Add TimeSpan if timestamps are available
            if gps_points[0].timestamp and gps_points[-1].timestamp:
                time_span = ET.SubElement(placemark, 'TimeSpan')
                begin = ET.SubElement(time_span, 'begin')
                begin.text = gps_points[0].timestamp.isoformat() + 'Z' if gps_points[0].timestamp.tzinfo is None else gps_points[0].timestamp.isoformat()
                end = ET.SubElement(time_span, 'end')
                end.text = gps_points[-1].timestamp.isoformat() + 'Z' if gps_points[-1].timestamp.tzinfo is None else gps_points[-1].timestamp.isoformat()
            
            # Write KML file
            tree = ET.ElementTree(kml)
            tree.write(output_file, encoding='utf-8', xml_declaration=True)
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write KML file: {str(e)}")

