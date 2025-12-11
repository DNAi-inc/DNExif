# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Geolocation module - Reverse geolocation (city name to GPS coordinates).

This module provides functionality to obtain GPS coordinates from city names,
which is useful for geotagging images with location information.
"""

from typing import Optional, Dict, Any, List
import re


class Geolocation:
    """
    Geolocation service for reverse geocoding (city name to GPS coordinates).
    
    This is a basic implementation that can be enhanced with a full geolocation
    database (e.g., geonames.org) for accurate reverse geocoding.
    """
    
    # Basic city database (can be expanded or replaced with external database)
    # Format: {city_name: {'latitude': float, 'longitude': float, 'country': str}}
    CITY_DATABASE = {
        'new york': {'latitude': 40.7128, 'longitude': -74.0060, 'country': 'USA'},
        'los angeles': {'latitude': 34.0522, 'longitude': -118.2437, 'country': 'USA'},
        'chicago': {'latitude': 41.8781, 'longitude': -87.6298, 'country': 'USA'},
        'houston': {'latitude': 29.7604, 'longitude': -95.3698, 'country': 'USA'},
        'phoenix': {'latitude': 33.4484, 'longitude': -112.0740, 'country': 'USA'},
        'london': {'latitude': 51.5074, 'longitude': -0.1278, 'country': 'UK'},
        'paris': {'latitude': 48.8566, 'longitude': 2.3522, 'country': 'France'},
        'tokyo': {'latitude': 35.6762, 'longitude': 139.6503, 'country': 'Japan'},
        'sydney': {'latitude': -33.8688, 'longitude': 151.2093, 'country': 'Australia'},
        'toronto': {'latitude': 43.6532, 'longitude': -79.3832, 'country': 'Canada'},
    }
    
    def __init__(self, database: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize Geolocation service.
        
        Args:
            database: Optional custom city database dictionary
        """
        self.database = database if database else self.CITY_DATABASE
    
    def geolocate(self, city_name: str, use_regex: bool = False) -> Optional[Dict[str, Any]]:
        """
        Obtain GPS coordinates from city name (reverse geolocation).
        
        Args:
            city_name: Name of the city
            use_regex: If True, use regular expression matching for city names
            
        Returns:
            Dictionary with GPS coordinates and location information, or None if not found
        """
        if not city_name:
            return None
        
        city_name_lower = city_name.lower().strip()
        
        # Direct lookup
        if city_name_lower in self.database:
            result = self.database[city_name_lower].copy()
            result['city'] = city_name
            result['Geolocation:City'] = city_name
            result['Geolocation:Latitude'] = result['latitude']
            result['Geolocation:Longitude'] = result['longitude']
            result['Geolocation:Country'] = result.get('country', '')
            return result
        
        # Regex matching if enabled
        if use_regex:
            for db_city, location_data in self.database.items():
                pattern = re.compile(re.escape(city_name_lower), re.IGNORECASE)
                if pattern.search(db_city):
                    result = location_data.copy()
                    result['city'] = city_name
                    result['Geolocation:City'] = city_name
                    result['Geolocation:Latitude'] = result['latitude']
                    result['Geolocation:Longitude'] = result['longitude']
                    result['Geolocation:Country'] = result.get('country', '')
                    return result
        
        # Partial match (contains)
        for db_city, location_data in self.database.items():
            if city_name_lower in db_city or db_city in city_name_lower:
                result = location_data.copy()
                result['city'] = city_name
                result['Geolocation:City'] = city_name
                result['Geolocation:Latitude'] = result['latitude']
                result['Geolocation:Longitude'] = result['longitude']
                result['Geolocation:Country'] = result.get('country', '')
                return result
        
        return None
    
    def add_city(self, city_name: str, latitude: float, longitude: float, country: str = '') -> None:
        """
        Add a city to the geolocation database.
        
        Args:
            city_name: Name of the city
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            country: Country name (optional)
        """
        if not (-90 <= latitude <= 90):
            raise ValueError(f"Invalid latitude: {latitude}")
        if not (-180 <= longitude <= 180):
            raise ValueError(f"Invalid longitude: {longitude}")
        
        self.database[city_name.lower()] = {
            'latitude': latitude,
            'longitude': longitude,
            'country': country
        }
    
    def get_coordinates(self, city_name: str, use_regex: bool = False) -> Optional[tuple]:
        """
        Get GPS coordinates as a tuple (latitude, longitude).
        
        Args:
            city_name: Name of the city
            use_regex: If True, use regular expression matching
            
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        result = self.geolocate(city_name, use_regex=use_regex)
        if result:
            return (result['latitude'], result['longitude'])
        return None
    
    def geolocate_with_feature_type(self, city_name: str, use_regex: bool = False) -> Optional[Dict[str, Any]]:
        """
        Geolocate city and add feature type information.
        
        Args:
            city_name: Name of the city
            use_regex: If True, use regular expression matching
            
        Returns:
            Dictionary with GPS coordinates and feature type information, or None if not found
        """
        result = self.geolocate(city_name, use_regex=use_regex)
        if result:
            # Add feature type (city, town, village, etc.)
            # This is a simplified implementation - full version would use geonames.org feature codes
            result['Geolocation:FeatureType'] = 'city'  # Default to city
            result['Geolocation:FeatureCode'] = 'PPL'  # Place (PPL) code from geonames.org
            return result
        return None
    
    def geolocate_with_alternate_names(self, city_name: str) -> Optional[Dict[str, Any]]:
        """
        Geolocate city with support for alternate city names.
        
        Args:
            city_name: Name of the city (can be alternate name)
            
        Returns:
            Dictionary with GPS coordinates and location information, or None if not found
        """
        # Try direct lookup first
        result = self.geolocate(city_name)
        if result:
            return result
        
        # Try common alternate names
        alternate_names = {
            'nyc': 'new york',
            'new york city': 'new york',
            'la': 'los angeles',
            'sf': 'san francisco',
            'sf bay area': 'san francisco',
            'sf bay': 'san francisco',
        }
        
        city_name_lower = city_name.lower().strip()
        if city_name_lower in alternate_names:
            return self.geolocate(alternate_names[city_name_lower])
        
        return None
    
    def geolocate_with_language(self, city_name: str, language: str = 'en') -> Optional[Dict[str, Any]]:
        """
        Geolocate city with language translation support.
        
        Args:
            city_name: Name of the city (can be in different language)
            language: Language code for location names (default: 'en')
            
        Returns:
            Dictionary with GPS coordinates and location information, or None if not found
        """
        # Try direct lookup first
        result = self.geolocate(city_name)
        if result:
            result['Geolocation:Language'] = language
            return result
        
        # Language-specific city name mappings (can be expanded)
        language_mappings = {
            'es': {  # Spanish
                'nueva york': 'new york',
                'los angeles': 'los angeles',
                'londres': 'london',
                'paris': 'paris',
                'tokio': 'tokyo',
            },
            'fr': {  # French
                'new york': 'new york',
                'los angeles': 'los angeles',
                'londres': 'london',
                'paris': 'paris',
                'tokyo': 'tokyo',
            },
            'de': {  # German
                'new york': 'new york',
                'los angeles': 'los angeles',
                'london': 'london',
                'paris': 'paris',
                'tokio': 'tokyo',
            },
            'ja': {  # Japanese
                'ニューヨーク': 'new york',
                'ロサンゼルス': 'los angeles',
                'ロンドン': 'london',
                'パリ': 'paris',
                '東京': 'tokyo',
            },
        }
        
        city_name_lower = city_name.lower().strip()
        if language in language_mappings and city_name_lower in language_mappings[language]:
            english_name = language_mappings[language][city_name_lower]
            result = self.geolocate(english_name)
            if result:
                result['Geolocation:Language'] = language
                result['Geolocation:OriginalName'] = city_name
                return result
        
        return None
    
    def geolocate_and_geotag(self, file_path: str, city_name: str, use_regex: bool = False, 
                             use_alternate_names: bool = True, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Geolocate a city and geotag an image file with the coordinates.
        
        This combines reverse geolocation (city name to GPS) with geotagging
        (writing GPS coordinates to image file).
        
        Args:
            file_path: Path to image file to geotag
            city_name: Name of the city to geolocate
            use_regex: If True, use regular expression matching for city names
            use_alternate_names: If True, try alternate names if direct lookup fails
            language: Optional language code for city name translation
            
        Returns:
            Dictionary with geolocation and geotagging results, or None if city not found
        """
        from pathlib import Path
        from dnexif.advanced_features import AdvancedFeatures
        
        # Try to geolocate the city
        result = None
        
        # Try language translation first if language specified
        if language:
            result = self.geolocate_with_language(city_name, language=language)
        
        # Try alternate names if enabled
        if not result and use_alternate_names:
            result = self.geolocate_with_alternate_names(city_name)
        
        # Try direct geolocation
        if not result:
            result = self.geolocate(city_name, use_regex=use_regex)
        
        if not result:
            return None
        
        # Geotag the file with the coordinates
        try:
            geotag_result = AdvancedFeatures.geotag(
                file_path,
                result['latitude'],
                result['longitude']
            )
            
            # Combine results
            combined_result = result.copy()
            combined_result['Geotagging:File'] = str(file_path)
            combined_result['Geotagging:Success'] = True
            combined_result['Geotagging:Latitude'] = result['latitude']
            combined_result['Geotagging:Longitude'] = result['longitude']
            
            return combined_result
            
        except Exception as e:
            # Return geolocation result even if geotagging fails
            result['Geotagging:Success'] = False
            result['Geotagging:Error'] = str(e)
            return result
    
    def geolocate_and_write_location_shown(self, file_path: str, city_name: str, 
                                           use_regex: bool = False, use_alternate_names: bool = True,
                                           language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Geolocate a city and write XMP-iptcExt LocationShown tags to an image file.
        
        This combines reverse geolocation (city name to GPS) with writing
        XMP-iptcExt LocationShown tags (IPTC Extension location shown metadata).
        
        Args:
            file_path: Path to image file to write LocationShown tags
            city_name: Name of the city to geolocate
            use_regex: If True, use regular expression matching for city names
            use_alternate_names: If True, try alternate names if direct lookup fails
            language: Optional language code for city name translation
            
        Returns:
            Dictionary with geolocation and LocationShown writing results, or None if city not found
        """
        from pathlib import Path
        from dnexif.core import DNExif
        
        # Try to geolocate the city
        result = None
        
        # Try language translation first if language specified
        if language:
            result = self.geolocate_with_language(city_name, language=language)
        
        # Try alternate names if enabled
        if not result and use_alternate_names:
            result = self.geolocate_with_alternate_names(city_name)
        
        # Try direct geolocation
        if not result:
            result = self.geolocate(city_name, use_regex=use_regex)
        
        if not result:
            return None
        
        # Write XMP-iptcExt LocationShown tags
        try:
            with DNExif(file_path) as exif:
                # Write LocationShown tags
                exif.set_tag('XMP:LocationShownCity', result.get('city', city_name))
                exif.set_tag('XMP:LocationShownCountryName', result.get('country', ''))
                exif.set_tag('XMP:LocationShownProvinceState', result.get('state', ''))
                
                # Write GPS coordinates if available
                if 'latitude' in result and 'longitude' in result:
                    exif.set_tag('XMP:LocationShownGPSLatitude', result['latitude'])
                    exif.set_tag('XMP:LocationShownGPSLongitude', result['longitude'])
                
                # Write feature type and code if available
                if 'Geolocation:FeatureType' in result:
                    exif.set_tag('XMP:LocationShownFeatureType', result['Geolocation:FeatureType'])
                if 'Geolocation:FeatureCode' in result:
                    exif.set_tag('XMP:LocationShownFeatureCode', result['Geolocation:FeatureCode'])
                
                exif.save()
            
            # Combine results
            combined_result = result.copy()
            combined_result['LocationShown:File'] = str(file_path)
            combined_result['LocationShown:Success'] = True
            combined_result['LocationShown:City'] = result.get('city', city_name)
            combined_result['LocationShown:Country'] = result.get('country', '')
            
            return combined_result
            
        except Exception as e:
            # Return geolocation result even if writing fails
            result['LocationShown:Success'] = False
            result['LocationShown:Error'] = str(e)
            return result

