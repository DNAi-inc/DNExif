# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Core DNExif class

This module provides the main API for reading and writing metadata from image files.
It combines EXIF, IPTC, and XMP parsers into a unified interface.

This is a 100% pure Python implementation - no external standard format dependencies.

Copyright 2025 DNAi inc.
"""

from typing import Dict, Any, Optional, Union, List, Callable
from pathlib import Path
import tempfile
import struct
import sys
import os

from dnexif.exif_parser import ExifParser
from dnexif.exif_writer import EXIFWriter
from dnexif.iptc_parser import IPTCParser
from dnexif.iptc_writer import IPTCWriter
from dnexif.xmp_parser import XMPParser
from dnexif.xmp_writer import XMPWriter
from dnexif.raw_parser import RAWParser
from dnexif.tiff_writer import TIFFWriter
from dnexif.png_writer import PNGWriter
from dnexif.webp_writer import WebPWriter
from dnexif.webp_parser import WebPParser
from dnexif.gif_writer import GIFWriter
from dnexif.raw_writer import RAWWriter
from dnexif.video_writer import VideoWriter
from dnexif.audio_writer import AudioWriter
from dnexif.pdf_writer import PDFWriter
from dnexif.heic_writer import HEICWriter
from dnexif.bmp_writer import BMPWriter
from dnexif.svg_writer import SVGWriter
from dnexif.psd_writer import PSDWriter
from dnexif.metadata_standards_writer import MetadataStandardsWriter
from dnexif.jpeg_modifier import JPEGModifier
from dnexif.format_detector import FormatDetector
from dnexif.video_parser import VideoParser
from dnexif.document_parser import DocumentParser
from dnexif.audio_parser import AudioParser
from dnexif.ico_parser import ICOParser
from dnexif.pcx_parser import PCXParser
from dnexif.tga_parser import TGAParser
from dnexif.tga_writer import TGAWriter
from dnexif.exceptions import (
    DNExifError,
    MetadataReadError,
    MetadataWriteError,
    UnsupportedFormatError,
    InvalidTagError,
)
from dnexif.value_formatter import format_exif_value
from dnexif.image_hash_calculator import calculate_image_data_hash, add_image_data_hash_to_metadata
try:
    from dnexif.exif_tags import EXIF_TAG_NAMES
except ImportError:
    EXIF_TAG_NAMES = {}
try:
    from dnexif.iptc_tags import IPTC_TAG_NAMES
except ImportError:
    IPTC_TAG_NAMES = {}
import os
import stat
from datetime import datetime, timedelta, timezone


class DNExif:
    """
    Main class for reading and writing metadata from image files.
    
    This is a 100% pure Python implementation with no dependencies on
    external standard format executables or libraries. All metadata parsing is
    done natively in Python by reading binary file structures.
    
    Supports EXIF, IPTC, and XMP metadata standards.
    
    Example:
        >>> with DNExif('image.jpg') as exif:
        ...     metadata = exif.get_all_metadata()
        ...     camera = exif.get_tag('EXIF:Make')
        ...     exif.set_tag('EXIF:Artist', 'John Doe')
        ...     exif.save()
    """
    
    # Supported file formats
    SUPPORTED_FORMATS = {
        # Image formats
        '.jpg', '.jpeg', '.jph', '.jfif', '.jpe', '.tif', '.tiff', '.png',
        '.heic', '.heif', '.avif', '.jxl', '.bmp', '.svg', '.psd', '.gif', '.webp',
        '.ico', '.cur', '.pcx', '.tga',
        # RAW formats
        '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.raf',
        '.rw2', '.srw', '.srf', '.sr2', '.pef', '.x3f', '.crw', '.mrw', '.mdc', '.nrw', '.3fr', '.erf', '.mef', '.mos', '.dcr', '.gpr', '.kdc', '.ari', '.bay', '.dcs', '.drf', '.eip', '.fff', '.iiq', '.rwl', '.hif', '.raw',
        # Thermal formats
        '.seq',
        # Document formats
        '.pdf',
        # Video formats
        '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp', '.3g2', '.wtv', '.dvr-ms', '.dvr_ms',
        # Audio formats
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus', '.dsf',
        # Medical imaging formats
        '.dcm', '.dicom', '.DCM', '.DICOM',
        # Nikon adjustment formats
        '.nka', '.nxd',
        # Astronomical image formats
        '.xisf', '.fts',
        # GPS formats
        '.gpx', '.kml',
        # Data formats
        '.csv',
        # Windows formats
        '.url', '.lnk', '.exe', '.dll', '.sys', '.ocx', '.drv', '.scr', '.cpl', '.tnef', '.dat',
        # HDR image formats
        '.pfm', '.hdr', '.exr',
        # Stereo image formats
        '.jps',
        # Medical/scientific image formats
        '.mrc',
        # Preset formats
        '.onp',
        # Font formats
        '.woff', '.woff2',
        # Network capture formats
        '.pcap', '.cap', '.pcapng',
        # Graphics formats
        '.wpg', '.mng',
        # Document formats
        '.vnt',
        # Thermal imaging formats
        '.ijpeg',
        # Leica formats
        '.lif', '.lifext',
        # macOS formats
        '.ds_store', '.lifext',
        # Zeiss formats
        '.czi',
        # Archive formats
        '.7z', '.rar', '.zip',
        # Apple formats
        '.aae',
        # Metadata sidecar formats
        '.xmp', '.exif', '.iptc',
        # Additional image formats
        '.jp2', '.dds', '.pam', '.pbm', '.cube',
        # Text formats
        '.txt', '.log',
        # Data formats
        '.json', '.xml', '.pgm', '.pnm', '.ppm', '.pcd', '.pes', '.picon', '.pict', '.ras', '.sfw', '.sgi', '.wbmp', '.xbm', '.xcf', '.xpm', '.xwd', '.mng'
    }
    
    def __init__(
        self,
        file_path: Union[str, Path],
        read_only: bool = False,
        fast_mode: bool = False,
        scan_for_xmp: bool = False,
        ignore_minor_errors: bool = False,
        length: Optional[int] = None
    ):
        """
        Initialize DNExif with an image file.
        
        Args:
            file_path: Path to the image file
            read_only: If True, file will not be modified (default: False)
            fast_mode: If True, skip some processing for faster execution (default: False)
            scan_for_xmp: If True, scan entire file for XMP packets (default: False)
            ignore_minor_errors: If True, ignore minor parsing errors (default: False)
            length: Optional maximum number of bytes to read from file for optimization.
                   Metadata is typically in the first 128KB of files. If None, reads entire file.
                   Note: May miss metadata in unusual locations if length is too small.
            
        Raises:
            FileNotFoundError: If the file does not exist
            UnsupportedFormatError: If the file format is not supported
        """
        self.file_path = Path(file_path)
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file format (allow .DS_Store files without extension)
        file_ext = self.file_path.suffix.lower()
        if file_ext not in self.SUPPORTED_FORMATS and not (self.file_path.name == '.DS_Store'):
            raise UnsupportedFormatError(
                f"Unsupported file format: {self.file_path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )
        
        self.read_only = read_only
        self.fast_mode = fast_mode
        self.scan_for_xmp = scan_for_xmp
        self.ignore_minor_errors = ignore_minor_errors
        self.length = length  # Maximum bytes to read for optimization
        self.metadata: Dict[str, Any] = {}
        self.modified_tags: Dict[str, Any] = {}
        self._exif_parser: Optional[ExifParser] = None
        self._iptc_parser: Optional[IPTCParser] = None
        self._xmp_parser: Optional[XMPParser] = None
        self.alternate_files: Dict[int, Path] = {}  # Dictionary mapping index to alternate file paths
        self._cached_file_data: Optional[bytes] = None  # Cached file data (can be cleared to save memory)
        
        # Initialize API options with defaults
        self.options: Dict[str, Any] = {}
        self._initialize_default_options()
        
        # Apply FastScan option to fast_mode if set
        if self.get_option('FastScan', False):
            self.fast_mode = True
        
        # Load metadata
        self._load_metadata()
    
    def _initialize_default_options(self) -> None:
        """
        Initialize default API options from available_options().
        """
        available = self.available_options()
        for option_name, option_info in available.items():
            if 'default' in option_info:
                self.options[option_name] = option_info['default']
    
    def set_option(self, option_name: str, value: Any) -> None:
        """
        Set an API option value.
        
        Args:
            option_name: Name of the option (e.g., 'NoWarning', 'ByteUnit')
            value: Value to set for the option
            
        Raises:
            ValueError: If option name is not recognized
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('NoWarning', True)
            >>> exif.set_option('ByteUnit', 'KB')
        """
        available = self.available_options()
        if option_name not in available:
            raise ValueError(f"Unknown option: {option_name}. Use available_options() to see valid options.")
        
        # Validate value type if option info specifies type
        option_info = available[option_name]
        if 'type' in option_info:
            expected_type = option_info['type']
            if expected_type == 'bool' and not isinstance(value, bool):
                # Try to convert string 'true'/'false' to bool
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    value = bool(value)
            elif expected_type == 'int' and not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Option {option_name} requires int value, got {type(value).__name__}")
            elif expected_type == 'float' and not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Option {option_name} requires float value, got {type(value).__name__}")
        
        self.options[option_name] = value
    
    def get_option(self, option_name: str, default: Any = None) -> Any:
        """
        Get an API option value.
        
        Args:
            option_name: Name of the option (e.g., 'NoWarning', 'ByteUnit')
            default: Default value if option is not set
            
        Returns:
            Option value or default if not set
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> no_warning = exif.get_option('NoWarning', False)
            >>> byte_unit = exif.get_option('ByteUnit', 'B')
        """
        return self.options.get(option_name, default)
    
    def set_user_param(self, param_name: str, value: Any) -> None:
        """
        Set a user-defined parameter using the UserParam option.
        
        User parameters can be used in formatting expressions and other operations.
        They are stored in the UserParam option dictionary.
        
        Args:
            param_name: Name of the parameter
            value: Value to set for the parameter
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_user_param('CustomValue', 'test')
            >>> value = exif.get_user_param('CustomValue')
            >>> print(value)  # 'test'
        """
        user_params = self.get_option('UserParam', {})
        if not isinstance(user_params, dict):
            user_params = {}
        user_params[param_name] = value
        self.set_option('UserParam', user_params)
    
    def get_user_param(self, param_name: str, default: Any = None) -> Any:
        """
        Get a user-defined parameter from the UserParam option.
        
        Args:
            param_name: Name of the parameter
            default: Default value if parameter is not found
            
        Returns:
            Parameter value or default if not found
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_user_param('CustomValue', 'test')
            >>> value = exif.get_user_param('CustomValue')
            >>> print(value)  # 'test'
        """
        user_params = self.get_option('UserParam', {})
        if isinstance(user_params, dict):
            return user_params.get(param_name, default)
        return default
    
    def get_all_user_params(self) -> Dict[str, Any]:
        """
        Get all user-defined parameters from the UserParam option.
        
        Returns:
            Dictionary of all user parameters
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_user_param('Param1', 'value1')
            >>> exif.set_user_param('Param2', 'value2')
            >>> all_params = exif.get_all_user_params()
            >>> print(all_params)  # {'Param1': 'value1', 'Param2': 'value2'}
        """
        user_params = self.get_option('UserParam', {})
        if isinstance(user_params, dict):
            return user_params.copy()
        return {}
    
    def encode_file_name(self, file_name: str) -> bytes:
        """
        Encode a file name using the CharsetFileName option.
        
        Args:
            file_name: File name string to encode
            
        Returns:
            Encoded file name as bytes
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('CharsetFileName', 'UTF8')
            >>> encoded = exif.encode_file_name('test.jpg')
        """
        charset = self.get_option('CharsetFileName', 'UTF8').upper()
        
        # Map common charset names to Python encoding names
        charset_map = {
            'UTF8': 'utf-8',
            'UTF-8': 'utf-8',
            'LATIN1': 'latin-1',
            'LATIN-1': 'latin-1',
            'ISO-8859-1': 'latin-1',
            'ASCII': 'ascii',
            'CP1252': 'cp1252',
            'WINDOWS-1252': 'cp1252',
        }
        
        encoding = charset_map.get(charset, charset.lower())
        
        try:
            return file_name.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            # Fallback to UTF-8 if encoding fails
            return file_name.encode('utf-8')
    
    def decode_file_name(self, file_name_bytes: bytes) -> str:
        """
        Decode a file name using the CharsetFileName option.
        
        Args:
            file_name_bytes: File name bytes to decode
            
        Returns:
            Decoded file name as string
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('CharsetFileName', 'UTF8')
            >>> decoded = exif.decode_file_name(b'test.jpg')
        """
        charset = self.get_option('CharsetFileName', 'UTF8').upper()
        
        # Map common charset names to Python encoding names
        charset_map = {
            'UTF8': 'utf-8',
            'UTF-8': 'utf-8',
            'LATIN1': 'latin-1',
            'LATIN-1': 'latin-1',
            'ISO-8859-1': 'latin-1',
            'ASCII': 'ascii',
            'CP1252': 'cp1252',
            'WINDOWS-1252': 'cp1252',
        }
        
        encoding = charset_map.get(charset, charset.lower())
        
        try:
            return file_name_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # Fallback to UTF-8 if decoding fails
            return file_name_bytes.decode('utf-8', errors='replace')
    
    def apply_global_time_shift(self) -> int:
        """
        Apply GlobalTimeShift option to all timestamp tags.
        
        Shifts all date/time tags by the amount specified in GlobalTimeShift option.
        Format: "+1:00:00" (hours:minutes:seconds) or "+30" (seconds) or "-1:30:00"
        
        Returns:
            Number of tags that were shifted
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('GlobalTimeShift', '+1:00:00')
            >>> shifted_count = exif.apply_global_time_shift()
        """
        global_time_shift = self.get_option('GlobalTimeShift', '')
        
        if not global_time_shift:
            return 0
        
        # Parse time shift value
        try:
            if ':' in global_time_shift:
                # Format: "+1:00:00" or "-1:30:00"
                parts = global_time_shift.replace('+', '').replace('-', '').split(':')
                hours = int(parts[0]) if len(parts) > 0 else 0
                minutes = int(parts[1]) if len(parts) > 1 else 0
                seconds = int(parts[2]) if len(parts) > 2 else 0
                shift = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                if global_time_shift.startswith('-'):
                    shift = -shift
            else:
                # Format: "+30" or "-30" (seconds)
                seconds = int(global_time_shift)
                shift = timedelta(seconds=seconds)
        except (ValueError, TypeError):
            # Invalid format, return 0
            return 0
        
        # List of date/time tag patterns
        date_tag_patterns = [
            'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
            'CreateDate', 'ModifyDate', 'GPSDateStamp', 'GPSTimeStamp',
            'FileModifyDate', 'FileAccessDate', 'FileInodeChangeDate'
        ]
        
        shifted_count = 0
        
        # Get all tags from both metadata and modified_tags
        all_tags = {}
        all_tags.update(self.metadata)
        all_tags.update(self.modified_tags)
        
        # Apply shift to all matching tags
        for tag_name in list(all_tags.keys()):
            # Check if tag matches any date pattern
            matches_pattern = any(pattern in tag_name for pattern in date_tag_patterns)
            
            if matches_pattern:
                value = all_tags.get(tag_name)
                if isinstance(value, str):
                    try:
                        # Try to parse as datetime
                        # Common formats: '2023:01:15 12:30:45', '2023-01-15 12:30:45', etc.
                        dt = None
                        for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                            try:
                                dt = datetime.strptime(value, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if dt is not None:
                            new_dt = dt + shift
                            new_value = new_dt.strftime('%Y:%m:%d %H:%M:%S')
                            self.set_tag(tag_name, new_value)
                            shifted_count += 1
                    except Exception:
                        # Skip tags that can't be parsed as dates
                        pass
        
        return shifted_count
    
    def format_gps_speed(self, speed_value: Union[int, float], speed_ref: Optional[str] = None) -> str:
        """
        Format a GPS speed value using the GeoSpeedRef option.
        
        Formats GPS speed values according to the GeoSpeedRef option setting:
        - 'K': kilometers per hour (km/h)
        - 'M': miles per hour (mph)
        - 'N': knots (nautical miles per hour)
        
        Args:
            speed_value: Speed value to format (in m/s if speed_ref is None)
            speed_ref: Optional speed reference ('K', 'M', 'N'). If None, uses GeoSpeedRef option.
            
        Returns:
            Formatted string with appropriate unit
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('GeoSpeedRef', 'K')
            >>> formatted = exif.format_gps_speed(10.0)  # 10 m/s -> km/h
        """
        if speed_ref is None:
            speed_ref = self.get_option('GeoSpeedRef', 'K').upper()
        else:
            speed_ref = speed_ref.upper()
        
        speed_value = float(speed_value)
        
        # If speed_ref is not set or empty, default to km/h
        if not speed_ref:
            speed_ref = 'K'
        
        if speed_ref == 'K':
            # Convert m/s to km/h (multiply by 3.6)
            speed_kmh = speed_value * 3.6
            return f"{speed_kmh:.2f} km/h"
        elif speed_ref == 'M':
            # Convert m/s to mph (multiply by 2.237)
            speed_mph = speed_value * 2.237
            return f"{speed_mph:.2f} mph"
        elif speed_ref == 'N':
            # Convert m/s to knots (multiply by 1.944)
            speed_knots = speed_value * 1.944
            return f"{speed_knots:.2f} knots"
        else:
            # Default to km/h for unknown reference
            speed_kmh = speed_value * 3.6
            return f"{speed_kmh:.2f} km/h"
    
    def format_datetime_with_utc(self, dt: datetime, tag_name: str = '') -> str:
        """
        Format a datetime value using the KeepUTCTime option.
        
        If KeepUTCTime is enabled, preserves UTC timezone information.
        If KeepUTCTime is disabled, converts to local time or removes timezone.
        
        Args:
            dt: Datetime object to format
            tag_name: Optional tag name for context
            
        Returns:
            Formatted datetime string
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('KeepUTCTime', True)
            >>> from datetime import datetime, timezone
            >>> dt = datetime(2023, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
            >>> formatted = exif.format_datetime_with_utc(dt)
        """
        keep_utc = self.get_option('KeepUTCTime', False)
        
        if keep_utc and dt.tzinfo:
            # Keep UTC timezone information
            # Format as: YYYY:MM:DD HH:MM:SS+00:00 for UTC
            date_str = dt.strftime('%Y:%m:%d %H:%M:%S')
            offset = dt.utcoffset()
            if offset:
                total_seconds = int(offset.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                if hours == 0 and minutes == 0:
                    date_str += '+00:00'  # UTC
                else:
                    if hours >= 0:
                        date_str += f"+{hours:02d}:{minutes:02d}"
                    else:
                        date_str += f"{hours:03d}:{minutes:02d}"
            else:
                date_str += '+00:00'  # UTC
            return date_str
        else:
            # Convert to naive datetime (remove timezone) or use as-is
            if dt.tzinfo:
                # Convert to UTC first, then remove timezone info
                dt_utc = dt.astimezone(timezone.utc)
                dt_naive = dt_utc.replace(tzinfo=None)
            else:
                dt_naive = dt
            return dt_naive.strftime('%Y:%m:%d %H:%M:%S')
    
    def limit_long_value(self, value: Any) -> Any:
        """
        Limit the length of a tag value using the LimitLongValues option.
        
        If LimitLongValues is set to a positive integer, truncates string values
        and limits list/tuple lengths to that value.
        
        Args:
            value: Tag value to limit
            
        Returns:
            Limited value (truncated if necessary)
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('LimitLongValues', 100)
            >>> limited = exif.limit_long_value('A' * 200)  # Truncates to 100 chars
        """
        limit = self.get_option('LimitLongValues', 0)
        
        if limit <= 0:
            # No limit, return as-is
            return value
        
        if isinstance(value, str):
            # Truncate string to limit
            if len(value) > limit:
                return value[:limit]
            return value
        elif isinstance(value, (list, tuple)):
            # Limit list/tuple length
            if len(value) > limit:
                limited = value[:limit]
                return type(value)(limited)  # Preserve original type
            return value
        elif isinstance(value, bytes):
            # Truncate bytes to limit
            if len(value) > limit:
                return value[:limit]
            return value
        else:
            # For other types, convert to string and truncate
            value_str = str(value)
            if len(value_str) > limit:
                return value_str[:limit]
            return value
    
    def format_byte_value(self, bytes_value: Union[int, float]) -> str:
        """
        Format a byte value using the ByteUnit option.
        
        Formats byte values according to the ByteUnit option setting:
        - 'B': bytes (no conversion)
        - 'KB': kilobytes (1000 bytes)
        - 'MB': megabytes (1000 * 1000 bytes)
        - 'GB': gigabytes (1000 * 1000 * 1000 bytes)
        
        Args:
            bytes_value: Byte value to format
            
        Returns:
            Formatted string with appropriate unit
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('ByteUnit', 'KB')
            >>> formatted = exif.format_byte_value(1500)
            >>> print(formatted)  # "1.5 KB"
        """
        byte_unit = self.get_option('ByteUnit', 'B').upper()
        bytes_value = int(bytes_value)
        
        if byte_unit == 'B':
            return f"{bytes_value} bytes"
        elif byte_unit == 'KB':
            size_kb = bytes_value / 1000.0
            if size_kb < 10 and abs(size_kb - round(size_kb)) >= 0.05:
                return f"{size_kb:.1f} KB"
            return f"{round(size_kb)} KB"
        elif byte_unit == 'MB':
            size_mb = bytes_value / (1000.0 * 1000.0)
            if size_mb < 10 and abs(size_mb - round(size_mb)) >= 0.05:
                return f"{size_mb:.1f} MB"
            return f"{round(size_mb)} MB"
        elif byte_unit == 'GB':
            size_gb = bytes_value / (1000.0 * 1000.0 * 1000.0)
            if size_gb < 10 and abs(size_gb - round(size_gb)) >= 0.05:
                return f"{size_gb:.1f} GB"
            return f"{round(size_gb)} GB"
        else:
            # Unknown unit, default to bytes
            return f"{bytes_value} bytes"
    
    def format_tag_name_with_id(self, tag_name: str) -> str:
        """
        Format a tag name with its ID using the HexTagIDs option.
        
        If HexTagIDs option is enabled, appends hexadecimal tag ID to tag name.
        Format: "TagName [0xXXXX]" for EXIF tags, "TagName [ID]" for other tags.
        
        Args:
            tag_name: Tag name to format (e.g., 'EXIF:Make', 'IPTC:Keywords')
            
        Returns:
            Formatted tag name with ID if HexTagIDs is enabled, otherwise original tag name
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('HexTagIDs', True)
            >>> formatted = exif.format_tag_name_with_id('EXIF:Make')
            >>> print(formatted)  # "EXIF:Make [0x010F]"
        """
        if not self.get_option('HexTagIDs', False):
            return tag_name
        
        # Extract group and tag name
        if ':' in tag_name:
            group, name = tag_name.split(':', 1)
        else:
            group = ''
            name = tag_name
        
        tag_id = None
        
        # Look up tag ID based on group
        if group == 'EXIF' and EXIF_TAG_NAMES:
            # Reverse lookup: tag_name -> tag_id
            for tid, tname in EXIF_TAG_NAMES.items():
                if tname == name:
                    tag_id = tid
                    break
        
        elif group == 'IPTC' and IPTC_TAG_NAMES:
            # IPTC uses dataset numbers
            if name in IPTC_TAG_NAMES:
                tag_id = IPTC_TAG_NAMES[name]
        
        # Format with hexadecimal ID
        if tag_id is not None:
            if isinstance(tag_id, int):
                return f"{tag_name} [0x{tag_id:04X}]"
            else:
                return f"{tag_name} [{tag_id}]"
        
        return tag_name
    
    def format_list_value(self, value: Any) -> Any:
        """
        Format a list value using the ListJoin option.
        
        If ListJoin option is set, joins list values with the specified separator.
        If ListJoin is empty or not set, returns the original value.
        
        Args:
            value: Value to format (list, tuple, or other value)
            
        Returns:
            Joined string if value is a list/tuple and ListJoin is set, otherwise original value
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('ListJoin', ', ')
            >>> formatted = exif.format_list_value(['tag1', 'tag2', 'tag3'])
            >>> print(formatted)  # "tag1, tag2, tag3"
        """
        list_join = self.get_option('ListJoin', '')
        
        # If ListJoin is not set or empty, return original value
        if not list_join:
            return value
        
        # If value is a list or tuple, join with separator
        if isinstance(value, (list, tuple)):
            # Convert all items to strings and join
            return list_join.join(str(item) for item in value)
        
        # For non-list values, return as-is
        return value
    
    def remove_duplicates_from_list(self, value: Any) -> Any:
        """
        Remove duplicate items from list-type tags using the NoDups option.
        
        If NoDups option is enabled, removes duplicate items from list/tuple values
        while preserving order (first occurrence is kept).
        If NoDups is disabled or value is not a list/tuple, returns the original value.
        
        Args:
            value: Value to process (list, tuple, or other value)
            
        Returns:
            List with duplicates removed if NoDups is enabled and value is a list/tuple,
            otherwise original value
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('NoDups', True)
            >>> deduplicated = exif.remove_duplicates_from_list(['tag1', 'tag2', 'tag1', 'tag3'])
            >>> print(deduplicated)  # ['tag1', 'tag2', 'tag3']
        """
        if not self.get_option('NoDups', False):
            return value
        
        # If value is a list or tuple, remove duplicates while preserving order
        if isinstance(value, (list, tuple)):
            seen = set()
            result = []
            for item in value:
                # Use tuple for hashable items, string representation for unhashable items
                try:
                    item_key = item
                except TypeError:
                    item_key = str(item)
                
                if item_key not in seen:
                    seen.add(item_key)
                    result.append(item)
            
            # Return same type as input (list or tuple)
            if isinstance(value, tuple):
                return tuple(result)
            return result
        
        # For non-list values, return as-is
        return value
    
    def format_structured_value(self, value: Any) -> str:
        """
        Format a structured value using the StructFormat option.
        
        If StructFormat option is set to 'JSON' or 'JSONQ', formats structured values
        (dictionaries, lists, tuples) as JSON strings.
        If StructFormat is not set or value is not structured, returns string representation.
        
        Args:
            value: Value to format (dict, list, tuple, or other value)
            
        Returns:
            JSON string if StructFormat is JSON/JSONQ and value is structured,
            otherwise string representation
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('StructFormat', 'JSON')
            >>> formatted = exif.format_structured_value({'key': 'value', 'number': 123})
            >>> print(formatted)  # '{"key": "value", "number": 123}'
        """
        struct_format = self.get_option('StructFormat', 'JSON').upper()
        
        # Check if value is a structured type (dict, list, tuple)
        if isinstance(value, (dict, list, tuple)):
            import json
            
            if struct_format in ('JSON', 'JSONQ'):
                try:
                    # Format as JSON
                    json_str = json.dumps(value, default=str, ensure_ascii=False)
                    
                    # JSONQ format: quote the JSON string
                    if struct_format == 'JSONQ':
                        return json.dumps(json_str, ensure_ascii=False)
                    
                    return json_str
                except Exception:
                    # If JSON serialization fails, fall back to string representation
                    return str(value)
        
        # For non-structured values, return string representation
        return str(value)
    
    def should_ignore_tag(self, tag_name: str) -> bool:
        """
        Check if a tag should be ignored based on the IgnoreTags and IgnoreGroups options.
        
        If IgnoreTags option is set, checks if the tag name matches any of the
        ignored tag patterns (supports wildcards with *).
        If IgnoreGroups option is set, checks if the tag's group matches any of the
        ignored group names.
        
        Args:
            tag_name: Tag name to check (e.g., 'EXIF:Make', 'IPTC:Keywords')
            
        Returns:
            True if tag should be ignored, False otherwise
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('IgnoreTags', ['EXIF:Artist', 'IPTC:*'])
            >>> exif.should_ignore_tag('EXIF:Artist')  # True
            >>> exif.should_ignore_tag('IPTC:Keywords')  # True
            >>> exif.should_ignore_tag('EXIF:Make')  # False
            >>> exif.set_option('IgnoreGroups', ['EXIF'])
            >>> exif.should_ignore_tag('EXIF:Make')  # True
        """
        # Check IgnoreTags option first
        ignore_tags = self.get_option('IgnoreTags', [])
        
        if ignore_tags:
            # Support both list and string (single tag)
            if isinstance(ignore_tags, str):
                ignore_tags = [ignore_tags]
            
            from fnmatch import fnmatch
            
            # Check if tag matches any ignore pattern
            for pattern in ignore_tags:
                if fnmatch(tag_name, pattern) or tag_name == pattern:
                    return True
        
        # Check IgnoreGroups option
        ignore_groups = self.get_option('IgnoreGroups', [])
        
        if ignore_groups:
            # Support both list and string (single group)
            if isinstance(ignore_groups, str):
                ignore_groups = [ignore_groups]
            
            # Extract group from tag name (part before colon)
            if ':' in tag_name:
                tag_group = tag_name.split(':', 1)[0]
                # Case-insensitive comparison
                for group in ignore_groups:
                    if tag_group.lower() == group.lower():
                        return True
        
        return False
    
    def format_text_output(self, text: str) -> str:
        """
        Format text output using the Compact option.
        
        If Compact option is enabled, removes blank lines and extra whitespace
        to create compact output format.
        
        Args:
            text: Text output to format
            
        Returns:
            Formatted text (compact if Compact option is enabled)
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('Compact', True)
            >>> formatted = exif.format_text_output("Tag1: Value1\\n\\nTag2: Value2")
            >>> print(formatted)  # "Tag1: Value1\\nTag2: Value2" (blank line removed)
        """
        if not self.get_option('Compact', False):
            return text
        
        # Remove blank lines and normalize whitespace
        lines = []
        for line in text.split('\n'):
            stripped = line.rstrip()
            if stripped:  # Skip blank lines
                lines.append(stripped)
        
        return '\n'.join(lines)
    
    def format_xmp_tag_name(self, tag_name: str) -> str:
        """
        Format XMP tag name using XMPShorthand option.
        
        If XMPShorthand option is enabled, removes the "XMP:" prefix from tag names
        to use shorthand notation (e.g., "XMP:Title" becomes "Title").
        If XMPShorthand is disabled or tag is not an XMP tag, returns original tag name.
        
        Args:
            tag_name: Tag name to format (e.g., 'XMP:Title', 'EXIF:Make')
            
        Returns:
            Formatted tag name (shorthand if XMPShorthand is enabled and tag is XMP),
            otherwise original tag name
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('XMPShorthand', True)
            >>> formatted = exif.format_xmp_tag_name('XMP:Title')
            >>> print(formatted)  # 'Title'
            >>> formatted = exif.format_xmp_tag_name('EXIF:Make')
            >>> print(formatted)  # 'EXIF:Make' (not XMP, so unchanged)
        """
        if not self.get_option('XMPShorthand', False):
            return tag_name
        
        # Remove XMP: prefix for shorthand notation
        if tag_name.startswith('XMP:'):
            return tag_name[4:]  # Remove "XMP:" prefix
        
        # Also handle XMP- prefixed tags (some formats use XMP- prefix)
        if tag_name.startswith('XMP-'):
            return tag_name[4:]  # Remove "XMP-" prefix
        
        return tag_name
    
    def calculate_image_data_hash(self) -> Optional[str]:
        """
        Calculate hash of image data (excluding metadata) using ImageHashType option.
        
        This method uses the ImageHashType option to determine which hash algorithm
        to use (MD5, SHA1, SHA256). The hash is calculated from image pixel data only,
        excluding all metadata segments.
        
        Returns:
            Hexadecimal hash string or None if calculation fails
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('ImageHashType', 'SHA256')
            >>> hash_value = exif.calculate_image_data_hash()
        """
        hash_type = self.get_option('ImageHashType', 'MD5').upper()
        # Normalize hash type (MD5 -> md5, SHA1 -> sha1, SHA256 -> sha256)
        if hash_type == 'MD5':
            hash_type = 'md5'
        elif hash_type == 'SHA1':
            hash_type = 'sha1'
        elif hash_type == 'SHA256':
            hash_type = 'sha256'
        else:
            # Default to md5 if unknown type
            hash_type = 'md5'
        
        return calculate_image_data_hash(self.file_path, hash_type=hash_type)
    
    def _get_file_path_string(self, file_path: Optional[Union[str, Path]] = None) -> str:
        """
        Get file path as string, applying WindowsLongPath and WindowsWideFile options if needed.
        
        On Windows, when WindowsLongPath option is enabled and path is longer
        than 260 characters, prefixes the path with "\\?\" to enable long path support.
        
        On Windows, when WindowsWideFile option is enabled, ensures the path is properly
        encoded for wide character file operations.
        
        Args:
            file_path: Optional file path. If None, uses self.file_path.
            
        Returns:
            File path as string with WindowsLongPath/WindowsWideFile options applied if needed.
        """
        if file_path is None:
            file_path = self.file_path
        else:
            file_path = Path(file_path)
        
        path_str = str(file_path)
        
        # Check if WindowsLongPath option is enabled
        windows_long_path = self.get_option('WindowsLongPath', False)
        
        # Check if WindowsWideFile option is enabled
        windows_wide_file = self.get_option('WindowsWideFile', False)
        
        # Only apply on Windows
        if sys.platform == 'win32':
            # Apply WindowsLongPath prefix if needed
            if windows_long_path:
                # Check if path is longer than MAX_PATH (260 characters)
                if len(path_str) > 260:
                    # Apply Windows long path prefix "\\?\"
                    # Convert to absolute path first
                    abs_path = os.path.abspath(path_str)
                    if not abs_path.startswith('\\\\?\\'):
                        # Prefix with "\\?\" for long path support
                        path_str = '\\\\?\\' + abs_path
            
            # Apply WindowsWideFile encoding if needed
            # Python's pathlib and open() already handle Unicode paths correctly on Windows,
            # but we ensure proper encoding when WindowsWideFile is enabled
            if windows_wide_file:
                # On Windows, Python automatically handles wide character paths,
                # but we can ensure the path is properly normalized
                # Convert to absolute path to ensure proper encoding
                if not path_str.startswith('\\\\?\\'):
                    # Normalize path for wide character support
                    path_str = os.path.normpath(path_str)
        
        return path_str
    
    def _read_file_data(self, max_length: Optional[int] = None) -> bytes:
        """
        Read file data, optionally limiting to specified length for optimization.
        
        Uses buffered reading for large files (>10MB) to reduce memory usage.
        If LargeFileSupport option is enabled, ensures proper handling of files >2GB.
        Python 3 handles large files natively, but this option serves as a compatibility flag.
        
        Args:
            max_length: Optional maximum length to read (overrides self.length if provided)
        
        Returns:
            File data as bytes, limited to max_length or self.length if specified
        """
        # Check LargeFileSupport option (Python 3 handles large files natively)
        large_file_support = self.get_option('LargeFileSupport', True)
        
        # Use WindowsLongPath-aware path conversion
        file_path_str = self._get_file_path_string()
        
        # Determine read length
        read_length = max_length if max_length is not None else self.length
        
        # Get file size to determine if buffered reading should be used
        file_size = self.file_path.stat().st_size
        
        # Use buffered reading for large files (>10MB) to reduce memory usage
        # This is especially important when reading entire file
        BUFFER_SIZE = 1024 * 1024  # 1MB buffer
        LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB threshold
        
        with open(file_path_str, 'rb', buffering=BUFFER_SIZE) as f:
            if read_length is not None:
                # Read specific length (optimized for small reads)
                if read_length <= BUFFER_SIZE:
                    return f.read(read_length)
                else:
                    # For larger reads, use buffered reading
                    data = bytearray()
                    remaining = read_length
                    while remaining > 0:
                        chunk_size = min(BUFFER_SIZE, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        data.extend(chunk)
                        remaining -= len(chunk)
                    return bytes(data)
            else:
                # Read entire file
                if file_size <= LARGE_FILE_THRESHOLD:
                    # Small files: read all at once (faster)
                    return f.read()
                else:
                    # Large files: use buffered reading to reduce memory usage
                    data = bytearray()
                    while True:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        data.extend(chunk)
                    return bytes(data)
    
    def _parse_jpeg_dimensions(self) -> tuple:
        """
        Parse JPEG image dimensions from SOF (Start of Frame) segment.
        
        Returns:
            Tuple of (width, height) or (None, None) if not found
        """
        try:
            with open(str(self.file_path), 'rb') as f:
                file_data = f.read(65536)  # Read first 64KB
            
            if not file_data.startswith(b'\xff\xd8'):
                return (None, None)
            
            # Simple search for SOF markers
            # SOF markers: 0xFFC0-0xFFC3, 0xFFC5-0xFFC7, 0xFFC9-0xFFCB, 0xFFCD-0xFFCF
            sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
            
            # Search for 0xFF followed by a SOF marker
            max_search = len(file_data) - 9
            for i in range(max_search):
                if file_data[i] == 0xFF:
                    marker = file_data[i + 1]
                    if marker in sof_markers:
                        # Found SOF marker at offset i
                        # Check we have enough data
                        if i + 9 <= len(file_data):
                            # Height is at i + 5 (2 bytes, big-endian)
                            height = struct.unpack('>H', file_data[i + 5:i + 7])[0]
                            # Width is at i + 7 (2 bytes, big-endian)
                            width = struct.unpack('>H', file_data[i + 7:i + 9])[0]
                            return (width, height)
        except Exception as e:
            # JPEG dimension parsing is optional - silently fail if parsing fails
            # This is non-critical metadata that doesn't affect core functionality
            pass
        
        return (None, None)
    
    def _parse_png_header(self) -> Dict[str, Any]:
        """
        Parse PNG header (IHDR chunk) to extract image properties.
        
        Returns:
            Dictionary of PNG metadata tags
        """
        metadata = {}
        try:
            with open(str(self.file_path), 'rb') as f:
                file_data = f.read(33)  # Read enough for PNG signature + IHDR chunk
            
            # Check PNG signature
            if file_data[:8] != b'\x89PNG\r\n\x1a\n':
                return metadata
            
            # IHDR chunk starts at offset 8 (after signature)
            # IHDR structure: length(4) + 'IHDR'(4) + width(4) + height(4) + bit_depth(1) + 
            #                 color_type(1) + compression(1) + filter(1) + interlace(1) + CRC(4)
            if len(file_data) < 33:
                return metadata
            
            # Skip chunk length (4 bytes) and chunk type (4 bytes) = offset 16
            width = struct.unpack('>I', file_data[16:20])[0]
            height = struct.unpack('>I', file_data[20:24])[0]
            bit_depth = file_data[24]
            color_type = file_data[25]
            compression = file_data[26]
            filter_method = file_data[27]
            interlace = file_data[28]
            
            # Add PNG tags
            metadata['PNG:ImageWidth'] = width
            metadata['PNG:ImageHeight'] = height
            metadata['PNG:BitDepth'] = bit_depth
            
            # ColorType mapping
            color_type_map = {
                0: 'Grayscale',
                2: 'RGB',
                3: 'Palette',
                4: 'Grayscale with Alpha',
                6: 'RGB with Alpha'
            }
            metadata['PNG:ColorType'] = color_type_map.get(color_type, f'Unknown ({color_type})')
            
            # Compression (always 0 = Deflate/Inflate for PNG)
            if compression == 0:
                metadata['PNG:Compression'] = 'Deflate/Inflate'
            else:
                metadata['PNG:Compression'] = f'Unknown ({compression})'
            
            # Filter (always 0 = Adaptive for PNG)
            if filter_method == 0:
                metadata['PNG:Filter'] = 'Adaptive'
            else:
                metadata['PNG:Filter'] = f'Unknown ({filter_method})'
            
            # Interlace
            if interlace == 0:
                metadata['PNG:Interlace'] = 'Noninterlaced'
            elif interlace == 1:
                metadata['PNG:Interlace'] = 'Adam7 Interlace'
            else:
                metadata['PNG:Interlace'] = f'Unknown ({interlace})'
                
        except Exception as e:
            # PNG header parsing is optional - silently fail if parsing fails
            # This is non-critical metadata that doesn't affect core functionality
            pass
        
        return metadata
    
    def _parse_png_text_chunks(self) -> Dict[str, Any]:
        """
        Parse PNG tEXt, zTXt, and iTXt chunks to extract text metadata.
        This includes Stable Diffusion metadata stored in tEXt chunks.
        
        Returns:
            Dictionary of PNG text metadata tags
        """
        metadata = {}
        try:
            with open(str(self.file_path), 'rb') as f:
                file_data = f.read()
            
            # Check PNG signature
            if file_data[:8] != b'\x89PNG\r\n\x1a\n':
                return metadata
            
            offset = 8  # Skip PNG signature
            
            while offset < len(file_data) - 8:
                # Read chunk length (4 bytes, big-endian)
                if offset + 4 > len(file_data):
                    break
                chunk_length = struct.unpack('>I', file_data[offset:offset + 4])[0]
                offset += 4
                
                # Read chunk type (4 bytes)
                if offset + 4 > len(file_data):
                    break
                chunk_type = file_data[offset:offset + 4]
                offset += 4
                
                # Read chunk data
                if offset + chunk_length > len(file_data):
                    break
                chunk_data = file_data[offset:offset + chunk_length]
                offset += chunk_length
                
                # Skip CRC (4 bytes)
                if offset + 4 > len(file_data):
                    break
                offset += 4
                
                # Parse tEXt chunks (uncompressed text)
                if chunk_type == b'tEXt':
                    try:
                        # tEXt format: keyword (null-terminated) + text
                        null_pos = chunk_data.find(b'\x00')
                        if null_pos > 0:
                            keyword = chunk_data[:null_pos].decode('ascii', errors='ignore')
                            text = chunk_data[null_pos + 1:].decode('utf-8', errors='ignore')
                            
                            # Store as PNG:Text:Keyword tag
                            tag_name = f'PNG:Text:{keyword}'
                            metadata[tag_name] = text
                            
                            # Check for Stable Diffusion metadata
                            if keyword.lower() in ('parameters', 'comment', 'usercomment'):
                                # Check if it looks like Stable Diffusion metadata
                                if 'steps:' in text.lower() or 'sampler:' in text.lower() or 'cfg scale:' in text.lower():
                                    metadata['PNG:StableDiffusion:Parameters'] = text
                                    # Try to parse individual parameters
                                    self._parse_stable_diffusion_parameters(text, metadata)
                    except Exception:
                        pass
                
                # Parse zTXt chunks (compressed text)
                elif chunk_type == b'zTXt':
                    try:
                        import zlib
                        # zTXt format: keyword (null-terminated) + compression method (1 byte) + compressed text
                        null_pos = chunk_data.find(b'\x00')
                        if null_pos > 0:
                            keyword = chunk_data[:null_pos].decode('ascii', errors='ignore')
                            compression_method = chunk_data[null_pos + 1]
                            compressed_text = chunk_data[null_pos + 2:]
                            
                            if compression_method == 0:  # zlib compression
                                try:
                                    text = zlib.decompress(compressed_text).decode('utf-8', errors='ignore')
                                    tag_name = f'PNG:Text:{keyword}'
                                    metadata[tag_name] = text
                                    
                                    # Check for Stable Diffusion metadata
                                    if keyword.lower() in ('parameters', 'comment', 'usercomment'):
                                        if 'steps:' in text.lower() or 'sampler:' in text.lower() or 'cfg scale:' in text.lower():
                                            metadata['PNG:StableDiffusion:Parameters'] = text
                                            self._parse_stable_diffusion_parameters(text, metadata)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                
                # Stop at IEND chunk
                if chunk_type == b'IEND':
                    break
                    
        except Exception as e:
            # PNG text chunk parsing is optional - silently fail if parsing fails
            pass
        
        return metadata
    
    def _parse_stable_diffusion_parameters(self, text: str, metadata: Dict[str, Any]) -> None:
        """
        Parse Stable Diffusion parameters from text string.
        
        Args:
            text: Parameter text string
            metadata: Metadata dictionary to update
        """
        try:
            # Common Stable Diffusion parameter patterns
            import re
            
            # Steps: 20
            steps_match = re.search(r'steps:\s*(\d+)', text, re.IGNORECASE)
            if steps_match:
                metadata['PNG:StableDiffusion:Steps'] = int(steps_match.group(1))
            
            # Sampler: Euler a
            sampler_match = re.search(r'sampler:\s*([^\n,]+)', text, re.IGNORECASE)
            if sampler_match:
                metadata['PNG:StableDiffusion:Sampler'] = sampler_match.group(1).strip()
            
            # CFG Scale: 7
            cfg_match = re.search(r'cfg\s*scale:\s*([\d.]+)', text, re.IGNORECASE)
            if cfg_match:
                metadata['PNG:StableDiffusion:CFGScale'] = float(cfg_match.group(1))
            
            # Seed: 12345
            seed_match = re.search(r'seed:\s*(\d+)', text, re.IGNORECASE)
            if seed_match:
                metadata['PNG:StableDiffusion:Seed'] = int(seed_match.group(1))
            
            # Size: 512x512
            size_match = re.search(r'size:\s*(\d+)\s*x\s*(\d+)', text, re.IGNORECASE)
            if size_match:
                metadata['PNG:StableDiffusion:Width'] = int(size_match.group(1))
                metadata['PNG:StableDiffusion:Height'] = int(size_match.group(2))
            
            # Model: model_name
            model_match = re.search(r'model:\s*([^\n,]+)', text, re.IGNORECASE)
            if model_match:
                metadata['PNG:StableDiffusion:Model'] = model_match.group(1).strip()
            
            # Prompt extraction (usually first line or after "Prompt:")
            prompt_match = re.search(r'(?:prompt:)?\s*([^\n]+)', text, re.IGNORECASE)
            if prompt_match:
                prompt = prompt_match.group(1).strip()
                # Remove common prefixes
                prompt = re.sub(r'^(prompt|positive prompt):\s*', '', prompt, flags=re.IGNORECASE)
                if prompt and len(prompt) > 5:  # Reasonable prompt length
                    metadata['PNG:StableDiffusion:Prompt'] = prompt
            
            # Negative prompt
            neg_match = re.search(r'negative\s*prompt:\s*([^\n]+)', text, re.IGNORECASE)
            if neg_match:
                metadata['PNG:StableDiffusion:NegativePrompt'] = neg_match.group(1).strip()
                
        except Exception:
            # Parameter parsing is optional - silently fail if parsing fails
            pass
    
    def _add_file_tags(self) -> None:
        """
        Add File tags (FileSize, FilePermissions, FileType, etc.) to metadata.
        These tags standard format's File group tags.
        """
        try:
            # SourceFile - standard format includes this tag
            self.metadata['SourceFile'] = str(self.file_path)
            
            # File:FileName
            self.metadata['File:FileName'] = self.file_path.name
            
            # File:Directory
            self.metadata['File:Directory'] = str(self.file_path.parent)
            
            # File:FileSize (store as bytes, will be formatted by value_formatter)
            try:
                file_size = self.file_path.stat().st_size
                self.metadata['File:FileSize'] = file_size
            except OSError:
                pass
            
            # File:FileModifyDate
            try:
                mtime = self.file_path.stat().st_mtime
                # Use localtime to get correct timezone (handles DST)
                import time
                local_time = time.localtime(mtime)
                # Format: "2025:11:25 13:53:38-05:00" (with timezone)
                # Get timezone offset (accounting for DST)
                if local_time.tm_isdst:
                    offset_seconds = -time.altzone
                else:
                    offset_seconds = -time.timezone
                offset_hours = offset_seconds // 3600
                offset_minutes = abs((offset_seconds % 3600) // 60)
                tz_str = f"{offset_hours:+03d}:{offset_minutes:02d}"
                dt_str = time.strftime(f'%Y:%m:%d %H:%M:%S{tz_str}', local_time)
                self.metadata['File:FileModifyDate'] = dt_str
            except OSError:
                pass
            
            # File:FileAccessDate
            try:
                atime = self.file_path.stat().st_atime
                import time
                local_time = time.localtime(atime)
                if local_time.tm_isdst:
                    offset_seconds = -time.altzone
                else:
                    offset_seconds = -time.timezone
                offset_hours = offset_seconds // 3600
                offset_minutes = abs((offset_seconds % 3600) // 60)
                tz_str = f"{offset_hours:+03d}:{offset_minutes:02d}"
                dt_str = time.strftime(f'%Y:%m:%d %H:%M:%S{tz_str}', local_time)
                self.metadata['File:FileAccessDate'] = dt_str
            except OSError:
                pass
            
            # File:FileInodeChangeDate
            try:
                ctime = self.file_path.stat().st_ctime
                import time
                local_time = time.localtime(ctime)
                if local_time.tm_isdst:
                    offset_seconds = -time.altzone
                else:
                    offset_seconds = -time.timezone
                offset_hours = offset_seconds // 3600
                offset_minutes = abs((offset_seconds % 3600) // 60)
                tz_str = f"{offset_hours:+03d}:{offset_minutes:02d}"
                dt_str = time.strftime(f'%Y:%m:%d %H:%M:%S{tz_str}', local_time)
                self.metadata['File:FileInodeChangeDate'] = dt_str
            except OSError:
                pass
            
            # File:FilePermissions
            try:
                file_stat = self.file_path.stat()
                # Use stat.filemode to get string representation like standard format
                perms = stat.filemode(file_stat.st_mode)
                self.metadata['File:FilePermissions'] = perms
            except OSError:
                pass
            
            # File:FileType (Standard format uses specific names)
            file_ext = self.file_path.suffix.lower()
            file_type_map = {
                '.jpg': 'JPEG', '.jpeg': 'JPEG', '.jph': 'JPEG', '.jfif': 'JPEG', '.jpe': 'JPEG',
                '.tif': 'TIFF', '.tiff': 'TIFF',
                '.png': 'PNG',
                '.gif': 'GIF',
                '.bmp': 'BMP',
                '.webp': 'WEBP',  # Standard format shows WEBP, not Matroska
                '.heic': 'HEIC', '.heif': 'HEIF',
                '.svg': 'SVG',
                '.psd': 'PSD',
                '.ico': 'ICO', '.cur': 'CUR',
                '.pcx': 'PCX',
                '.tga': 'TGA',
                '.dds': 'DDS',
                '.exr': 'EXR',
                '.hdr': 'HDR',
                '.pam': 'PAM', '.pbm': 'PBM', '.pgm': 'PGM', '.ppm': 'PPM', '.pnm': 'PNM',
                '.ras': 'RAS',
                '.sgi': 'SGI',
                '.wbmp': 'WBMP',
                '.xbm': 'XBM',
                '.xpm': 'XPM',
                '.pcd': 'PCD',
                '.picon': 'PICON',
                '.mng': 'MNG',
                '.xwd': 'XWD',
                '.sfw': 'SFW',
                '.pes': 'PES',
                '.pict': 'PICT',
                '.xcf': 'XCF',
                '.jp2': 'JP2',
                '.cube': 'CUBE',
                '.txt': 'TXT', '.log': 'TXT',
                '.json': 'JSON',
                '.xml': 'XML',
                '.pdf': 'PDF',
                '.dcm': 'DICOM', '.dicom': 'DICOM',  # DICOM medical imaging format
                '.mp4': 'MP4',
                '.mov': 'MOV',  # Standard format shows MOV, not QuickTime
                '.avi': 'AVI',
                '.mkv': 'MKV',  # Standard format shows MKV, not Matroska
                '.webm': 'WEBM',  # Standard format shows WEBM, not Matroska
                '.m4v': 'M4V',  # Standard format shows M4V, not MP4
                '.m4a': 'M4A',  # Standard format shows M4A, not MP4
                '.aac': 'M4A',  # Standard format shows M4A for .aac files
                '.3gp': '3GP',
                '.3g2': '3G2',
                '.mp3': 'MP3',
                '.wav': 'WAV',
                '.flac': 'FLAC',
                '.ogg': 'OGG',
                '.wma': 'WMA',  # Standard format shows WMA, not ASF
                '.opus': 'OPUS',  # Standard format shows OPUS, not OGG
            }
            # Add RAW formats (Standard format uses uppercase)
            # Note: CR3 and HIF are handled separately as they may use ISO BMFF container (like HEIC/AVIF)
            raw_formats = {'.cr2', '.nef', '.arw', '.dng', '.orf', '.raf', '.rw2', '.srw',
                          '.pef', '.x3f', '.crw', '.mrw', '.mdc', '.nrw', '.3fr', '.erf', '.mef', '.mos', '.gpr', '.kdc',
                          '.sr2', '.ari', '.bay', '.dcs', '.drf', '.eip', '.fff', '.iiq', '.rwl', '.raw'}
            if file_ext in raw_formats:
                self.metadata['File:FileType'] = file_ext[1:].upper()
            else:
                self.metadata['File:FileType'] = file_type_map.get(file_ext, 'Unknown')
            
            # File:FileTypeExtension (Standard format uses lowercase)
            # standard format maps .tiff to "tif" (not "tiff")
            # standard format maps .tga to "cur" when detected as CUR
            # standard format maps .aac to "m4a" (AAC files are typically in MP4 containers)
            # standard format maps .heif to "heic" when file uses HEIC format (major brand "heic")
            if file_ext:
                # Check if FileTypeExtension was already set by HEIC parser
                if 'File:FileTypeExtension' not in self.metadata:
                    ext_lower = file_ext[1:].lower()
                    # Map .tiff to "tif" to standard format
                    if ext_lower == 'tiff':
                        ext_lower = 'tif'
                    # Map .tga to "cur" to standard format (when detected as CUR)
                    elif ext_lower == 'tga' and self.metadata.get('File:FileType') == 'CUR':
                        ext_lower = 'cur'
                    # Map .aac to "m4a" if file uses QuickTime container (Standard format shows m4a for QuickTime AAC files)
                    elif ext_lower == 'aac':
                        # Check if file has QuickTime structure (ftyp atom)
                        try:
                            with open(str(self.file_path), 'rb') as f:
                                file_data = f.read(20)
                                if len(file_data) >= 12 and file_data[4:8] == b'ftyp':
                                    # Has QuickTime container, use m4a extension
                                    ext_lower = 'm4a'
                                # If not QuickTime container, keep as 'aac'
                        except Exception:
                            # Default to m4a for AAC files (most use QuickTime container)
                            ext_lower = 'm4a'
                    self.metadata['File:FileTypeExtension'] = ext_lower
            
            # File:MIMEType
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(self.file_path))
            
            # RAW format MIME types (standard format-specific mappings)
            raw_mime_map = {
                '.cr2': 'image/x-canon-cr2',
                '.crw': 'image/x-canon-crw',
                '.nef': 'image/x-nikon-nef',
                '.nrw': 'image/x-nikon-nrw',
                '.arw': 'image/x-sony-arw',
                '.raf': 'image/x-fujifilm-raf',
                '.orf': 'image/x-olympus-orf',
                '.rw2': 'image/x-panasonic-rw2',
                '.pef': 'image/x-pentax-pef',
                '.srw': 'image/x-samsung-srw',
                '.x3f': 'image/x-sigma-x3f',
                '.3fr': 'image/x-hasselblad-3fr',
                '.erf': 'image/x-epson-erf',
                '.mef': 'image/x-mamiya-mef',
                '.mos': 'image/x-raw',  # Leaf MOS format
                '.mrw': 'image/x-minolta-mrw',
                '.dng': 'image/x-adobe-dng',
            }
            
            # Override MIME type for specific cases to standard format
            if file_ext in raw_mime_map:
                mime_type = raw_mime_map[file_ext]
            elif file_ext in {'.dcm', '.dicom'}:
                mime_type = 'application/dicom'  # Standard format shows application/dicom for DICOM files
            elif file_ext == '.tga' and self.metadata.get('File:FileType') == 'CUR':
                mime_type = 'image/x-cursor'  # Standard format shows image/x-cursor for TGA files detected as CUR
            elif file_ext == '.flac':
                mime_type = 'audio/flac'  # Standard format shows audio/flac, not audio/x-flac
            elif file_ext == '.m4a':
                mime_type = 'audio/mp4'  # Standard format shows audio/mp4 for M4A files
            elif file_ext == '.aac':
                mime_type = 'audio/mp4'  # Standard format shows audio/mp4 for AAC files (not audio/mp4a-latm)
            elif file_ext == '.mkv':
                mime_type = 'video/x-matroska'  # Standard format shows video/x-matroska for MKV
            elif file_ext == '.webm':
                mime_type = 'video/webm'  # Standard format shows video/webm for WebM
            elif file_ext == '.avi':
                mime_type = 'video/x-msvideo'  # Standard format shows video/x-msvideo for AVI
            elif file_ext == '.mov':
                mime_type = 'video/quicktime'  # Standard format shows video/quicktime for MOV
            elif file_ext == '.m4v':
                mime_type = 'video/x-m4v'  # Standard format shows video/x-m4v for M4V
            elif file_ext in {'.3gp', '.3g2'}:
                mime_type = 'video/3gpp'  # Standard format shows video/3gpp for 3GP/3G2
            elif file_ext == '.mp3':
                mime_type = 'audio/mpeg'  # Standard format shows audio/mpeg for MP3
            elif file_ext == '.wav':
                mime_type = 'audio/x-wav'  # Standard format shows audio/x-wav for WAV
            elif file_ext == '.ogg':
                mime_type = 'audio/ogg'  # Standard format shows audio/ogg for OGG
            elif file_ext == '.wma':
                mime_type = 'audio/x-ms-wma'  # Standard format shows audio/x-ms-wma for WMA
            elif file_ext == '.opus':
                mime_type = 'audio/ogg'  # Standard format shows audio/ogg for Opus (in OGG container)
            elif file_ext == '.svg':
                mime_type = 'image/svg+xml'  # Standard format shows image/svg+xml for SVG
            elif file_ext == '.psd':
                mime_type = 'image/vnd.adobe.photoshop'  # Standard format shows image/vnd.adobe.photoshop for PSD
            elif file_ext == '.ico':
                mime_type = 'image/x-icon'  # Standard format shows image/x-icon for ICO
            elif file_ext == '.pcx':
                mime_type = 'image/x-pcx'  # Standard format shows image/x-pcx for PCX
            elif file_ext == '.pdf':
                mime_type = 'application/pdf'  # Standard format shows application/pdf for PDF
            elif file_ext == '.cube':
                mime_type = 'application/x-cube-lut'  # CUBE LUT files
            elif file_ext in {'.txt', '.log'}:
                mime_type = 'text/plain'  # Plain text files
            elif file_ext == '.json':
                mime_type = 'application/json'  # JSON files
            elif file_ext == '.xml':
                mime_type = 'application/xml'  # XML files
            elif file_ext in {'.heic', '.heif', '.avif', '.jxl', '.cr3', '.hif'}:
                if file_ext == '.avif':
                    mime_type = 'image/avif'  # Standard format shows image/avif for AVIF
                elif file_ext == '.jxl':
                    mime_type = 'image/jxl'  # Standard format shows image/jxl for JXL
                elif file_ext == '.cr3':
                    mime_type = 'image/x-canon-cr3'  # Standard format shows image/x-canon-cr3 for CR3
                elif file_ext == '.hif':
                    mime_type = 'image/x-fujifilm-hif'  # Standard format shows image/x-fujifilm-hif for HIF
                else:
                    mime_type = 'image/heic'  # Standard format shows image/heic for HEIC/HEIF
            
            if mime_type:
                self.metadata['File:MIMEType'] = mime_type
            else:
                # Fallback MIME types
                mime_map = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.jfif': 'image/jpeg', '.jpe': 'image/jpeg',
                    '.tif': 'image/tiff', '.tiff': 'image/tiff',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp',
                    '.tga': 'image/x-tga',
                    '.dds': 'image/vnd.ms-dds',
                    '.exr': 'image/x-exr',
                    '.hdr': 'image/vnd.radiance',
                    '.pam': 'image/x-portable-arbitrarymap',
                    '.pbm': 'image/x-portable-bitmap',
                    '.pgm': 'image/x-portable-graymap',
                    '.ppm': 'image/x-portable-pixmap',
                    '.pnm': 'image/x-portable-anymap',
                    '.ras': 'image/x-sun-raster',
                    '.sgi': 'image/x-sgi',
                    '.wbmp': 'image/vnd.wap.wbmp',
                    '.xbm': 'image/x-xbitmap',
                    '.xpm': 'image/x-xpixmap',
                    '.pcd': 'image/x-photo-cd',
                    '.picon': 'image/x-picon',
                    '.mng': 'video/x-mng',
                    '.xwd': 'image/x-xwindowdump',
                    '.sfw': 'image/x-sfw',
                    '.pes': 'application/x-pes',
                    '.pict': 'image/x-pict',
                    '.xcf': 'image/x-xcf',
                    '.jp2': 'image/jp2',
                    '.cur': 'image/x-cursor',
                    '.flac': 'audio/flac',
                    '.dcm': 'application/dicom', '.dicom': 'application/dicom',
                    '.m4a': 'audio/mp4',
                    '.aac': 'audio/mp4',
                    '.mkv': 'video/x-matroska', '.webm': 'video/webm',
                    '.avi': 'video/x-msvideo',
                    '.mov': 'video/quicktime',
                    '.m4v': 'video/x-m4v',
                    '.3gp': 'video/3gpp', '.3g2': 'video/3gpp',
                    '.mp3': 'audio/mpeg',
                    '.wav': 'audio/x-wav',
                    '.ogg': 'audio/ogg',
                    '.wma': 'audio/x-ms-wma',
                    '.opus': 'audio/ogg',
                    '.svg': 'image/svg+xml',
                    '.psd': 'image/vnd.adobe.photoshop',
                    '.ico': 'image/x-icon',
                    '.pcx': 'image/x-pcx',
                    '.pdf': 'application/pdf',
                    '.heic': 'image/heic', '.heif': 'image/heic',
                }
                # Merge RAW format mappings into fallback map
                mime_map.update(raw_mime_map)
                self.metadata['File:MIMEType'] = mime_map.get(file_ext, 'application/octet-stream')
            
            # File:ImageWidth and File:ImageHeight (parse from file headers if not in EXIF)
            file_ext = self.file_path.suffix.lower()
            if file_ext in ('.jpg', '.jpeg', '.jfif', '.jpe'):
                # For JPEG files, prioritize EXIF dimensions over SOF dimensions
                # Standard format uses ExifImageWidth/ExifImageHeight for File:ImageWidth/ImageHeight
                # These are aliases for PixelXDimension (0xa002) and PixelYDimension (0xa003) in EXIF SubIFD
                exif_width = (self.metadata.get('EXIF:ExifImageWidth') or 
                             self.metadata.get('EXIF:PixelXDimension') or 
                             self.metadata.get('EXIF:ImageWidth'))
                exif_height = (self.metadata.get('EXIF:ExifImageHeight') or 
                              self.metadata.get('EXIF:PixelYDimension') or 
                              self.metadata.get('EXIF:ImageHeight') or 
                              self.metadata.get('EXIF:ImageLength'))
                
                if exif_width and exif_height:
                    # Use EXIF dimensions (standard format behavior)
                    # Handle tuple/list values
                    if isinstance(exif_width, (list, tuple)) and len(exif_width) > 0:
                        exif_width = exif_width[0]
                    if isinstance(exif_height, (list, tuple)) and len(exif_height) > 0:
                        exif_height = exif_height[0]
                    self.metadata['File:ImageWidth'] = int(exif_width)
                    self.metadata['File:ImageHeight'] = int(exif_height)
                else:
                    # Fallback to parsing from JPEG SOF segment
                    width, height = self._parse_jpeg_dimensions()
                    if width and height:
                        self.metadata['File:ImageWidth'] = width
                        self.metadata['File:ImageHeight'] = height
            elif file_ext == '.png':
                # Parse from PNG header
                try:
                    with open(str(self.file_path), 'rb') as f:
                        file_data = f.read(24)
                    if file_data[:8] == b'\x89PNG\r\n\x1a\n' and len(file_data) >= 24:
                        width = struct.unpack('>I', file_data[16:20])[0]
                        height = struct.unpack('>I', file_data[20:24])[0]
                        self.metadata['File:ImageWidth'] = width
                        self.metadata['File:ImageHeight'] = height
                except Exception:
                    pass
            elif file_ext == '.gif':
                # Parse from GIF header
                try:
                    with open(str(self.file_path), 'rb') as f:
                        file_data = f.read(10)
                    if (file_data[:6] == b'GIF87a' or file_data[:6] == b'GIF89a') and len(file_data) >= 10:
                        width = struct.unpack('<H', file_data[6:8])[0]
                        height = struct.unpack('<H', file_data[8:10])[0]
                        self.metadata['File:ImageWidth'] = width
                        self.metadata['File:ImageHeight'] = height
                except Exception:
                    pass
            elif file_ext == '.bmp':
                # Parse from BMP header
                try:
                    with open(str(self.file_path), 'rb') as f:
                        file_data = f.read(26)
                    if file_data[:2] == b'BM' and len(file_data) >= 26:
                        width = abs(struct.unpack('<i', file_data[18:22])[0])
                        height = abs(struct.unpack('<i', file_data[22:26])[0])
                        self.metadata['File:ImageWidth'] = width
                        self.metadata['File:ImageHeight'] = height
                except Exception:
                    pass
        except Exception:
            pass  # File tags are optional
    
    def _detect_sidecar_files(self) -> Dict[str, Path]:
        """
        Detect sidecar files for the current file.
        
        Checks for common sidecar file naming conventions:
        - filename.xmp (same name, .xmp extension)
        - filename.ext.xmp (original extension preserved)
        - filename.exif (EXIF sidecar files)
        - filename.iptc (IPTC sidecar files)
        
        Returns:
            Dictionary mapping sidecar type to Path if found
        """
        sidecar_files = {}
        file_dir = self.file_path.parent
        file_stem = self.file_path.stem
        file_ext = self.file_path.suffix.lower()
        
        # Check for XMP sidecar files
        # Convention 1: filename.xmp (same name, .xmp extension)
        xmp_sidecar1 = file_dir / f"{file_stem}.xmp"
        if xmp_sidecar1.exists() and xmp_sidecar1.is_file():
            sidecar_files['xmp'] = xmp_sidecar1
        
        # Convention 2: filename.ext.xmp (original extension preserved)
        if file_ext:
            xmp_sidecar2 = file_dir / f"{file_stem}{file_ext}.xmp"
            if xmp_sidecar2.exists() and xmp_sidecar2.is_file():
                # Prefer convention 2 if both exist (more specific)
                sidecar_files['xmp'] = xmp_sidecar2
        
        # Check for EXIF sidecar files
        # Convention: filename.exif or filename.ext.exif
        exif_sidecar1 = file_dir / f"{file_stem}.exif"
        if exif_sidecar1.exists() and exif_sidecar1.is_file():
            sidecar_files['exif'] = exif_sidecar1
        
        if file_ext:
            exif_sidecar2 = file_dir / f"{file_stem}{file_ext}.exif"
            if exif_sidecar2.exists() and exif_sidecar2.is_file():
                sidecar_files['exif'] = exif_sidecar2
        
        # Check for IPTC sidecar files
        # Convention: filename.iptc or filename.ext.iptc
        iptc_sidecar1 = file_dir / f"{file_stem}.iptc"
        if iptc_sidecar1.exists() and iptc_sidecar1.is_file():
            sidecar_files['iptc'] = iptc_sidecar1
        
        if file_ext:
            iptc_sidecar2 = file_dir / f"{file_stem}{file_ext}.iptc"
            if iptc_sidecar2.exists() and iptc_sidecar2.is_file():
                sidecar_files['iptc'] = iptc_sidecar2
        
        return sidecar_files
    
    def _load_sidecar_metadata(self, sidecar_files: Dict[str, Path]) -> Dict[str, Any]:
        """
        Load metadata from sidecar files.
        
        Args:
            sidecar_files: Dictionary mapping sidecar type to Path
            
        Returns:
            Dictionary of sidecar metadata
        """
        sidecar_metadata = {}
        
        # Load XMP sidecar metadata
        if 'xmp' in sidecar_files:
            try:
                xmp_sidecar_path = sidecar_files['xmp']
                xmp_parser = XMPParser(file_path=str(xmp_sidecar_path))
                xmp_data = xmp_parser.read(scan_entire_file=True)
                if xmp_data:
                    # Mark metadata as coming from sidecar
                    for key in list(xmp_data.keys()):
                        # Add sidecar indicator to tag names
                        sidecar_key = f"Sidecar:{key}" if not key.startswith("Sidecar:") else key
                        sidecar_metadata[sidecar_key] = xmp_data[key]
                    # Add sidecar file info
                    sidecar_metadata['Sidecar:XMP:SidecarFile'] = str(xmp_sidecar_path)
                    sidecar_metadata['Sidecar:XMP:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar loading - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
        
        # Load EXIF sidecar metadata
        if 'exif' in sidecar_files:
            try:
                exif_sidecar_path = sidecar_files['exif']
                # EXIF sidecar files are typically TIFF files containing EXIF data
                exif_parser = ExifParser(file_path=str(exif_sidecar_path))
                exif_data = exif_parser.read()
                if exif_data:
                    # Mark metadata as coming from sidecar
                    for key in list(exif_data.keys()):
                        # Add sidecar indicator to tag names
                        sidecar_key = f"Sidecar:{key}" if not key.startswith("Sidecar:") else key
                        sidecar_metadata[sidecar_key] = exif_data[key]
                    # Add sidecar file info
                    sidecar_metadata['Sidecar:EXIF:SidecarFile'] = str(exif_sidecar_path)
                    sidecar_metadata['Sidecar:EXIF:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar loading - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
        
        # Load IPTC sidecar metadata
        if 'iptc' in sidecar_files:
            try:
                iptc_sidecar_path = sidecar_files['iptc']
                # IPTC sidecar files are typically binary IPTC data files
                # Read file and parse as IPTC
                with open(iptc_sidecar_path, 'rb') as f:
                    iptc_data = f.read()
                
                # Try to parse IPTC data
                iptc_parser = IPTCParser(file_data=iptc_data)
                iptc_metadata = iptc_parser.read()
                if iptc_metadata:
                    # Mark metadata as coming from sidecar
                    for key in list(iptc_metadata.keys()):
                        # Add sidecar indicator to tag names
                        sidecar_key = f"Sidecar:{key}" if not key.startswith("Sidecar:") else key
                        sidecar_metadata[sidecar_key] = iptc_metadata[key]
                    # Add sidecar file info
                    sidecar_metadata['Sidecar:IPTC:SidecarFile'] = str(iptc_sidecar_path)
                    sidecar_metadata['Sidecar:IPTC:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar loading - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
        
        return sidecar_metadata
    
    def _clear_parser_cache(self) -> None:
        """
        Clear cached file data from parsers to reduce memory usage.
        
        This method clears file_data from parser instances after metadata
        has been extracted. This is safe because metadata is already stored
        in self.metadata and doesn't depend on the cached file data.
        """
        # Clear file_data from EXIF parser if it exists
        if self._exif_parser and hasattr(self._exif_parser, 'file_data'):
            self._exif_parser.file_data = None
        
        # Clear file_data from IPTC parser if it exists
        if self._iptc_parser and hasattr(self._iptc_parser, 'file_data'):
            self._iptc_parser.file_data = None
        
        # Clear file_data from XMP parser if it exists
        if self._xmp_parser and hasattr(self._xmp_parser, 'file_data'):
            self._xmp_parser.file_data = None
        
        # Clear cached file data if it exists
        if hasattr(self, '_cached_file_data'):
            self._cached_file_data = None
    
    def _load_metadata(self) -> None:
        """Load all metadata from the file."""
        try:
            # Add File tags first
            self._add_file_tags()
            
            file_ext = self.file_path.suffix.lower()
            
            # Detect and load sidecar files (before loading main file metadata)
            # Sidecar metadata will supplement main file metadata
            sidecar_files = self._detect_sidecar_files()
            if sidecar_files:
                sidecar_metadata = self._load_sidecar_metadata(sidecar_files)
                if sidecar_metadata:
                    # Merge sidecar metadata (sidecar metadata supplements main metadata)
                    # Main file metadata takes precedence, but sidecar fills gaps
                    for key, value in sidecar_metadata.items():
                        # Only add sidecar metadata if main file doesn't have it
                        if key not in self.metadata:
                            self.metadata[key] = value
                        # Always add sidecar-specific tags
                        if key.startswith('Sidecar:'):
                            self.metadata[key] = value
            
            # Check if it's a video format
            video_formats = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.m4a', '.aac', '.3gp', '.3g2'}
            if file_ext in video_formats:
                # Use video parser for video files
                try:
                    video_parser = VideoParser(file_path=str(self.file_path))
                    video_data = video_parser.parse()
                    self.metadata.update(video_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse video metadata from {self.file_path}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # Video files handled separately for now
            
            # Check if it's an XMP sidecar file
            if file_ext == '.xmp':
                try:
                    # XMP sidecar files are standalone XML files containing XMP packets
                    # Use XMPParser to parse the sidecar file
                    xmp_parser = XMPParser(file_path=str(self.file_path))
                    xmp_data = xmp_parser.read(scan_entire_file=True)
                    if xmp_data:
                        # Add file type tags for XMP sidecar
                        self.metadata['File:FileType'] = 'XMP'
                        self.metadata['File:FileTypeExtension'] = 'xmp'
                        self.metadata['File:MIMEType'] = 'application/rdf+xml'
                        self.metadata['XMP:SidecarFile'] = True
                        # Merge XMP metadata
                        self.metadata.update(xmp_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XMP sidecar metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XMP sidecar files handled separately
            
            # Check if it's an EXIF sidecar file
            if file_ext == '.exif':
                try:
                    # EXIF sidecar files are standalone TIFF files containing EXIF metadata
                    # Use ExifParser to parse the sidecar file
                    exif_parser = ExifParser(file_path=str(self.file_path))
                    exif_data = exif_parser.read()
                    if exif_data:
                        # Add file type tags for EXIF sidecar
                        self.metadata['File:FileType'] = 'EXIF'
                        self.metadata['File:FileTypeExtension'] = 'exif'
                        self.metadata['File:MIMEType'] = 'image/tiff'
                        self.metadata['EXIF:SidecarFile'] = True
                        # Merge EXIF metadata
                        self.metadata.update(exif_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse EXIF sidecar metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # EXIF sidecar files handled separately
            
            # Check if it's an IPTC sidecar file
            if file_ext == '.iptc':
                try:
                    # IPTC sidecar files are standalone binary files containing IPTC metadata
                    # Use IPTCParser to parse the sidecar file
                    iptc_parser = IPTCParser(file_path=str(self.file_path))
                    iptc_data = iptc_parser.read()
                    if iptc_data:
                        # Add file type tags for IPTC sidecar
                        self.metadata['File:FileType'] = 'IPTC'
                        self.metadata['File:FileTypeExtension'] = 'iptc'
                        self.metadata['File:MIMEType'] = 'application/octet-stream'
                        self.metadata['IPTC:SidecarFile'] = True
                        # Merge IPTC metadata
                        self.metadata.update(iptc_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse IPTC sidecar metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # IPTC sidecar files handled separately
            
            # Read file data for signature checks
            try:
                with open(str(self.file_path), 'rb') as f:
                    file_data = f.read(1024)  # Read first 1KB for signature checks
            except Exception:
                file_data = b''
            
            # Check if it's a RAR archive file
            if file_ext == '.rar' or (len(file_data) >= 8 and (
                file_data.startswith(b'Rar!\x1A\x07\x01\x00') or  # RAR v5.0
                file_data.startswith(b'Rar!\x1A\x07\x00')  # RAR v4.x
            )):
                try:
                    from dnexif.rar_parser import RARParser
                    rar_parser = RARParser(file_path=str(self.file_path))
                    rar_data = rar_parser.parse()
                    if rar_data:
                        self.metadata.update(rar_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse RAR metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # RAR files handled separately
            
            # Check if it's a 7z archive file
            if file_ext == '.7z' or (len(file_data) >= 6 and file_data.startswith(b'7z\xBC\xAF\x27\x1C')):
                try:
                    from dnexif.sevenz_parser import SevenZParser
                    sevenz_parser = SevenZParser(file_path=str(self.file_path))
                    sevenz_data = sevenz_parser.parse()
                    if sevenz_data:
                        self.metadata.update(sevenz_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse 7z metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # 7z files handled separately
            
            # Check if it's a ZIP file
            if file_ext == '.zip' or (len(file_data) >= 2 and file_data.startswith(b'PK')):
                try:
                    from dnexif.zip_parser import ZIPParser
                    zip_parser = ZIPParser(file_path=str(self.file_path), file_data=self.file_data)
                    zip_data = zip_parser.parse()
                    if zip_data:
                        self.metadata.update(zip_data)
                except Exception as zip_e:
                    # ZIP parsing is optional
                    pass
            
            # Check if it's an AAE file (Apple Adjustments)
            if file_ext == '.aae':
                try:
                    from dnexif.aae_parser import AAParser
                    aae_parser = AAParser(file_path=str(self.file_path))
                    aae_data = aae_parser.parse()
                    self.metadata.update(aae_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse AAE metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # AAE files handled separately
            
            # Check if it's a Nikon adjustment file
            if file_ext in ('.nka', '.nxd'):
                try:
                    from dnexif.nikon_adjustment_parser import NikonAdjustmentParser
                    nikon_parser = NikonAdjustmentParser(file_path=str(self.file_path))
                    nikon_data = nikon_parser.parse()
                    self.metadata.update(nikon_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse Nikon adjustment metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # Nikon adjustment files handled separately
            
            # Check if it's an XISF file
            if file_ext == '.xisf':
                try:
                    from dnexif.xisf_parser import XISFParser
                    xisf_parser = XISFParser(file_path=str(self.file_path))
                    xisf_data = xisf_parser.parse()
                    self.metadata.update(xisf_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XISF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XISF files handled separately
            
            # Check if it's a GPX file
            if file_ext == '.gpx':
                try:
                    from dnexif.gpx_parser import GPXParser
                    gpx_parser = GPXParser(file_path=str(self.file_path))
                    gpx_data = gpx_parser.parse()
                    self.metadata.update(gpx_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse GPX metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # GPX files handled separately
            
            # Check if it's a KML file
            if file_ext == '.kml':
                try:
                    from dnexif.kml_parser import KMLParser
                    kml_parser = KMLParser(file_path=str(self.file_path))
                    kml_data = kml_parser.parse()
                    self.metadata.update(kml_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse KML metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # KML files handled separately
            
            # Check if it's a CSV file
            if file_ext == '.csv':
                try:
                    from dnexif.csv_parser import CSVParser
                    csv_parser = CSVParser(file_path=str(self.file_path))
                    csv_data = csv_parser.parse()
                    self.metadata.update(csv_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse CSV metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # CSV files handled separately
            
            # Check if it's a PFM file
            if file_ext == '.pfm':
                try:
                    from dnexif.pfm_parser import PFMParser
                    pfm_parser = PFMParser(file_path=str(self.file_path))
                    pfm_data = pfm_parser.parse()
                    self.metadata.update(pfm_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PFM metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PFM files handled separately
            
            # Check if it's a CUBE file
            if file_ext == '.cube':
                try:
                    from dnexif.cube_parser import CUBEParser
                    cube_parser = CUBEParser(file_path=str(self.file_path))
                    cube_data = cube_parser.parse()
                    self.metadata.update(cube_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse CUBE metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # CUBE files handled separately
            
            # Check if it's a text file
            if file_ext in {'.txt', '.log'}:
                try:
                    from dnexif.text_parser import TextParser
                    text_parser = TextParser(file_path=str(self.file_path))
                    text_data = text_parser.parse()
                    self.metadata.update(text_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse text file metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # Text files handled separately
            
            # Check if it's a JSON file
            if file_ext == '.json':
                try:
                    from dnexif.json_parser import JSONParser
                    json_parser = JSONParser(file_path=str(self.file_path))
                    json_data = json_parser.parse()
                    self.metadata.update(json_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse JSON file metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # JSON files handled separately
            
            # Check if it's an XML file
            if file_ext == '.xml':
                try:
                    from dnexif.xml_parser import XMLParser
                    xml_parser = XMLParser(file_path=str(self.file_path))
                    xml_data = xml_parser.parse()
                    self.metadata.update(xml_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XML file metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XML files handled separately
            
            # Check if it's an InfiRay IJPEG file
            if file_ext == '.ijpeg':
                try:
                    from dnexif.infiray_parser import InfiRayParser
                    infiray_parser = InfiRayParser(file_path=str(self.file_path))
                    infiray_data = infiray_parser.parse()
                    self.metadata.update(infiray_data)
                    # Also parse as JPEG to get full JPEG metadata
                    # The JPEG parser will be called later in the flow
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse InfiRay IJPEG metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # InfiRay IJPEG files handled separately
            
            # Check if it's a Parrot Bebop-Pro Thermal image (JPEG with Parrot thermal data)
            if file_ext in ('.jpg', '.jpeg', '.jpe', '.jfif'):
                try:
                    # Try to detect Parrot thermal images by checking file data
                    file_data_preview = self._read_file_data(max_length=50000)  # Read first 50KB
                    if file_data_preview:
                        # Check for Parrot patterns
                        parrot_patterns = [b'Parrot', b'PARROT', b'Bebop', b'BEBOP', b'Bebop-Pro']
                        is_parrot = any(pattern in file_data_preview for pattern in parrot_patterns)
                        
                        if is_parrot:
                            from dnexif.parrot_parser import ParrotParser
                            parrot_parser = ParrotParser(file_path=str(self.file_path))
                            parrot_data = parrot_parser.parse()
                            if parrot_data and parrot_data.get('Parrot:HasParrotMetadata'):
                                self.metadata.update(parrot_data)
                except Exception as e:
                    # Parrot parsing is optional - don't raise error if not Parrot image
                    if not self.ignore_minor_errors and 'Parrot' in str(e):
                        pass  # Silently ignore if not a Parrot image
                    pass
            
            # Check if it's a DJI RJPEG thermal image (JPEG with DJI thermal data)
            if file_ext in ('.jpg', '.jpeg', '.jpe', '.jfif', '.rjpeg'):
                try:
                    # Try to detect DJI RJPEG images by checking file data
                    # Read first 50KB for pattern detection
                    try:
                        with open(self.file_path, 'rb') as f:
                            file_data_preview = f.read(50000)
                    except Exception:
                        file_data_preview = None
                    if file_data_preview:
                        # Check for DJI RJPEG patterns
                        dji_patterns = [b'DJI', b'dji', b'DJI_', b'DJI-', b'DJI ', b'RJPEG', b'rjpeg', b'R-JPEG']
                        is_dji_rjpeg = any(pattern in file_data_preview for pattern in dji_patterns)
                        
                        if is_dji_rjpeg:
                            from dnexif.dji_rjpeg_parser import DJIRJPEGParser
                            dji_rjpeg_parser = DJIRJPEGParser(file_path=str(self.file_path))
                            dji_rjpeg_data = dji_rjpeg_parser.parse()
                            if dji_rjpeg_data and dji_rjpeg_data.get('DJI:HasDJIMetadata'):
                                self.metadata.update(dji_rjpeg_data)
                        
                        # Check for Vivo phone JPEG images (proprietary metadata)
                        vivo_patterns = [
                            b'Vivo',
                            b'VIVO',
                            b'vivo',
                            b'VIVO ',
                            b'vivo ',
                            b'VivoPhone',
                            b'VIVOPHONE',
                            b'vivophone',
                            b'BBK',
                            b'bbk',
                            b'BBK ',
                            b'X Series',
                            b'X series',
                            b'X SERIES',
                            b'Y Series',
                            b'Y series',
                            b'Y SERIES',
                            b'S Series',
                            b'S series',
                            b'S SERIES',
                        ]
                        is_vivo_jpeg = any(pattern in file_data_preview for pattern in vivo_patterns)
                        
                        if is_vivo_jpeg:
                            vivo_metadata = self._extract_vivo_jpeg_metadata(file_data_preview)
                            if vivo_metadata:
                                self.metadata.update(vivo_metadata)
                except Exception as e:
                    # DJI RJPEG parsing is optional - don't raise error if not DJI RJPEG image
                    if not self.ignore_minor_errors and 'DJI' in str(e):
                        pass  # Silently ignore if not a DJI RJPEG image
                    pass
            
            # Check if it's a FLIR SEQ file (thermal sequence)
            if file_ext == '.seq':
                try:
                    from dnexif.flir_seq_parser import FLIRSeqParser
                    # Use enhanced extraction mode (equivalent to -ee2 flag) to extract raw thermal data from all frames
                    flir_seq_parser = FLIRSeqParser(file_path=str(self.file_path), enhanced_extraction=True)
                    flir_seq_data = flir_seq_parser.parse()
                    if flir_seq_data and flir_seq_data.get('FLIR:HasFLIRMetadata'):
                        self.metadata.update(flir_seq_data)
                except Exception as e:
                    # FLIR SEQ parsing is optional - don't raise error if not FLIR SEQ file
                    if not self.ignore_minor_errors and 'FLIR' in str(e):
                        pass  # Silently ignore if not a FLIR SEQ file
                    pass
            
            # Check if it's a JPS file
            if file_ext == '.jps':
                try:
                    from dnexif.jps_parser import JPSParser
                    jps_parser = JPSParser(file_path=str(self.file_path))
                    jps_data = jps_parser.parse()
                    self.metadata.update(jps_data)
                    # Also parse as JPEG to get full JPEG metadata
                    # The JPEG parser will be called later in the flow
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse JPS metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                # Don't return here - continue to JPEG parsing for full metadata
            
            # Check if it's an MRC file
            if file_ext == '.mrc':
                try:
                    from dnexif.mrc_parser import MRCParser
                    mrc_parser = MRCParser(file_path=str(self.file_path))
                    mrc_data = mrc_parser.parse()
                    self.metadata.update(mrc_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse MRC metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # MRC files handled separately
            
            # Check if it's a MacOS AppleDouble sidecar file (._filename)
            if self.file_path and self.file_path.name.startswith('._'):
                try:
                    from dnexif.appledouble_parser import AppleDoubleParser
                    appledouble_parser = AppleDoubleParser(file_path=str(self.file_path))
                    appledouble_data = appledouble_parser.parse()
                    self.metadata.update(appledouble_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse AppleDouble metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # AppleDouble files handled separately
            
            # Check if it's an ON1 preset file
            if file_ext == '.onp':
                try:
                    from dnexif.on1_parser import ON1Parser
                    on1_parser = ON1Parser(file_path=str(self.file_path))
                    on1_data = on1_parser.parse()
                    self.metadata.update(on1_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse ON1 preset metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # ON1 preset files handled separately
            
            # Check if it's a document format
            document_formats = {'.pdf'}
            if file_ext in document_formats:
                # Use document parser for document files
                try:
                    document_parser = DocumentParser(file_path=str(self.file_path))
                    document_data = document_parser.parse()
                    self.metadata.update(document_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse document metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # Document files handled separately for now
            
            # Check if it's a TNEF file
            if file_ext in ('.tnef', '.dat'):
                # Check if it's a TNEF file (winmail.dat)
                try:
                    # Read first 4 bytes to check signature
                    with open(self.file_path, 'rb') as f:
                        signature_bytes = f.read(4)
                    if len(signature_bytes) == 4:
                        signature = struct.unpack('<I', signature_bytes)[0]
                        if signature == 0x223E9F78:  # TNEF signature
                            from dnexif.tnef_parser import TNEFParser
                            tnef_parser = TNEFParser(file_path=str(self.file_path))
                            tnef_data = tnef_parser.parse()
                            self.metadata.update(tnef_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse TNEF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # TNEF files handled separately
            
            # Check if it's a PCAP or CAP packet capture file
            if file_ext in ('.pcap', '.cap'):
                try:
                    from dnexif.pcap_parser import PCAPParser
                    pcap_parser = PCAPParser(file_path=str(self.file_path))
                    pcap_data = pcap_parser.parse()
                    # Adjust file type for CAP files
                    if file_ext == '.cap':
                        # Override file type metadata for CAP files
                        pcap_data['File:FileType'] = 'CAP'
                        pcap_data['File:FileTypeExtension'] = 'cap'
                        # Keep PCAP tags but also add CAP-specific tags
                        pcap_data['CAP:ByteOrder'] = pcap_data.get('PCAP:ByteOrder', '')
                        pcap_data['CAP:Version'] = pcap_data.get('PCAP:Version', '')
                        pcap_data['CAP:NetworkType'] = pcap_data.get('PCAP:NetworkType', '')
                        pcap_data['CAP:PacketCount'] = pcap_data.get('PCAP:PacketCount', 0)
                    self.metadata.update(pcap_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PCAP/CAP metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PCAP/CAP files handled separately
            
            # Check if it's a WOFF or WOFF2 font file
            if file_ext == '.woff':
                try:
                    from dnexif.woff_parser import WOFFParser
                    woff_parser = WOFFParser(file_path=str(self.file_path))
                    woff_data = woff_parser.parse()
                    self.metadata.update(woff_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WOFF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # WOFF files handled separately
            
            if file_ext == '.woff2':
                try:
                    from dnexif.woff2_parser import WOFF2Parser
                    woff2_parser = WOFF2Parser(file_path=str(self.file_path))
                    woff2_data = woff2_parser.parse()
                    self.metadata.update(woff2_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WOFF2 metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # WOFF2 files handled separately
            
            # Legacy WOFF check (kept for backward compatibility)
            if file_ext == '.woff':
                try:
                    from dnexif.woff_parser import WOFFParser
                    woff_parser = WOFFParser(file_path=str(self.file_path))
                    woff_data = woff_parser.parse()
                    self.metadata.update(woff_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WOFF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # WOFF files handled separately
            
            # Check if it's a Windows .URL file
            if file_ext == '.url':
                try:
                    from dnexif.url_parser import URLParser
                    url_parser = URLParser(file_path=str(self.file_path))
                    url_data = url_parser.parse()
                    self.metadata.update(url_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse .URL metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # .URL files handled separately
            
            # Check if it's a Windows .LNK file
            if file_ext == '.lnk':
                try:
                    from dnexif.lnk_parser import LNKParser
                    lnk_parser = LNKParser(file_path=str(self.file_path))
                    lnk_data = lnk_parser.parse()
                    self.metadata.update(lnk_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse .LNK metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # .LNK files handled separately
            
            # Check if it's a Win32 PE format file (EXE, DLL, SYS, OCX, DRV, SCR, CPL)
            if file_ext in ('.exe', '.dll', '.sys', '.ocx', '.drv', '.scr', '.cpl'):
                try:
                    from dnexif.exe_parser import EXEParser
                    exe_parser = EXEParser(file_path=str(self.file_path))
                    exe_data = exe_parser.parse()
                    self.metadata.update(exe_data)
                    # Set file type based on extension
                    file_type_map = {
                        '.dll': ('DLL', 'dll', 'application/x-msdownload'),
                        '.sys': ('SYS', 'sys', 'application/x-msdownload'),
                        '.ocx': ('OCX', 'ocx', 'application/x-msdownload'),
                        '.drv': ('DRV', 'drv', 'application/x-msdownload'),
                        '.scr': ('SCR', 'scr', 'application/x-msdownload'),
                        '.cpl': ('CPL', 'cpl', 'application/x-msdownload'),
                    }
                    if file_ext in file_type_map:
                        file_type, ext, mime = file_type_map[file_ext]
                        self.metadata['File:FileType'] = file_type
                        self.metadata['File:FileTypeExtension'] = ext
                        self.metadata['File:MIMEType'] = mime
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse .{file_ext.upper()} metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PE format files handled separately
            
            # Check if it's an iWork file
            if file_ext in ('.pages', '.numbers', '.key'):
                try:
                    from dnexif.iwork_parser import IWorkParser
                    iwork_parser = IWorkParser(file_path=str(self.file_path))
                    iwork_data = iwork_parser.parse()
                    self.metadata.update(iwork_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse iWork metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # iWork files handled separately
            
            # Check if it's a FITS file
            if file_ext in ('.fits', '.fit', '.fts'):
                try:
                    from dnexif.fits_parser import FITSParser
                    fits_parser = FITSParser(file_path=str(self.file_path))
                    fits_data = fits_parser.parse()
                    self.metadata.update(fits_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse FITS metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # FITS files handled separately
            
            # Check if it's a Netpbm file (PAM, PBM, PGM, PPM, PNM)
            if file_ext in ('.pam', '.pbm', '.pgm', '.ppm', '.pnm'):
                try:
                    from dnexif.netpbm_parser import NetPBMParser
                    netpbm_parser = NetPBMParser(file_path=str(self.file_path))
                    netpbm_data = netpbm_parser.parse()
                    self.metadata.update(netpbm_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse Netpbm metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # Netpbm files handled separately
            
            # Check if it's an HDR file
            if file_ext == '.hdr':
                try:
                    from dnexif.hdr_parser import HDRParser
                    hdr_parser = HDRParser(file_path=str(self.file_path))
                    hdr_data = hdr_parser.parse()
                    self.metadata.update(hdr_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse HDR metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # HDR files handled separately
            
            # Check if it's a DDS file
            if file_ext == '.dds':
                try:
                    from dnexif.dds_parser import DDSParser
                    dds_parser = DDSParser(file_path=str(self.file_path))
                    dds_data = dds_parser.parse()
                    self.metadata.update(dds_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse DDS metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # DDS files handled separately
            
            # Check if it's an EXR file
            if file_ext == '.exr':
                try:
                    from dnexif.exr_parser import EXRParser
                    exr_parser = EXRParser(file_path=str(self.file_path))
                    exr_data = exr_parser.parse()
                    self.metadata.update(exr_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse EXR metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # EXR files handled separately
            
            # Check if it's a WBMP file
            if file_ext == '.wbmp':
                try:
                    from dnexif.wbmp_parser import WBMPParser
                    wbmp_parser = WBMPParser(file_path=str(self.file_path))
                    wbmp_data = wbmp_parser.parse()
                    self.metadata.update(wbmp_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WBMP metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # WBMP files handled separately
            
            # Check if it's an XBM file
            if file_ext == '.xbm':
                try:
                    from dnexif.xbm_parser import XBMParser
                    xbm_parser = XBMParser(file_path=str(self.file_path))
                    xbm_data = xbm_parser.parse()
                    self.metadata.update(xbm_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XBM metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XBM files handled separately
            
            # Check if it's an XPM file
            if file_ext == '.xpm':
                try:
                    from dnexif.xpm_parser import XPMParser
                    xpm_parser = XPMParser(file_path=str(self.file_path))
                    xpm_data = xpm_parser.parse()
                    self.metadata.update(xpm_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XPM metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XPM files handled separately
            
            # Check if it's a RAS file
            if file_ext == '.ras':
                try:
                    from dnexif.ras_parser import RASParser
                    ras_parser = RASParser(file_path=str(self.file_path))
                    ras_data = ras_parser.parse()
                    self.metadata.update(ras_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse RAS metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # RAS files handled separately
            
            # Check if it's an SGI file
            if file_ext == '.sgi':
                try:
                    from dnexif.sgi_parser import SGIParser
                    sgi_parser = SGIParser(file_path=str(self.file_path))
                    sgi_data = sgi_parser.parse()
                    self.metadata.update(sgi_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse SGI metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # SGI files handled separately
            
            # Check if it's a PCD file
            if file_ext == '.pcd':
                try:
                    from dnexif.pcd_parser import PCDParser
                    pcd_parser = PCDParser(file_path=str(self.file_path))
                    pcd_data = pcd_parser.parse()
                    self.metadata.update(pcd_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PCD metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PCD files handled separately
            
            # Check if it's a PICON file
            if file_ext == '.picon':
                try:
                    from dnexif.picon_parser import PICONParser
                    picon_parser = PICONParser(file_path=str(self.file_path))
                    picon_data = picon_parser.parse()
                    self.metadata.update(picon_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PICON metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PICON files handled separately
            
            # Check if it's an MNG file
            if file_ext == '.mng':
                try:
                    from dnexif.mng_parser import MNGParser
                    mng_parser = MNGParser(file_path=str(self.file_path))
                    mng_data = mng_parser.parse()
                    self.metadata.update(mng_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse MNG metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # MNG files handled separately
            
            # Check if it's an XWD file
            if file_ext == '.xwd':
                try:
                    from dnexif.xwd_parser import XWDParser
                    xwd_parser = XWDParser(file_path=str(self.file_path))
                    xwd_data = xwd_parser.parse()
                    self.metadata.update(xwd_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XWD metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XWD files handled separately
            
            # Check if it's an SFW file
            if file_ext == '.sfw':
                try:
                    from dnexif.sfw_parser import SFWParser
                    sfw_parser = SFWParser(file_path=str(self.file_path))
                    sfw_data = sfw_parser.parse()
                    self.metadata.update(sfw_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse SFW metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # SFW files handled separately
            
            # Check if it's a PES file
            if file_ext == '.pes':
                try:
                    from dnexif.pes_parser import PESParser
                    pes_parser = PESParser(file_path=str(self.file_path))
                    pes_data = pes_parser.parse()
                    self.metadata.update(pes_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PES metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PES files handled separately
            
            # Check if it's a PICT file
            if file_ext == '.pict':
                try:
                    from dnexif.pict_parser import PICTParser
                    pict_parser = PICTParser(file_path=str(self.file_path))
                    pict_data = pict_parser.parse()
                    self.metadata.update(pict_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PICT metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PICT files handled separately
            
            # Check if it's an XCF file
            if file_ext == '.xcf':
                try:
                    from dnexif.xcf_parser import XCFParser
                    xcf_parser = XCFParser(file_path=str(self.file_path))
                    xcf_data = xcf_parser.parse()
                    self.metadata.update(xcf_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse XCF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # XCF files handled separately
            
            # Check if it's a JP2 file (JPEG 2000)
            if file_ext == '.jp2':
                try:
                    # JP2 files are JPEG 2000 format, similar structure to JPEG but different compression
                    # For now, try to extract basic information
                    # Full JP2 parsing would require JPEG 2000 codec support
                    metadata = {}
                    metadata['File:FileType'] = 'JP2'
                    metadata['File:FileTypeExtension'] = 'jp2'
                    metadata['File:MIMEType'] = 'image/jp2'
                    # JP2 files start with JPEG 2000 signature
                    # Read file data
                    with open(self.file_path, 'rb') as f:
                        file_data = f.read(100)
                    
                    if len(file_data) >= 12:
                        if file_data[:4] == b'\x00\x00\x00\x0c' and file_data[4:12] == b'jP  \r\n\x87\n':
                            metadata['JP2:HasSignature'] = True
                            metadata['JP2:Signature'] = 'JP2'
                    self.metadata.update(metadata)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse JP2 metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # JP2 files handled separately
            
            # Check if it's an SVG file
            if file_ext == '.svg':
                try:
                    from dnexif.svg_parser import SVGParser
                    svg_parser = SVGParser(file_path=str(self.file_path))
                    svg_data = svg_parser.parse()
                    self.metadata.update(svg_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse SVG metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # SVG files handled separately
            
            # Check if it's a BMP file
            if file_ext in {'.bmp', '.dib'}:
                try:
                    from dnexif.bmp_parser import BMPParser
                    bmp_parser = BMPParser(file_path=str(self.file_path))
                    bmp_data = bmp_parser.parse()
                    self.metadata.update(bmp_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise
                    pass
                self._add_composite_tags()
                return  # BMP files handled separately
            
            # Check if it's a PSD file
            if file_ext == '.psd':
                try:
                    from dnexif.psd_parser import PSDParser
                    psd_parser = PSDParser(file_path=str(self.file_path))
                    psd_data = psd_parser.parse()
                    self.metadata.update(psd_data)
                    
                    # PSD files may also contain EXIF, IPTC, and XMP in image resources
                    # These are already parsed by the PSD parser
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse PSD metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # PSD files handled separately
            
            # Check for ICO/CUR files
            if file_ext in ('.ico', '.cur'):
                try:
                    ico_parser = ICOParser(file_path=str(self.file_path))
                    ico_data = ico_parser.parse()
                    self.metadata.update(ico_data)
                except Exception as e:
                    # ICO/CUR parsing errors are non-critical, silently continue
                    if not self.ignore_minor_errors:
                        # Log but don't fail for ICO/CUR parsing issues
                        pass
                    pass
                self._add_composite_tags()
                return  # ICO/CUR files handled separately
            
            # Check for PCX files
            if file_ext == '.pcx':
                try:
                    pcx_parser = PCXParser(file_path=str(self.file_path))
                    pcx_data = pcx_parser.parse()
                    self.metadata.update(pcx_data)
                except Exception as e:
                    # PCX parsing errors are non-critical, silently continue
                    if not self.ignore_minor_errors:
                        # Log but don't fail for PCX parsing issues
                        pass
                    pass
                self._add_composite_tags()
                return  # PCX files handled separately
            
            # Check for TGA files
            if file_ext in ('.tga', '.targa'):
                try:
                    tga_parser = TGAParser(file_path=str(self.file_path))
                    tga_data = tga_parser.parse()
                    self.metadata.update(tga_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse TGA metadata from {self.file_path}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return
            
            # Check for WPG files
            if file_ext == '.wpg':
                try:
                    from dnexif.wpg_parser import WGPParser
                    wpg_parser = WGPParser(file_path=str(self.file_path))
                    wpg_data = wpg_parser.parse()
                    self.metadata.update(wpg_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WPG metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # WPG files handled separately
            
            # Check for VNT files
            if file_ext == '.vnt':
                try:
                    from dnexif.vnt_parser import VNTParser
                    vnt_parser = VNTParser(file_path=str(self.file_path))
                    vnt_data = vnt_parser.parse()
                    self.metadata.update(vnt_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse VNT metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # VNT files handled separately
            
            # Check for Leica LIF files
            if file_ext == '.lif':
                try:
                    from dnexif.lif_parser import LIFParser
                    lif_parser = LIFParser(file_path=str(self.file_path))
                    lif_data = lif_parser.parse()
                    self.metadata.update(lif_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse LIF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # LIF files handled separately
            
            # Check for Leica LIFEXT files
            if file_ext == '.lifext':
                try:
                    from dnexif.lifext_parser import LIFEXTParser
                    lifext_parser = LIFEXTParser(file_path=str(self.file_path))
                    lifext_data = lifext_parser.parse()
                    self.metadata.update(lifext_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse LIFEXT metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # LIFEXT files handled separately
            
            # Check for macOS DS_Store files (can be .DS_Store or .ds_store extension, or filename .DS_Store)
            if file_ext == '.ds_store' or (self.file_path and self.file_path.name == '.DS_Store'):
                try:
                    from dnexif.ds_store_parser import DSStoreParser
                    ds_store_parser = DSStoreParser(file_path=str(self.file_path))
                    ds_store_data = ds_store_parser.parse()
                    self.metadata.update(ds_store_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse DS_Store metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # DS_Store files handled separately
            
            # Check for Zeiss CZI files
            if file_ext == '.czi':
                try:
                    from dnexif.czi_parser import CZIParser
                    czi_parser = CZIParser(file_path=str(self.file_path))
                    czi_data = czi_parser.parse()
                    self.metadata.update(czi_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse CZI metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # CZI files handled separately
            
            # Check if it's a GIF file
            if file_ext == '.gif':
                try:
                    from dnexif.gif_parser import GIFParser
                    gif_parser = GIFParser(file_path=str(self.file_path))
                    gif_data = gif_parser.parse()
                    self.metadata.update(gif_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse GIF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # GIF files handled separately

            # Check if it's a WebP file
            if file_ext == '.webp':
                try:
                    webp_parser = WebPParser(file_path=str(self.file_path))
                    webp_data = webp_parser.parse()
                    self.metadata.update(webp_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse WebP metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                # Calculate Composite tags before returning
                self._add_composite_tags()
                return  # WebP files handled separately
            
            # Check if it's a DICOM file
            if file_ext in {'.dcm', '.dicom'}:
                try:
                    from dnexif.dicom_parser import DICOMParser
                    dicom_parser = DICOMParser(file_path=str(self.file_path))
                    dicom_data = dicom_parser.parse()
                    self.metadata.update(dicom_data)
                except Exception as e:
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse DICOM metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # DICOM files handled separately
            
            # Check if it's a HEIC/HEIF/AVIF/JXL/CR3/HIF file (all can use ISO BMFF container)
            if file_ext in {'.heic', '.heif', '.avif', '.jxl', '.cr3', '.hif'}:
                try:
                    from dnexif.heic_parser import HEICParser
                    heic_parser = HEICParser(file_path=str(self.file_path))
                    heic_data = heic_parser.parse()
                    self.metadata.update(heic_data)
                    
                    # Check major brand to determine actual format
                    # standard format reports HEIF files with "heic" major brand as "HEIC" format
                    major_brand = heic_data.get('HEIC:MajorBrand', '').lower()
                    if major_brand == 'heic':
                        # File uses HEIC format, report as HEIC regardless of extension
                        self.metadata['File:FileType'] = 'HEIC'
                        self.metadata['File:FileTypeExtension'] = 'heic'
                    elif major_brand in ('heif', 'mif1', 'msf1'):
                        # File uses HEIF format, report as HEIF
                        self.metadata['File:FileType'] = 'HEIF'
                        self.metadata['File:FileTypeExtension'] = 'heif'
                    elif major_brand in ('avif', 'avis'):
                        # File uses AVIF format, report as AVIF
                        self.metadata['File:FileType'] = 'AVIF'
                        self.metadata['File:FileTypeExtension'] = 'avif'
                    elif major_brand in ('jxl ', 'jxl') or major_brand.strip() == 'jxl':
                        # File uses JXL format (box format), report as JXL
                        self.metadata['File:FileType'] = 'JXL'
                        self.metadata['File:FileTypeExtension'] = 'jxl'
                    elif file_ext == '.jxl':
                        # JXL format (could be codestream or box format)
                        # If we got here, it's likely JXL format
                        if 'File:FileType' not in self.metadata:
                            self.metadata['File:FileType'] = 'JXL'
                            self.metadata['File:FileTypeExtension'] = 'jxl'
                    elif file_ext == '.cr3' or major_brand in ('crx', 'cr3'):
                        # CR3 format (Canon RAW 3) uses ISO BMFF container
                        self.metadata['File:FileType'] = 'CR3'
                        self.metadata['File:FileTypeExtension'] = 'cr3'
                        self.metadata['File:MIMEType'] = 'image/x-canon-cr3'  # Set MIME type for CR3
                    elif file_ext == '.hif':
                        # HIF format (Fujifilm HIF) - may use ISO BMFF container or RAF-like structure
                        self.metadata['File:FileType'] = 'HIF'
                        self.metadata['File:FileTypeExtension'] = 'hif'
                        self.metadata['File:MIMEType'] = 'image/x-fujifilm-hif'  # Set MIME type for HIF
                        
                        # Extract JPEG previews from HIF files
                        try:
                            jpeg_previews = self._extract_hif_jpeg_previews()
                            if jpeg_previews:
                                self.metadata.update(jpeg_previews)
                        except Exception:
                            # JPEG preview extraction is optional
                            pass
                    
                    # HEIC/CR3/HIF files may also contain EXIF and XMP in meta boxes
                    # Try to extract them
                    try:
                        self._exif_parser = ExifParser(file_path=str(self.file_path))
                        exif_data = self._exif_parser.read()
                        exif_prefixed = {f"EXIF:{k}": v for k, v in exif_data.items() if not k.startswith('EXIF:')}
                        self.metadata.update(exif_prefixed)
                    except Exception as exif_e:
                        # EXIF extraction from HEIC is optional
                        pass
                    
                    try:
                        self._xmp_parser = XMPParser(file_path=str(self.file_path))
                        if self.scan_for_xmp:
                            xmp_data = self._xmp_parser.read(scan_entire_file=True)
                        else:
                            xmp_data = self._xmp_parser.read()
                        self.metadata.update(xmp_data)
                    except Exception as xmp_e:
                        # XMP extraction from HEIC is optional
                        pass
                except Exception as e:
                    # For HIF files, try to extract JPEG previews even if HEIC parsing fails
                    if file_ext == '.hif':
                        try:
                            jpeg_previews = self._extract_hif_jpeg_previews()
                            if jpeg_previews:
                                self.metadata.update(jpeg_previews)
                        except Exception:
                            # JPEG preview extraction is optional
                            pass
                    
                    if not self.ignore_minor_errors:
                        raise MetadataReadError(
                            f"Failed to parse HEIC/HEIF/AVIF/JXL/CR3/HIF metadata from {self.file_path.name}: {str(e)}"
                        ) from e
                    pass
                self._add_composite_tags()
                return  # HEIC files handled separately
            
            # Check if it's an audio format
            audio_formats = {'.mp3', '.wav', '.flac', '.ogg', '.wma', '.opus'}
            if file_ext in audio_formats:
                # Use audio parser for audio files
                try:
                    audio_parser = AudioParser(file_path=str(self.file_path))
                    audio_data = audio_parser.parse()
                    self.metadata.update(audio_data)
                except Exception as e:
                    # Audio parsing errors are non-critical, silently continue
                    if not self.ignore_minor_errors:
                        # Log but don't fail for audio parsing issues
                        pass
                    pass
                self._add_composite_tags()
                
                # Clean up any double-prefixed tags that might have been added anywhere
                double_prefixed = {k: v for k, v in self.metadata.items() if k.startswith('EXIF:EXIF:')}
                for double_key, double_value in double_prefixed.items():
                    # Remove double prefix and add with single prefix
                    single_key = double_key[5:]  # Remove first "EXIF:"
                    if single_key not in self.metadata:
                        self.metadata[single_key] = double_value
                    # Remove double-prefixed version
                    del self.metadata[double_key]
                
                return  # Audio files handled separately for now
            
            # Check if it's a RAW format
            # Note: CR3 and HIF are handled separately as they may use ISO BMFF container
            raw_formats = {'.cr2', '.cr3', '.crw', '.nef', '.arw', '.dng', 
                          '.orf', '.raf', '.rw2', '.srw', '.pef', '.x3f',
                          '.3fr', '.ari', '.bay', '.cap', '.dcs', '.dcr',
                          '.drf', '.eip', '.erf', '.fff', '.iiq', '.mef',
                          '.mos', '.mrw', '.mdc', '.nrw', '.rwl', '.srf', '.hif', '.raw'}
            
            if file_ext in raw_formats:
                # Use RAW parser for complete metadata extraction
                try:
                    raw_parser = RAWParser(file_path=str(self.file_path))
                    raw_data = raw_parser.parse()
                    self.metadata.update(raw_data)
                except Exception as raw_e:
                    # RAW parsing errors are non-critical, continue with EXIF parser
                    if not self.ignore_minor_errors:
                        # Log but don't fail for RAW parsing issues
                        pass
                
                # Also try standard EXIF parser (RAW files often have EXIF)
                # IMPROVEMENT (Build 1489): Skip ExifParser for MOS files to prevent timeout
                # MOS parser already handles metadata extraction and ExifParser causes timeout issues
                if file_ext != '.mos':
                    try:
                        exif_parser = ExifParser(file_path=str(self.file_path))
                        self._exif_parser = exif_parser  # Store for File:ExifByteOrder extraction
                        exif_data = exif_parser.read()
                        # Add tags with proper prefixes
                        # Canon/Nikon/Sony/Olympus/Pentax/Fujifilm/Panasonic/MakerNote tags should not have EXIF prefix
                        for k, v in exif_data.items():
                            if (k.startswith('Canon') or k.startswith('Nikon') or k.startswith('Sony') or 
                                k.startswith('Olympus') or k.startswith('Pentax') or k.startswith('Fujifilm') or 
                                k.startswith('Panasonic') or k.startswith('MakerNote:') or k.startswith('MakerNotes:')):
                                # Manufacturer tags should be used as-is (already formatted correctly)
                                self.metadata[k] = v
                            elif k.startswith('EXIF:') or k.startswith('GPS:') or k.startswith('IFD'):
                                # Already has proper prefix
                                self.metadata[k] = v
                            elif k in ('ImageWidth', 'ImageHeight', 'ImageLength'):
                                # Keep ImageWidth/ImageHeight/ImageLength without prefix (used by standard format)
                                self.metadata[k] = v
                            else:
                                # Add EXIF prefix for standard EXIF tags
                                self.metadata[f"EXIF:{k}"] = v
                        
                        # Special handling for Sony ARW and similar formats:
                        # If EXIF:SubfileType exists and is "Full-resolution image", use it as SubfileType
                        # This standard format behavior where SubIFD's SubfileType takes precedence
                        if 'EXIF:SubfileType' in self.metadata:
                            exif_subfile_type = self.metadata.get('EXIF:SubfileType')
                            if (exif_subfile_type == 0 or 
                                exif_subfile_type == 'Full-resolution image' or
                                str(exif_subfile_type).strip() == '0' or
                                (isinstance(exif_subfile_type, str) and 'Full-resolution' in exif_subfile_type)):
                                from dnexif.value_formatter import format_exif_value
                                self.metadata['SubfileType'] = format_exif_value('SubfileType', 0)
                    except Exception as exif_e:
                        # EXIF extraction from RAW is optional
                        pass
                
                # Cleanup: Remove EXIF/IFD prefixes from MakerNote tags (should be "MakerNotes:" not "EXIF:MakerNotes:" or "IFD1:MakerNotes:")
                # This fixes any tags that incorrectly got EXIF/IFD prefix added
                tags_to_fix = {}
                for k, v in list(self.metadata.items()):
                    # Check for EXIF:MakerNotes: or EXIF:MakerNote:
                    if k.startswith('EXIF:MakerNotes:') or k.startswith('EXIF:MakerNote:'):
                        # Remove EXIF prefix - keep only "MakerNotes:" or "MakerNote:"
                        new_key = k.replace('EXIF:', '', 1)  # Remove first occurrence only
                        tags_to_fix[new_key] = v
                        # Remove old key with EXIF prefix
                        del self.metadata[k]
                    # Check for IFD1:MakerNotes: or IFD1:MakerNote: (from thumbnail IFD)
                    elif k.startswith('IFD1:MakerNotes:') or k.startswith('IFD1:MakerNote:'):
                        # Remove IFD1 prefix - keep only "MakerNotes:" or "MakerNote:"
                        new_key = k.replace('IFD1:', '', 1)  # Remove first occurrence only
                        tags_to_fix[new_key] = v
                        # Remove old key with IFD1 prefix
                        del self.metadata[k]
                    # Check for IFD0:MakerNotes: or IFD0:MakerNote: (from main IFD)
                    elif k.startswith('IFD0:MakerNotes:') or k.startswith('IFD0:MakerNote:'):
                        # Remove IFD0 prefix - keep only "MakerNotes:" or "MakerNote:"
                        new_key = k.replace('IFD0:', '', 1)  # Remove first occurrence only
                        tags_to_fix[new_key] = v
                        # Remove old key with IFD0 prefix
                        del self.metadata[k]
                # Add corrected tags
                self.metadata.update(tags_to_fix)
                
                # Detect DNG 1.7.0.0 version for DNG files
                if file_ext == '.dng':
                    try:
                        # Check for DNGVersion tag (formatted as "1.7.0.0" for DNG 1.7.0.0)
                        dng_version = None
                        for tag_key in ['DNGVersion', 'EXIF:DNGVersion', 'DNG:DNGVersion']:
                            if tag_key in self.metadata:
                                dng_version = self.metadata[tag_key]
                                break
                        
                        if dng_version:
                            # DNGVersion is formatted as "X.Y.Z.W" (e.g., "1.7.0.0")
                            if isinstance(dng_version, str):
                                version_parts = dng_version.split('.')
                                if len(version_parts) >= 2:
                                    try:
                                        major = int(version_parts[0])
                                        minor = int(version_parts[1])
                                        # DNG 1.7.0.0 has major=1, minor=7
                                        if major == 1 and minor >= 7:
                                            self.metadata['DNG:DNG1.7.0.0'] = True
                                            self.metadata['DNG:DNGStandard'] = 'DNG 1.7.0.0'
                                            
                                            # Check for DNG 1.7.1 (minor version 7, patch >= 1)
                                            if len(version_parts) >= 3:
                                                try:
                                                    patch = int(version_parts[2])
                                                    if patch >= 1:
                                                        self.metadata['DNG:DNG1.7.1'] = True
                                                        self.metadata['DNG:DNGStandard'] = 'DNG 1.7.1'
                                                except (ValueError, IndexError):
                                                    pass
                                    except (ValueError, IndexError):
                                        pass
                            elif isinstance(dng_version, (list, tuple)) and len(dng_version) >= 2:
                                # DNGVersion might be raw array [1, 7, 0, 0] or [1, 7, 1, 0]
                                try:
                                    major = int(dng_version[0])
                                    minor = int(dng_version[1])
                                    if major == 1 and minor >= 7:
                                        self.metadata['DNG:DNG1.7.0.0'] = True
                                        self.metadata['DNG:DNGStandard'] = 'DNG 1.7.0.0'
                                        
                                        # Check for DNG 1.7.1 (patch version >= 1)
                                        if len(dng_version) >= 3:
                                            try:
                                                patch = int(dng_version[2])
                                                if patch >= 1:
                                                    self.metadata['DNG:DNG1.7.1'] = True
                                                    self.metadata['DNG:DNGStandard'] = 'DNG 1.7.1'
                                            except (ValueError, IndexError, TypeError):
                                                pass
                                except (ValueError, IndexError, TypeError):
                                    pass
                    except Exception:
                        # DNG version detection is optional
                        pass
            elif file_ext in ('.png',):
                # PNG files - parse PNG header (IHDR chunk), EXIF (eXIf chunks), and text chunks
                try:
                    # Parse PNG header for basic image properties
                    png_header_data = self._parse_png_header()
                    self.metadata.update(png_header_data)
                    
                    # Parse PNG text chunks (tEXt, zTXt) including Stable Diffusion metadata
                    png_text_data = self._parse_png_text_chunks()
                    self.metadata.update(png_text_data)
                    
                    # Try EXIF parser (supports eXIf chunks)
                    self._exif_parser = ExifParser(file_path=str(self.file_path))
                    exif_data = self._exif_parser.read()
                    # Filter out empty EXIF tags
                    exif_prefixed = {f"EXIF:{k}": v for k, v in exif_data.items() 
                                   if not k.startswith('EXIF:') and v and str(v).strip()}
                    self.metadata.update(exif_prefixed)
                except Exception as png_e:
                    # PNG EXIF extraction is optional
                    pass
            else:
                # Load EXIF metadata (JPEG, TIFF, etc.)
                self._exif_parser = ExifParser(file_path=str(self.file_path))
                exif_data = self._exif_parser.read()
                
                # Process EXIF data - handle tags that already have EXIF: prefix separately
                # Optimized: batch updates and reduce redundant string operations
                double_prefixed_fix = {}  # Collect double-prefixed tags for batch fix
                batch_updates = {}  # Batch dictionary updates for better performance
                
                for k, v in exif_data.items():
                    # Fix double-prefixed tags (EXIF:EXIF:...) - optimized check
                    if k.startswith('EXIF:EXIF:'):
                        # Remove double prefix and collect for batch fix
                        single_key = k[5:]  # Remove first "EXIF:"
                        double_prefixed_fix[single_key] = (k, v)
                        k = single_key
                    
                    # Optimized: cache prefix checks to avoid redundant string operations
                    has_exif_prefix = k.startswith('EXIF:')
                    has_makernote_prefix = k.startswith('MakerNote:') or k.startswith('MakerNotes:')
                    has_panasonic_prefix = k.startswith('PanasonicRaw:')
                    
                    if has_exif_prefix:
                        # Tags that already have EXIF: prefix - use as-is (don't double-prefix)
                        batch_updates[k] = v
                    elif has_makernote_prefix:
                        # MakerNote tags - use as-is
                        batch_updates[k] = v
                    elif has_panasonic_prefix:
                        # PanasonicRaw tags - use as-is (don't add MakerNote prefix)
                        batch_updates[k] = v
                    else:
                        # Tags without prefix - add EXIF: prefix
                        batch_updates[f"EXIF:{k}"] = v
                        # Also add without prefix for backward compatibility
                        batch_updates[k] = v
                
                # Batch update metadata dictionary (more efficient than individual assignments)
                self.metadata.update(batch_updates)
                
                # Fix double-prefixed tags in batch
                for single_key, (double_key, double_value) in double_prefixed_fix.items():
                    if single_key not in self.metadata:
                        self.metadata[single_key] = double_value
                    # Remove double-prefixed version if it exists
                    if double_key in self.metadata:
                        del self.metadata[double_key]
                
                # Clean up any remaining double-prefixed tags that might have been added
                # Optimized: use list comprehension for faster iteration
                double_prefixed_keys = [k for k in self.metadata.keys() if k.startswith('EXIF:EXIF:')]
                for double_key in double_prefixed_keys:
                    single_key = double_key[5:]  # Remove first "EXIF:"
                    if single_key not in self.metadata:
                        self.metadata[single_key] = self.metadata[double_key]
                    # Remove double-prefixed version
                    del self.metadata[double_key]
            
            # Load IPTC metadata (works for JPEG and some RAW)
            try:
                self._iptc_parser = IPTCParser(file_path=str(self.file_path))
                iptc_data = self._iptc_parser.read()
                iptc_prefixed = {f"IPTC:{k}": v for k, v in iptc_data.items()}
                self.metadata.update(iptc_prefixed)
            except Exception as e:
                if not self.ignore_minor_errors:
                    raise MetadataReadError(
                        f"Failed to parse IPTC metadata from {self.file_path.name}: {str(e)}"
                    ) from e
                pass  # IPTC is optional
            
            # Load XMP metadata (works for JPEG, PNG, and RAW)
            # For RAW files (and some other formats like PNG), enable full file scanning by default
            # since XMP may be stored throughout the file or in non-standard locations.
            try:
                self._xmp_parser = XMPParser(file_path=str(self.file_path))
                # For RAW formats and PNG, scan entire file for XMP (many formats store XMP throughout the file)
                if self.scan_for_xmp or file_ext in raw_formats or file_ext == '.png':
                    # Scan entire file for XMP (slower but more thorough)
                    xmp_data = self._xmp_parser.read(scan_entire_file=True)
                else:
                    xmp_data = self._xmp_parser.read()
                self.metadata.update(xmp_data)
            except Exception as e:
                if not self.ignore_minor_errors:
                    raise MetadataReadError(
                        f"Failed to parse XMP metadata from {self.file_path.name}: {str(e)}"
                    ) from e
                pass  # XMP is optional
            
            # Load SEAL metadata (works for JPEG, TIFF, PNG, WEBP, HEIC, MOV, MP4, PDF, MKV, WAV, etc.)
            try:
                from dnexif.seal_parser import SEALParser
                seal_parser = SEALParser(file_path=str(self.file_path))
                seal_data = seal_parser.parse()
                if seal_data and seal_data.get('SEAL:HasSEALMetadata'):
                    self.metadata.update(seal_data)
            except Exception as e:
                # SEAL parsing is optional - don't raise error if SEAL not found
                pass
            
            # Load C2PA JUMBF metadata (works for PNG, JPEG, TIFF, MP4, MOV, WebP, etc.)
            try:
                from dnexif.c2pa_parser import C2PAParser
                c2pa_parser = C2PAParser(file_path=str(self.file_path))
                c2pa_data = c2pa_parser.parse()
                if c2pa_data and c2pa_data.get('C2PA:HasC2PAMetadata'):
                    self.metadata.update(c2pa_data)
            except Exception as e:
                # C2PA parsing is optional - don't raise error if C2PA not found
                pass
            
            # Load additional metadata standards (JFIF, ICC, Photoshop IRB, FlashPix)
            try:
                from dnexif.metadata_standards import MetadataStandards
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
                
                # Parse JFIF
                jfif_data = MetadataStandards.parse_jfif(file_data)
                self.metadata.update(jfif_data)
                
                # Parse ICC profile
                icc_data = MetadataStandards.parse_icc_profile(file_data)
                self.metadata.update(icc_data)
                
                # Parse Photoshop IRB
                ps_irb_data = MetadataStandards.parse_photoshop_irb(file_data)
                self.metadata.update(ps_irb_data)
                
                # Parse FlashPix
                try:
                    from dnexif.flashpix_parser import FlashPixParser
                    flashpix_parser = FlashPixParser(file_data=file_data)
                    flashpix_data = flashpix_parser.parse()
                    self.metadata.update(flashpix_data)
                except Exception as flashpix_e:
                    # FlashPix is optional
                    pass
                
                # Parse AFCP
                try:
                    from dnexif.afcp_parser import AFCPParser
                    afcp_parser = AFCPParser(file_data=file_data)
                    afcp_data = afcp_parser.parse()
                    self.metadata.update(afcp_data)
                except Exception as afcp_e:
                    # AFCP is optional
                    pass
                
                # Parse MPF (Multi-picture Format) metadata
                if file_ext in {'.jpg', '.jpeg'}:
                    try:
                        from dnexif.mpf_parser import MPFParser
                        mpf_parser = MPFParser(file_data=file_data)
                        mpf_data = mpf_parser.parse()
                        self.metadata.update(mpf_data)
                    except Exception as mpf_e:
                        # MPF is optional
                        pass
                
                    # Parse APP6 (GoPro) metadata
                    try:
                        from dnexif.app6_parser import APP6Parser
                        app6_parser = APP6Parser(file_data=file_data)
                        app6_data = app6_parser.parse()
                        self.metadata.update(app6_data)
                    except Exception as app6_e:
                        # APP6 is optional
                        pass
                    
                    # Parse APP10 (AROT - Adobe Rotation) metadata
                    try:
                        app10_metadata = self._parse_app10_arot(file_data)
                        if app10_metadata:
                            self.metadata.update(app10_metadata)
                    except Exception as app10_e:
                        # APP10 is optional
                        pass
                
                # Parse DICOM (if file is DICOM format)
                # Only parse DICOM for actual DICOM files, not for all files
                file_ext = self.file_path.suffix.lower()
                if file_ext in {'.dcm', '.dicom'}:
                    try:
                        from dnexif.dicom_parser import DICOMParser
                        dicom_parser = DICOMParser(file_data=file_data)
                        dicom_data = dicom_parser.parse()
                        if dicom_data.get('DICOM:HasDICOM'):
                            self.metadata.update(dicom_data)
                    except Exception as dicom_e:
                        # DICOM is optional
                        pass
            except Exception as standards_e:
                # Additional standards are optional
                pass
            
            # Add File tags derived from EXIF data
            # NOTE: Must be called BEFORE _clear_parser_cache() so _exif_parser is still available
            self._add_file_tags_from_exif()
            
            # Map EXIF:ImageLength to EXIF:ImageHeight (they're the same in TIFF/EXIF)
            if 'EXIF:ImageLength' in self.metadata and 'EXIF:ImageHeight' not in self.metadata:
                self.metadata['EXIF:ImageHeight'] = self.metadata['EXIF:ImageLength']
            
            # Clear cached file data from parsers to reduce memory usage
            # This is safe because metadata has already been extracted
            # NOTE: _add_file_tags_from_exif() must be called before this to access _exif_parser
            self._clear_parser_cache()
            
            # Calculate Composite tags (ImageSize, Megapixels, etc.)
            self._add_composite_tags()
            
            # Add Canon-specific composite tags for CR2 and CRW files
            if file_ext in ('.cr2', '.crw'):
                self._add_canon_composite_tags()
            
        except Exception as e:
            if isinstance(e, MetadataReadError):
                raise
            raise MetadataReadError(
                f"Failed to load metadata from {self.file_path.name}: {str(e)}"
            ) from e
    
    def _extract_hif_jpeg_previews(self) -> Dict[str, Any]:
        """
        Extract JPEG previews from FujiFilm HIF files.
        
        HIF files may contain embedded JPEG preview images.
        This method searches for JPEG signatures in HIF files and extracts preview information.
        
        Returns:
            Dictionary containing JPEG preview metadata
        """
        metadata = {}
        try:
            # Read file data
            file_data = self._read_file_data()
            if not file_data or len(file_data) < 100:
                return metadata
            
            # Search for JPEG signatures (0xFF 0xD8 0xFF)
            jpeg_signatures = []
            offset = 0
            
            while offset < len(file_data) - 2:
                # Look for JPEG start marker (0xFFD8FF)
                jpeg_start = file_data.find(b'\xff\xd8\xff', offset)
                if jpeg_start == -1:
                    break
                
                # Skip JPEG markers at the very beginning (might be file header)
                if jpeg_start < 100:
                    offset = jpeg_start + 3
                    continue
                
                # Try to find JPEG end marker (0xFFD9)
                jpeg_end = file_data.find(b'\xff\xd9', jpeg_start + 2)
                if jpeg_end > jpeg_start:
                    jpeg_size = jpeg_end + 2 - jpeg_start
                    # Only consider JPEGs larger than 1KB (likely previews, not tiny markers)
                    if jpeg_size > 1024:
                        jpeg_signatures.append({
                            'offset': jpeg_start,
                            'size': jpeg_size,
                            'end': jpeg_end + 2
                        })
                    offset = jpeg_end + 2  # Skip past this JPEG
                else:
                    offset = jpeg_start + 3
            
            if jpeg_signatures:
                metadata['HIF:HasJPEGPreview'] = True
                metadata['HIF:JPEGPreviewCount'] = len(jpeg_signatures)
                
                # Extract information about the first (usually largest) preview
                if len(jpeg_signatures) > 0:
                    first_preview = jpeg_signatures[0]
                    metadata['HIF:JPEGPreviewOffset'] = first_preview['offset']
                    metadata['HIF:JPEGPreviewSize'] = first_preview['size']
                    metadata['HIF:JPEGPreviewLength'] = f"{first_preview['size']} bytes"
                
                # Extract information about all previews
                for i, preview in enumerate(jpeg_signatures):
                    if i == 0:
                        # First preview already extracted above
                        continue
                    metadata[f'HIF:JPEGPreview{i+1}:Offset'] = preview['offset']
                    metadata[f'HIF:JPEGPreview{i+1}:Size'] = preview['size']
                    metadata[f'HIF:JPEGPreview{i+1}:Length'] = f"{preview['size']} bytes"
            
        except Exception:
            # JPEG preview extraction is optional - don't raise errors
            pass
        
        return metadata
    
    def _extract_vivo_jpeg_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract proprietary information from Vivo phone JPEG images.
        
        Vivo phones store proprietary metadata in JPEG APP segments or EXIF data.
        This method searches for Vivo-specific patterns and extracts proprietary information.
        
        Args:
            file_data: JPEG file data (first 50KB or full file)
            
        Returns:
            Dictionary containing Vivo proprietary metadata
        """
        metadata = {}
        try:
            if not file_data or len(file_data) < 100:
                return metadata
            
            # Detect if this is a Vivo phone JPEG image
            is_vivo_jpeg = False
            vivo_patterns = [
                b'Vivo',
                b'VIVO',
                b'vivo',
                b'VIVO ',
                b'vivo ',
                b'VivoPhone',
                b'VIVOPHONE',
                b'vivophone',
                b'BBK',
                b'bbk',
                b'BBK ',
                b'X Series',
                b'X series',
                b'X SERIES',
                b'Y Series',
                b'Y series',
                b'Y SERIES',
                b'S Series',
                b'S series',
                b'S SERIES',
            ]
            
            for pattern in vivo_patterns:
                if pattern in file_data:
                    is_vivo_jpeg = True
                    metadata['JPEG:Vivo:IsVivoPhone'] = True
                    break
            
            if not is_vivo_jpeg:
                return metadata
            
            metadata['JPEG:Vivo:HasVivoMetadata'] = True
            
            # Search for Vivo-specific metadata in JPEG APP segments
            offset = 2  # Skip JPEG SOI marker
            vivo_metadata_found = False
            
            while offset < len(file_data) - 1:
                # Check for segment marker
                if file_data[offset] != 0xFF:
                    break
                
                marker = file_data[offset + 1] if offset + 1 < len(file_data) else 0
                
                # APP segments (0xE0-0xEF) may contain Vivo metadata
                if marker >= 0xE0 and marker <= 0xEF:
                    if offset + 4 < len(file_data):
                        segment_length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        if segment_length > 0 and offset + 2 + segment_length <= len(file_data):
                            segment_data = file_data[offset + 4:offset + 2 + segment_length]
                            
                            # Search for Vivo-specific patterns in segment data
                            for pattern in vivo_patterns:
                                if pattern in segment_data:
                                    vivo_metadata_found = True
                                    metadata[f'JPEG:Vivo:HasAPP{marker - 0xE0}Metadata'] = True
                                    metadata[f'JPEG:Vivo:APP{marker - 0xE0}Offset'] = offset
                                    metadata[f'JPEG:Vivo:APP{marker - 0xE0}Length'] = segment_length
                                    break
                            
                            # Try to extract text metadata from segment
                            try:
                                segment_str = segment_data[:500].decode('utf-8', errors='ignore')
                                
                                # Look for Vivo-specific metadata fields
                                vivo_metadata_fields = [
                                    'Model',
                                    'MODEL',
                                    'model',
                                    'Serial',
                                    'SERIAL',
                                    'serial',
                                    'Firmware',
                                    'FIRMWARE',
                                    'firmware',
                                    'Version',
                                    'VERSION',
                                    'version',
                                    'Camera',
                                    'CAMERA',
                                    'camera',
                                    'Lens',
                                    'LENS',
                                    'lens',
                                    'ISO',
                                    'iso',
                                    'Shutter',
                                    'SHUTTER',
                                    'shutter',
                                    'Aperture',
                                    'APERTURE',
                                    'aperture',
                                    'FocalLength',
                                    'FOCALLENGTH',
                                    'focal_length',
                                    'WhiteBalance',
                                    'WHITEBALANCE',
                                    'white_balance',
                                ]
                                
                                for field in vivo_metadata_fields:
                                    if field in segment_str:
                                        metadata[f'JPEG:Vivo:Has{field}'] = True
                            except Exception:
                                pass
                            
                            offset += 2 + segment_length
                            continue
                
                # Skip to next segment
                if marker == 0xD8:  # SOI
                    offset += 2
                elif marker == 0xD9:  # EOI
                    break
                elif marker >= 0xE0 and marker <= 0xEF:  # APP segments
                    if offset + 4 < len(file_data):
                        length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        offset += 2 + length
                    else:
                        break
                else:
                    # Skip other segments
                    if offset + 2 < len(file_data):
                        length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        offset += 2 + length
                    else:
                        break
            
            if vivo_metadata_found:
                metadata['JPEG:Vivo:HasVivoMetadata'] = True
            
            # Search for Vivo-specific patterns in EXIF data (if available)
            # EXIF data is typically in APP1 segment
            exif_patterns = [
                b'Vivo',
                b'VIVO',
                b'vivo',
                b'BBK',
                b'bbk',
            ]
            
            for pattern in exif_patterns:
                if pattern in file_data:
                    metadata['JPEG:Vivo:HasVivoEXIF'] = True
                    break
            
            # Count Vivo-specific APP segments
            vivo_app_segments = []
            for i in range(0xE0, 0xF0):
                app_key = f'JPEG:Vivo:HasAPP{i - 0xE0}Metadata'
                if metadata.get(app_key):
                    vivo_app_segments.append(i - 0xE0)
            
            if vivo_app_segments:
                metadata['JPEG:Vivo:VivoAPPSegmentCount'] = len(vivo_app_segments)
                metadata['JPEG:Vivo:VivoAPPSegments'] = ','.join(map(str, vivo_app_segments))
            
        except Exception:
            # Vivo JPEG metadata extraction is optional - don't raise errors
            pass
        
        return metadata
    
    def _parse_app10_arot(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse APP10 segment for AROT (Adobe Rotation) metadata.
        
        APP10 marker is 0xFFEA.
        AROT can contain HDR gain curve data.
        
        Args:
            file_data: JPEG file data
            
        Returns:
            Dictionary of AROT metadata
        """
        metadata = {}
        
        if not file_data.startswith(b'\xff\xd8'):
            return metadata
        
        offset = 2  # Skip JPEG signature
        
        while offset < len(file_data) - 4:
            # Look for APP10 marker (0xFFEA)
            if file_data[offset:offset+2] == b'\xff\xea':
                # Read segment length
                if offset + 4 > len(file_data):
                    break
                length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                
                if length < 4 or offset + 2 + length > len(file_data):
                    break
                
                # Extract segment data (skip marker and length)
                segment_data = file_data[offset+4:offset+2+length]
                
                # Check for AROT identifier
                # AROT typically starts with "AROT" or similar identifier
                if len(segment_data) >= 4:
                    # Look for AROT signature
                    if segment_data[:4] == b'AROT' or b'AROT' in segment_data[:16]:
                        # Parse AROT data
                        # AROT structure may contain HDRGainCurveSize
                        # This is typically a 4-byte integer indicating the size of the HDR gain curve
                        try:
                            # Try to find HDRGainCurveSize in the AROT data
                            # The exact structure depends on the AROT version, but typically
                            # HDRGainCurveSize is stored as a 32-bit integer
                            if len(segment_data) >= 8:
                                # Skip AROT header (4 bytes) and read potential size field
                                # AROT structure: [AROT][version?][data...]
                                # HDRGainCurveSize might be at offset 4 or later
                                for i in range(4, min(len(segment_data) - 4, 32), 4):
                                    # Try to read as 32-bit integer (big-endian)
                                    try:
                                        curve_size = struct.unpack('>I', segment_data[i:i+4])[0]
                                        # Validate: HDR gain curve size should be reasonable (e.g., < 1MB)
                                        if 0 < curve_size < 1048576:  # 1MB limit
                                            metadata['AROT:HDRGainCurveSize'] = curve_size
                                            metadata['AROT:Present'] = 'Yes'
                                            break
                                    except (struct.error, IndexError):
                                        continue
                            
                            # If we found AROT but not HDRGainCurveSize, still mark as present
                            if 'AROT:Present' not in metadata:
                                metadata['AROT:Present'] = 'Yes'
                                metadata['AROT:DataSize'] = len(segment_data)
                        except Exception:
                            # If parsing fails, still mark as present if AROT signature found
                            if b'AROT' in segment_data[:16]:
                                metadata['AROT:Present'] = 'Yes'
                                metadata['AROT:DataSize'] = len(segment_data)
                
                offset += length
            else:
                offset += 1
        
        return metadata
    
    def _add_file_tags_from_exif(self) -> None:
        """
        Add File tags that are derived from EXIF data or file structure.
        These standard format's File group tags that come from EXIF.
        """
        try:
            # CRITICAL: Fix incorrectly prefixed tags FIRST, before any other processing
            # Fix EXIF:File:ExifByteOrder -> File:ExifByteOrder
            if 'EXIF:File:ExifByteOrder' in self.metadata:
                byte_order_value = self.metadata['EXIF:File:ExifByteOrder']
                self.metadata['File:ExifByteOrder'] = byte_order_value
                del self.metadata['EXIF:File:ExifByteOrder']
            file_ext = self.file_path.suffix.lower()
            
            # File:BitsPerSample - from EXIF:BitsPerSample or default for JPEG
            if 'File:BitsPerSample' not in self.metadata:
                bits_per_sample = self.metadata.get('EXIF:BitsPerSample')
                if bits_per_sample:
                    if isinstance(bits_per_sample, (list, tuple)):
                        # Format as space-separated values, but File tag is typically single value
                        self.metadata['File:BitsPerSample'] = str(bits_per_sample[0]) if bits_per_sample else None
                    else:
                        self.metadata['File:BitsPerSample'] = str(bits_per_sample)
                elif file_ext in ('.jpg', '.jpeg'):
                    # JPEG files are typically 8 bits per sample
                    self.metadata['File:BitsPerSample'] = '8'
                elif file_ext == '.rw2':
                    # Panasonic RW2 files are typically 12 bits per sample
                    # This is a fallback if EXIF:BitsPerSample is not found in IFD
                    if 'EXIF:BitsPerSample' not in self.metadata:
                        self.metadata['EXIF:BitsPerSample'] = 12
                    self.metadata['File:BitsPerSample'] = '12'
            
            # File:ColorComponents - from EXIF:SamplesPerPixel or JPEG structure
            if 'File:ColorComponents' not in self.metadata:
                samples_per_pixel = self.metadata.get('EXIF:SamplesPerPixel')
                if samples_per_pixel:
                    self.metadata['File:ColorComponents'] = str(samples_per_pixel)
                elif file_ext in ('.jpg', '.jpeg'):
                    # JPEG files are typically 3 components (RGB) or 1 (grayscale)
                    # Check if it's grayscale by looking at SOF marker
                    try:
                        width, height = self._parse_jpeg_dimensions()
                        # For now, default to 3 (RGB) - could parse from SOF for accuracy
                        self.metadata['File:ColorComponents'] = '3'
                    except Exception:
                        pass
            
            # EXIF:FlashpixVersion - fallback for RAW files if not found in EXIF IFD
            # FlashpixVersion is typically "0100" (version 1.0) for most cameras
            # EXIF 3.0: FlashpixVersion is no longer mandatory
            # Only add default FlashpixVersion for EXIF 2.3 and earlier compatibility
            # For EXIF 3.0, FlashpixVersion is optional and should not be added automatically
            # Check if EXIF version is explicitly set to 2.3 or earlier
            exif_version = self.metadata.get('EXIF:ExifVersion', '0300')  # Default to 3.0
            if 'EXIF:FlashpixVersion' not in self.metadata:
                # Only add default FlashpixVersion for EXIF 2.3 and earlier
                if exif_version < '0300' and file_ext in ('.rw2', '.cr2', '.nef', '.arw', '.raf', '.orf', '.pef', '.x3f', '.mos', '.erf', '.srw', '.nrw', '.mrw', '.crw', '.3fr', '.mef', '.dng'):
                    # Most RAW formats use FlashPix version 1.0 (for EXIF 2.3 and earlier)
                    self.metadata['EXIF:FlashpixVersion'] = '0100'
            
            # File:EncodingProcess - from EXIF:Compression or JPEG structure
            if 'File:EncodingProcess' not in self.metadata and file_ext in ('.jpg', '.jpeg'):
                # JPEG uses "Baseline DCT, Huffman coding" for standard JPEG
                self.metadata['File:EncodingProcess'] = 'Baseline DCT, Huffman coding'
            
            # File:ExifByteOrder - from EXIF endianness
            # CRITICAL: Fix incorrectly prefixed tag FIRST (EXIF:File:ExifByteOrder -> File:ExifByteOrder)
            # This must happen before the check for File:ExifByteOrder
            if 'EXIF:File:ExifByteOrder' in self.metadata:
                byte_order_value = self.metadata['EXIF:File:ExifByteOrder']
                self.metadata['File:ExifByteOrder'] = byte_order_value
                del self.metadata['EXIF:File:ExifByteOrder']
            
            # Set File:ExifByteOrder if not already present (after fixing incorrectly prefixed version)
            if 'File:ExifByteOrder' not in self.metadata:
                # Try to get from _exif_parser first (most reliable)
                if self._exif_parser and hasattr(self._exif_parser, 'endian'):
                    if self._exif_parser.endian == '<':
                        self.metadata['File:ExifByteOrder'] = 'Little-endian (Intel, II)'
                    elif self._exif_parser.endian == '>':
                        self.metadata['File:ExifByteOrder'] = 'Big-endian (Motorola, MM)'
                # Fallback: Check if EXIF:ByteOrder exists and use it
                elif 'EXIF:ByteOrder' in self.metadata:
                    self.metadata['File:ExifByteOrder'] = self.metadata['EXIF:ByteOrder']
                # Fallback: Check if we have file_data and can read byte order from TIFF header
                elif hasattr(self, 'file_data') and self.file_data and len(self.file_data) >= 2:
                    if self.file_data[0:2] == b'II':
                        self.metadata['File:ExifByteOrder'] = 'Little-endian (Intel, II)'
                    elif self.file_data[0:2] == b'MM':
                        self.metadata['File:ExifByteOrder'] = 'Big-endian (Motorola, MM)'
                # Final fallback: Try to read from file if file_path is available
                elif self.file_path:
                    try:
                        with open(self.file_path, 'rb') as f:
                            header = f.read(2)
                            if header == b'II':
                                self.metadata['File:ExifByteOrder'] = 'Little-endian (Intel, II)'
                            elif header == b'MM':
                                self.metadata['File:ExifByteOrder'] = 'Big-endian (Motorola, MM)'
                    except:
                        pass
            
            # File:YCbCrSubSampling - from EXIF:YCbCrSubSampling or JPEG structure
            if 'File:YCbCrSubSampling' not in self.metadata:
                # Check for YCbCrSubSampling in various possible locations
                ycbcr_subsampling = (self.metadata.get('EXIF:YCbCrSubSampling') or 
                                    self.metadata.get('YCbCrSubSampling') or
                                    self.metadata.get('IFD0:YCbCrSubSampling'))
                if ycbcr_subsampling:
                    if isinstance(ycbcr_subsampling, (list, tuple)) and len(ycbcr_subsampling) >= 2:
                        # Format as "YCbCr4:2:0 (2 2)" or similar
                        h, v = ycbcr_subsampling[0], ycbcr_subsampling[1]
                        if h == 2 and v == 2:
                            self.metadata['File:YCbCrSubSampling'] = 'YCbCr4:2:0 (2 2)'
                        elif h == 2 and v == 1:
                            self.metadata['File:YCbCrSubSampling'] = 'YCbCr4:2:2 (2 1)'
                        elif h == 1 and v == 1:
                            self.metadata['File:YCbCrSubSampling'] = 'YCbCr4:4:4 (1 1)'
                        else:
                            self.metadata['File:YCbCrSubSampling'] = f'YCbCr ({h} {v})'
                    else:
                        self.metadata['File:YCbCrSubSampling'] = str(ycbcr_subsampling)
                elif file_ext in ('.jpg', '.jpeg'):
                    # Try to extract YCbCrSubSampling from JPEG SOF segment
                    ycbcr_from_sof = self._extract_ycbcr_subsampling_from_jpeg()
                    if ycbcr_from_sof:
                        self.metadata['File:YCbCrSubSampling'] = ycbcr_from_sof
                    else:
                        # Default JPEG subsampling is typically 4:2:0
                        self.metadata['File:YCbCrSubSampling'] = 'YCbCr4:2:0 (2 2)'
            
            # IMPROVEMENT (Build 1281): Copy FocalPlane tags and BatteryLevel from MakerNotes to EXIF namespace
            # For DCR files, these tags are extracted from MakerNotes IFD but Standard format shows them with EXIF: prefix
            # This ensures they standard format's output format
            focal_plane_tags = ['FocalPlaneXResolution', 'FocalPlaneYResolution', 'FocalPlaneResolutionUnit']
            for tag_name in focal_plane_tags:
                maker_tag = f'MakerNotes:{tag_name}'
                exif_tag = f'EXIF:{tag_name}'
                if maker_tag in self.metadata and exif_tag not in self.metadata:
                    # Copy from MakerNotes to EXIF namespace
                    self.metadata[exif_tag] = self.metadata[maker_tag]
            
            # BatteryLevel: Check both BatteryLevel and BatteryVoltage in MakerNotes
            if 'EXIF:BatteryLevel' not in self.metadata:
                battery_level = (self.metadata.get('MakerNotes:BatteryLevel') or 
                               self.metadata.get('MakerNotes:BatteryVoltage'))
                if battery_level is not None:
                    # Copy to EXIF namespace
                    self.metadata['EXIF:BatteryLevel'] = battery_level
        except Exception:
            pass  # File tags from EXIF are optional
    
    def _add_composite_tags(self) -> None:
        """
        Add Composite tags (calculated/derived tags) to metadata.
        These tags standard format's Composite group tags.
        """
        try:
            # Add aliases for ExifImageWidth/ExifImageHeight (Standard format shows these as aliases for PixelXDimension/PixelYDimension)
            if 'EXIF:PixelXDimension' in self.metadata and 'EXIF:ExifImageWidth' not in self.metadata:
                self.metadata['EXIF:ExifImageWidth'] = self.metadata['EXIF:PixelXDimension']
            if 'EXIF:PixelYDimension' in self.metadata and 'EXIF:ExifImageHeight' not in self.metadata:
                self.metadata['EXIF:ExifImageHeight'] = self.metadata['EXIF:PixelYDimension']
            
            # For JPEG files, update File:ImageWidth/ImageHeight from EXIF dimensions if available
            # This fixes cases where _add_file_tags set them from SOF before EXIF was parsed
            file_ext = self.file_path.suffix.lower()
            if file_ext in ('.jpg', '.jpeg', '.jfif', '.jpe'):
                exif_width = (self.metadata.get('EXIF:ExifImageWidth') or 
                             self.metadata.get('EXIF:PixelXDimension') or 
                             self.metadata.get('EXIF:ImageWidth'))
                exif_height = (self.metadata.get('EXIF:ExifImageHeight') or 
                              self.metadata.get('EXIF:PixelYDimension') or 
                              self.metadata.get('EXIF:ImageHeight') or 
                              self.metadata.get('EXIF:ImageLength'))
                
                if exif_width and exif_height:
                    # Handle tuple/list values
                    if isinstance(exif_width, (list, tuple)) and len(exif_width) > 0:
                        exif_width = exif_width[0]
                    if isinstance(exif_height, (list, tuple)) and len(exif_height) > 0:
                        exif_height = exif_height[0]
                    # Update File:ImageWidth/ImageHeight from EXIF dimensions (standard format behavior)
                    self.metadata['File:ImageWidth'] = int(exif_width)
                    self.metadata['File:ImageHeight'] = int(exif_height)
            
            # Get image dimensions
            width = None
            height = None
            
            # Try various sources for width/height (File tags first, then EXIF, then others)
            width_tags = [
                'File:ImageWidth',  # File tags take precedence
                'EXIF:ImageWidth', 'EXIF:ExifImageWidth', 'EXIF:PixelXDimension', 'ImageWidth',
                'EXIF:ImageLength', 'BMP:ImageWidth', 'PSD:ImageWidth',
                'PNG:ImageWidth', 'TGA:Width', 'PCX:Width', 'SVG:Width',
                'ICO:ImageWidth'  # ICO format
            ]
            height_tags = [
                'File:ImageHeight',  # File tags take precedence
                'EXIF:ImageHeight', 'EXIF:ExifImageHeight', 'EXIF:PixelYDimension', 'ImageHeight',
                'EXIF:ImageLength', 'BMP:ImageHeight', 'PSD:ImageHeight',
                'PNG:ImageHeight', 'TGA:Height', 'PCX:Height', 'SVG:Height',
                'ICO:ImageHeight'  # ICO format
            ]
            
            for tag in width_tags:
                if tag in self.metadata:
                    try:
                        val = self.metadata[tag]
                        # Handle formatted values (might be strings)
                        if isinstance(val, str):
                            # Try to extract number from formatted string
                            import re
                            match = re.search(r'\d+', val)
                            if match:
                                width = int(match.group())
                        elif isinstance(val, tuple) and len(val) == 2:
                            # Rational number
                            width = int(val[0] / val[1]) if val[1] != 0 else int(val[0])
                        elif isinstance(val, (list, tuple)):
                            # List - take first value
                            width = int(val[0]) if val else None
                        else:
                            width = int(val)
                        if width:
                            break
                    except (ValueError, TypeError, ZeroDivisionError):
                        continue
            
            for tag in height_tags:
                if tag in self.metadata:
                    try:
                        val = self.metadata[tag]
                        if isinstance(val, str):
                            import re
                            match = re.search(r'\d+', val)
                            if match:
                                height = int(match.group())
                        elif isinstance(val, tuple) and len(val) == 2:
                            # Rational number
                            height = int(val[0] / val[1]) if val[1] != 0 else int(val[0])
                        elif isinstance(val, (list, tuple)):
                            # List - take first value
                            height = int(val[0]) if val else None
                        else:
                            height = int(val)
                        if height:
                            break
                    except (ValueError, TypeError, ZeroDivisionError):
                        continue
            
            # Composite:ImageSize (format: "WxH")
            # Composite:ImageWidth and Composite:ImageHeight (individual values)
            if width is not None and height is not None:
                self.metadata['Composite:ImageSize'] = f"{width}x{height}"
                self.metadata['Composite:ImageWidth'] = width
                self.metadata['Composite:ImageHeight'] = height
                
                # Composite:Megapixels
                megapixels = (width * height) / 1000000.0
                # Format to standard format:
                # - For values >= 1: integer if whole, otherwise 1 decimal place
                # - For values < 1: 3 decimals by default, but use higher precision
                #   for extremely small images (e.g., 16x16 icons -> 0.000256 MP)
                if megapixels >= 1.0:
                    if megapixels == int(megapixels):
                        self.metadata['Composite:Megapixels'] = f"{int(megapixels)}"
                    else:
                        self.metadata['Composite:Megapixels'] = f"{megapixels:.1f}"
                else:
                    if megapixels < 0.001:
                        # Tiny images: keep up to 6 decimals so values like 0.000256
                        # are not rounded down to 0.000
                        formatted = f"{megapixels:.6f}".rstrip('0').rstrip('.')
                    else:
                        # For values between 0.001 and 1.0, use 3 decimal places
                        # Standard format shows 0.518 (3 decimals) for 960x540 video
                        rounded_mp = round(megapixels, 3)
                        formatted = f"{rounded_mp:.3f}"
                        # For values like 0.518, keep all 3 decimals (don't strip trailing zeros)
                        # Only strip if the value is exactly a whole number
                        if formatted.endswith('.000'):
                            formatted = f"{int(rounded_mp)}"
                    self.metadata['Composite:Megapixels'] = formatted
            
            # EXIF:ISO (alias from EXIF:ISOSpeedRatings if ISO is missing)
            if 'EXIF:ISO' not in self.metadata:
                iso = self.metadata.get('EXIF:ISOSpeedRatings')
                if iso is not None:
                    try:
                        if isinstance(iso, (list, tuple)):
                            iso = iso[0] if iso else None
                        if iso is not None:
                            self.metadata['EXIF:ISO'] = str(int(iso))
                    except (ValueError, TypeError):
                        pass
            
            # Composite:ISO (from EXIF:ISO or EXIF:ISOSpeedRatings)
            if 'Composite:ISO' not in self.metadata:
                iso = self.metadata.get('EXIF:ISO') or self.metadata.get('EXIF:ISOSpeedRatings')
                if iso is not None:
                    try:
                        if isinstance(iso, (list, tuple)):
                            iso = iso[0] if iso else None
                        if iso is not None:
                            self.metadata['Composite:ISO'] = str(int(iso))
                    except (ValueError, TypeError):
                        pass
            
            # EXIF:ModifyDate (alias from EXIF:DateTime if ModifyDate is missing)
            if 'EXIF:ModifyDate' not in self.metadata:
                modify_date = self.metadata.get('EXIF:DateTime')
                if modify_date:
                    self.metadata['EXIF:ModifyDate'] = modify_date
            
            # EXIF:RawDataUniqueID (from OpcodeList3 in IFD1 for 3FR files, or from tag 0x82B0)
            if 'EXIF:RawDataUniqueID' not in self.metadata:
                # Check if we have OpcodeList3 in IFD1 (3FR format stores RawDataUniqueID here)
                opcode_list3 = self.metadata.get('IFD1:OpcodeList3')
                if opcode_list3 and isinstance(opcode_list3, list):
                    # Convert list of byte values to hex string
                    try:
                        hex_str = ''.join(f'{b:02X}' for b in opcode_list3)
                        self.metadata['EXIF:RawDataUniqueID'] = hex_str
                    except (ValueError, TypeError):
                        pass
                # Also check for tag 0x82B0 (RawDataUniqueID) if it exists but wasn't formatted correctly
                raw_data_id = self.metadata.get('EXIF:RawDataUniqueID')
                if raw_data_id and isinstance(raw_data_id, (list, tuple, bytes)):
                    try:
                        if isinstance(raw_data_id, bytes):
                            hex_str = raw_data_id.hex().upper()
                        elif isinstance(raw_data_id, (list, tuple)):
                            hex_str = ''.join(f'{b:02X}' for b in raw_data_id)
                        else:
                            hex_str = str(raw_data_id)
                        self.metadata['EXIF:RawDataUniqueID'] = hex_str
                    except (ValueError, TypeError):
                        pass
            
            # EXIF:ThumbnailTIFF (extract from IFD1 thumbnail data)
            if 'EXIF:ThumbnailTIFF' not in self.metadata:
                # Check if we have IFD1 thumbnail data
                strip_offset = self.metadata.get('IFD1:StripOffsets')
                strip_byte_counts = self.metadata.get('IFD1:StripByteCounts')
                if strip_offset and strip_byte_counts:
                    try:
                        # Read thumbnail data from file
                        with open(str(self.file_path), 'rb') as f:
                            file_size = f.seek(0, 2)
                            f.seek(0)
                            
                            # Handle both single values and lists
                            if isinstance(strip_offset, (list, tuple)):
                                offset = int(strip_offset[0]) if strip_offset else 0
                            else:
                                offset = int(strip_offset)
                            
                            if isinstance(strip_byte_counts, (list, tuple)):
                                length = int(strip_byte_counts[0]) if strip_byte_counts else 0
                            else:
                                length = int(strip_byte_counts)
                            
                            if offset > 0 and length > 0 and offset + length <= file_size:
                                # For 3FR and some formats, standard format includes the entire thumbnail TIFF structure
                                # which may include IFD headers and padding. Try to find the TIFF header start.
                                # Search backwards from strip offset for TIFF header (II 2A 00 or MM 00 2A)
                                thumbnail_start = offset
                                search_start = max(0, offset - 300)
                                f.seek(search_start)
                                search_data = f.read(min(300, offset - search_start))
                                
                                # Look for TIFF header (little-endian: II 2A 00)
                                for i in range(len(search_data) - 8, -1, -1):
                                    if (search_data[i:i+2] == b'II' and search_data[i+2] == 0x2A and 
                                        search_data[i+3] == 0x00):
                                        # Found TIFF header
                                        thumbnail_start = search_start + i
                                        # Recalculate size from header to end of strip data
                                        length = (offset + length) - thumbnail_start
                                        break
                                
                                f.seek(thumbnail_start)
                                thumbnail_data = f.read(length)
                                if thumbnail_data:
                                    # Standard format shows this as binary data with size
                                    # Store as a marker that thumbnail exists (full binary data would be too large)
                                    self.metadata['EXIF:ThumbnailTIFF'] = f"(Binary data {len(thumbnail_data)} bytes, use -b option to extract)"
                    except (IOError, ValueError, IndexError):
                        pass
            
            # Composite:FocalLength35efl (35mm equivalent focal length)
            # standard format: "17.0 mm (35 mm equivalent: 26.7 mm)" when both are available
            # Or just "26.7 mm" when only 35mm equivalent is available
            if 'Composite:FocalLength35efl' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                focal_length_35 = self.metadata.get('EXIF:FocalLengthIn35mmFilm')
                
                # Handle case where focal length is 0 (unknown) - Standard format shows "0.0 mm"
                if focal_length and isinstance(focal_length, tuple) and len(focal_length) == 2:
                    if focal_length[0] == 0 or focal_length[1] == 0:
                        # Focal length is 0 or invalid - set to "0.0 mm" to standard format
                        self.metadata['Composite:FocalLength35efl'] = "0.0 mm"
                        focal_length = None  # Don't process further
                
                if focal_length_35:
                    try:
                        if isinstance(focal_length_35, (list, tuple)):
                            focal_length_35 = focal_length_35[0]
                        if isinstance(focal_length_35, str):
                            # Extract number from formatted string
                            import re
                            match = re.search(r'[\d.]+', focal_length_35)
                            if match:
                                fl35 = float(match.group())
                                # standard format: "X.X mm (35 mm equivalent: Y.Y mm)" if we have both
                                # Or just "Y.Y mm" if we only have 35mm equivalent
                                if focal_length:
                                    # Extract actual focal length
                                    if isinstance(focal_length, tuple) and len(focal_length) == 2:
                                        fl_actual = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                                    elif isinstance(focal_length, str):
                                        fl_match = re.search(r'[\d.]+', focal_length)
                                        fl_actual = float(fl_match.group()) if fl_match else fl35
                                    else:
                                        fl_actual = float(focal_length)
                                    # Format as "X.X mm (35 mm equivalent: Y.Y mm)"
                                    self.metadata['Composite:FocalLength35efl'] = f"{fl_actual:.1f} mm (35 mm equivalent: {fl35:.1f} mm)"
                                else:
                                    self.metadata['Composite:FocalLength35efl'] = f"{fl35:.1f} mm"
                        else:
                            fl35 = float(focal_length_35)
                            # standard format: "X.X mm (35 mm equivalent: Y.Y mm)" if we have both
                            if focal_length:
                                # Extract actual focal length
                                if isinstance(focal_length, tuple) and len(focal_length) == 2:
                                    fl_actual = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                                elif isinstance(focal_length, str):
                                    import re
                                    fl_match = re.search(r'[\d.]+', focal_length)
                                    fl_actual = float(fl_match.group()) if fl_match else fl35
                                else:
                                    fl_actual = float(focal_length)
                                # Format as "X.X mm (35 mm equivalent: Y.Y mm)"
                                self.metadata['Composite:FocalLength35efl'] = f"{fl_actual:.1f} mm (35 mm equivalent: {fl35:.1f} mm)"
                            else:
                                self.metadata['Composite:FocalLength35efl'] = f"{fl35:.1f} mm"
                    except (ValueError, TypeError):
                        pass
                elif focal_length:
                    # If FocalLengthIn35mmFilm is not available, try to calculate from ScaleFactor35efl
                    # standard format calculates 35mm equivalent from focal length * scale factor
                    scale_factor = self.metadata.get('Composite:ScaleFactor35efl')
                    try:
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            import re
                            match = re.search(r'[\d.]+', focal_length)
                            if match:
                                fl = float(match.group())
                            else:
                                fl = None
                        else:
                            fl = float(focal_length)
                        
                        if fl and fl > 0:
                            if scale_factor:
                                # Calculate 35mm equivalent from scale factor
                                try:
                                    sf = float(str(scale_factor))
                                    if sf > 0:
                                        fl35 = fl * sf
                                        # Format as "X.X mm (35 mm equivalent: Y.Y mm)" to standard format
                                        self.metadata['Composite:FocalLength35efl'] = f"{fl:.1f} mm (35 mm equivalent: {fl35:.1f} mm)"
                                    else:
                                        # Scale factor invalid, just show focal length
                                        self.metadata['Composite:FocalLength35efl'] = f"{fl:.1f} mm"
                                except (ValueError, TypeError):
                                    # Scale factor parsing failed, just show focal length
                                    self.metadata['Composite:FocalLength35efl'] = f"{fl:.1f} mm"
                            else:
                                # No scale factor available, just show focal length
                                self.metadata['Composite:FocalLength35efl'] = f"{fl:.1f} mm"
                    except (ValueError, TypeError):
                        pass
            
            # Composite:ScaleFactor35efl (crop factor)
            if 'Composite:ScaleFactor35efl' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                focal_length_35 = self.metadata.get('EXIF:FocalLengthIn35mmFilm')
                
                # Fallback: try to extract from Composite:FocalLength35efl if available
                if not focal_length_35:
                    focal_length_35efl_str = self.metadata.get('Composite:FocalLength35efl')
                    if focal_length_35efl_str:
                        # Extract 35mm equivalent from string like "17.0 mm (35 mm equivalent: 26.7 mm)"
                        import re
                        match = re.search(r'\(35 mm equivalent:\s*([\d.]+)', str(focal_length_35efl_str))
                        if match:
                            try:
                                focal_length_35 = float(match.group(1))
                            except (ValueError, TypeError):
                                pass
                
                # Calculate from focal lengths if available
                if focal_length and focal_length_35:
                    try:
                        # Calculate scale factor
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            import re
                            match = re.search(r'[\d.]+', focal_length)
                            fl = float(match.group()) if match else 0
                        else:
                            fl = float(focal_length)
                        
                        if isinstance(focal_length_35, tuple) and len(focal_length_35) == 2:
                            fl35 = focal_length_35[0] / focal_length_35[1] if focal_length_35[1] != 0 else 0
                        elif isinstance(focal_length_35, str):
                            import re
                            match = re.search(r'[\d.]+', focal_length_35)
                            fl35 = float(match.group()) if match else 0
                        else:
                            fl35 = float(focal_length_35)
                        
                        if fl > 0:
                            scale_factor = fl35 / fl
                            # Standard format shows ScaleFactor35efl with 1 decimal place (e.g., "1.7" not "1.686746987951807")
                            self.metadata['Composite:ScaleFactor35efl'] = f"{scale_factor:.1f}"
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                
                # Fallback: Calculate from sensor dimensions if focal lengths not available
                # NOTE: This calculation is moved to the final block at the end of _add_composite_tags
                # to ensure it runs after all other composite tags and can recalculate if needed
                # The first calculation block is disabled to prevent incorrect values from being set
                pass  # Calculation moved to final block
            
            # Composite:Aperture (from EXIF:FNumber)
            if 'Composite:Aperture' not in self.metadata:
                fnumber = self.metadata.get('EXIF:FNumber')
                if fnumber is not None:
                    try:
                        if isinstance(fnumber, tuple) and len(fnumber) == 2:
                            aperture = fnumber[0] / fnumber[1] if fnumber[1] != 0 else 0
                        elif isinstance(fnumber, str):
                            # Extract number from formatted string like "f/2.8"
                            import re
                            match = re.search(r'[\d.]+', fnumber)
                            if match:
                                aperture = float(match.group())
                            else:
                                aperture = None
                        else:
                            aperture = float(fnumber)
                        
                        if aperture and aperture > 0:
                            # Standard format shows Composite:Aperture with 1 decimal place (e.g., "8.0" not "8")
                            # Always format with 1 decimal place to standard format
                            self.metadata['Composite:Aperture'] = f"{aperture:.1f}"
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
            
            # Composite:BlueBalance (from WB_RGGBLevels, WB RGB Levels, or EXIF WB Levels)
            if 'Composite:BlueBalance' not in self.metadata:
                blue_balance_calculated = False
                # IMPROVEMENT (Build 1258): Enhanced WB_RGGBLevels lookup - check multiple tag name variations
                # Check for RGGB format (4 values) first
                wb_rggb = (self.metadata.get('Composite:WB_RGGBLevels') or 
                           self.metadata.get('MakerNotes:WB_RGGBLevels') or
                           self.metadata.get('EXIF:WB_RGGBLevels'))
                if wb_rggb and isinstance(wb_rggb, str) and wb_rggb.strip() != 'Auto':
                    # Only try WB_RGGBLevels if it's not "Auto" (which is not numeric)
                    try:
                        if isinstance(wb_rggb, str):
                            # Parse "1621 1024 1024 2427" format
                            parts = wb_rggb.split()
                            if len(parts) >= 4:
                                r = float(parts[0])
                                g1 = float(parts[1])
                                g2 = float(parts[2])
                                b = float(parts[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                        elif isinstance(wb_rggb, (list, tuple)) and len(wb_rggb) >= 4:
                            r = float(wb_rggb[0])
                            g1 = float(wb_rggb[1])
                            g2 = float(wb_rggb[2])
                            b = float(wb_rggb[3])
                            g = (g1 + g2) / 2.0
                            if g > 0:
                                blue_balance = b / g
                                self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                blue_balance_calculated = True
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                
                # IMPROVEMENT (Build 1258): Enhanced RGB format support for Kodak DCR files
                # Check for RGB format (3 values) - Kodak uses RGB, not RGGB
                # IMPROVEMENT (Build 1260): Enhanced WB_RGBLevels lookup - check more namespace variations
                if not blue_balance_calculated:
                    wb_rgb = (self.metadata.get('MakerNotes:WB_RGBLevels') or
                              self.metadata.get('Kodak:WB_RGBLevels') or
                              self.metadata.get('EXIF:WB_RGBLevels') or
                              self.metadata.get('WB_RGBLevels') or
                              self.metadata.get('Composite:WB_RGBLevels'))
                    if wb_rgb and isinstance(wb_rgb, str) and wb_rgb.strip() != 'Auto':
                        try:
                            if isinstance(wb_rgb, str):
                                # Parse "R G B" format (Kodak RGB format)
                                parts = wb_rgb.split()
                                if len(parts) >= 3:
                                    r = float(parts[0])
                                    g = float(parts[1])
                                    b = float(parts[2])
                                    if g > 0:
                                        blue_balance = b / g
                                        self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                        blue_balance_calculated = True
                            elif isinstance(wb_rgb, (list, tuple)) and len(wb_rgb) >= 3:
                                r = float(wb_rgb[0])
                                g = float(wb_rgb[1])
                                b = float(wb_rgb[2])
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
            
                # Also try EXIF:WBBlueLevel and EXIF:WBGreenLevel (Panasonic RW2 format)
                # This fallback should work even if WB_RGGBLevels is "Auto" or doesn't exist
                if not blue_balance_calculated:
                    wb_blue = self.metadata.get('EXIF:WBBlueLevel') or self.metadata.get('MakerNotes:WBBlueLevel')
                    wb_green = self.metadata.get('EXIF:WBGreenLevel') or self.metadata.get('MakerNotes:WBGreenLevel')
                    # Check if both WB levels exist and are valid
                    if wb_blue is not None and wb_green is not None:
                        try:
                            # Convert to float - handle string values like "7", "16", "3"
                            blue_val = float(str(wb_blue).strip())
                            green_val = float(str(wb_green).strip())
                            if green_val > 0:
                                blue_balance = blue_val / green_val
                                self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            # Silently continue if calculation fails
                            pass
            
            # Composite:RedBalance (from WB_RGGBLevels, WB RGB Levels, or EXIF WB Levels)
            if 'Composite:RedBalance' not in self.metadata:
                red_balance_calculated = False
                # IMPROVEMENT (Build 1258): Enhanced WB_RGGBLevels lookup - check multiple tag name variations
                # Check for RGGB format (4 values) first
                wb_rggb = (self.metadata.get('Composite:WB_RGGBLevels') or 
                           self.metadata.get('MakerNotes:WB_RGGBLevels') or
                           self.metadata.get('EXIF:WB_RGGBLevels'))
                if wb_rggb and isinstance(wb_rggb, str) and wb_rggb.strip() != 'Auto':
                    # Only try WB_RGGBLevels if it's not "Auto" (which is not numeric)
                    try:
                        if isinstance(wb_rggb, str):
                            # Parse "1621 1024 1024 2427" format
                            parts = wb_rggb.split()
                            if len(parts) >= 4:
                                r = float(parts[0])
                                g1 = float(parts[1])
                                g2 = float(parts[2])
                                b = float(parts[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                        elif isinstance(wb_rggb, (list, tuple)) and len(wb_rggb) >= 4:
                            r = float(wb_rggb[0])
                            g1 = float(wb_rggb[1])
                            g2 = float(wb_rggb[2])
                            b = float(wb_rggb[3])
                            g = (g1 + g2) / 2.0
                            if g > 0:
                                red_balance = r / g
                                self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                red_balance_calculated = True
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                
                # IMPROVEMENT (Build 1258): Enhanced RGB format support for Kodak DCR files
                # Check for RGB format (3 values) - Kodak uses RGB, not RGGB
                # IMPROVEMENT (Build 1260): Enhanced WB_RGBLevels lookup - check more namespace variations
                if not red_balance_calculated:
                    wb_rgb = (self.metadata.get('MakerNotes:WB_RGBLevels') or
                              self.metadata.get('Kodak:WB_RGBLevels') or
                              self.metadata.get('EXIF:WB_RGBLevels') or
                              self.metadata.get('WB_RGBLevels') or
                              self.metadata.get('Composite:WB_RGBLevels'))
                    if wb_rgb and isinstance(wb_rgb, str) and wb_rgb.strip() != 'Auto':
                        try:
                            if isinstance(wb_rgb, str):
                                # Parse "R G B" format (Kodak RGB format)
                                parts = wb_rgb.split()
                                if len(parts) >= 3:
                                    r = float(parts[0])
                                    g = float(parts[1])
                                    b = float(parts[2])
                                    if g > 0:
                                        red_balance = r / g
                                        self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                        red_balance_calculated = True
                            elif isinstance(wb_rgb, (list, tuple)) and len(wb_rgb) >= 3:
                                r = float(wb_rgb[0])
                                g = float(wb_rgb[1])
                                b = float(wb_rgb[2])
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                
                # Also try EXIF:WBRedLevel and EXIF:WBGreenLevel (Panasonic RW2 format)
                # This fallback should work even if WB_RGGBLevels is "Auto" or doesn't exist
                if not red_balance_calculated:
                    wb_red = self.metadata.get('EXIF:WBRedLevel') or self.metadata.get('MakerNotes:WBRedLevel')
                    wb_green = self.metadata.get('EXIF:WBGreenLevel') or self.metadata.get('MakerNotes:WBGreenLevel')
                    # Check if both WB levels exist and are valid
                    if wb_red is not None and wb_green is not None:
                        try:
                            # Convert to float - handle string values like "7", "16", "3"
                            red_val = float(str(wb_red).strip())
                            green_val = float(str(wb_green).strip())
                            if green_val > 0:
                                red_balance = red_val / green_val
                                self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            # Silently continue if calculation fails
                            pass
            
            # Composite:CircleOfConfusion (calculated from sensor size or crop factor)
            if 'Composite:CircleOfConfusion' not in self.metadata:
                # Default CoC values based on sensor size (full frame = 0.030mm, APS-C = 0.019mm, etc.)
                # Try to determine from sensor dimensions or crop factor
                scale_factor = self.metadata.get('Composite:ScaleFactor35efl')
                if scale_factor:
                    try:
                        sf = float(scale_factor)
                        # CoC scales with crop factor (smaller sensor = smaller CoC)
                        # Full frame (1.0) = 0.030mm, APS-C (1.6) = 0.019mm, etc.
                        if sf >= 1.0:
                            coc = 0.030 / sf
                            self.metadata['Composite:CircleOfConfusion'] = f"{coc:.3f} mm"
                    except (ValueError, TypeError):
                        pass
                # Default to APS-C if no scale factor available
                if 'Composite:CircleOfConfusion' not in self.metadata:
                    self.metadata['Composite:CircleOfConfusion'] = "0.019 mm"
            
            # Composite:FOV (Field of View - calculated from focal length and sensor size)
            if 'Composite:FOV' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                scale_factor = self.metadata.get('Composite:ScaleFactor35efl')
                if focal_length and scale_factor:
                    try:
                        import math
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            import re
                            match = re.search(r'[\d.]+', focal_length)
                            fl = float(match.group()) if match else 0
                        else:
                            fl = float(focal_length)
                        
                        sf = float(scale_factor)
                        if fl > 0 and sf > 0:
                            # Sensor width = 36mm / scale_factor (full frame width / crop factor)
                            sensor_width_mm = 36.0 / sf
                            # FOV = 2 * arctan(sensor_width / (2 * focal_length)) * 180 / π
                            fov_rad = 2 * math.atan(sensor_width_mm / (2 * fl))
                            fov_deg = fov_rad * 180 / math.pi
                            self.metadata['Composite:FOV'] = f"{fov_deg:.1f} deg"
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
            
            # Composite:DOF (Depth of Field - calculated from focal length, aperture, focus distance, and CoC)
            if 'Composite:DOF' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                fnumber = self.metadata.get('EXIF:FNumber')
                coc_str = self.metadata.get('Composite:CircleOfConfusion', '0.019 mm')
                # Note: Focus distance is rarely in EXIF, so DOF calculation is often approximate
                try:
                    import math
                    import re
                    coc_value = float(re.search(r'[\d.]+', coc_str).group()) if re.search(r'[\d.]+', coc_str) else 0.019
                    
                    if focal_length and fnumber and coc_value > 0:
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            match = re.search(r'[\d.]+', focal_length)
                            fl = float(match.group()) if match else 0
                        else:
                            fl = float(focal_length)
                        
                        if isinstance(fnumber, tuple) and len(fnumber) == 2:
                            f = fnumber[0] / fnumber[1] if fnumber[1] != 0 else 0
                        elif isinstance(fnumber, str):
                            match = re.search(r'[\d.]+', fnumber)
                            f = float(match.group()) if match else 0
                        else:
                            f = float(fnumber)
                        
                        if fl > 0 and f > 0:
                            # Hyperfocal distance = (focal_length^2) / (f_number * circle_of_confusion)
                            hyperfocal_mm = (fl * fl) / (f * coc_value)
                            # Without focus distance, we can't calculate exact DOF, but we can indicate infinity
                            self.metadata['Composite:DOF'] = f"inf (0.00 m - inf)"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Composite:HyperfocalDistance (calculated from focal length, aperture, and CoC)
            if 'Composite:HyperfocalDistance' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                fnumber = self.metadata.get('EXIF:FNumber')
                coc_str = self.metadata.get('Composite:CircleOfConfusion', '0.019 mm')
                try:
                    import math
                    import re
                    coc_value = float(re.search(r'[\d.]+', coc_str).group()) if re.search(r'[\d.]+', coc_str) else 0.019
                    
                    if focal_length and fnumber and coc_value > 0:
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            match = re.search(r'[\d.]+', focal_length)
                            fl = float(match.group()) if match else 0
                        else:
                            fl = float(focal_length)
                        
                        if isinstance(fnumber, tuple) and len(fnumber) == 2:
                            f = fnumber[0] / fnumber[1] if fnumber[1] != 0 else 0
                        elif isinstance(fnumber, str):
                            match = re.search(r'[\d.]+', fnumber)
                            f = float(match.group()) if match else 0
                        else:
                            f = float(fnumber)
                        
                        if fl > 0 and f > 0:
                            # Hyperfocal distance = (focal_length^2) / (f_number * circle_of_confusion)
                            # Result is in mm, convert to meters
                            hyperfocal_mm = (fl * fl) / (f * coc_value)
                            hyperfocal_m = hyperfocal_mm / 1000.0
                            self.metadata['Composite:HyperfocalDistance'] = f"{hyperfocal_m:.2f} m"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Composite:FOV (Field Of View - calculated from focal length and sensor size)
            # NOTE: FOV calculation is done in the final block after ScaleFactor35efl is calculated
            # to ensure ScaleFactor35efl is available when needed
            
            # Composite:LightValue (calculated from aperture, shutter speed, and ISO)
            if 'Composite:LightValue' not in self.metadata:
                # IMPROVEMENT (Build 1260): Enhanced LightValue calculation - check multiple tag name variations
                # IMPROVEMENT (Build 1261): Also check MakerNotes namespace for aperture, exposure time, and ISO
                # IMPROVEMENT (Build 1281): Also check Kodak namespace for DCR files
                fnumber = (self.metadata.get('EXIF:FNumber') or 
                          self.metadata.get('EXIF:ApertureValue') or
                          self.metadata.get('EXIF:MaxApertureValue') or
                          self.metadata.get('FNumber') or
                          self.metadata.get('ApertureValue') or
                          self.metadata.get('MakerNotes:FNumber') or
                          self.metadata.get('MakerNotes:ApertureValue') or
                          self.metadata.get('Kodak:FNumber') or
                          self.metadata.get('Kodak:ApertureValue') or
                          self.metadata.get('Kodak:Aperture'))
                exposure_time = (self.metadata.get('EXIF:ExposureTime') or
                               self.metadata.get('EXIF:ShutterSpeedValue') or
                               self.metadata.get('ExposureTime') or
                               self.metadata.get('ShutterSpeedValue') or
                               self.metadata.get('MakerNotes:ExposureTime') or
                               self.metadata.get('MakerNotes:ShutterSpeed') or
                               self.metadata.get('Kodak:ExposureTime') or
                               self.metadata.get('Kodak:ShutterSpeed'))
                iso = (self.metadata.get('EXIF:ISO') or 
                      self.metadata.get('EXIF:ISOSpeedRatings') or
                      self.metadata.get('EXIF:ISOValue') or
                      self.metadata.get('ISO') or
                      self.metadata.get('ISOSpeedRatings') or
                      self.metadata.get('MakerNotes:ISO') or
                      self.metadata.get('MakerNotes:ISOSpeedRatings') or
                      self.metadata.get('MakerNotes:BaseISO') or  # IMPROVEMENT (Build 1282): Use BaseISO as ISO fallback for DCR files
                      self.metadata.get('MakerNotes:AnalogCaptureISO') or  # IMPROVEMENT (Build 1282): Use AnalogCaptureISO as ISO fallback
                      self.metadata.get('Kodak:ISO') or
                      self.metadata.get('Kodak:ISOSpeedRatings') or
                      self.metadata.get('Kodak:BaseISO') or  # IMPROVEMENT (Build 1282): Use Kodak:BaseISO as ISO fallback
                      self.metadata.get('Kodak:AnalogCaptureISO') or  # IMPROVEMENT (Build 1282): Use Kodak:AnalogCaptureISO as ISO fallback
                      self.metadata.get('EXIF:ExposureIndex'))  # IMPROVEMENT (Build 1282): Use ExposureIndex as ISO fallback (common in DCR files)
                try:
                    import math
                    import re
                    if fnumber and exposure_time and iso:
                        if isinstance(fnumber, tuple) and len(fnumber) == 2:
                            f = fnumber[0] / fnumber[1] if fnumber[1] != 0 else 0
                        elif isinstance(fnumber, str):
                            match = re.search(r'[\d.]+', fnumber)
                            f = float(match.group()) if match else 0
                        else:
                            f = float(fnumber)
                        
                        if isinstance(exposure_time, tuple) and len(exposure_time) == 2:
                            t = exposure_time[0] / exposure_time[1] if exposure_time[1] != 0 else 0
                        elif isinstance(exposure_time, str):
                            # Handle "1/20" format
                            if '/' in exposure_time:
                                parts = exposure_time.split('/')
                                if len(parts) == 2:
                                    t = float(parts[0]) / float(parts[1])
                                else:
                                    t = 0
                            else:
                                match = re.search(r'[\d.]+', exposure_time)
                                t = float(match.group()) if match else 0
                        else:
                            t = float(exposure_time)
                        
                        if isinstance(iso, (list, tuple)):
                            # Handle RATIONAL format (e.g., [16000, 100] = 160)
                            if len(iso) == 2:
                                iso_val = float(iso[0]) / float(iso[1]) if iso[1] != 0 else 0
                            else:
                                iso_val = float(iso[0]) if iso else 0
                        elif isinstance(iso, str):
                            # Handle "16000 100" format (RATIONAL as string)
                            if ' ' in iso:
                                parts = iso.split()
                                if len(parts) >= 2:
                                    try:
                                        iso_val = float(parts[0]) / float(parts[1]) if float(parts[1]) != 0 else 0
                                    except (ValueError, ZeroDivisionError):
                                        # Try to extract just the first number
                                        match = re.search(r'[\d.]+', iso)
                                        iso_val = float(match.group()) if match else 0
                                else:
                                    match = re.search(r'[\d.]+', iso)
                                    iso_val = float(match.group()) if match else 0
                            else:
                                match = re.search(r'[\d.]+', iso)
                                iso_val = float(match.group()) if match else 0
                        else:
                            iso_val = float(iso)
                        
                        if f > 0 and t > 0 and iso_val > 0:
                            # Light Value (LV) = log2((f^2) / t) - log2(ISO/100)
                            # Simplified: LV = log2(f^2 / t) - log2(ISO/100)
                            lv = math.log2((f * f) / t) - math.log2(iso_val / 100.0)
                            # Standard format shows LightValue with 1 decimal place (e.g., "14.8" not "14.78")
                            self.metadata['Composite:LightValue'] = f"{lv:.1f}"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Composite:ShutterSpeed (from EXIF:ExposureTime or DICOM:ExposureTime)
            if 'Composite:ShutterSpeed' not in self.metadata:
                # Check EXIF first, then DICOM
                exposure_time = self.metadata.get('EXIF:ExposureTime') or self.metadata.get('DICOM:ExposureTime')
                is_dicom = 'DICOM:ExposureTime' in self.metadata
                
                if exposure_time is not None:
                    try:
                        if isinstance(exposure_time, tuple) and len(exposure_time) == 2:
                            exp_time = exposure_time[0] / exposure_time[1] if exposure_time[1] != 0 else 0
                        elif isinstance(exposure_time, str):
                            # Extract number from formatted string
                            import re
                            match = re.search(r'[\d.]+', exposure_time)
                            if match:
                                exp_time = float(match.group())
                            else:
                                exp_time = None
                        else:
                            exp_time = float(exposure_time)
                        
                        if exp_time and exp_time > 0:
                            # For DICOM files, Standard format shows raw value (e.g., "1601" not "1/1601" or "1601 s")
                            if is_dicom:
                                # DICOM ExposureTime is in milliseconds, Standard format shows it as-is
                                if exp_time == int(exp_time):
                                    self.metadata['Composite:ShutterSpeed'] = str(int(exp_time))
                                else:
                                    self.metadata['Composite:ShutterSpeed'] = str(exp_time)
                            else:
                                # For EXIF files, format as "1/X" for fast speeds, or "X s" for slow speeds
                                if exp_time < 1.0:
                                    shutter_speed = 1.0 / exp_time
                                    if shutter_speed == int(shutter_speed):
                                        self.metadata['Composite:ShutterSpeed'] = f"1/{int(shutter_speed)}"
                                    else:
                                        # Round to nearest reasonable fraction
                                        self.metadata['Composite:ShutterSpeed'] = f"1/{int(round(shutter_speed))}"
                                else:
                                    # For slow speeds, show as seconds
                                    if exp_time == int(exp_time):
                                        self.metadata['Composite:ShutterSpeed'] = f"{int(exp_time)} s"
                                    else:
                                        self.metadata['Composite:ShutterSpeed'] = f"{exp_time:.2f} s"
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
            
            # Composite:GPSPosition (from GPS:GPSLatitude and GPS:GPSLongitude)
            if 'Composite:GPSPosition' not in self.metadata:
                gps_lat = self.metadata.get('GPS:GPSLatitude')
                gps_lon = self.metadata.get('GPS:GPSLongitude')
                gps_alt = self.metadata.get('GPS:GPSAltitude')
                
                if gps_lat is not None and gps_lon is not None:
                    try:
                        # Extract numeric values from GPS coordinates
                        import re
                        
                        # Handle tuple format (degrees, minutes, seconds)
                        if isinstance(gps_lat, tuple) and len(gps_lat) == 3:
                            lat_deg = float(gps_lat[0]) + float(gps_lat[1])/60.0 + float(gps_lat[2])/3600.0
                        elif isinstance(gps_lat, str):
                            # Extract number from string like "37.7749 deg" or "37° 46' 29.64\" N"
                            match = re.search(r'([\d.]+)', str(gps_lat))
                            lat_deg = float(match.group(1)) if match else None
                        else:
                            lat_deg = float(gps_lat)
                        
                        if isinstance(gps_lon, tuple) and len(gps_lon) == 3:
                            lon_deg = float(gps_lon[0]) + float(gps_lon[1])/60.0 + float(gps_lon[2])/3600.0
                        elif isinstance(gps_lon, str):
                            match = re.search(r'([\d.]+)', str(gps_lon))
                            lon_deg = float(match.group(1)) if match else None
                        else:
                            lon_deg = float(gps_lon)
                        
                        if lat_deg is not None and lon_deg is not None:
                            # Check for hemisphere indicators (N/S, E/W)
                            lat_ref = self.metadata.get('GPS:GPSLatitudeRef', '')
                            lon_ref = self.metadata.get('GPS:GPSLongitudeRef', '')
                            
                            # Apply hemisphere sign
                            if lat_ref.upper() == 'S':
                                lat_deg = -lat_deg
                            if lon_ref.upper() == 'W':
                                lon_deg = -lon_deg
                            
                            # Format as "lat, lon" or "lat, lon (altitude)" if altitude is available
                            if gps_alt is not None:
                                # Extract altitude value
                                if isinstance(gps_alt, tuple) and len(gps_alt) == 2:
                                    alt_val = float(gps_alt[0]) / float(gps_alt[1]) if gps_alt[1] != 0 else 0
                                elif isinstance(gps_alt, str):
                                    match = re.search(r'([\d.]+)', str(gps_alt))
                                    alt_val = float(match.group(1)) if match else 0
                                else:
                                    alt_val = float(gps_alt)
                                
                                # Format with altitude: "lat, lon (altitude m)"
                                self.metadata['Composite:GPSPosition'] = f"{lat_deg:.6f}, {lon_deg:.6f} ({alt_val:.1f} m)"
                            else:
                                # Format without altitude: "lat, lon"
                                self.metadata['Composite:GPSPosition'] = f"{lat_deg:.6f}, {lon_deg:.6f}"
                    except (ValueError, TypeError, AttributeError):
                        pass
            
            # Composite:Duration (for audio/video files)
            if 'Composite:Duration' not in self.metadata:
                # Check for video duration
                duration = (self.metadata.get('QuickTime:Duration') or 
                           self.metadata.get('QuickTime:MediaDuration') or
                           self.metadata.get('Video:Duration') or
                           self.metadata.get('AVI:Duration'))
                
                # Check for audio duration
                if not duration:
                    duration = (self.metadata.get('Audio:Duration') or
                               self.metadata.get('Audio:MP3:Duration') or
                               self.metadata.get('Audio:WAV:Duration') or
                               self.metadata.get('Audio:FLAC:Duration') or
                               self.metadata.get('Audio:OGG:Duration') or
                               self.metadata.get('Audio:OPUS:Duration') or
                               self.metadata.get('MP3:Duration') or
                               self.metadata.get('WAV:Duration') or
                               self.metadata.get('FLAC:Duration'))
                
                if duration:
                    # If already formatted as string, use as-is
                    if isinstance(duration, str):
                        self.metadata['Composite:Duration'] = duration
                    else:
                        # Format duration in seconds
                        try:
                            if isinstance(duration, (int, float)):
                                duration_sec = float(duration)
                                # Format similar to standard format (HH:MM:SS for long, X.XX s for short)
                                if duration_sec >= 60:
                                    hours = int(duration_sec // 3600)
                                    minutes = int((duration_sec % 3600) // 60)
                                    secs = int(duration_sec % 60)
                                    self.metadata['Composite:Duration'] = f"{hours}:{minutes:02d}:{secs:02d}"
                                elif duration_sec == 0:
                                    self.metadata['Composite:Duration'] = "0 s"
                                else:
                                    self.metadata['Composite:Duration'] = f"{duration_sec:.2f} s"
                        except (ValueError, TypeError):
                            pass
            
            # Format TIFF/EPStandardID as "1.0.0.0" instead of [1, 0, 0, 0]
            if 'EXIF:TIFF/EPStandardID' in self.metadata:
                ep_std_id = self.metadata['EXIF:TIFF/EPStandardID']
                if isinstance(ep_std_id, (list, tuple)) and len(ep_std_id) >= 4:
                    self.metadata['EXIF:TIFF-EPStandardID'] = f"{ep_std_id[0]}.{ep_std_id[1]}.{ep_std_id[2]}.{ep_std_id[3]}"
                elif isinstance(ep_std_id, (list, tuple)) and len(ep_std_id) > 0:
                    # Format as dot-separated values
                    self.metadata['EXIF:TIFF-EPStandardID'] = '.'.join(str(v) for v in ep_std_id)
            
            # Map CFALayout to CFAPattern2 and format as "0 1 1 2"
            if 'EXIF:CFALayout' in self.metadata and 'EXIF:CFAPattern2' not in self.metadata:
                cfa_layout = self.metadata['EXIF:CFALayout']
                if isinstance(cfa_layout, (list, tuple)):
                    self.metadata['EXIF:CFAPattern2'] = ' '.join(str(v) for v in cfa_layout)
            
            # Map CFAPlaneColor to CFARepeatPatternDim and format as "2 2"
            if 'EXIF:CFAPlaneColor' in self.metadata and 'EXIF:CFARepeatPatternDim' not in self.metadata:
                cfa_plane_color = self.metadata['EXIF:CFAPlaneColor']
                if isinstance(cfa_plane_color, (list, tuple)):
                    self.metadata['EXIF:CFARepeatPatternDim'] = ' '.join(str(v) for v in cfa_plane_color)
            
            # Use ExposureBiasValue as ExposureCompensation and format correctly
            if 'EXIF:ExposureBiasValue' in self.metadata and 'EXIF:ExposureCompensation' not in self.metadata:
                exp_bias = self.metadata['EXIF:ExposureBiasValue']
                if isinstance(exp_bias, (list, tuple)) and len(exp_bias) == 2:
                    # Format as rational: numerator/denominator, then convert to decimal
                    num, den = exp_bias
                    if den != 0:
                        exp_comp = num / den
                        # Format as integer if whole number, otherwise as decimal
                        if exp_comp == int(exp_comp):
                            self.metadata['EXIF:ExposureCompensation'] = str(int(exp_comp))
                        else:
                            self.metadata['EXIF:ExposureCompensation'] = str(exp_comp)
                elif isinstance(exp_bias, (int, float)):
                    self.metadata['EXIF:ExposureCompensation'] = str(exp_bias)
            
            # Composite:CFAPattern (Color Filter Array pattern for RAW files)
            if 'Composite:CFAPattern' not in self.metadata:
                # Check for CFAPattern in various locations
                cfa_pattern = (self.metadata.get('EXIF:CFAPattern') or
                              self.metadata.get('EXIF:CFAPattern2') or
                              self.metadata.get('EXIF:CFARepeatPatternDim') or
                              self.metadata.get('MakerNote:CFAPattern') or
                              self.metadata.get('MakerNote:Minolta:BayerPattern'))
                
                if cfa_pattern:
                    # Format CFAPattern (usually 2x2 pattern like "RGGB", "GBRG", etc.)
                    if isinstance(cfa_pattern, (list, tuple)):
                        # If it's a list of values, convert to pattern string
                        if len(cfa_pattern) >= 4:
                            # Map numeric values to color names (0=Red, 1=Green, 2=Blue) to standard format
                            color_map = {0: 'Red', 1: 'Green', 2: 'Blue'}
                            # Format as "[Red,Green][Green,Blue]" to standard format
                            self.metadata['Composite:CFAPattern'] = f"[{color_map.get(int(cfa_pattern[0]), 'Unknown')},{color_map.get(int(cfa_pattern[1]), 'Unknown')}][{color_map.get(int(cfa_pattern[2]), 'Unknown')},{color_map.get(int(cfa_pattern[3]), 'Unknown')}]"
                    elif isinstance(cfa_pattern, str):
                        # If it's a space-separated string like "0 1 1 2", convert to pattern
                        if ' ' in cfa_pattern:
                            parts = cfa_pattern.split()
                            if len(parts) >= 4:
                                color_map = {0: 'Red', 1: 'Green', 2: 'Blue'}
                                try:
                                    # Format as "[Red,Green][Green,Blue]" to standard format
                                    self.metadata['Composite:CFAPattern'] = f"[{color_map.get(int(parts[0]), 'Unknown')},{color_map.get(int(parts[1]), 'Unknown')}][{color_map.get(int(parts[2]), 'Unknown')},{color_map.get(int(parts[3]), 'Unknown')}]"
                                except (ValueError, TypeError):
                                    pass
                        else:
                            # If already a string, use as-is (might be "RGGB", "GBRG", etc.)
                            self.metadata['Composite:CFAPattern'] = cfa_pattern.upper()
            
            # EXIF:BlackLevelRed, EXIF:BlackLevelGreen, EXIF:BlackLevelBlue (split from EXIF:BlackLevel)
            # standard format splits BlackLevel array into separate Red/Green/Blue tags
            if 'EXIF:BlackLevel' in self.metadata and 'EXIF:BlackLevelRed' not in self.metadata:
                black_level = self.metadata.get('EXIF:BlackLevel')
                try:
                    if isinstance(black_level, (list, tuple)) and len(black_level) >= 3:
                        # BlackLevel is an array: [Red, Green, Blue] or [Red, Green1, Green2, Blue]
                        self.metadata['EXIF:BlackLevelRed'] = str(black_level[0])
                        if len(black_level) >= 4:
                            # If 4 values, Green is average of Green1 and Green2
                            green_val = (float(black_level[1]) + float(black_level[2])) / 2.0
                            self.metadata['EXIF:BlackLevelGreen'] = str(int(green_val) if green_val == int(green_val) else green_val)
                        else:
                            # If 3 values, use middle value as Green
                            self.metadata['EXIF:BlackLevelGreen'] = str(black_level[1])
                        self.metadata['EXIF:BlackLevelBlue'] = str(black_level[-1])
                    elif isinstance(black_level, str):
                        # BlackLevel is a space-separated string like "0 0 0" or "0 0 0 0"
                        parts = black_level.split()
                        if len(parts) >= 3:
                            self.metadata['EXIF:BlackLevelRed'] = parts[0]
                            if len(parts) >= 4:
                                # If 4 values, Green is average of Green1 and Green2
                                green_val = (float(parts[1]) + float(parts[2])) / 2.0
                                self.metadata['EXIF:BlackLevelGreen'] = str(int(green_val) if green_val == int(green_val) else green_val)
                            else:
                                # If 3 values, use middle value as Green
                                self.metadata['EXIF:BlackLevelGreen'] = parts[1]
                            self.metadata['EXIF:BlackLevelBlue'] = parts[-1]
                except (ValueError, TypeError, IndexError):
                    pass
            
            # Composite:Rotation (for video files)
            if 'Composite:Rotation' not in self.metadata:
                # Check for rotation in video metadata
                rotation = (self.metadata.get('QuickTime:Rotation') or
                           self.metadata.get('Video:Rotation') or
                           self.metadata.get('EXIF:Orientation'))
                
                if rotation is not None:
                    try:
                        if isinstance(rotation, str):
                            # Extract number from string
                            import re
                            match = re.search(r'\d+', rotation)
                            if match:
                                rotation_val = int(match.group())
                            else:
                                rotation_val = None
                        else:
                            rotation_val = int(rotation)
                        
                        if rotation_val is not None:
                            # Map orientation to rotation angle
                            # Orientation: 1=0°, 3=180°, 6=90°CW, 8=90°CCW
                            orientation_map = {
                                1: 0, 3: 180, 6: 90, 8: 270
                            }
                            if rotation_val in orientation_map:
                                self.metadata['Composite:Rotation'] = f"{orientation_map[rotation_val]}°"
                            elif isinstance(rotation, (int, float)):
                                # Direct rotation value
                                self.metadata['Composite:Rotation'] = f"{int(rotation)}°"
                    except (ValueError, TypeError):
                        pass
            
            # GPS Composite tags (signed coordinates combining value + reference)
            # GPSLatitude (signed) - combines GPSLatitude + GPSLatitudeRef
            if 'GPS:GPSLatitude' in self.metadata and 'GPS:GPSLatitudeRef' in self.metadata:
                try:
                    lat = self.metadata['GPS:GPSLatitude']
                    lat_ref = self.metadata['GPS:GPSLatitudeRef']
                    
                    # Parse latitude (can be rational number tuple, string, or float)
                    if isinstance(lat, tuple) and len(lat) == 3:
                        # Rational format: (deg/1, min/1, sec/100)
                        deg = lat[0][0] / lat[0][1] if isinstance(lat[0], tuple) else float(lat[0])
                        min_val = lat[1][0] / lat[1][1] if isinstance(lat[1], tuple) else float(lat[1])
                        sec = lat[2][0] / lat[2][1] if isinstance(lat[2], tuple) else float(lat[2])
                        lat_decimal = deg + min_val/60.0 + sec/3600.0
                    elif isinstance(lat, str):
                        # Parse string format like "37 deg 25' 19.26\" N"
                        import re
                        # Try to extract degrees, minutes, seconds
                        parts = re.findall(r'([\d.]+)', lat)
                        if len(parts) >= 3:
                            lat_decimal = float(parts[0]) + float(parts[1])/60.0 + float(parts[2])/3600.0
                        elif len(parts) >= 1:
                            lat_decimal = float(parts[0])
                        else:
                            lat_decimal = None
                    else:
                        lat_decimal = float(lat)
                    
                    if lat_decimal is not None:
                        # Apply sign based on reference (S = negative, N = positive)
                        if isinstance(lat_ref, str) and lat_ref.upper() in ('S', 'SOUTH'):
                            lat_decimal = -abs(lat_decimal)
                        else:
                            lat_decimal = abs(lat_decimal)
                        
                        # Store as separate composite tag (preserve original GPS:GPSLatitude)
                        # Format with 6 decimal places (standard format precision)
                        self.metadata['Composite:GPSLatitude'] = f"{lat_decimal:.6f}"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # GPSLongitude (signed) - combines GPSLongitude + GPSLongitudeRef
            if 'GPS:GPSLongitude' in self.metadata and 'GPS:GPSLongitudeRef' in self.metadata:
                try:
                    lon = self.metadata['GPS:GPSLongitude']
                    lon_ref = self.metadata['GPS:GPSLongitudeRef']
                    
                    # Parse longitude (can be rational number tuple, string, or float)
                    if isinstance(lon, tuple) and len(lon) == 3:
                        # Rational format: (deg/1, min/1, sec/100)
                        deg = lon[0][0] / lon[0][1] if isinstance(lon[0], tuple) else float(lon[0])
                        min_val = lon[1][0] / lon[1][1] if isinstance(lon[1], tuple) else float(lon[1])
                        sec = lon[2][0] / lon[2][1] if isinstance(lon[2], tuple) else float(lon[2])
                        lon_decimal = deg + min_val/60.0 + sec/3600.0
                    elif isinstance(lon, str):
                        # Parse string format like "122 deg 7' 58.86\" W"
                        import re
                        # Try to extract degrees, minutes, seconds
                        parts = re.findall(r'([\d.]+)', lon)
                        if len(parts) >= 3:
                            lon_decimal = float(parts[0]) + float(parts[1])/60.0 + float(parts[2])/3600.0
                        elif len(parts) >= 1:
                            lon_decimal = float(parts[0])
                        else:
                            lon_decimal = None
                    else:
                        lon_decimal = float(lon)
                    
                    if lon_decimal is not None:
                        # Apply sign based on reference (W = negative, E = positive)
                        if isinstance(lon_ref, str) and lon_ref.upper() in ('W', 'WEST'):
                            lon_decimal = -abs(lon_decimal)
                        else:
                            lon_decimal = abs(lon_decimal)
                        
                        # Store as separate composite tag (preserve original GPS:GPSLongitude)
                        # Format with 6 decimal places (standard format precision)
                        self.metadata['Composite:GPSLongitude'] = f"{lon_decimal:.6f}"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # GPSAltitude (signed) - combines GPSAltitude + GPSAltitudeRef
            if 'GPS:GPSAltitude' in self.metadata:
                try:
                    alt = self.metadata['GPS:GPSAltitude']
                    alt_ref = self.metadata.get('GPS:GPSAltitudeRef', '0')
                    
                    # Parse altitude (can be rational number tuple, string, or float)
                    if isinstance(alt, tuple) and len(alt) == 2:
                        # Rational format: (value/1)
                        alt_value = alt[0] / alt[1] if alt[1] != 0 else float(alt[0])
                    elif isinstance(alt, str):
                        # Parse string format like "123 m" or "123/1"
                        import re
                        parts = re.findall(r'([\d.]+)', alt)
                        if parts:
                            alt_value = float(parts[0])
                        else:
                            alt_value = None
                    else:
                        alt_value = float(alt)
                    
                    if alt_value is not None:
                        # Apply sign based on reference (1 = below sea level, 0 = above sea level)
                        if isinstance(alt_ref, str):
                            alt_ref_val = 1 if alt_ref.upper() in ('1', 'BELOW', 'BELOW SEA LEVEL') else 0
                        else:
                            alt_ref_val = int(alt_ref)
                        
                        if alt_ref_val == 1:
                            alt_value = -abs(alt_value)
                        else:
                            alt_value = abs(alt_value)
                        
                        # Store as separate composite tag (preserve original GPS:GPSAltitude)
                        # Format with 2 decimal places (standard format precision)
                        self.metadata['Composite:GPSAltitude'] = f"{alt_value:.2f}"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Promote XMP core date tags into EXIF when EXIF dates are missing
            # This helps align with standard behavior (which often reflects XMP
            # dates in EXIF:CreateDate/EXIF:DateTimeOriginal for DNG and other files)
            for exif_tag, xmp_candidates in [
                ('EXIF:CreateDate', ['XMP:CreateDate']),
                ('EXIF:ModifyDate', ['XMP:ModifyDate', 'XMP:MetadataDate']),
                ('EXIF:DateTimeOriginal', ['XMP:DateTimeOriginal', 'XMP:CreateDate']),
            ]:
                if exif_tag not in self.metadata:
                    for xmp_tag in xmp_candidates:
                        value = self.metadata.get(xmp_tag)
                        if value:
                            self.metadata[exif_tag] = value
                            break
            
            # QuickTime/3GP/M4V format fixes
            # QuickTime:SourceImageWidth and SourceImageHeight (promote from track-specific or set from ImageWidth/Height)
            if 'QuickTime:SourceImageWidth' not in self.metadata:
                source_width = (self.metadata.get('QuickTime:Track:SourceImageWidth') or
                              self.metadata.get('QuickTime:Track1:SourceImageWidth') or
                              self.metadata.get('QuickTime:Video:SourceImageWidth') or
                              self.metadata.get('QuickTime:ImageWidth'))
                if source_width:
                    self.metadata['QuickTime:SourceImageWidth'] = source_width
            
            if 'QuickTime:SourceImageHeight' not in self.metadata:
                source_height = (self.metadata.get('QuickTime:Track:SourceImageHeight') or
                               self.metadata.get('QuickTime:Track1:SourceImageHeight') or
                               self.metadata.get('QuickTime:Video:SourceImageHeight') or
                               self.metadata.get('QuickTime:ImageHeight'))
                if source_height:
                    self.metadata['QuickTime:SourceImageHeight'] = source_height
            
            # QuickTime:ImageWidth and QuickTime:ImageHeight (aliases from SourceImageWidth/SourceImageHeight)
            if 'QuickTime:ImageWidth' not in self.metadata:
                image_width = self.metadata.get('QuickTime:SourceImageWidth')
                if image_width:
                    self.metadata['QuickTime:ImageWidth'] = image_width
            
            if 'QuickTime:ImageHeight' not in self.metadata:
                image_height = self.metadata.get('QuickTime:SourceImageHeight')
                if image_height:
                    self.metadata['QuickTime:ImageHeight'] = image_height
            
            # QuickTime:XResolution and YResolution (promote from track-specific if not set)
            if 'QuickTime:XResolution' not in self.metadata:
                x_res = (self.metadata.get('QuickTime:Track:XResolution') or
                        self.metadata.get('QuickTime:Track1:XResolution') or
                        self.metadata.get('QuickTime:Video:XResolution'))
                if x_res:
                    self.metadata['QuickTime:XResolution'] = x_res
            
            if 'QuickTime:YResolution' not in self.metadata:
                y_res = (self.metadata.get('QuickTime:Track:YResolution') or
                        self.metadata.get('QuickTime:Track1:YResolution') or
                        self.metadata.get('QuickTime:Video:YResolution'))
                if y_res:
                    self.metadata['QuickTime:YResolution'] = y_res
            
            # QuickTime:CompressorID (promote from track-specific if not set)
            if 'QuickTime:CompressorID' not in self.metadata:
                compressor_id = (self.metadata.get('QuickTime:Track:CompressorID') or
                               self.metadata.get('QuickTime:Track1:CompressorID') or
                               self.metadata.get('QuickTime:Video:CompressorID'))
                if compressor_id:
                    self.metadata['QuickTime:CompressorID'] = compressor_id
            
            # QuickTime:MediaLanguageCode (set even if 'und' to standard format)
            if 'QuickTime:MediaLanguageCode' not in self.metadata:
                # Check track-specific MediaLanguageCode
                track_lang = self.metadata.get('QuickTime:Track:MediaLanguageCode')
                if track_lang:
                    self.metadata['QuickTime:MediaLanguageCode'] = track_lang
                # If still not set, default to 'und' (undefined) to standard format
                if 'QuickTime:MediaLanguageCode' not in self.metadata:
                    self.metadata['QuickTime:MediaLanguageCode'] = 'und'
            
            # QuickTime:MediaTimeScale (use track's MediaTimeScale, not movie's)
            # For MP4 files with both video and audio tracks, Standard format uses audio track's MediaTimeScale
            # For MOV files or video-only files, Standard format uses video track's MediaTimeScale
            # Check for audio track MediaTimeScale first (for MP4 with audio)
            audio_track_time_scale = None
            video_track_time_scale = None
            for key in self.metadata.keys():
                if ':MediaTimeScale' in key and 'Track' in key:
                    if 'Track:' in key or 'Track2' in key:
                        # Check which track this is
                        if 'Track2' in key or (':Track:' in key and self.metadata.get(key.replace(':MediaTimeScale', ':HandlerType')) in ('soun', 'Audio Track')):
                            audio_track_time_scale = self.metadata.get(key)
                        elif ':Track:' in key and self.metadata.get(key.replace(':MediaTimeScale', ':HandlerType')) in ('vide', 'Video Track'):
                            video_track_time_scale = self.metadata.get(key)
            
            # Use audio track's MediaTimeScale if available (for MP4 with audio), otherwise use video track's
            if audio_track_time_scale:
                self.metadata['QuickTime:MediaTimeScale'] = audio_track_time_scale
            elif video_track_time_scale:
                self.metadata['QuickTime:MediaTimeScale'] = video_track_time_scale
            else:
                # Fallback to first track's MediaTimeScale
                track_media_time_scale = self.metadata.get('QuickTime:Track:MediaTimeScale')
                if track_media_time_scale and 'QuickTime:MediaTimeScale' in self.metadata:
                    movie_media_time_scale = self.metadata.get('QuickTime:MediaTimeScale')
                    if movie_media_time_scale != track_media_time_scale:
                        self.metadata['QuickTime:MediaTimeScale'] = track_media_time_scale
            
            # QuickTime:MediaDuration (for MP4 with audio, use audio track's MediaDuration)
            # For MP4 files with both video and audio tracks, Standard format uses audio track's MediaDuration
            audio_track_duration = None
            video_track_duration = None
            for key in self.metadata.keys():
                if ':MediaDuration' in key and 'Track' in key:
                    if 'Track2' in key or (':Track:' in key and self.metadata.get(key.replace(':MediaDuration', ':HandlerType')) in ('soun', 'Audio Track')):
                        audio_track_duration = self.metadata.get(key)
                    elif ':Track:' in key and self.metadata.get(key.replace(':MediaDuration', ':HandlerType')) in ('vide', 'Video Track'):
                        video_track_duration = self.metadata.get(key)
            
            # Use audio track's MediaDuration if available (for MP4 with audio), otherwise use video track's
            if audio_track_duration:
                self.metadata['QuickTime:MediaDuration'] = audio_track_duration
            elif video_track_duration:
                self.metadata['QuickTime:MediaDuration'] = video_track_duration
            
            # QuickTime:StartTimeScale and StartTimeSampleSize (from XMP xmpDM namespace)
            # Standard format shows these as QuickTime tags even though they come from XMP
            # XMP parser extracts them as lowercase: startTimeScale, startTimeSampleSize
            if 'QuickTime:StartTimeScale' not in self.metadata:
                # Check XMP tags (xmpDM namespace) - try both capitalized and lowercase
                xmp_start_time_scale = (self.metadata.get('XMP:StartTimeScale') or 
                                       self.metadata.get('XMP:startTimeScale') or
                                       self.metadata.get('XMP-xmpDM:StartTimeScale') or
                                       self.metadata.get('XMP-xmpDM:startTimeScale'))
                if xmp_start_time_scale:
                    self.metadata['QuickTime:StartTimeScale'] = xmp_start_time_scale
            
            if 'QuickTime:StartTimeSampleSize' not in self.metadata:
                # Check XMP tags (xmpDM namespace) - try both capitalized and lowercase
                xmp_start_time_sample_size = (self.metadata.get('XMP:StartTimeSampleSize') or 
                                              self.metadata.get('XMP:startTimeSampleSize') or
                                              self.metadata.get('XMP-xmpDM:StartTimeSampleSize') or
                                              self.metadata.get('XMP-xmpDM:startTimeSampleSize'))
                if xmp_start_time_sample_size:
                    self.metadata['QuickTime:StartTimeSampleSize'] = xmp_start_time_sample_size
            
            # QuickTime:TrackDuration (use MediaDuration if TrackDuration is 0 or missing)
            if 'QuickTime:TrackDuration' not in self.metadata or self.metadata.get('QuickTime:TrackDuration') == '0 s':
                media_duration = self.metadata.get('QuickTime:MediaDuration') or self.metadata.get('QuickTime:Track:MediaDuration')
                if media_duration:
                    self.metadata['QuickTime:TrackDuration'] = media_duration
            
            # QuickTime:HandlerType (format and prioritize alias/data handler tracks)
            # standard format prioritizes alias/data handler tracks over metadata/video/audio tracks
            # Check for alias/data handler tracks first
            alias_handler_type = None
            alias_handler_desc = None
            alias_handler_class = None
            for key in self.metadata.keys():
                if ':HandlerType' in key and key != 'QuickTime:HandlerType':
                    handler_val = self.metadata.get(key)
                    handler_desc_key = key.replace(':HandlerType', ':HandlerDescription')
                    handler_desc = self.metadata.get(handler_desc_key)
                    handler_class_key = key.replace(':HandlerType', ':HandlerClass')
                    handler_class = self.metadata.get(handler_class_key)
                    # Check if this is an alias/data handler track
                    # Standard format shows HandlerType = 'Alias Data' for tracks with handler type 'alis' or HandlerClass = 'Data Handler'
                    # Also check for 'Core Media Data Handler' in description
                    if (handler_val == 'alis' or handler_val == 'Alias Data' or
                        handler_desc == 'Alias Data Handler' or 
                        (handler_desc and ('Alias' in handler_desc or 'Data Handler' in handler_desc)) or 
                        handler_class == 'Data Handler'):
                        alias_handler_type = 'Alias Data'
                        alias_handler_desc = handler_desc or 'Alias Data Handler'
                        # If handler_class is 'Data Handler', use it; otherwise default to 'Data Handler' for alias tracks
                        alias_handler_class = handler_class if handler_class == 'Data Handler' else 'Data Handler'
                        break
            
            # Check for metadata track HandlerType (second priority)
            metadata_handler_type = None
            for key in ['QuickTime:Track2:HandlerType', 'QuickTime:Track3:HandlerType', 'QuickTime:Track:HandlerType']:
                handler_val = self.metadata.get(key)
                if handler_val and (handler_val == 'meta' or handler_val == 'text' or 'Metadata' in str(handler_val)):
                    # Found metadata track - format it
                    if handler_val == 'meta' or handler_val == 'text':
                        metadata_handler_type = 'Metadata'
                    else:
                        metadata_handler_type = str(handler_val)
                    break
            
            handler_type = self.metadata.get('QuickTime:HandlerType')
            # Priority: alias/data handler > metadata handler > video/audio track
            # Check if HandlerType was already set to "Metadata" from meta atom (but alias takes precedence)
            if alias_handler_type:
                # Prioritize alias/data handler track (standard behavior)
                self.metadata['QuickTime:HandlerType'] = alias_handler_type
                # Always overwrite HandlerDescription with alias handler description
                if alias_handler_desc:
                    self.metadata['QuickTime:HandlerDescription'] = alias_handler_desc
                # Also set HandlerClass from alias track (overwrite if already set)
                if alias_handler_class:
                    self.metadata['QuickTime:HandlerClass'] = alias_handler_class
            elif self.metadata.get('QuickTime:HandlerType') == 'Metadata':
                # Already set from meta atom - keep it
                pass
            elif metadata_handler_type:
                # Prioritize metadata track HandlerType (standard behavior)
                self.metadata['QuickTime:HandlerType'] = metadata_handler_type
            elif handler_type == 'vide':
                self.metadata['QuickTime:HandlerType'] = 'Video Track'
            elif handler_type == 'soun':
                self.metadata['QuickTime:HandlerType'] = 'Audio Track'
            elif handler_type == 'meta' or handler_type == 'text':
                self.metadata['QuickTime:HandlerType'] = 'Metadata'
            
            # QuickTime:MatrixStructure (fix identity matrix formatting)
            # Standard format shows identity matrix as "1 0 0 0 1 0 0 0 1"
            matrix = self.metadata.get('QuickTime:MatrixStructure')
            if matrix and isinstance(matrix, str):
                parts = matrix.split()
                if len(parts) == 9:
                    try:
                        values = [float(p) for p in parts]
                        # Check if it's an identity matrix (1 0 0 0 1 0 0 0 1)
                        # Allow small floating point differences and check for near-zero values
                        is_identity = (
                            abs(values[0] - 1.0) < 0.01 and abs(values[1]) < 0.01 and abs(values[2]) < 0.01 and
                            abs(values[3]) < 0.01 and abs(values[4] - 1.0) < 0.01 and abs(values[5]) < 0.01 and
                            abs(values[6]) < 0.01 and abs(values[7]) < 0.01 and abs(values[8] - 1.0) < 0.01
                        )
                        # Also check for patterns like "0 1.52587890625e-05 256 1 0 0 0 1 0" which might be misread identity
                        # Check if values[2] and values[3] are swapped or if there's a scaling issue
                        if not is_identity:
                            # Check if it's close to identity but with different element positions
                            # Pattern: [0, small, large, 1, 0, 0, 0, 1, 0] might be identity with wrong parsing
                            if (abs(values[0]) < 0.01 and abs(values[1]) < 1.0 and abs(values[2] - 256.0) < 1.0 and
                                abs(values[3] - 1.0) < 0.01 and abs(values[4]) < 0.01 and abs(values[5]) < 0.01 and
                                abs(values[6]) < 0.01 and abs(values[7] - 1.0) < 0.01 and abs(values[8]) < 0.01):
                                # This looks like identity matrix but with wrong element positions
                                self.metadata['QuickTime:MatrixStructure'] = '1 0 0 0 1 0 0 0 1'
                        elif is_identity:
                            self.metadata['QuickTime:MatrixStructure'] = '1 0 0 0 1 0 0 0 1'
                    except (ValueError, IndexError):
                        pass
            
            # QuickTime:TrackLayer - Standard format shows layer from first track (typically video track)
            # For MOV files with video tracks, check if video track layer should be used
            # Check all tracks to find the one standard format would use
            video_track_layer = None
            text_track_layer = None
            for key in self.metadata.keys():
                if ':TrackLayer' in key and key != 'QuickTime:TrackLayer':
                    # Get corresponding handler type
                    track_key = key.replace(':TrackLayer', ':HandlerType')
                    handler_type = self.metadata.get(track_key)
                    layer_value = self.metadata.get(key)
                    if handler_type == 'vide' and video_track_layer is None:
                        video_track_layer = layer_value
                    elif handler_type == 'text' and text_track_layer is None:
                        text_track_layer = layer_value
            
            # standard format typically shows video track layer, but for some files it might show text track layer
            # Use video track layer if available, otherwise use first track layer
            if video_track_layer is not None:
                self.metadata['QuickTime:TrackLayer'] = video_track_layer
            elif text_track_layer is not None:
                self.metadata['QuickTime:TrackLayer'] = text_track_layer
            
            # Fallback: For audio-only files, TrackLayer is typically 0
            track_layer = self.metadata.get('QuickTime:TrackLayer')
            if track_layer == 1:
                # Check if this is an audio file - check both HandlerType and Track:HandlerType
                handler_type = self.metadata.get('QuickTime:HandlerType')
                track_handler_type = self.metadata.get('QuickTime:Track:HandlerType')
                # Audio tracks have handler type 'soun' or 'Audio Track'
                # Note: HandlerType might be "Metadata" for files with meta atom, but Track:HandlerType will be 'soun'
                if (handler_type == 'Audio Track' or handler_type == 'soun' or 
                    track_handler_type == 'soun' or track_handler_type == 'Audio Track'):
                    # Audio tracks typically have layer 0
                    self.metadata['QuickTime:TrackLayer'] = 0
            
            # QuickTime:TrackVolume (fix for audio tracks - should be 100.00%, not 0.00%)
            # For audio files, TrackVolume is typically 100.00% (full volume)
            track_volume = self.metadata.get('QuickTime:TrackVolume')
            if track_volume == '0.00%':
                handler_type = self.metadata.get('QuickTime:HandlerType')
                track_handler_type = self.metadata.get('QuickTime:Track:HandlerType')
                # Check if this is an audio file - check both HandlerType and Track:HandlerType
                if (handler_type == 'Audio Track' or handler_type == 'soun' or 
                    track_handler_type == 'soun' or track_handler_type == 'Audio Track'):
                    # Check if we have a track-specific volume that's different
                    track_vol = self.metadata.get('QuickTime:Track:TrackVolume')
                    if track_vol and track_vol != '0.00%':
                        self.metadata['QuickTime:TrackVolume'] = track_vol
                    else:
                        # Audio tracks typically have 100% volume
                        self.metadata['QuickTime:TrackVolume'] = '100.00%'
            
            # QuickTime:GraphicsMode - Standard format shows GraphicsMode from alias/text track if available
            # Check for GraphicsMode from tracks with HandlerType "Alias Data" or "text"
            alias_track_graphics_mode = None
            for key in self.metadata.keys():
                if ':GraphicsMode' in key and key != 'QuickTime:GraphicsMode' and 'GenGraphicsMode' not in key:
                    # Get corresponding handler type and description
                    track_key = key.replace(':GraphicsMode', ':HandlerType')
                    handler_type = self.metadata.get(track_key)
                    handler_desc = self.metadata.get(track_key.replace(':HandlerType', ':HandlerDescription'))
                    graphics_mode_value = self.metadata.get(key)
                    # Standard format shows GraphicsMode from alias/text tracks
                    if (handler_type == 'text' or handler_desc == 'Alias Data' or 
                        (handler_desc and 'Alias' in handler_desc)):
                        alias_track_graphics_mode = graphics_mode_value
                        break
            
            # Standard format shows GraphicsMode matching GenGraphicsMode when available
            # Priority: GenGraphicsMode > Track2 GenGraphicsMode (Time Code track) > vmhd GraphicsMode > alias/text track > video track
            gen_graphics_mode = self.metadata.get('QuickTime:GenGraphicsMode')
            if not gen_graphics_mode:
                # Check Track2 (Time Code track) for GenGraphicsMode - Standard format shows it from Time Code track
                gen_graphics_mode = self.metadata.get('QuickTime:Track2:GenGraphicsMode')
            if gen_graphics_mode:
                self.metadata['QuickTime:GraphicsMode'] = gen_graphics_mode
                # Also set GenGraphicsMode if not already set
                if 'QuickTime:GenGraphicsMode' not in self.metadata:
                    self.metadata['QuickTime:GenGraphicsMode'] = gen_graphics_mode
            elif alias_track_graphics_mode:
                self.metadata['QuickTime:GraphicsMode'] = alias_track_graphics_mode
            else:
                # Check vmhd GraphicsMode (from Video Media Header atom) - Standard format shows this for video tracks
                vmhd_graphics_mode = self.metadata.get('QuickTime:Track:GraphicsMode')
                if vmhd_graphics_mode:
                    self.metadata['QuickTime:GraphicsMode'] = vmhd_graphics_mode
                else:
                    # Fallback to video track GraphicsMode from stsd
                    video_track_graphics_mode = self.metadata.get('QuickTime:Track:GraphicsMode')
                    if video_track_graphics_mode:
                        self.metadata['QuickTime:GraphicsMode'] = video_track_graphics_mode
            
            # QuickTime:OpColor - Standard format shows OpColor from alias/text track if available
            alias_track_op_color = None
            for key in self.metadata.keys():
                if ':OpColor' in key and key != 'QuickTime:OpColor' and 'GenOpColor' not in key:
                    # Get corresponding handler type and description
                    track_key = key.replace(':OpColor', ':HandlerType')
                    handler_type = self.metadata.get(track_key)
                    handler_desc = self.metadata.get(track_key.replace(':HandlerType', ':HandlerDescription'))
                    op_color_value = self.metadata.get(key)
                    # Standard format shows OpColor from alias/text tracks
                    if (handler_type == 'text' or handler_desc == 'Alias Data' or 
                        (handler_desc and 'Alias' in handler_desc)):
                        alias_track_op_color = op_color_value
                        break
            
            # Standard format shows OpColor matching GenOpColor when available
            # Priority: GenOpColor > Track2 GenOpColor (Time Code track) > vmhd OpColor > alias/text track > video track
            gen_op_color = self.metadata.get('QuickTime:GenOpColor')
            if not gen_op_color:
                # Check Track2 (Time Code track) for GenOpColor - Standard format shows it from Time Code track
                gen_op_color = self.metadata.get('QuickTime:Track2:GenOpColor')
            if gen_op_color:
                self.metadata['QuickTime:OpColor'] = gen_op_color
                # Also set GenOpColor if not already set
                if 'QuickTime:GenOpColor' not in self.metadata:
                    self.metadata['QuickTime:GenOpColor'] = gen_op_color
            elif alias_track_op_color:
                self.metadata['QuickTime:OpColor'] = alias_track_op_color
            else:
                # Check vmhd OpColor (from Video Media Header atom) - Standard format shows this for video tracks
                # Note: vmhd OpColor might be stored as QuickTime:Track:OpColor if vmhd was parsed
                vmhd_op_color = None
                for key in self.metadata.keys():
                    if ':OpColor' in key and key != 'QuickTime:OpColor' and 'GenOpColor' not in key:
                        # Check if this is from vmhd (video track)
                        track_key = key.replace(':OpColor', ':HandlerType')
                        handler_type = self.metadata.get(track_key)
                        if handler_type == 'vide':
                            vmhd_op_color = self.metadata.get(key)
                            break
                if vmhd_op_color:
                    self.metadata['QuickTime:OpColor'] = vmhd_op_color
                else:
                    # Fallback to video track OpColor from stsd
                    video_track_op_color = self.metadata.get('QuickTime:Track:OpColor')
                    if video_track_op_color:
                        self.metadata['QuickTime:OpColor'] = video_track_op_color
            
            # Promote generic handler tags from track-specific to top-level
            # Standard format shows these as top-level tags: GenMediaVersion, GenBalance, TextFace, TextSize, TextFont, FontName, GenGraphicsMode, GenOpColor, GenFlags, OtherFormat, TextColor
            generic_tags_to_promote = ['GenMediaVersion', 'GenBalance', 'TextFace', 'TextSize', 'TextFont', 'FontName', 'GenGraphicsMode', 'GenOpColor', 'GenFlags', 'OtherFormat', 'TextColor']
            for tag_name in generic_tags_to_promote:
                if f'QuickTime:{tag_name}' not in self.metadata:
                    # Check Track2 (Time Code track) first, then other tracks
                    track2_tag = self.metadata.get(f'QuickTime:Track2:{tag_name}')
                    if track2_tag is not None:
                        self.metadata[f'QuickTime:{tag_name}'] = track2_tag
                    else:
                        # Check other tracks
                        for key in self.metadata.keys():
                            if f':{tag_name}' in key and key != f'QuickTime:{tag_name}':
                                self.metadata[f'QuickTime:{tag_name}'] = self.metadata[key]
                                break
            
            # QuickTime:VideoFrameRate (calculate from SampleDuration and MediaTimeScale)
            # First check if already set, otherwise calculate from stts data
            # For video tracks, we need to get SampleDuration from the video track's stts atom
            # and MediaTimeScale from the video track's mdhd atom
            if 'QuickTime:VideoFrameRate' not in self.metadata:
                # Find video track's SampleDuration and MediaTimeScale
                # Look for tracks with HandlerType 'vide' or 'Video Track'
                sample_duration = None
                track_media_time_scale = None
                
                # First, find which track is the video track
                video_track_prefix = None
                for key in self.metadata.keys():
                    if ':HandlerType' in key:
                        handler_type = self.metadata.get(key)
                        if handler_type in ('vide', 'Video Track', 'Video'):
                            # This is a video track
                            if ':Track:' in key:
                                video_track_prefix = 'QuickTime:Track'
                            elif ':Track1:' in key:
                                video_track_prefix = 'QuickTime:Track1'
                            elif ':Track2:' in key:
                                video_track_prefix = 'QuickTime:Track2'
                            break
                
                # If we found a video track prefix, use it
                if video_track_prefix:
                    sample_duration = self.metadata.get(f'{video_track_prefix}:SampleDuration')
                    track_media_time_scale = self.metadata.get(f'{video_track_prefix}:MediaTimeScale')
                
                # Fallback: check all possible track prefixes for SampleDuration from video tracks
                if not sample_duration:
                    for key in self.metadata.keys():
                        if ':SampleDuration' in key:
                            # Check if this track is a video track
                            track_key = key.replace(':SampleDuration', ':HandlerType')
                            handler_type = self.metadata.get(track_key)
                            if handler_type in ('vide', 'Video Track', 'Video'):
                                sample_duration = self.metadata.get(key)
                                # Get corresponding MediaTimeScale from same track
                                track_key = key.replace(':SampleDuration', ':MediaTimeScale')
                                track_media_time_scale = self.metadata.get(track_key)
                                if track_media_time_scale:
                                    break
                
                # If still not found, try direct lookups (might be from first track)
                if not sample_duration:
                    sample_duration = (self.metadata.get('QuickTime:Track:SampleDuration') or
                                     self.metadata.get('QuickTime:Track1:SampleDuration'))
                
                if not track_media_time_scale:
                    track_media_time_scale = (self.metadata.get('QuickTime:Track:MediaTimeScale') or
                                            self.metadata.get('QuickTime:Track1:MediaTimeScale') or
                                            self.metadata.get('QuickTime:MediaTimeScale'))
                
                # Calculate frame rate: frame_rate = time_scale / sample_duration
                # For 29.97 fps: time_scale=30000, sample_duration=1001 -> 30000/1001 = 29.97
                if sample_duration and track_media_time_scale:
                    try:
                        # Convert to integers, handling string representations
                        if isinstance(sample_duration, str):
                            # Try to extract number from string
                            import re
                            num_match = re.search(r'(\d+)', str(sample_duration))
                            sample_duration_int = int(num_match.group(1)) if num_match else None
                        else:
                            sample_duration_int = int(sample_duration) if sample_duration else None
                        
                        if isinstance(track_media_time_scale, str):
                            import re
                            num_match = re.search(r'(\d+)', str(track_media_time_scale))
                            time_scale_int = int(num_match.group(1)) if num_match else None
                        else:
                            time_scale_int = int(track_media_time_scale) if track_media_time_scale else None
                        
                        if sample_duration_int and time_scale_int and sample_duration_int > 0 and time_scale_int > 0:
                            frame_rate = time_scale_int / sample_duration_int
                            # Only set if frame rate is reasonable (between 1 and 120 fps)
                            if 1.0 <= frame_rate <= 120.0:
                                self.metadata['QuickTime:VideoFrameRate'] = f"{frame_rate:.2f}"
                    except (ValueError, TypeError, ZeroDivisionError, AttributeError):
                        pass
                
                # If still not set, try promoting from track-specific tags
                if 'QuickTime:VideoFrameRate' not in self.metadata:
                    video_frame_rate = (self.metadata.get('QuickTime:Track:VideoFrameRate') or
                                      self.metadata.get('QuickTime:Track1:VideoFrameRate') or
                                      self.metadata.get('QuickTime:Video:VideoFrameRate'))
                    if video_frame_rate:
                        self.metadata['QuickTime:VideoFrameRate'] = video_frame_rate
            
            # QuickTime:PlaybackFrameRate - calculated from PreferredRate in mvhd atom
            # PlaybackFrameRate is the preferred playback rate, which is stored as a fixed-point 16.16 value in mvhd
            # Standard format shows VideoFrameRate as PlaybackFrameRate when PreferredRate is 1.0 (normal speed)
            # Otherwise, it shows PreferredRate * VideoFrameRate or just PreferredRate
            if 'QuickTime:PlaybackFrameRate' not in self.metadata:
                preferred_rate = self.metadata.get('QuickTime:PreferredRate')
                video_frame_rate = self.metadata.get('QuickTime:VideoFrameRate')
                
                if preferred_rate is not None:
                    try:
                        # PreferredRate is already converted from fixed-point 16.16 to float
                        if isinstance(preferred_rate, (int, float)):
                            playback_rate_value = float(preferred_rate)
                        else:
                            # Try to extract number from string
                            import re
                            num_match = re.search(r'([\d.]+)', str(preferred_rate))
                            playback_rate_value = float(num_match.group(1)) if num_match else None
                        
                        if playback_rate_value is not None:
                            # When PreferredRate is 1.0 (normal speed), Standard format shows VideoFrameRate as PlaybackFrameRate
                            if abs(playback_rate_value - 1.0) < 0.001 and video_frame_rate:
                                try:
                                    # Extract VideoFrameRate value
                                    if isinstance(video_frame_rate, (int, float)):
                                        vfr_value = float(video_frame_rate)
                                    else:
                                        import re
                                        vfr_match = re.search(r'([\d.]+)', str(video_frame_rate))
                                        vfr_value = float(vfr_match.group(1)) if vfr_match else None
                                    
                                    if vfr_value and vfr_value > 0:
                                        # Standard format shows PlaybackFrameRate as integer when it's a whole number
                                        if vfr_value == int(vfr_value):
                                            self.metadata['QuickTime:PlaybackFrameRate'] = int(vfr_value)
                                        else:
                                            self.metadata['QuickTime:PlaybackFrameRate'] = f"{vfr_value:.2f}"
                                except (ValueError, TypeError, AttributeError):
                                    # Fallback to PreferredRate if VideoFrameRate extraction fails
                                    if playback_rate_value == int(playback_rate_value):
                                        self.metadata['QuickTime:PlaybackFrameRate'] = int(playback_rate_value)
                                    else:
                                        self.metadata['QuickTime:PlaybackFrameRate'] = f"{playback_rate_value:.2f}"
                            else:
                                # PreferredRate is not 1.0, use it directly
                                if playback_rate_value == int(playback_rate_value):
                                    self.metadata['QuickTime:PlaybackFrameRate'] = int(playback_rate_value)
                                else:
                                    self.metadata['QuickTime:PlaybackFrameRate'] = f"{playback_rate_value:.2f}"
                    except (ValueError, TypeError, AttributeError):
                        pass
            
            # QuickTime:TimecodeTrack - detect if there's a timecode track and get track number
            # Timecode tracks have HandlerType 'tmcd' or HandlerDescription containing "Time Code"
            if 'QuickTime:TimecodeTrack' not in self.metadata:
                timecode_track_number = None
                for key in self.metadata.keys():
                    if ':HandlerType' in key:
                        handler_type = self.metadata.get(key)
                        handler_desc = self.metadata.get(key.replace(':HandlerType', ':HandlerDescription'))
                        if handler_type == 'tmcd' or (handler_desc and ('Time Code' in handler_desc or 'timecode' in handler_desc.lower())):
                            # Extract track number from key (e.g., "QuickTime:Track2:HandlerType" -> 2)
                            # Or use TrackID if available
                            track_key = key.replace(':HandlerType', '')
                            if 'Track' in track_key:
                                # Try to extract track number from key
                                parts = track_key.split(':')
                                for part in parts:
                                    if part.startswith('Track') and len(part) > 5:
                                        try:
                                            track_num = int(part[5:])
                                            timecode_track_number = track_num
                                            break
                                        except ValueError:
                                            pass
                                # If no track number found, try TrackID
                                if timecode_track_number is None:
                                    track_id_key = track_key.replace(':HandlerType', ':TrackID')
                                    track_id = self.metadata.get(track_id_key)
                                    if track_id:
                                        timecode_track_number = track_id
                            break
                if timecode_track_number is not None:
                    self.metadata['QuickTime:TimecodeTrack'] = str(timecode_track_number)
            
            # QuickTime:HandlerVendorID (use VendorID from stsd if HandlerVendorID not set)
            # standard format often shows HandlerVendorID from the codec vendor, not hdlr manufacturer
            if 'QuickTime:HandlerVendorID' not in self.metadata:
                vendor_id = self.metadata.get('QuickTime:VendorID')
                if vendor_id:
                    self.metadata['QuickTime:HandlerVendorID'] = vendor_id
                # Also check track-specific VendorID
                if 'QuickTime:HandlerVendorID' not in self.metadata:
                    track_vendor = self.metadata.get('QuickTime:Track:VendorID')
                    if track_vendor:
                        self.metadata['QuickTime:HandlerVendorID'] = track_vendor
                # Fallback: search for VendorID in stsd atom directly from file
                if 'QuickTime:HandlerVendorID' not in self.metadata and self.file_path:
                    try:
                        with open(str(self.file_path), 'rb') as f:
                            file_data = f.read()
                            # Find stsd atom
                            stsd_idx = file_data.find(b'stsd')
                            if stsd_idx >= 0 and stsd_idx >= 4:
                                stsd_size = int.from_bytes(file_data[stsd_idx-4:stsd_idx], 'big')
                                # Look for 'appl' (Apple) in stsd data (VendorID for Apple)
                                if stsd_idx + stsd_size <= len(file_data):
                                    stsd_data = file_data[stsd_idx+8:stsd_idx+stsd_size]
                                    appl_idx = stsd_data.find(b'appl')
                                    if appl_idx >= 0 and appl_idx < len(stsd_data) - 4:
                                        vendor_bytes = stsd_data[appl_idx:appl_idx+4]
                                        if vendor_bytes == b'appl':
                                            self.metadata['QuickTime:HandlerVendorID'] = 'Apple'
                                            self.metadata['QuickTime:VendorID'] = 'Apple'
                    except Exception:
                        pass
            
            # QuickTime:Encoder (extract from ©too atom if not set)
            if 'QuickTime:Encoder' not in self.metadata and self.file_path:
                try:
                    with open(str(self.file_path), 'rb') as f:
                        file_data = f.read()
                        # Find ©too atom (copyright-tool)
                        too_idx = file_data.find(b'\xa9too')
                        if too_idx >= 0:
                            if too_idx >= 4:
                                too_size = int.from_bytes(file_data[too_idx-4:too_idx], 'big')
                                # Atom size includes the 8-byte header, so payload is too_size - 8
                                # Check if we can read at least the header + some payload
                                if too_idx + 8 < len(file_data):
                                    # Read available payload (may be less than too_size - 8 if file is truncated)
                                    payload_size = min(too_size - 8, len(file_data) - (too_idx + 8))
                                    if payload_size > 0:
                                        too_data = file_data[too_idx+8:too_idx+8+payload_size]
                                        # Look for encoder strings (Lavf, FFmpeg, etc.)
                                        # Encoder might be after 'data' atom header (12 bytes: size(4) + 'data'(4) + version(1) + flags(3) + locale(4))
                                        for enc_prefix in [b'Lavf', b'FFmpeg', b'x264', b'libx264']:
                                            enc_idx = too_data.find(enc_prefix)
                                            if enc_idx >= 0:
                                                # Extract string from this position
                                                remaining = too_data[enc_idx:]
                                                null_pos = remaining.find(b'\x00')
                                                if null_pos > 0:
                                                    encoder_str = remaining[:null_pos].decode('utf-8', errors='ignore').strip()
                                                else:
                                                    encoder_str = remaining[:50].decode('utf-8', errors='ignore').strip('\x00').strip()
                                                if encoder_str and len(encoder_str) > 3 and len(encoder_str) < 100:
                                                    self.metadata['QuickTime:Encoder'] = encoder_str
                                                    break
                except Exception:
                    pass
            
            # QuickTime:HandlerVendorID fallback: use MajorBrand if it contains "Apple"
            if 'QuickTime:HandlerVendorID' not in self.metadata:
                major_brand = self.metadata.get('QuickTime:MajorBrand')
                if major_brand and 'Apple' in str(major_brand):
                    self.metadata['QuickTime:HandlerVendorID'] = 'Apple'
                # Fallback: search for VendorID in stsd atom directly from file
                if 'QuickTime:HandlerVendorID' not in self.metadata and self.file_path:
                    try:
                        with open(str(self.file_path), 'rb') as f:
                            file_data = f.read()
                            # Find stsd atom
                            stsd_idx = file_data.find(b'stsd')
                            if stsd_idx >= 0 and stsd_idx >= 4:
                                stsd_size = int.from_bytes(file_data[stsd_idx-4:stsd_idx], 'big')
                                # stsd payload: version(1) + flags(3) + entry_count(4) + entries
                                # First entry: size(4) + format(4) + reserved(6) + data_ref(2) + version(2) + revision(2) + vendor(4)
                                # VendorID is at offset 8 (entry header) + 20 (audio sample desc fields) = 28 from stsd start
                                # But stsd_data from _find_atom starts after 8-byte header, so offset is 28-8 = 20
                                # Actually, let's search for 'appl' (Apple) in stsd
                                if stsd_idx + stsd_size <= len(file_data):
                                    stsd_data = file_data[stsd_idx+8:stsd_idx+stsd_size]
                                    # Look for 'appl' in stsd data (VendorID for Apple)
                                    appl_idx = stsd_data.find(b'appl')
                                    if appl_idx >= 0 and appl_idx < len(stsd_data) - 4:
                                        # Check if it's a valid VendorID (4 bytes, might be followed by other data)
                                        vendor_bytes = stsd_data[appl_idx:appl_idx+4]
                                        if vendor_bytes == b'appl':
                                            self.metadata['QuickTime:HandlerVendorID'] = 'Apple'
                                            self.metadata['QuickTime:VendorID'] = 'Apple'
                    except Exception:
                        pass
            
            # QuickTime audio tags (promote from Track: prefix to top level for audio files)
            # AudioSampleRate, AudioChannels, AudioFormat, Balance
            if 'QuickTime:AudioSampleRate' not in self.metadata:
                audio_sample_rate = (self.metadata.get('QuickTime:Track:AudioSampleRate') or 
                                    self.metadata.get('QuickTime:Track1:AudioSampleRate'))
                if audio_sample_rate:
                    self.metadata['QuickTime:AudioSampleRate'] = audio_sample_rate
            
            if 'QuickTime:AudioChannels' not in self.metadata:
                audio_channels = (self.metadata.get('QuickTime:Track:AudioChannels') or 
                                self.metadata.get('QuickTime:Track1:AudioChannels'))
                if audio_channels:
                    self.metadata['QuickTime:AudioChannels'] = audio_channels
            
            if 'QuickTime:AudioFormat' not in self.metadata:
                audio_format = (self.metadata.get('QuickTime:Track:CompressorID') or 
                              self.metadata.get('QuickTime:Track1:CompressorID') or
                              self.metadata.get('QuickTime:CompressorID'))
                if audio_format:
                    self.metadata['QuickTime:AudioFormat'] = audio_format
            
            # QuickTime:Balance (promote from Track:Balance and format)
            balance = self.metadata.get('QuickTime:Balance')
            if balance is None:
                balance = (self.metadata.get('QuickTime:Track:Balance') or 
                          self.metadata.get('QuickTime:Track1:Balance'))
            if balance is not None:
                # Format Balance: Standard format shows 0 for center balance, not 0.000823974609375
                try:
                    balance_float = float(balance)
                    # If balance is very close to 0 (within 0.01), show as 0
                    if abs(balance_float) < 0.01:
                        self.metadata['QuickTime:Balance'] = 0
                    else:
                        self.metadata['QuickTime:Balance'] = balance
                except (ValueError, TypeError):
                    self.metadata['QuickTime:Balance'] = balance
            
            # QuickTime:BitDepth (alias from Track:BitDepth if not set at top level)
            if 'QuickTime:BitDepth' not in self.metadata:
                # Check all track variations
                bit_depth = (self.metadata.get('QuickTime:Track:BitDepth') or 
                           self.metadata.get('QuickTime:Track1:BitDepth') or
                           self.metadata.get('QuickTime:Track2:BitDepth'))
                if bit_depth:
                    self.metadata['QuickTime:BitDepth'] = bit_depth
                # If still not found, calculate from video format (24 bits for most video codecs)
                # This is a fallback - Standard format shows 24 for H.264/AVC video
                if 'QuickTime:BitDepth' not in self.metadata:
                    compressor_id = self.metadata.get('QuickTime:CompressorID')
                    if compressor_id and compressor_id.lower() in ('avc1', 'h264', 'mp4v'):
                        self.metadata['QuickTime:BitDepth'] = 24
            
            # QuickTime:NextTrackID - Standard format shows max track ID + 1, not the value from mvhd
            # Find all track IDs and use max + 1
            track_ids = []
            for key in self.metadata.keys():
                if ':TrackID' in key and key != 'QuickTime:NextTrackID':
                    track_id = self.metadata.get(key)
                    if isinstance(track_id, (int,)):
                        track_ids.append(track_id)
            if track_ids:
                max_track_id = max(track_ids)
                self.metadata['QuickTime:NextTrackID'] = max_track_id + 1
            
            # QuickTime:MatrixStructure (fix if it's close to identity but formatted wrong)
            # The matrix might be stored with different byte order or we're reading wrong values
            matrix = self.metadata.get('QuickTime:MatrixStructure')
            if matrix and isinstance(matrix, str):
                parts = matrix.split()
                if len(parts) == 9:
                    try:
                        values = [float(p) for p in parts]
                        # Check if values are [0, 0, 0, 1, 0, 0, 0, 1, 0] which should be identity [1, 0, 0, 0, 1, 0, 0, 0, 1]
                        # This might indicate we're reading the matrix in wrong order or format
                        if (abs(values[0]) < 0.01 and abs(values[1]) < 0.01 and abs(values[2]) < 0.01 and
                            abs(values[3] - 1.0) < 0.01 and abs(values[4]) < 0.01 and abs(values[5]) < 0.01 and
                            abs(values[6]) < 0.01 and abs(values[7] - 1.0) < 0.01 and abs(values[8]) < 0.01):
                            # This looks like identity matrix but with wrong element positions
                            # Reorder to identity: [1, 0, 0, 0, 1, 0, 0, 0, 1]
                            self.metadata['QuickTime:MatrixStructure'] = '1 0 0 0 1 0 0 0 1'
                    except (ValueError, IndexError):
                        pass
            
            # Composite:WB_RGGBLevels (from MakerNotes or calculated)
            if 'Composite:WB_RGGBLevels' not in self.metadata:
                # Try to get from MakerNotes (check multiple variants in priority order)
                # Standard format uses WB_RGGBLevelsAsShot as primary source
                wb_rggb = (self.metadata.get('MakerNotes:WB_RGGBLevelsAsShot') or  # Canon CR2 - primary
                          self.metadata.get('MakerNotes:WB_RGGBLevels') or 
                          self.metadata.get('MakerNotes:WB_RGGBLevelsAuto') or  # Canon CR2
                          self.metadata.get('MakerNotes:WB_RGGBLevelsMeasured') or  # Canon CR2
                          self.metadata.get('MakerNotes:WhiteBalance') or
                          self.metadata.get('EXIF:WhiteBalance'))
                
                # IMPROVEMENT (Build 1252): Also check for Kodak WB_RGBLevels (tag 0x001C) - RGB format, not RGGB
                # For Kodak DCR files, WB_RGBLevels is in RGB format (3 values), need to convert to RGGB (4 values)
                if not wb_rggb:
                    wb_rgb = (self.metadata.get('MakerNotes:WB_RGBLevels') or 
                              self.metadata.get('Kodak:WB_RGBLevels'))
                    if wb_rgb:
                        # Convert RGB to RGGB format: RGB -> RGGB (R, G, B -> R, G, G, B)
                        try:
                            if isinstance(wb_rgb, str):
                                parts = wb_rgb.split()
                                if len(parts) >= 3:
                                    r = float(parts[0])
                                    g = float(parts[1])
                                    b = float(parts[2])
                                    # Convert RGB to RGGB: R, G, B -> R, G, G, B
                                    wb_rggb = f"{r} {g} {g} {b}"
                            elif isinstance(wb_rgb, (list, tuple)) and len(wb_rgb) >= 3:
                                r = float(wb_rgb[0])
                                g = float(wb_rgb[1])
                                b = float(wb_rgb[2])
                                # Convert RGB to RGGB: R, G, B -> R, G, G, B
                                wb_rggb = f"{r} {g} {g} {b}"
                        except (ValueError, TypeError, IndexError):
                            pass
                
                if wb_rggb:
                    # Format as space-separated string if it's a list/tuple
                    if isinstance(wb_rggb, (list, tuple)):
                        wb_rggb = ' '.join(str(v) for v in wb_rggb)
                    self.metadata['Composite:WB_RGGBLevels'] = str(wb_rggb).strip()
            
            # Composite:RedBalance and Composite:BlueBalance (calculate AFTER WB_RGGBLevels is set)
            # These calculations need to run after Composite:WB_RGGBLevels is set to ensure proper fallback logic
            # Composite:BlueBalance (from WB_RGGBLevels, WB RGB Levels, or EXIF WB Levels)
            if 'Composite:BlueBalance' not in self.metadata:
                blue_balance_calculated = False
                wb_rggb = self.metadata.get('Composite:WB_RGGBLevels') or self.metadata.get('MakerNotes:WB_RGGBLevels')
                if wb_rggb and isinstance(wb_rggb, str) and wb_rggb.strip() != 'Auto':
                    # Only try WB_RGGBLevels if it's not "Auto" (which is not numeric)
                    try:
                        if isinstance(wb_rggb, str):
                            # Parse "1621 1024 1024 2427" format (RGGB) or "1621 1024 2427" format (RGB)
                            parts = wb_rggb.split()
                            if len(parts) >= 4:
                                # RGGB format: R, G1, G2, B
                                r = float(parts[0])
                                g1 = float(parts[1])
                                g2 = float(parts[2])
                                b = float(parts[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                            elif len(parts) == 3:
                                # RGB format (Kodak): R, G, B -> BlueBalance = B / G
                                r = float(parts[0])
                                g = float(parts[1])
                                b = float(parts[2])
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                        elif isinstance(wb_rggb, (list, tuple)):
                            if len(wb_rggb) >= 4:
                                # RGGB format: R, G1, G2, B
                                r = float(wb_rggb[0])
                                g1 = float(wb_rggb[1])
                                g2 = float(wb_rggb[2])
                                b = float(wb_rggb[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                            elif len(wb_rggb) == 3:
                                # RGB format (Kodak): R, G, B -> BlueBalance = B / G
                                r = float(wb_rggb[0])
                                g = float(wb_rggb[1])
                                b = float(wb_rggb[2])
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                
                # IMPROVEMENT (Build 1258): Enhanced RGB format lookup - check multiple tag name variations
                # IMPROVEMENT (Build 1261): Also check WB_RGBLevels without prefix and Composite:WB_RGBLevels
                if not blue_balance_calculated:
                    wb_rgb = (self.metadata.get('MakerNotes:WB_RGBLevels') or 
                              self.metadata.get('Kodak:WB_RGBLevels') or
                              self.metadata.get('EXIF:WB_RGBLevels') or
                              self.metadata.get('WB_RGBLevels') or
                              self.metadata.get('Composite:WB_RGBLevels'))
                    if wb_rgb:
                        try:
                            if isinstance(wb_rgb, str):
                                parts = wb_rgb.split()
                                if len(parts) >= 3:
                                    r = float(parts[0])
                                    g = float(parts[1])
                                    b = float(parts[2])
                                    if g > 0:
                                        blue_balance = b / g
                                        self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                        blue_balance_calculated = True
                            elif isinstance(wb_rgb, (list, tuple)) and len(wb_rgb) >= 3:
                                r = float(wb_rgb[0])
                                g = float(wb_rgb[1])
                                b = float(wb_rgb[2])
                                if g > 0:
                                    blue_balance = b / g
                                    self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                                    blue_balance_calculated = True
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                
                # Also try EXIF:WBBlueLevel and EXIF:WBGreenLevel (Panasonic RW2 format)
                # This fallback should work even if WB_RGGBLevels is "Auto" or doesn't exist
                if not blue_balance_calculated:
                    wb_blue = self.metadata.get('EXIF:WBBlueLevel') or self.metadata.get('MakerNotes:WBBlueLevel')
                    wb_green = self.metadata.get('EXIF:WBGreenLevel') or self.metadata.get('MakerNotes:WBGreenLevel')
                    # Check if both WB levels exist and are valid
                    if wb_blue is not None and wb_green is not None:
                        try:
                            # Convert to float - handle string values like "7", "16", "3"
                            blue_val = float(str(wb_blue).strip())
                            green_val = float(str(wb_green).strip())
                            if green_val > 0:
                                blue_balance = blue_val / green_val
                                self.metadata['Composite:BlueBalance'] = f"{blue_balance:.6f}"
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            # Silently continue if calculation fails
                            pass
            
            # Composite:RedBalance (from WB_RGGBLevels, WB RGB Levels, or EXIF WB Levels)
            if 'Composite:RedBalance' not in self.metadata:
                red_balance_calculated = False
                # IMPROVEMENT (Build 1258): Enhanced WB_RGGBLevels lookup - check multiple tag name variations
                # Check for RGGB format (4 values) first
                wb_rggb = (self.metadata.get('Composite:WB_RGGBLevels') or 
                           self.metadata.get('MakerNotes:WB_RGGBLevels') or
                           self.metadata.get('EXIF:WB_RGGBLevels'))
                if wb_rggb and isinstance(wb_rggb, str) and wb_rggb.strip() != 'Auto':
                    # Only try WB_RGGBLevels if it's not "Auto" (which is not numeric)
                    try:
                        if isinstance(wb_rggb, str):
                            # Parse "1621 1024 1024 2427" format (RGGB) or "1621 1024 2427" format (RGB)
                            parts = wb_rggb.split()
                            if len(parts) >= 4:
                                # RGGB format: R, G1, G2, B
                                r = float(parts[0])
                                g1 = float(parts[1])
                                g2 = float(parts[2])
                                b = float(parts[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                            elif len(parts) == 3:
                                # RGB format (Kodak): R, G, B -> RedBalance = R / G
                                r = float(parts[0])
                                g = float(parts[1])
                                b = float(parts[2])
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                        elif isinstance(wb_rggb, (list, tuple)):
                            if len(wb_rggb) >= 4:
                                # RGGB format: R, G1, G2, B
                                r = float(wb_rggb[0])
                                g1 = float(wb_rggb[1])
                                g2 = float(wb_rggb[2])
                                b = float(wb_rggb[3])
                                g = (g1 + g2) / 2.0
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                            elif len(wb_rggb) == 3:
                                # RGB format (Kodak): R, G, B -> RedBalance = R / G
                                r = float(wb_rggb[0])
                                g = float(wb_rggb[1])
                                b = float(wb_rggb[2])
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
                
                # IMPROVEMENT (Build 1258): Enhanced RGB format lookup - check multiple tag name variations
                # IMPROVEMENT (Build 1261): Also check WB_RGBLevels without prefix and Composite:WB_RGBLevels
                if not red_balance_calculated:
                    wb_rgb = (self.metadata.get('MakerNotes:WB_RGBLevels') or 
                              self.metadata.get('Kodak:WB_RGBLevels') or
                              self.metadata.get('EXIF:WB_RGBLevels') or
                              self.metadata.get('WB_RGBLevels') or
                              self.metadata.get('Composite:WB_RGBLevels'))
                    if wb_rgb:
                        try:
                            if isinstance(wb_rgb, str):
                                parts = wb_rgb.split()
                                if len(parts) >= 3:
                                    r = float(parts[0])
                                    g = float(parts[1])
                                    b = float(parts[2])
                                    if g > 0:
                                        red_balance = r / g
                                        self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                        red_balance_calculated = True
                            elif isinstance(wb_rgb, (list, tuple)) and len(wb_rgb) >= 3:
                                r = float(wb_rgb[0])
                                g = float(wb_rgb[1])
                                b = float(wb_rgb[2])
                                if g > 0:
                                    red_balance = r / g
                                    self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                                    red_balance_calculated = True
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                
                # Also try EXIF:WBRedLevel and EXIF:WBGreenLevel (Panasonic RW2 format)
                # This fallback should work even if WB_RGGBLevels is "Auto" or doesn't exist
                if not red_balance_calculated:
                    wb_red = self.metadata.get('EXIF:WBRedLevel') or self.metadata.get('MakerNotes:WBRedLevel')
                    wb_green = self.metadata.get('EXIF:WBGreenLevel') or self.metadata.get('MakerNotes:WBGreenLevel')
                    # Check if both WB levels exist and are valid
                    if wb_red is not None and wb_green is not None:
                        try:
                            # Convert to float - handle string values like "7", "16", "3"
                            red_val = float(str(wb_red).strip())
                            green_val = float(str(wb_green).strip())
                            if green_val > 0:
                                red_balance = red_val / green_val
                                self.metadata['Composite:RedBalance'] = f"{red_balance:.6f}"
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            # Silently continue if calculation fails
                            pass
            
            # Composite:DriveMode (from MakerNotes)
            if 'Composite:DriveMode' not in self.metadata:
                drive_mode = (self.metadata.get('MakerNotes:DriveMode') or 
                             self.metadata.get('MakerNotes:CanonDriveMode') or
                             self.metadata.get('MakerNotes:ContinuousDrive'))
                
                # Also check SelfTimer - if SelfTimer exists, it's "Self-timer Operation"
                self_timer = self.metadata.get('MakerNotes:SelfTimer')
                if self_timer:
                    # SelfTimer exists - format as "Self-timer Operation"
                    try:
                        # SelfTimer might be a number (seconds) or string
                        timer_val = str(self_timer)
                        if timer_val and timer_val.strip() not in ('', '0', 'Off', 'None'):
                            self.metadata['Composite:DriveMode'] = 'Self-timer Operation'
                            drive_mode = None  # Don't use other drive mode if SelfTimer is set
                    except:
                        pass
                
                if drive_mode:
                    # Format drive mode to standard format format
                    drive_str = str(drive_mode)
                    if drive_str == 'Single':
                        drive_str = 'Single'
                    elif drive_str == 'Continuous':
                        drive_str = 'Continuous'
                    elif drive_str == 'Self-timer':
                        drive_str = 'Self-timer Operation'
                    elif drive_str.isdigit():
                        # Drive mode might be numeric - map common values
                        drive_int = int(drive_str)
                        if drive_int == 0:
                            drive_str = 'Single'
                        elif drive_int == 1:
                            drive_str = 'Continuous'
                        elif drive_int == 2:
                            drive_str = 'Self-timer Operation'
                        elif drive_int == 10:
                            drive_str = 'Self-timer Operation'
                    self.metadata['Composite:DriveMode'] = drive_str
            
            # Composite:FileNumber (from MakerNotes)
            if 'Composite:FileNumber' not in self.metadata:
                file_number = (self.metadata.get('MakerNotes:FileNumber') or 
                              self.metadata.get('MakerNotes:CanonFileNumber') or
                              self.metadata.get('MakerNotes:FileIndex'))
                dir_index = (self.metadata.get('MakerNotes:DirectoryIndex') or
                            self.metadata.get('MakerNotes:CanonDirectoryIndex'))
                
                if file_number and dir_index:
                    # Format file number to standard format format (e.g., "100-0028")
                    file_str = str(file_number).strip()
                    dir_str = str(dir_index).strip()
                    # Pad file number to 4 digits
                    try:
                        file_int = int(file_str)
                        file_str = f"{file_int:04d}"
                    except:
                        file_str = file_str.zfill(4)
                    self.metadata['Composite:FileNumber'] = f"{dir_str}-{file_str}"
                elif file_number:
                    # Only file number available
                    file_str = str(file_number).strip()
                    self.metadata['Composite:FileNumber'] = file_str
                elif dir_index:
                    # Only directory index available - use as-is
                    self.metadata['Composite:FileNumber'] = str(dir_index).strip()
            
            # Composite:ShootingMode (from MakerNotes)
            # Recalculate if current value is numeric (likely incorrect) or if not set
            current_shooting_mode = self.metadata.get('Composite:ShootingMode')
            should_recalc = (current_shooting_mode is None or 
                           (isinstance(current_shooting_mode, (int, float)) and current_shooting_mode < 10) or
                           (isinstance(current_shooting_mode, str) and current_shooting_mode.strip().isdigit()))
            
            if should_recalc:
                shooting_mode = (self.metadata.get('MakerNotes:ShootingMode') or 
                                self.metadata.get('MakerNotes:CanonExposureMode') or
                                self.metadata.get('EXIF:ExposureMode'))
                if shooting_mode:
                    # Use the actual mode name, not numeric value
                    shooting_str = str(shooting_mode).strip()
                    # If it's a numeric string, try to map it
                    if shooting_str.isdigit():
                        mode_map = {'0': 'Auto', '1': 'Manual', '2': 'Aperture-priority', 
                                   '3': 'Shutter-priority', '4': 'Program'}
                        shooting_str = mode_map.get(shooting_str, shooting_str)
                    self.metadata['Composite:ShootingMode'] = shooting_str
            
            # Composite:Lens (from MakerNotes or EXIF, or calculated from focal length range)
            if 'Composite:Lens' not in self.metadata:
                lens = (self.metadata.get('MakerNotes:Lens') or 
                       self.metadata.get('EXIF:LensModel') or
                       self.metadata.get('EXIF:LensType'))
                
                # Try to extract focal length range from LensModel or LensID if they contain range info
                # Example: "17-50mm", "17 - 50 mm", "Tamron AF 17-50mm f/2.8"
                if lens:
                    import re
                    # Check if lens string contains focal length range (e.g., "17-50mm", "17 - 50 mm")
                    range_match = re.search(r'(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*mm', str(lens), re.IGNORECASE)
                    if range_match:
                        min_val = float(range_match.group(1))
                        max_val = float(range_match.group(2))
                        if min_val > 0 and max_val > 0:
                            if min_val == max_val:
                                lens = f"{min_val:.1f} mm"
                            else:
                                lens = f"{min_val:.1f} - {max_val:.1f} mm"
                    else:
                        # Check for single focal length (e.g., "50mm", "50 mm")
                        single_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', str(lens), re.IGNORECASE)
                        if single_match:
                            focal_val = float(single_match.group(1))
                            if focal_val > 0:
                                lens = f"{focal_val:.1f} mm"
                
                # If not found, try to calculate from MinFocalLength and MaxFocalLength (like standard format)
                if not lens:
                    min_fl = self.metadata.get('MakerNotes:MinFocalLength') or self.metadata.get('EXIF:MinFocalLength')
                    max_fl = self.metadata.get('MakerNotes:MaxFocalLength') or self.metadata.get('EXIF:MaxFocalLength')
                    if min_fl and max_fl:
                        try:
                            import re
                            # Extract numeric values
                            min_match = re.search(r'[\d.]+', str(min_fl))
                            max_match = re.search(r'[\d.]+', str(max_fl))
                            if min_match and max_match:
                                min_val = float(min_match.group())
                                max_val = float(max_match.group())
                                if min_val > 0 and max_val > 0:
                                    if min_val == max_val:
                                        lens = f"{min_val:.1f} mm"
                                    else:
                                        lens = f"{min_val:.1f} - {max_val:.1f} mm"
                        except (ValueError, TypeError):
                            pass
                    
                    # Fallback: If MinFocalLength/MaxFocalLength not available, use current FocalLength
                    # This provides at least some lens information when full range isn't available
                    if not lens:
                        focal_length = (self.metadata.get('Composite:FocalLength') or 
                                      self.metadata.get('EXIF:FocalLength') or
                                      self.metadata.get('FocalLength'))
                        if focal_length:
                            try:
                                import re
                                # Extract numeric value from focal length string (e.g., "17.0 mm" -> 17.0)
                                focal_match = re.search(r'[\d.]+', str(focal_length))
                                if focal_match:
                                    focal_val = float(focal_match.group())
                                    if focal_val > 0:
                                        lens = f"{focal_val:.1f} mm"
                            except (ValueError, TypeError):
                                pass
                
                if lens:
                    self.metadata['Composite:Lens'] = str(lens)
            
            # Composite:LensID (from MakerNotes)
            if 'Composite:LensID' not in self.metadata:
                lens_id = (self.metadata.get('MakerNotes:LensID') or 
                          self.metadata.get('MakerNotes:CanonLensID') or
                          self.metadata.get('MakerNotes:LensType') or  # Canon (e.g., "Canon EF 28-70mm f/2.8L USM or Other Lens")
                          self.metadata.get('MakerNotes:CameraLensType') or  # Panasonic
                          self.metadata.get('MakerNotes:LensModel'))  # Panasonic/Nikon
                if lens_id:
                    lens_id_str = str(lens_id).strip()
                    # Remove "or Other Lens" suffix if present (Canon format)
                    if ' or Other Lens' in lens_id_str:
                        lens_id_str = lens_id_str.replace(' or Other Lens', '')
                    self.metadata['Composite:LensID'] = lens_id_str
            
            # Composite:AdvancedSceneMode (from MakerNotes - Panasonic)
            if 'Composite:AdvancedSceneMode' not in self.metadata:
                advanced_scene_mode = (self.metadata.get('MakerNotes:AdvancedSceneMode') or
                                     self.metadata.get('MakerNotes:PanasonicAdvancedSceneMode'))
                if advanced_scene_mode:
                    self.metadata['Composite:AdvancedSceneMode'] = str(advanced_scene_mode)
            
            # Composite:Lens35efl (35mm equivalent lens range)
            # Format: "17.0 - 50.0 mm (35 mm equivalent: 26.7 - 78.6 mm)"
            if 'Composite:Lens35efl' not in self.metadata:
                try:
                    import re
                    # Get MinFocalLength and MaxFocalLength directly from MakerNotes or EXIF
                    min_fl = self.metadata.get('MakerNotes:MinFocalLength') or self.metadata.get('EXIF:MinFocalLength')
                    max_fl = self.metadata.get('MakerNotes:MaxFocalLength') or self.metadata.get('EXIF:MaxFocalLength')
                    
                    # Extract numeric values
                    min_val = None
                    max_val = None
                    if min_fl:
                        min_match = re.search(r'[\d.]+', str(min_fl))
                        if min_match:
                            min_val = float(min_match.group())
                    if max_fl:
                        max_match = re.search(r'[\d.]+', str(max_fl))
                        if max_match:
                            max_val = float(max_match.group())
                    
                    # If MinFocalLength/MaxFocalLength not available, try to extract from Composite:Lens string
                    if (not min_val or not max_val) and 'Composite:Lens' in self.metadata:
                        lens_str = str(self.metadata['Composite:Lens'])
                        # Try to match "17.0 - 50.0 mm" or "17.0-50.0 mm" format
                        lens_range_match = re.search(r'([\d.]+)\s*-\s*([\d.]+)', lens_str)
                        if lens_range_match:
                            if not min_val:
                                min_val = float(lens_range_match.group(1))
                            if not max_val:
                                max_val = float(lens_range_match.group(2))
                    
                    # If we have both values, calculate 35mm equivalent
                    if min_val and max_val and min_val > 0 and max_val > 0:
                        scale_factor = self.metadata.get('Composite:ScaleFactor35efl')
                        if scale_factor:
                            try:
                                sf = float(scale_factor)
                                if sf > 0:
                                    min_fl35 = min_val * sf
                                    max_fl35 = max_val * sf
                                    self.metadata['Composite:Lens35efl'] = f"{min_val:.1f} - {max_val:.1f} mm (35 mm equivalent: {min_fl35:.1f} - {max_fl35:.1f} mm)"
                            except (ValueError, TypeError):
                                pass
                        else:
                            # If no scale factor, try to use FocalLengthIn35mmFilm if available
                            focal_35 = self.metadata.get('EXIF:FocalLengthIn35mmFilm')
                            if focal_35:
                                try:
                                    fl35_match = re.search(r'[\d.]+', str(focal_35))
                                    if fl35_match:
                                        fl35 = float(fl35_match.group())
                                        # Estimate scale factor from current focal length
                                        current_fl = self.metadata.get('EXIF:FocalLength')
                                        if current_fl:
                                            fl_match = re.search(r'[\d.]+', str(current_fl))
                                            if fl_match:
                                                fl = float(fl_match.group())
                                                if fl > 0:
                                                    est_sf = fl35 / fl
                                                    min_fl35 = min_val * est_sf
                                                    max_fl35 = max_val * est_sf
                                                    self.metadata['Composite:Lens35efl'] = f"{min_val:.1f} - {max_val:.1f} mm (35 mm equivalent: {min_fl35:.1f} - {max_fl35:.1f} mm)"
                                except (ValueError, TypeError):
                                    pass
                except (ValueError, TypeError):
                    pass
            
            # Composite:Model2 (combines Make and Model - e.g., "Canon EOS 5D Mark III")
            if 'Composite:Model2' not in self.metadata and 'Model2' not in self.metadata:
                make = self.metadata.get('EXIF:Make') or self.metadata.get('Make')
                model = self.metadata.get('EXIF:Model') or self.metadata.get('Model')
                if make and model:
                    make_str = str(make).strip()
                    model_str = str(model).strip()
                    # Combine Make and Model (standard format: "Make Model")
                    if make_str and model_str:
                        model2_value = f"{make_str} {model_str}"
                        self.metadata['Composite:Model2'] = model2_value
                        # Also add as Model2 (without Composite: prefix) for compatibility
                        self.metadata['Model2'] = model2_value
                        # standard outputs Model2 as EXIF:Model2, so add that alias too
                        self.metadata['EXIF:Model2'] = model2_value
            
            # Composite:DateTimeOriginal, Composite:CreateDate, Composite:ModifyDate (Standard format shows these as composite tags)
            # These combine the date/time with subseconds if available
            if 'Composite:DateTimeOriginal' not in self.metadata:
                dt_original = self.metadata.get('EXIF:DateTimeOriginal')
                subsec_original = self.metadata.get('EXIF:SubSecTimeOriginal')
                if dt_original:
                    if subsec_original:
                        # Combine date/time with subseconds (format: "YYYY:MM:DD HH:MM:SS.sss")
                        try:
                            dt_str = str(dt_original)
                            if '.' not in dt_str and subsec_original:
                                # Add subseconds if not already present
                                subsec_str = str(subsec_original).zfill(3)[:3]  # Pad to 3 digits, max 3
                                self.metadata['Composite:DateTimeOriginal'] = f"{dt_str}.{subsec_str}"
                            else:
                                self.metadata['Composite:DateTimeOriginal'] = dt_str
                        except Exception:
                            self.metadata['Composite:DateTimeOriginal'] = dt_original
                    else:
                        self.metadata['Composite:DateTimeOriginal'] = dt_original
            
            if 'Composite:CreateDate' not in self.metadata:
                create_date = self.metadata.get('EXIF:CreateDate') or self.metadata.get('XMP:CreateDate')
                subsec_create = self.metadata.get('EXIF:SubSecTime')
                if create_date:
                    if subsec_create:
                        try:
                            dt_str = str(create_date)
                            if '.' not in dt_str and subsec_create:
                                subsec_str = str(subsec_create).zfill(3)[:3]
                                self.metadata['Composite:CreateDate'] = f"{dt_str}.{subsec_str}"
                            else:
                                self.metadata['Composite:CreateDate'] = dt_str
                        except Exception:
                            self.metadata['Composite:CreateDate'] = create_date
                    else:
                        self.metadata['Composite:CreateDate'] = create_date
            
            if 'Composite:ModifyDate' not in self.metadata:
                modify_date = self.metadata.get('EXIF:ModifyDate') or self.metadata.get('EXIF:DateTime') or self.metadata.get('XMP:ModifyDate')
                subsec_modify = self.metadata.get('EXIF:SubSecTimeDigitized')
                if modify_date:
                    if subsec_modify:
                        try:
                            dt_str = str(modify_date)
                            if '.' not in dt_str and subsec_modify:
                                subsec_str = str(subsec_modify).zfill(3)[:3]
                                self.metadata['Composite:ModifyDate'] = f"{dt_str}.{subsec_str}"
                            else:
                                self.metadata['Composite:ModifyDate'] = dt_str
                        except Exception:
                            self.metadata['Composite:ModifyDate'] = modify_date
                    else:
                        self.metadata['Composite:ModifyDate'] = modify_date
            
            # Composite:DateTime (general DateTime - Standard format shows this as an alias for ModifyDate/DateTime)
            # This is typically the same as ModifyDate but standard format provides it as a separate composite tag
            if 'Composite:DateTime' not in self.metadata:
                date_time = (self.metadata.get('EXIF:DateTime') or 
                           self.metadata.get('EXIF:ModifyDate') or 
                           self.metadata.get('XMP:ModifyDate') or
                           self.metadata.get('Composite:ModifyDate'))
                if date_time:
                    self.metadata['Composite:DateTime'] = date_time
            
            # Composite:GPSDateTime (combines GPSDateStamp and GPSTimeStamp if both are available)
            if 'Composite:GPSDateTime' not in self.metadata:
                gps_date = self.metadata.get('GPS:GPSDateStamp') or self.metadata.get('GPSDateStamp')
                gps_time = self.metadata.get('GPS:GPSTimeStamp') or self.metadata.get('GPSTimeStamp')
                if gps_date and gps_time:
                    try:
                        # Format GPSDateTime as "YYYY:MM:DD HH:MM:SS" (combines date and time)
                        # GPSDateStamp format: "YYYY:MM:DD"
                        # GPSTimeStamp format: tuple (HH, MM, SS) or "HH:MM:SS"
                        date_str = str(gps_date).strip()
                        if isinstance(gps_time, tuple) and len(gps_time) >= 3:
                            # GPSTimeStamp is a tuple (HH, MM, SS) - may be rational numbers
                            h = gps_time[0]
                            m = gps_time[1] if len(gps_time) > 1 else 0
                            s = gps_time[2] if len(gps_time) > 2 else 0
                            # Handle rational numbers
                            if isinstance(h, tuple) and len(h) == 2:
                                h = h[0] / h[1] if h[1] != 0 else 0
                            if isinstance(m, tuple) and len(m) == 2:
                                m = m[0] / m[1] if m[1] != 0 else 0
                            if isinstance(s, tuple) and len(s) == 2:
                                s = s[0] / s[1] if s[1] != 0 else 0
                            time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
                        elif isinstance(gps_time, str):
                            time_str = str(gps_time).strip()
                        else:
                            time_str = str(gps_time)
                        
                        # Combine date and time
                        self.metadata['Composite:GPSDateTime'] = f"{date_str} {time_str}"
                    except (ValueError, TypeError, IndexError):
                        pass
            
            # Composite:DigitalCreationDateTime (from IPTC - combines DigitalCreationDate and DigitalCreationTime)
            if 'Composite:DigitalCreationDateTime' not in self.metadata:
                digital_date = (self.metadata.get('IPTC:DigitalCreationDate') or 
                              self.metadata.get('IPTC:DateCreated') or
                              self.metadata.get('IPTC:Date'))
                digital_time = (self.metadata.get('IPTC:DigitalCreationTime') or 
                              self.metadata.get('IPTC:TimeCreated') or
                              self.metadata.get('IPTC:Time'))
                if digital_date and digital_time:
                    try:
                        date_str = str(digital_date).strip()
                        time_str = str(digital_time).strip()
                        # Format as "YYYY:MM:DD HH:MM:SS" or "YYYY-MM-DD HH:MM:SS"
                        self.metadata['Composite:DigitalCreationDateTime'] = f"{date_str} {time_str}"
                    except (ValueError, TypeError):
                        pass
            
            # Composite:SubSecCreateDate, SubSecDateTimeOriginal, SubSecModifyDate
            # These are typically in EXIF but may need to be constructed from DateTime + SubSecTime
            # Format: "2010:03:03 21:50:57.67" (2 digits for subseconds to standard format)
            for tag_name, base_tag, subsec_tag in [
                ('Composite:SubSecCreateDate', 'EXIF:CreateDate', 'EXIF:SubSecTime'),
                ('Composite:SubSecDateTimeOriginal', 'EXIF:DateTimeOriginal', 'EXIF:SubSecTimeOriginal'),
                ('Composite:SubSecModifyDate', 'EXIF:ModifyDate', 'EXIF:SubSecTimeDigitized')
            ]:
                if tag_name not in self.metadata:
                    base_date = self.metadata.get(base_tag)
                    subsec = self.metadata.get(subsec_tag)
                    if base_date and subsec:
                        try:
                            # Format: "2010:03:03 21:50:57.67" (2 digits for subseconds)
                            if isinstance(subsec, (int, float)):
                                # Convert to 2-digit string (e.g., 67 -> "67", 7 -> "07")
                                subsec_int = int(subsec)
                                subsec_str = f".{subsec_int:02d}" if subsec_int < 100 else f".{subsec_int}"
                            else:
                                subsec_str_val = str(subsec).strip()
                                # If it's already a number string, format it
                                try:
                                    subsec_int = int(float(subsec_str_val))
                                    subsec_str = f".{subsec_int:02d}" if subsec_int < 100 else f".{subsec_int}"
                                except (ValueError, TypeError):
                                    subsec_str = f".{subsec_str_val[:2]}" if len(subsec_str_val) >= 2 else f".{subsec_str_val}"
                            
                            # Ensure base_date doesn't already have subseconds
                            base_date_str = str(base_date)
                            if '.' not in base_date_str:
                                self.metadata[tag_name] = f"{base_date_str}{subsec_str}"
                            else:
                                # Already has subseconds, use as-is
                                self.metadata[tag_name] = base_date_str
                        except (ValueError, TypeError):
                            pass
            
            # Composite:Flash (decode EXIF:Flash bitmask)
            # EXIF Flash bitmask: bit 0 = fired, bit 1 = return, bit 2 = mode, bit 3 = function, bit 4 = red-eye
            if 'Composite:Flash' not in self.metadata:
                flash = self.metadata.get('EXIF:Flash')
                if flash is not None:
                    try:
                        flash_val = int(flash)
                        # Decode flash bitmask
                        flash_fired = "Yes" if (flash_val & 0x01) else "No"
                        flash_return = "Return detected" if (flash_val & 0x02) else "No return"
                        flash_mode_map = {
                            0: "Unknown",
                            1: "Compulsory",
                            2: "No flash",
                            3: "Auto"
                        }
                        flash_mode = flash_mode_map.get((flash_val >> 2) & 0x03, "Unknown")
                        flash_function = "Yes" if (flash_val & 0x08) else "No"
                        flash_red_eye = "Yes" if (flash_val & 0x10) else "No"
                        
                        # Format as "Fired, Return detected, Compulsory, Function, Red-eye"
                        flash_parts = [flash_fired, flash_return, flash_mode]
                        if flash_function == "Yes":
                            flash_parts.append("Function")
                        if flash_red_eye == "Yes":
                            flash_parts.append("Red-eye")
                        
                        self.metadata['Composite:Flash'] = ", ".join(flash_parts)
                        self.metadata['Composite:FlashFired'] = flash_fired
                        self.metadata['Composite:FlashReturn'] = flash_return
                        self.metadata['Composite:FlashMode'] = flash_mode
                        self.metadata['Composite:FlashFunction'] = flash_function
                        self.metadata['Composite:FlashRedEyeMode'] = flash_red_eye
                    except (ValueError, TypeError):
                        pass
            
            # Composite:CFAPattern (for RAW files with CFA pattern)
            if 'Composite:CFAPattern' not in self.metadata:
                cfa_pattern = self.metadata.get('EXIF:CFAPattern')
                if cfa_pattern is not None:
                    try:
                        # CFAPattern is typically stored as 2x2 or larger pattern
                        # Format as hex string or pattern description
                        if isinstance(cfa_pattern, (tuple, list)) and len(cfa_pattern) >= 2:
                            # Format as hex values
                            if len(cfa_pattern) == 2:
                                # Two 32-bit values
                                hex_str = f"{cfa_pattern[0]:08X} {cfa_pattern[1]:08X}"
                                self.metadata['Composite:CFAPattern'] = hex_str
                            else:
                                # Pattern array
                                hex_str = " ".join(f"{v:02X}" if isinstance(v, int) else str(v) for v in cfa_pattern)
                                self.metadata['Composite:CFAPattern'] = hex_str
                        elif isinstance(cfa_pattern, bytes):
                            # Bytes format
                            hex_str = " ".join(f"{b:02X}" for b in cfa_pattern)
                            self.metadata['Composite:CFAPattern'] = hex_str
                        else:
                            # String or other format
                            self.metadata['Composite:CFAPattern'] = str(cfa_pattern)
                    except (ValueError, TypeError):
                        pass
            
            # Promote Audio:WMA tags to ASF: namespace (Standard format shows WMA tags with ASF: prefix)
            # This ensures all WMA tags are available with the ASF: prefix
            file_ext = self.file_path.suffix.lower()
            if file_ext == '.wma':
                asf_tag_mappings = {
                    'Audio:WMA:FileLength': 'ASF:FileLength',
                    'Audio:WMA:CreationDate': 'ASF:CreationDate',
                    'Audio:WMA:Duration': 'ASF:Duration',
                    'Audio:WMA:SendDuration': 'ASF:SendDuration',
                    'Audio:WMA:Preroll': 'ASF:Preroll',
                    'Audio:WMA:MinPacketSize': 'ASF:MinPacketSize',
                    'Audio:WMA:MaxPacketSize': 'ASF:MaxPacketSize',
                    'Audio:WMA:MaxBitrate': 'ASF:MaxBitrate',
                    'Audio:WMA:StreamType': 'ASF:StreamType',
                    'Audio:WMA:ErrorCorrectionType': 'ASF:ErrorCorrectionType',
                    'Audio:WMA:StreamNumber': 'ASF:StreamNumber',
                    'Audio:WMA:AudioCodecID': 'ASF:AudioCodecID',
                    'Audio:WMA:AudioCodecName': 'ASF:AudioCodecName',
                    'Audio:WMA:AudioCodecDescription': 'ASF:AudioCodecDescription',
                    'Audio:WMA:AudioChannels': 'ASF:AudioChannels',
                    'Audio:WMA:AudioSampleRate': 'ASF:AudioSampleRate',
                    'Audio:WMA:EncodingSettings': 'ASF:EncodingSettings',
                }
                for audio_key, asf_key in asf_tag_mappings.items():
                    if audio_key in self.metadata and asf_key not in self.metadata:
                        self.metadata[asf_key] = self.metadata[audio_key]
                
                # Also promote any other Audio:WMA tags that don't have explicit mappings
                for key in list(self.metadata.keys()):
                    if key.startswith('Audio:WMA:') and key not in asf_tag_mappings:
                        asf_key = key.replace('Audio:WMA:', 'ASF:')
                        if asf_key not in self.metadata:
                            self.metadata[asf_key] = self.metadata[key]
            
            # Add aliases for composite tags without Composite: prefix (Standard format shows these both ways)
            # This standard format's behavior where composite tags are available with and without prefix
            composite_aliases = {
                'Composite:Aperture': 'Aperture',
                'Composite:ApertureValue': 'ApertureValue',
                'Composite:BlueBalance': 'BlueBalance',
                'Composite:RedBalance': 'RedBalance',
                'Composite:ShutterSpeed': 'ShutterSpeed',
                'Composite:ISO': 'ISO',
                'Composite:FocalLength': 'FocalLength',
                'Composite:FocalLength35efl': 'FocalLength35efl',
                'Composite:ImageSize': 'ImageSize',
                'Composite:ImageWidth': 'ImageWidth',
                'Composite:ImageHeight': 'ImageHeight',
                'Composite:Megapixels': 'Megapixels',
                'Composite:GPSPosition': 'GPSPosition',
                'Composite:GPSLatitude': 'GPSLatitude',
                'Composite:GPSLongitude': 'GPSLongitude',
                'Composite:Duration': 'Duration',
                'Composite:Rotation': 'Rotation',
                'Composite:Model2': 'Model2',
                'Composite:ScaleFactor35efl': 'ScaleFactor35efl',
                'Composite:CircleOfConfusion': 'CircleOfConfusion',
                'Composite:FOV': 'FOV',
                'Composite:DOF': 'DOF',
                'Composite:HyperfocalDistance': 'HyperfocalDistance',
                'Composite:LightValue': 'LightValue',
                'Composite:Lens': 'Lens',
                'Composite:LensID': 'LensID',
                'Composite:LensSpec': 'LensSpec',
                'Composite:AdvancedSceneMode': 'AdvancedSceneMode',
                'Composite:DateTimeOriginal': 'DateTimeOriginal',
                'Composite:CreateDate': 'CreateDate',
                'Composite:ModifyDate': 'ModifyDate',
                'Composite:DateTime': 'DateTime',
                'Composite:GPSDateTime': 'GPSDateTime',
                'Composite:DigitalCreationDateTime': 'DigitalCreationDateTime',
                'Composite:SubSecCreateDate': 'SubSecCreateDate',
                'Composite:SubSecDateTimeOriginal': 'SubSecDateTimeOriginal',
                'Composite:SubSecModifyDate': 'SubSecModifyDate',
                'Composite:Flash': 'Flash',
                'Composite:FlashFired': 'FlashFired',
                'Composite:FlashReturn': 'FlashReturn',
                'Composite:FlashMode': 'FlashMode',
                'Composite:FlashFunction': 'FlashFunction',
                'Composite:FlashRedEyeMode': 'FlashRedEyeMode',
                'Composite:CFAPattern': 'CFAPattern',
            }
            for composite_key, alias_key in composite_aliases.items():
                if composite_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[composite_key]
            
            # Add additional aliases that Standard format shows (some composite tags have multiple aliases)
            # ApertureValue is an alias for Aperture (same value)
            if 'Composite:Aperture' in self.metadata and 'ApertureValue' not in self.metadata:
                self.metadata['ApertureValue'] = self.metadata['Composite:Aperture']
            # FNumber is an alias for Aperture (same value)
            if 'Composite:Aperture' in self.metadata and 'FNumber' not in self.metadata:
                self.metadata['FNumber'] = self.metadata['Composite:Aperture']
            # ExposureTime is an alias for ShutterSpeed (same value)
            if 'Composite:ShutterSpeed' in self.metadata and 'ExposureTime' not in self.metadata:
                self.metadata['ExposureTime'] = self.metadata['Composite:ShutterSpeed']
            # FocalLength from EXIF:FocalLength if Composite:FocalLength doesn't exist
            if 'Composite:FocalLength' not in self.metadata:
                focal_length = self.metadata.get('EXIF:FocalLength')
                if focal_length:
                    try:
                        if isinstance(focal_length, tuple) and len(focal_length) == 2:
                            fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                        elif isinstance(focal_length, str):
                            import re
                            match = re.search(r'[\d.]+', focal_length)
                            fl = float(match.group()) if match else None
                        else:
                            fl = float(focal_length)
                        if fl and fl > 0:
                            self.metadata['Composite:FocalLength'] = f"{fl:.1f} mm"
                            if 'FocalLength' not in self.metadata:
                                self.metadata['FocalLength'] = self.metadata['Composite:FocalLength']
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass
        
            # Add aliases for common EXIF tags without EXIF: prefix (Standard format shows these both ways)
            # ImageWidth and ImageHeight aliases - check multiple sources
            if 'ImageWidth' not in self.metadata:
                image_width = (self.metadata.get('EXIF:ImageWidth') or 
                              self.metadata.get('File:ImageWidth') or
                              self.metadata.get('EXIF:ExifImageWidth') or
                              self.metadata.get('EXIF:PixelXDimension'))
                if image_width:
                    self.metadata['ImageWidth'] = image_width
            if 'ImageHeight' not in self.metadata:
                image_height = (self.metadata.get('EXIF:ImageHeight') or 
                               self.metadata.get('File:ImageHeight') or
                               self.metadata.get('EXIF:ExifImageHeight') or
                               self.metadata.get('EXIF:PixelYDimension') or
                               self.metadata.get('EXIF:ImageLength'))
                if image_height:
                    self.metadata['ImageHeight'] = image_height
            if 'ImageLength' not in self.metadata:
                image_length = (self.metadata.get('EXIF:ImageLength') or
                               self.metadata.get('EXIF:ImageHeight'))
                if image_length:
                    self.metadata['ImageLength'] = image_length
            # DateTimeOriginal alias
            if 'EXIF:DateTimeOriginal' in self.metadata and 'DateTimeOriginal' not in self.metadata:
                self.metadata['DateTimeOriginal'] = self.metadata['EXIF:DateTimeOriginal']
            
            # Add aliases for other common EXIF tags without EXIF: prefix (Standard format shows these both ways)
            # Common tags that Standard format shows without prefix: Make, Model, Software, Artist, Copyright, DateTime, etc.
            # Also add reverse aliases: if tag exists without prefix, ensure EXIF: version exists too
            common_exif_aliases = {
                'EXIF:Make': 'Make',
                'EXIF:Model': 'Model',
                'EXIF:Software': 'Software',
                'EXIF:Artist': 'Artist',
                'EXIF:Copyright': 'Copyright',
                'EXIF:DateTime': 'DateTime',
                'EXIF:ModifyDate': 'ModifyDate',
                'EXIF:CreateDate': 'CreateDate',
                'EXIF:DateTimeDigitized': 'DateTimeDigitized',
                'EXIF:ISO': 'ISO',
                'EXIF:ImageWidth': 'ImageWidth',
                'EXIF:ImageHeight': 'ImageHeight',
                'EXIF:ExifImageWidth': 'ExifImageWidth',
                'EXIF:ExifImageHeight': 'ExifImageHeight',
                'EXIF:Orientation': 'Orientation',
                'EXIF:XResolution': 'XResolution',
                'EXIF:YResolution': 'YResolution',
                'EXIF:ResolutionUnit': 'ResolutionUnit',
                'EXIF:YCbCrPositioning': 'YCbCrPositioning',
                'EXIF:YCbCrSubSampling': 'YCbCrSubSampling',
                'EXIF:ColorSpace': 'ColorSpace',
                'EXIF:ExifVersion': 'ExifVersion',
                'EXIF:FlashpixVersion': 'FlashpixVersion',
                'EXIF:ComponentsConfiguration': 'ComponentsConfiguration',
                'EXIF:CompressedBitsPerPixel': 'CompressedBitsPerPixel',
                'EXIF:BrightnessValue': 'BrightnessValue',
                'EXIF:ExposureBiasValue': 'ExposureBiasValue',
                'EXIF:MaxApertureValue': 'MaxApertureValue',
                'EXIF:SubjectDistance': 'SubjectDistance',
                'EXIF:MeteringMode': 'MeteringMode',
                'EXIF:LightSource': 'LightSource',
                'EXIF:Flash': 'Flash',
                'EXIF:WhiteBalance': 'WhiteBalance',
                'EXIF:DigitalZoomRatio': 'DigitalZoomRatio',
                'EXIF:FocalLengthIn35mmFilm': 'FocalLengthIn35mmFilm',
                'EXIF:SceneCaptureType': 'SceneCaptureType',
                'EXIF:GainControl': 'GainControl',
                'EXIF:Contrast': 'Contrast',
                'EXIF:Saturation': 'Saturation',
                'EXIF:Sharpness': 'Sharpness',
                'EXIF:SubjectDistanceRange': 'SubjectDistanceRange',
                'EXIF:ImageDescription': 'ImageDescription',
                'EXIF:UserComment': 'UserComment',
                'EXIF:ExposureProgram': 'ExposureProgram',
                'EXIF:ISOSpeedRatings': 'ISOSpeedRatings',
                'EXIF:ExposureMode': 'ExposureMode',
                'EXIF:ExposureCompensation': 'ExposureCompensation',
                'EXIF:ShutterSpeedValue': 'ShutterSpeedValue',
                'EXIF:ExposureTime': 'ExposureTime',
                'EXIF:FNumber': 'FNumber',
                'EXIF:FocalLength': 'FocalLength',
                'EXIF:ExifImageWidth': 'ExifImageWidth',
                'EXIF:ExifImageHeight': 'ExifImageHeight',
                'EXIF:BodySerialNumber': 'BodySerialNumber',
                'EXIF:CustomRendered': 'CustomRendered',
                'EXIF:DeviceSettingDescription': 'DeviceSettingDescription',
            }
            for exif_key, alias_key in common_exif_aliases.items():
                if exif_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[exif_key]
                # Reverse: if alias exists but EXIF: version doesn't, create it
                elif alias_key in self.metadata and exif_key not in self.metadata:
                    self.metadata[exif_key] = self.metadata[alias_key]
            
            # Add aliases for GPS tags without GPS: prefix (Standard format shows these both ways)
            # Common GPS tags that Standard format shows without prefix: GPSLatitude, GPSLongitude, GPSAltitude, etc.
            common_gps_aliases = {
                'GPS:GPSVersionID': 'GPSVersionID',
                'GPS:GPSLatitudeRef': 'GPSLatitudeRef',
                'GPS:GPSLatitude': 'GPSLatitude',
                'GPS:GPSLongitudeRef': 'GPSLongitudeRef',
                'GPS:GPSLongitude': 'GPSLongitude',
                'GPS:GPSAltitudeRef': 'GPSAltitudeRef',
                'GPS:GPSAltitude': 'GPSAltitude',
                'GPS:GPSTimeStamp': 'GPSTimeStamp',
                'GPS:GPSSatellites': 'GPSSatellites',
                'GPS:GPSStatus': 'GPSStatus',
                'GPS:GPSMeasureMode': 'GPSMeasureMode',
                'GPS:GPSDOP': 'GPSDOP',
                'GPS:GPSSpeedRef': 'GPSSpeedRef',
                'GPS:GPSSpeed': 'GPSSpeed',
                'GPS:GPSTrackRef': 'GPSTrackRef',
                'GPS:GPSTrack': 'GPSTrack',
                'GPS:GPSImgDirectionRef': 'GPSImgDirectionRef',
                'GPS:GPSImgDirection': 'GPSImgDirection',
                'GPS:GPSMapDatum': 'GPSMapDatum',
                'GPS:GPSDestLatitudeRef': 'GPSDestLatitudeRef',
                'GPS:GPSDestLatitude': 'GPSDestLatitude',
                'GPS:GPSDestLongitudeRef': 'GPSDestLongitudeRef',
                'GPS:GPSDestLongitude': 'GPSDestLongitude',
                'GPS:GPSDestBearingRef': 'GPSDestBearingRef',
                'GPS:GPSDestBearing': 'GPSDestBearing',
                'GPS:GPSDestDistanceRef': 'GPSDestDistanceRef',
                'GPS:GPSDestDistance': 'GPSDestDistance',
                'GPS:GPSProcessingMethod': 'GPSProcessingMethod',
                'GPS:GPSAreaInformation': 'GPSAreaInformation',
                'GPS:GPSDateStamp': 'GPSDateStamp',
                'GPS:GPSDifferential': 'GPSDifferential',
                'GPS:GPSHPositioningError': 'GPSHPositioningError',
            }
            for gps_key, alias_key in common_gps_aliases.items():
                if gps_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[gps_key]
            
            # Add aliases for Interop tags without Interop: prefix (Standard format shows these both ways)
            # Common Interop tags that Standard format shows without prefix: InteroperabilityIndex, InteroperabilityVersion, etc.
            common_interop_aliases = {
                'EXIF:Interop:InteroperabilityIndex': 'InteroperabilityIndex',
                'EXIF:Interop:InteroperabilityVersion': 'InteroperabilityVersion',
                'EXIF:Interop:RelatedImageFileFormat': 'RelatedImageFileFormat',
                'EXIF:Interop:RelatedImageWidth': 'RelatedImageWidth',
                'EXIF:Interop:RelatedImageLength': 'RelatedImageLength',
                'Interop:InteroperabilityIndex': 'InteroperabilityIndex',
                'Interop:InteroperabilityVersion': 'InteroperabilityVersion',
                'Interop:RelatedImageFileFormat': 'RelatedImageFileFormat',
                'Interop:RelatedImageWidth': 'RelatedImageWidth',
                'Interop:RelatedImageLength': 'RelatedImageLength',
            }
            for interop_key, alias_key in common_interop_aliases.items():
                if interop_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[interop_key]
            
            # Add aliases for common XMP tags without XMP: prefix (Standard format shows some XMP tags without prefix)
            # Common XMP tags that Standard format shows without prefix: Title, Creator, Description, Subject, Keywords, Rating, etc.
            common_xmp_aliases = {
                'XMP:Title': 'Title',
                'XMP:Creator': 'Creator',
                'XMP:Description': 'Description',
                'XMP:Subject': 'Subject',
                'XMP:Keywords': 'Keywords',
                'XMP:Rating': 'Rating',
                'XMP:CreateDate': 'CreateDate',
                'XMP:ModifyDate': 'ModifyDate',
                'XMP:MetadataDate': 'MetadataDate',
                'XMP:Orientation': 'Orientation',
                'XMP:Format': 'Format',
                'XMP:InstanceID': 'InstanceID',
                'XMP:DocumentID': 'DocumentID',
                'XMP:OriginalDocumentID': 'OriginalDocumentID',
                'XMP-dc:Title': 'Title',
                'XMP-dc:Creator': 'Creator',
                'XMP-dc:Description': 'Description',
                'XMP-dc:Subject': 'Subject',
                'XMP-xmp:CreateDate': 'CreateDate',
                'XMP-xmp:ModifyDate': 'ModifyDate',
                'XMP-xmp:MetadataDate': 'MetadataDate',
                'XMP-tiff:Orientation': 'Orientation',
            }
            for xmp_key, alias_key in common_xmp_aliases.items():
                if xmp_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[xmp_key]
            
            # Add aliases for common QuickTime tags without QuickTime: prefix (Standard format shows some QuickTime tags without prefix)
            # Common QuickTime tags that Standard format shows without prefix: Duration, VideoFrameRate, AudioSampleRate, VideoCodec, etc.
            common_quicktime_aliases = {
                'QuickTime:Duration': 'Duration',
                'QuickTime:VideoFrameRate': 'VideoFrameRate',
                'QuickTime:AudioSampleRate': 'AudioSampleRate',
                'QuickTime:VideoCodec': 'VideoCodec',
                'QuickTime:AudioCodec': 'AudioCodec',
                'QuickTime:ImageWidth': 'ImageWidth',
                'QuickTime:ImageHeight': 'ImageHeight',
                'QuickTime:Rotation': 'Rotation',
                'QuickTime:CreateDate': 'CreateDate',
                'QuickTime:ModifyDate': 'ModifyDate',
                'QuickTime:TimeScale': 'TimeScale',
                'QuickTime:MediaTimeScale': 'MediaTimeScale',
                'QuickTime:PreferredRate': 'PreferredRate',
                'QuickTime:PreferredVolume': 'PreferredVolume',
                'QuickTime:PreviewTime': 'PreviewTime',
                'QuickTime:PreviewDuration': 'PreviewDuration',
                'QuickTime:PosterTime': 'PosterTime',
                'QuickTime:SelectionTime': 'SelectionTime',
                'QuickTime:SelectionDuration': 'SelectionDuration',
                'QuickTime:CurrentTime': 'CurrentTime',
                'QuickTime:NextTrackID': 'NextTrackID',
            }
            for qt_key, alias_key in common_quicktime_aliases.items():
                if qt_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[qt_key]
            
            # Add aliases for common Video tags without Video: prefix (Standard format shows some Video tags without prefix)
            # Common Video tags that Standard format shows without prefix: Duration, VideoFrameRate, VideoCodec, etc.
            common_video_aliases = {
                'Video:Duration': 'Duration',
                'Video:VideoFrameRate': 'VideoFrameRate',
                'Video:VideoCodec': 'VideoCodec',
                'Video:ImageWidth': 'ImageWidth',
                'Video:ImageHeight': 'ImageHeight',
                'Video:Rotation': 'Rotation',
                'Video:BitRate': 'BitRate',
                'Video:FrameCount': 'FrameCount',
                'AVI:Duration': 'Duration',
                'AVI:VideoFrameRate': 'VideoFrameRate',
                'AVI:VideoCodec': 'VideoCodec',
                'AVI:ImageWidth': 'ImageWidth',
                'AVI:ImageHeight': 'ImageHeight',
            }
            for video_key, alias_key in common_video_aliases.items():
                if video_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[video_key]
            
            # Add aliases for common Audio tags without Audio: prefix (Standard format shows some Audio tags without prefix)
            # Common Audio tags that Standard format shows without prefix: Duration, AudioSampleRate, AudioCodec, etc.
            common_audio_aliases = {
                'Audio:Duration': 'Duration',
                'Audio:AudioSampleRate': 'AudioSampleRate',
                'Audio:AudioCodec': 'AudioCodec',
                'Audio:AudioChannels': 'AudioChannels',
                'Audio:AudioBitsPerSample': 'AudioBitsPerSample',
                'Audio:BitRate': 'BitRate',
                'Audio:MP3:Duration': 'Duration',
                'Audio:MP3:AudioSampleRate': 'AudioSampleRate',
                'Audio:MP3:AudioCodec': 'AudioCodec',
                'Audio:WAV:Duration': 'Duration',
                'Audio:WAV:AudioSampleRate': 'AudioSampleRate',
                'Audio:FLAC:Duration': 'Duration',
                'Audio:FLAC:AudioSampleRate': 'AudioSampleRate',
                'Audio:OGG:Duration': 'Duration',
                'Audio:OGG:AudioSampleRate': 'AudioSampleRate',
            }
            for audio_key, alias_key in common_audio_aliases.items():
                if audio_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[audio_key]
            
            # Add aliases for common Matroska tags without Matroska: prefix (Standard format shows some Matroska tags without prefix)
            # Common Matroska tags that Standard format shows without prefix: Duration, VideoFrameRate, VideoCodec, etc.
            common_matroska_aliases = {
                'Matroska:Duration': 'Duration',
                'Matroska:VideoFrameRate': 'VideoFrameRate',
                'Matroska:VideoCodec': 'VideoCodec',
                'Matroska:AudioCodec': 'AudioCodec',
                'Matroska:ImageWidth': 'ImageWidth',
                'Matroska:ImageHeight': 'ImageHeight',
                'Matroska:AudioSampleRate': 'AudioSampleRate',
                'Matroska:AudioChannels': 'AudioChannels',
                'Matroska:BitRate': 'BitRate',
            }
            for matroska_key, alias_key in common_matroska_aliases.items():
                if matroska_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[matroska_key]
            
            # Add aliases for common PDF tags without PDF: prefix (Standard format shows some PDF tags without prefix)
            # Common PDF tags that Standard format shows without prefix: Title, Author, Subject, Keywords, Creator, Producer, etc.
            common_pdf_aliases = {
                'PDF:Title': 'Title',
                'PDF:Author': 'Author',
                'PDF:Subject': 'Subject',
                'PDF:Keywords': 'Keywords',
                'PDF:Creator': 'Creator',
                'PDF:Producer': 'Producer',
                'PDF:CreateDate': 'CreateDate',
                'PDF:ModifyDate': 'ModifyDate',
                'PDF:PDFVersion': 'PDFVersion',
                'PDF:PageCount': 'PageCount',
                'PDF:Linearized': 'Linearized',
                'Document:PDF:Title': 'Title',
                'Document:PDF:Author': 'Author',
                'Document:PDF:Subject': 'Subject',
                'Document:PDF:Keywords': 'Keywords',
                'Document:PDF:Creator': 'Creator',
                'Document:PDF:Producer': 'Producer',
                'Document:PDF:CreateDate': 'CreateDate',
                'Document:PDF:ModifyDate': 'ModifyDate',
                'Document:PDF:PageCount': 'PageCount',
            }
            for pdf_key, alias_key in common_pdf_aliases.items():
                if pdf_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[pdf_key]
            
            # Add aliases for common PNG tags without PNG: prefix (Standard format shows some PNG tags without prefix)
            # Common PNG tags that Standard format shows without prefix: ImageWidth, ImageHeight, BitDepth, ColorType, etc.
            common_png_aliases = {
                'PNG:ImageWidth': 'ImageWidth',
                'PNG:ImageHeight': 'ImageHeight',
                'PNG:BitDepth': 'BitDepth',
                'PNG:ColorType': 'ColorType',
                'PNG:Compression': 'Compression',
                'PNG:Filter': 'Filter',
                'PNG:Interlace': 'Interlace',
            }
            for png_key, alias_key in common_png_aliases.items():
                if png_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[png_key]
            
            # Add aliases for common TIFF tags without TIFF: prefix (Standard format shows some TIFF tags without prefix)
            # Common TIFF tags that Standard format shows without prefix: ImageWidth, ImageHeight, BitsPerSample, etc.
            common_tiff_aliases = {
                'TIFF:ImageWidth': 'ImageWidth',
                'TIFF:ImageHeight': 'ImageHeight',
                'TIFF:BitsPerSample': 'BitsPerSample',
                'TIFF:Compression': 'Compression',
                'TIFF:PhotometricInterpretation': 'PhotometricInterpretation',
                'TIFF:Orientation': 'Orientation',
                'TIFF:SamplesPerPixel': 'SamplesPerPixel',
                'TIFF:PlanarConfiguration': 'PlanarConfiguration',
                'TIFF:XResolution': 'XResolution',
                'TIFF:YResolution': 'YResolution',
                'TIFF:ResolutionUnit': 'ResolutionUnit',
            }
            for tiff_key, alias_key in common_tiff_aliases.items():
                if tiff_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[tiff_key]
            
            # Add aliases for common JPEG tags without JPEG: prefix (Standard format shows some JPEG tags without prefix)
            # Common JPEG tags that Standard format shows without prefix: ImageWidth, ImageHeight, etc.
            common_jpeg_aliases = {
                'JPEG:ImageWidth': 'ImageWidth',
                'JPEG:ImageHeight': 'ImageHeight',
                'JPEG:Quality': 'Quality',
                'JPEG:ColorComponents': 'ColorComponents',
            }
            for jpeg_key, alias_key in common_jpeg_aliases.items():
                if jpeg_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[jpeg_key]
            
            # Add aliases for common WebP tags without WebP: prefix (Standard format shows some WebP tags without prefix)
            common_webp_aliases = {
                'WebP:ImageWidth': 'ImageWidth',
                'WebP:ImageHeight': 'ImageHeight',
            }
            for webp_key, alias_key in common_webp_aliases.items():
                if webp_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[webp_key]
            
            # Add aliases for common GIF tags without GIF: prefix (Standard format shows some GIF tags without prefix)
            common_gif_aliases = {
                'GIF:ImageWidth': 'ImageWidth',
                'GIF:ImageHeight': 'ImageHeight',
                'GIF:ColorTableSize': 'ColorTableSize',
                'GIF:HasColorTable': 'HasColorTable',
                'GIF:BackgroundColor': 'BackgroundColor',
            }
            for gif_key, alias_key in common_gif_aliases.items():
                if gif_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[gif_key]
            
            # Add aliases for common BMP tags without BMP: prefix (Standard format shows some BMP tags without prefix)
            common_bmp_aliases = {
                'BMP:ImageWidth': 'ImageWidth',
                'BMP:ImageHeight': 'ImageHeight',
                'BMP:BitsPerPixel': 'BitsPerPixel',
                'BMP:Compression': 'Compression',
            }
            for bmp_key, alias_key in common_bmp_aliases.items():
                if bmp_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[bmp_key]
            
            # Add aliases for common TGA tags without TGA: prefix (Standard format shows some TGA tags without prefix)
            common_tga_aliases = {
                'TGA:Width': 'ImageWidth',
                'TGA:Height': 'ImageHeight',
                'TGA:ImageWidth': 'ImageWidth',
                'TGA:ImageHeight': 'ImageHeight',
                'TGA:BitsPerPixel': 'BitsPerPixel',
            }
            for tga_key, alias_key in common_tga_aliases.items():
                if tga_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[tga_key]
            
            # Add aliases for common SVG tags without SVG: prefix (Standard format shows some SVG tags without prefix)
            common_svg_aliases = {
                'SVG:Width': 'ImageWidth',
                'SVG:Height': 'ImageHeight',
                'SVG:ImageWidth': 'ImageWidth',
                'SVG:ImageHeight': 'ImageHeight',
            }
            for svg_key, alias_key in common_svg_aliases.items():
                if svg_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[svg_key]
            
            # Add aliases for common MPF tags without MPF: prefix (Standard format shows some MPF tags without prefix)
            # Common MPF tags that Standard format shows without prefix: MPImageType, MPImageFlags, MPImageFormat, etc.
            common_mpf_aliases = {
                'MPF:MPImageType': 'MPImageType',
                'MPF:MPImageFlags': 'MPImageFlags',
                'MPF:MPImageFormat': 'MPImageFormat',
                'MPF:MPImageLength': 'MPImageLength',
                'MPF:MPImageStart': 'MPImageStart',
                'MPF:Version': 'Version',
                'MPF:NumberOfImages': 'NumberOfImages',
                'MPF:MPEntry': 'MPEntry',
            }
            for mpf_key, alias_key in common_mpf_aliases.items():
                if mpf_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[mpf_key]
            
            # Add aliases for MPF MPEntry tags (MPEntry0:MPImageStart -> MPImageStart, etc.)
            # Standard format shows MPEntry tags both with and without MPEntry prefix
            for key in list(self.metadata.keys()):
                if key.startswith('MPF:MPEntry') and ':' in key:
                    # Extract the tag name after MPEntry0:, MPEntry1:, etc.
                    parts = key.split(':', 2)
                    if len(parts) == 3:
                        entry_part = parts[1]  # MPEntry0, MPEntry1, etc.
                        tag_name = parts[2]  # MPImageStart, MPImageLength, etc.
                        # Create alias without MPEntry prefix
                        alias_key = tag_name
                        if alias_key not in self.metadata:
                            self.metadata[alias_key] = self.metadata[key]
            
            # Add aliases for common File tags without File: prefix (Standard format shows some File tags without prefix)
            # Common File tags that Standard format shows without prefix: FileName, FileSize, FileType, etc.
            common_file_aliases = {
                'File:FileName': 'FileName',
                'File:FileSize': 'FileSize',
                'File:FileType': 'FileType',
                'File:FileTypeExtension': 'FileTypeExtension',
                'File:MIMEType': 'MIMEType',
                'File:Directory': 'Directory',
                'File:FileModifyDate': 'FileModifyDate',
                'File:FileAccessDate': 'FileAccessDate',
                'File:FileInodeChangeDate': 'FileInodeChangeDate',
            }
            for file_key, alias_key in common_file_aliases.items():
                if file_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[file_key]
            
            # Add aliases for common IPTC tags without IPTC: prefix (Standard format shows some IPTC tags without prefix)
            # Common IPTC tags that Standard format shows without prefix: ObjectName, Keywords, Caption, Headline, Byline, etc.
            common_iptc_aliases = {
                'IPTC:ObjectName': 'ObjectName',
                'IPTC:Keywords': 'Keywords',
                'IPTC:Caption': 'Caption',
                'IPTC:Headline': 'Headline',
                'IPTC:Byline': 'Byline',
                'IPTC:BylineTitle': 'BylineTitle',
                'IPTC:Credit': 'Credit',
                'IPTC:Source': 'Source',
                'IPTC:Copyright': 'Copyright',
                'IPTC:Contact': 'Contact',
                'IPTC:City': 'City',
                'IPTC:State': 'State',
                'IPTC:Country': 'Country',
                'IPTC:DateCreated': 'DateCreated',
                'IPTC:TimeCreated': 'TimeCreated',
                'IPTC:DateSent': 'DateSent',
                'IPTC:TimeSent': 'TimeSent',
                'IPTC:DigitalCreationDate': 'DigitalCreationDate',
                'IPTC:DigitalCreationTime': 'DigitalCreationTime',
                'IPTC:OriginatingProgram': 'OriginatingProgram',
                'IPTC:ProgramVersion': 'ProgramVersion',
                'IPTC:ObjectCycle': 'ObjectCycle',
                'IPTC:BylineTitle': 'BylineTitle',
                'IPTC:ImageType': 'ImageType',
                'IPTC:ImageOrientation': 'ImageOrientation',
            }
            for iptc_key, alias_key in common_iptc_aliases.items():
                if iptc_key in self.metadata and alias_key not in self.metadata:
                    self.metadata[alias_key] = self.metadata[iptc_key]
            
            # Add aliases for Olympus MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Common Olympus tags that Standard format shows without prefix: AELock, AFAreas, MeteringMode, etc.
            olympus_makernote_aliases = [
                'AELock', 'AFAreas', 'MeteringMode', 'ExposureShift', 'NDFilter', 'CameraID',
                'MacroMode', 'FocusMode', 'FocusProcess', 'AFSearch', 'AFPointSelected',
                'AFFineTune', 'AFFineTuneAdj', 'FlashMode', 'FlashExposureComp',
                'SpecialMode', 'EquipmentVersion', 'SerialNumber', 'InternalSerialNumber',
                'FocalPlaneDiagonal', 'BodyFirmwareVersion', 'CameraType', 'TextInfo',
                'ImageWidth', 'ImageHeight', 'CompressedImageSize', 'PreviewImage',
                'PreviewImageStart', 'PreviewImageLength', 'AspectFrame', 'NoiseReduction',
                'DistortionCorrection', 'ShadingCompensation', 'CompressionFactor', 'Gradation',
                'PictureMode', 'PictureModeSaturation', 'PictureModeHue', 'PictureModeContrast',
                'PictureModeSharpness', 'PictureModeBWFilter', 'PictureModeTone', 'NoiseFilter',
                'ArtFilter', 'MagicFilter'
            ]
            for tag_name in olympus_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Sony MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Common Sony tags that Standard format shows without prefix: FocusStatus, AFPointSelected, FocusMode, etc.
            sony_makernote_aliases = [
                'FocusStatus', 'AFPointSelected', 'FocusMode', 'AFPoint', 'AFStatusActiveSensor',
                'LensSpec', 'DriveMode2', 'ExposureProgram', 'MeteringMode',
                'DynamicRangeOptimizerSetting', 'DynamicRangeOptimizerLevel', 'ColorSpace',
                'CreativeStyleSetting', 'ContrastSetting', 'SaturationSetting', 'SharpnessSetting',
                'WhiteBalanceSetting', 'FocalLength', 'ColorCompensationFilterSet',
                'FocalLengthTeleZoom', 'SonyCameraSettings', 'SonyFileFormat',
                'SonyDynamicRangeOptimizer', 'SonyImageStabilization', 'SonyColorMode',
                'SonyColorTemperature', 'SonyColorCompensationFilter', 'SonySceneMode',
                'SonyZoneMatching', 'SonyDynamicRangeOptimizerValue', 'SonyImageStabilizationSetting',
                'SonyLensType', 'SonyFullImageSize', 'SonyPreviewImageSize', 'SonyMacro',
                'SonyExposureMode', 'SonyFlashMode', 'SonyWhiteBalanceSetting', 'SonySequenceNumber',
                'SonyAntiBlur', 'SonyLongExposureNoiseReduction', 'SonyHighISONoiseReduction',
                'SonyHDR', 'SonyMultiFrameNR', 'SonyPictureEffect', 'SonySoftSkinEffect',
                'SonyVignettingCorrection', 'SonyLateralChromaticAberration', 'SonyDistortionCorrection',
                'SonyWBShiftABGM'
            ]
            for tag_name in sony_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Pentax MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Common Pentax tags that Standard format shows without prefix: LensType, FlashMode, FocusMode, etc.
            pentax_makernote_aliases = [
                'LensType', 'PentaxModelType', 'PreviewImageSize', 'PreviewImageLength', 'PreviewImageStart',
                'PentaxModelID', 'Date', 'Time', 'Quality', 'PentaxImageSize', 'PentaxSize',
                'PentaxFlash', 'FlashMode', 'FocusMode', 'AFPointSelected', 'PentaxContrast',
                'PentaxSharpness', 'PentaxSaturation', 'ExposureTime', 'FNumber', 'ISO',
                'PentaxISOSpeed', 'ExposureCompensation', 'MeteringMode', 'AutoBracketing',
                'WhiteBalance', 'WhiteBalanceMode', 'PentaxColorSpace', 'PentaxEffectiveLV',
                'FocalLength', 'PentaxImageProcessing', 'Saturation', 'Contrast', 'Sharpness',
                'WorldTimeLocation', 'HometownCity', 'DestinationCity', 'HometownDST', 'DestinationDST',
                'DSPFirmwareVersion', 'CPUFirmwareVersion', 'FrameNumber', 'PentaxVersion',
                'EffectiveLV', 'PentaxPictureMode', 'PentaxDriveMode'
            ]
            for tag_name in pentax_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Fujifilm MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Common Fujifilm tags that Standard format shows without prefix: FocusMode, FlashMode, Sharpness, etc.
            fujifilm_makernote_aliases = [
                'Version', 'InternalSerialNumber', 'FujifilmVersion', 'FujifilmSerialNumber',
                'FujifilmQuality', 'FujifilmSharpness', 'FujifilmWhiteBalance', 'FujifilmColor',
                'FujifilmTone', 'FujifilmColorMode', 'FujifilmDynamicRange', 'FujifilmFilmMode',
                'FujifilmDynamicRangeSetting', 'FujifilmDevelopmentDynamicRange', 'FujifilmMinFocalLength',
                'FujifilmMaxFocalLength', 'FujifilmMaxApertureAtMinFocal', 'FujifilmMaxApertureAtMaxFocal',
                'FujifilmFileSource', 'FujifilmOrderNumber', 'FujifilmFrameNumber', 'FujifilmParallax',
                'FujifilmLensType', 'FujifilmLensFocalLength', 'FujifilmLensAperture', 'FujifilmFocusMode',
                'FujifilmFocusPixel', 'FujifilmSlowSync', 'FujifilmFlashMode', 'FujifilmFlashStrength',
                'FujifilmMacro', 'FujifilmFlashExposureComp', 'FujifilmImageStabilization', 'FujifilmShutterType',
                'FujifilmShutterSpeed', 'FujifilmAperture', 'FujifilmISO', 'FujifilmExposureCompensation',
                'FujifilmWhiteBalanceFineTune', 'FujifilmColorTemperature', 'FujifilmNoiseReduction',
                'FujifilmHighISONoiseReduction', 'FujifilmFacesDetected', 'FujifilmFacePositions',
                'FujifilmFaceRecognition', 'SlowSync', 'PictureMode', 'ExposureCount',
                'ShadowTone', 'HighlightTone', 'LensModulationOptimizer', 'ShutterType'
            ]
            for tag_name in fujifilm_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Panasonic MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Panasonic tags are stored without "Panasonic" prefix in MakerNotes (e.g., "MakerNotes:WhiteBalance" not "MakerNotes:PanasonicWhiteBalance")
            # Common Panasonic tags that Standard format shows without prefix: Quality, WhiteBalance, MacroMode, etc.
            panasonic_makernote_aliases = [
                'Quality', 'FirmwareVersion', 'WhiteBalance', 'FocusMode', 'AFAreaMode', 'ImageStabilization',
                'MacroMode', 'ShootingMode', 'Audio', 'WhiteBalanceBias', 'FlashBias', 'SerialNumber',
                'WB_RBLevels', 'ProgramISO', 'AdvancedSceneMode', 'TextStamp', 'SceneMode', 'WBShiftAB',
                'WBShiftGM', 'FlashCurve', 'ColorTemp', 'WB_RBLevels2', 'WB_RBLevels3', 'WB_RBLevels4',
                'WB_RBLevels5', 'InternalSerialNumber', 'ExifVersion', 'VideoFrameRate', 'ColorEffect',
                'TimeSincePowerOn', 'BurstMode', 'SequenceNumber', 'ContrastMode', 'NoiseReduction', 'SelfTimer',
                'Rotation', 'AFAssistLamp', 'ColorMode', 'BabyAge', 'OpticalZoomMode', 'ConversionLens',
                'TravelDay', 'WorldTimeLocation', 'LensType', 'LensSerialNumber', 'AccessoryType',
                'AccessorySerialNumber', 'Transform', 'IntelligentExposure', 'LensFirmwareVersion', 'FaceRecInfo',
                'FlashWarning', 'RecognizedFaceFlags', 'Title', 'BabyName', 'Location', 'Country',
                'IntelligentResolution', 'BurstSpeed', 'IntelligentD-Range', 'ClearRetouch', 'PhotoStyle',
                'ShadingCompensation', 'AccelerometerZ', 'AccelerometerX', 'AccelerometerY', 'CameraOrientation',
                'RollAngle', 'PitchAngle', 'SweepPanoramaDirection', 'SweepPanoramaFieldOfView',
                'TimerRecording', 'InternalNDFilter', 'HDR', 'ShutterType', 'ClearRetouchValue', 'TouchAE',
                'PrintIM', 'MakerNoteVersion', 'WB_RGBLevels', 'AdvancedSceneType', 'Contrast', 'NoiseReduction2',
                'State', 'City', 'Landmark', 'NormalWhiteBalance', 'FlashWhiteBalance', 'CloudyWhiteBalance',
                'ShadeWhiteBalance', 'ColorTemperatureWhiteBalance', 'WhiteBalanceBlue', 'WhiteBalanceRed'
            ]
            for tag_name in panasonic_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Nikon MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Nikon tags are stored without "Nikon" prefix in MakerNotes (e.g., "MakerNotes:Quality" not "MakerNotes:NikonQuality")
            # Common Nikon tags that Standard format shows without prefix: Version, Quality, WhiteBalance, FocusMode, etc.
            nikon_makernote_aliases = [
                'Version', 'ISOSetting', 'ColorMode', 'Quality', 'WhiteBalance', 'ImageSharpening',
                'FocusMode', 'FlashSetting', 'FlashMode', 'WhiteBalanceFineTune', 'WB_RBLevels',
                'ProgramShift', 'ExposureDifference', 'ISOSelection', 'DataDump', 'PreviewIFD',
                'FlashExposureComp', 'ImageBoundary', 'FlashExposureBracketValue', 'ExposureBracketValue',
                'ImageProcessing', 'CropHiSpeed', 'ExposureTuning', 'SerialNumber', 'ColorSpace',
                'VRInfo', 'ImageAuthentication', 'ActiveD-Lighting', 'PictureControl', 'WorldTime',
                'ISOInfo', 'VignetteControl', 'DistortionControl', 'LensType', 'Lens'
            ]
            for tag_name in nikon_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Add aliases for Canon MakerNote tags without MakerNotes: prefix (Standard format shows these both ways)
            # Canon tags are stored with "MakerNotes:" prefix (e.g., "MakerNotes:FlashInfo", "MakerNotes:FocalLength")
            # Common Canon tags that Standard format shows without prefix: FlashInfo, FocalLength, ShotInfo, FirmwareVersion, etc.
            canon_makernote_aliases = [
                'FlashInfo', 'FocalLength', 'ShotInfo', 'FirmwareVersion', 'FileNumber', 'OwnerName',
                'SerialNumber', 'CameraInfo', 'CustomFunctions', 'ModelID', 'PictureInfo',
                'ThumbnailImageValidArea', 'SerialNumberFormat', 'SuperMacro', 'DateStampMode',
                'MyColors', 'FirmwareRevision', 'Categories', 'FaceDetectArray1', 'FaceDetectArray2',
                'AFInfo', 'ThumbnailImage', 'ColorBalance', 'MeasuredColor', 'ColorTemperature',
                'CanonFlags', 'ModifiedInfo', 'ToneCurveTable', 'Sharpness', 'SharpnessFreq',
                'WhiteBalanceTable', 'ColorBalance2', 'BlackLevel', 'CustomPictureStyleFile',
                'ColorInfo', 'VRD', 'SensorInfo', 'ColorData', 'CRWParam', 'FileInfo',
                'LensModel', 'InternalSerialNumber', 'DustRemovalData', 'LensFocalLength35efl',
                'FlashGuideNumber', 'FlashDetails', 'FlashMode', 'FlashColorFilter', 'FlashActivity',
                'FlashRedEyeReduction'
            ]
            for tag_name in canon_makernote_aliases:
                makernote_key = f'MakerNotes:{tag_name}'
                if makernote_key in self.metadata and tag_name not in self.metadata:
                    self.metadata[tag_name] = self.metadata[makernote_key]
            
            # Clean up any double-prefixed tags that might have been added anywhere
            double_prefixed = {k: v for k, v in self.metadata.items() if k.startswith('EXIF:EXIF:')}
            for double_key, double_value in double_prefixed.items():
                # Remove double prefix and add with single prefix
                single_key = double_key[5:]  # Remove first "EXIF:"
                if single_key not in self.metadata:
                    self.metadata[single_key] = double_value
                # Remove double-prefixed version
                del self.metadata[double_key]
            
            # Final attempt: Calculate ScaleFactor35efl from sensor dimensions if not already set or if value seems incorrect (>10)
            # This is done at the end to ensure it runs even if earlier code had exceptions
            # Also recalculate if existing value is suspiciously high (likely calculation error)
            should_recalculate = False
            if 'Composite:ScaleFactor35efl' not in self.metadata:
                should_recalculate = True
            else:
                try:
                    existing_value = float(self.metadata.get('Composite:ScaleFactor35efl', '0'))
                    if existing_value > 10:  # Suspiciously high - likely calculation error
                        # Delete incorrect value to force recalculation
                        del self.metadata['Composite:ScaleFactor35efl']
                        should_recalculate = True
                except (ValueError, TypeError):
                    should_recalculate = True
            
            if should_recalculate:
                try:
                    import re
                    # Get sensor dimensions from FocalPlane resolution
                    focal_plane_x_res = self.metadata.get('EXIF:FocalPlaneXResolution')
                    focal_plane_y_res = self.metadata.get('EXIF:FocalPlaneYResolution')
                    focal_plane_res_unit = self.metadata.get('EXIF:FocalPlaneResolutionUnit')
                    image_width = self.metadata.get('EXIF:ImageWidth') or self.metadata.get('File:ImageWidth')
                    image_height = self.metadata.get('EXIF:ImageHeight') or self.metadata.get('File:ImageHeight')
                    
                    # Calculate sensor width/height in mm
                    sensor_width_mm = None
                    sensor_height_mm = None
                    
                    if focal_plane_x_res and image_width and focal_plane_res_unit:
                        try:
                            # Parse resolution (might be string, number, or RATIONAL tuple)
                            if isinstance(focal_plane_x_res, tuple) and len(focal_plane_x_res) == 2:
                                # RATIONAL tuple (numerator, denominator)
                                res_x = focal_plane_x_res[0] / focal_plane_x_res[1] if focal_plane_x_res[1] != 0 else None
                            elif isinstance(focal_plane_x_res, str):
                                match = re.search(r'[\d.]+', focal_plane_x_res)
                                res_x = float(match.group()) if match else None
                            else:
                                res_x = float(focal_plane_x_res)
                            
                            if res_x and res_x > 0:
                                # Convert image_width to float (handles both string and numeric)
                                if isinstance(image_width, str):
                                    width_px = float(image_width)
                                elif isinstance(image_width, (int, float)):
                                    width_px = float(image_width)
                                else:
                                    width_px = None
                                
                                if width_px and width_px > 0:
                                    # Parse resolution unit (might be integer, string, or RATIONAL tuple)
                                    # NOTE: FocalPlaneResolutionUnit should be a SHORT (2=inches, 3=cm), but may be misread as RATIONAL
                                    unit_value = None
                                    if isinstance(focal_plane_res_unit, tuple) and len(focal_plane_res_unit) == 2:
                                        # RATIONAL tuple - check if it's close to 2 (inches) or 3 (cm)
                                        unit_ratio = focal_plane_res_unit[0] / focal_plane_res_unit[1] if focal_plane_res_unit[1] != 0 else None
                                        if unit_ratio:
                                            # Check if it's close to 2 (inches) or 3 (cm)
                                            if abs(unit_ratio - 2) < 0.1:
                                                unit_value = 2  # inches
                                            elif abs(unit_ratio - 3) < 0.1:
                                                unit_value = 3  # cm
                                            # If RATIONAL value is very large (likely misread tag), default to inches (2) for Canon CR2
                                            elif unit_ratio > 100:
                                                # Likely misread - Canon CR2 files typically use inches (2) for FocalPlaneResolutionUnit
                                                unit_value = 2  # Default to inches for Canon CR2
                                    elif isinstance(focal_plane_res_unit, str):
                                        if 'inch' in focal_plane_res_unit.lower():
                                            unit_value = 2
                                        elif 'cm' in focal_plane_res_unit.lower():
                                            unit_value = 3
                                    elif isinstance(focal_plane_res_unit, (int, float)):
                                        unit_value = int(focal_plane_res_unit)
                                    
                                    # Calculate sensor width based on unit
                                    if unit_value == 2:  # inches
                                        sensor_width_mm = (width_px / res_x) * 25.4
                                    elif unit_value == 3:  # cm
                                        sensor_width_mm = (width_px / res_x) * 10.0
                                    else:  # No unit or unknown - assume pixels per mm
                                        sensor_width_mm = width_px / res_x
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    if focal_plane_y_res and image_height and focal_plane_res_unit:
                        try:
                            # Parse resolution (might be string, number, or RATIONAL tuple)
                            if isinstance(focal_plane_y_res, tuple) and len(focal_plane_y_res) == 2:
                                # RATIONAL tuple (numerator, denominator)
                                res_y = focal_plane_y_res[0] / focal_plane_y_res[1] if focal_plane_y_res[1] != 0 else None
                            elif isinstance(focal_plane_y_res, str):
                                match = re.search(r'[\d.]+', focal_plane_y_res)
                                res_y = float(match.group()) if match else None
                            else:
                                res_y = float(focal_plane_y_res)
                            
                            if res_y and res_y > 0:
                                # Convert image_height to float (handles both string and numeric)
                                if isinstance(image_height, str):
                                    height_px = float(image_height)
                                elif isinstance(image_height, (int, float)):
                                    height_px = float(image_height)
                                else:
                                    height_px = None
                                
                                if height_px and height_px > 0:
                                    # Parse resolution unit (might be integer, string, or RATIONAL tuple)
                                    # NOTE: FocalPlaneResolutionUnit should be a SHORT (2=inches, 3=cm), but may be misread as RATIONAL
                                    unit_value = None
                                    if isinstance(focal_plane_res_unit, tuple) and len(focal_plane_res_unit) == 2:
                                        # RATIONAL tuple - check if it's close to 2 (inches) or 3 (cm)
                                        unit_ratio = focal_plane_res_unit[0] / focal_plane_res_unit[1] if focal_plane_res_unit[1] != 0 else None
                                        if unit_ratio:
                                            # Check if it's close to 2 (inches) or 3 (cm)
                                            if abs(unit_ratio - 2) < 0.1:
                                                unit_value = 2  # inches
                                            elif abs(unit_ratio - 3) < 0.1:
                                                unit_value = 3  # cm
                                            # If RATIONAL value is very large (likely misread tag), default to inches (2) for Canon CR2
                                            elif unit_ratio > 100:
                                                # Likely misread - Canon CR2 files typically use inches (2) for FocalPlaneResolutionUnit
                                                unit_value = 2  # Default to inches for Canon CR2
                                    elif isinstance(focal_plane_res_unit, str):
                                        if 'inch' in focal_plane_res_unit.lower():
                                            unit_value = 2
                                        elif 'cm' in focal_plane_res_unit.lower():
                                            unit_value = 3
                                    elif isinstance(focal_plane_res_unit, (int, float)):
                                        unit_value = int(focal_plane_res_unit)
                                    
                                    # Calculate sensor height based on unit
                                    if unit_value == 2:  # inches
                                        sensor_height_mm = (height_px / res_y) * 25.4
                                    elif unit_value == 3:  # cm
                                        sensor_height_mm = (height_px / res_y) * 10.0
                                    else:  # No unit or unknown - assume pixels per mm
                                        sensor_height_mm = height_px / res_y
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                    
                    # Calculate scale factor from sensor dimensions
                    # Full frame: 36mm x 24mm
                    if sensor_width_mm and sensor_width_mm > 0:
                        scale_factor = 36.0 / sensor_width_mm
                        self.metadata['Composite:ScaleFactor35efl'] = f"{scale_factor:.1f}"
                    elif sensor_height_mm and sensor_height_mm > 0:
                        scale_factor = 24.0 / sensor_height_mm
                        self.metadata['Composite:ScaleFactor35efl'] = f"{scale_factor:.1f}"
                    
                    # Recalculate Composite:FocalLength35efl now that ScaleFactor35efl is available
                    # This ensures we get the "X.X mm (35 mm equivalent: Y.Y mm)" format when ScaleFactor35efl is calculated
                    if 'Composite:ScaleFactor35efl' in self.metadata:
                        focal_length = self.metadata.get('EXIF:FocalLength')
                        focal_length_35 = self.metadata.get('EXIF:FocalLengthIn35mmFilm')
                        scale_factor_val = self.metadata.get('Composite:ScaleFactor35efl')
                        
                        # Only recalculate if FocalLengthIn35mmFilm is not available (otherwise it was already calculated correctly)
                        # Also recalculate if current value doesn't have 35mm equivalent format
                        current_focal35efl = self.metadata.get('Composite:FocalLength35efl', '')
                        needs_recalc = (not focal_length_35 and focal_length and scale_factor_val and 
                                       '35 mm equivalent' not in str(current_focal35efl))
                        
                        if needs_recalc:
                            try:
                                import re
                                # Parse focal length
                                if isinstance(focal_length, tuple) and len(focal_length) == 2:
                                    fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                                elif isinstance(focal_length, str):
                                    match = re.search(r'[\d.]+', focal_length)
                                    fl = float(match.group()) if match else 0
                                else:
                                    fl = float(focal_length)
                                
                                if fl > 0:
                                    # Parse scale factor
                                    if isinstance(scale_factor_val, str):
                                        match = re.search(r'[\d.]+', scale_factor_val)
                                        sf = float(match.group()) if match else None
                                    else:
                                        sf = float(scale_factor_val) if scale_factor_val else None
                                    
                                    if sf and sf > 0:
                                        fl35 = fl * sf
                                        # Format as "X.X mm (35 mm equivalent: Y.Y mm)" to standard format
                                        self.metadata['Composite:FocalLength35efl'] = f"{fl:.1f} mm (35 mm equivalent: {fl35:.1f} mm)"
                            except (ValueError, TypeError, ZeroDivisionError):
                                pass
                    
                    # Recalculate Composite:Lens35efl now that ScaleFactor35efl is available
                    # This ensures we get the range format "X.X - Y.Y mm (35 mm equivalent: Z.Z - W.W mm)" when ScaleFactor35efl is calculated
                    if 'Composite:ScaleFactor35efl' in self.metadata:
                        lens = self.metadata.get('Composite:Lens')
                        scale_factor_val = self.metadata.get('Composite:ScaleFactor35efl')
                        current_lens35efl = self.metadata.get('Composite:Lens35efl', '')
                        
                        # Recalculate if Composite:Lens has a range and current Lens35efl doesn't have the range format
                        needs_recalc = (lens and scale_factor_val and 
                                       ' - ' in str(lens) and 
                                       '35 mm equivalent' not in str(current_lens35efl))
                        
                        if needs_recalc:
                            try:
                                import re
                                # Extract range from Composite:Lens (e.g., "17.0 - 50.0 mm")
                                lens_range_match = re.search(r'([\d.]+)\s*-\s*([\d.]+)', str(lens))
                                if lens_range_match:
                                    min_val = float(lens_range_match.group(1))
                                    max_val = float(lens_range_match.group(2))
                                    
                                    if min_val > 0 and max_val > 0:
                                        # Parse scale factor
                                        if isinstance(scale_factor_val, str):
                                            match = re.search(r'[\d.]+', scale_factor_val)
                                            sf = float(match.group()) if match else None
                                        else:
                                            sf = float(scale_factor_val) if scale_factor_val else None
                                        
                                        if sf and sf > 0:
                                            min_fl35 = min_val * sf
                                            max_fl35 = max_val * sf
                                            # Format as "X.X - Y.Y mm (35 mm equivalent: Z.Z - W.W mm)" to standard format
                                            self.metadata['Composite:Lens35efl'] = f"{min_val:.1f} - {max_val:.1f} mm (35 mm equivalent: {min_fl35:.1f} - {max_fl35:.1f} mm)"
                            except (ValueError, TypeError, ZeroDivisionError):
                                pass
                    
                    # Calculate FOV now that ScaleFactor35efl is available
                    if 'Composite:FOV' not in self.metadata and 'Composite:ScaleFactor35efl' in self.metadata:
                        focal_length = self.metadata.get('EXIF:FocalLength') or self.metadata.get('Composite:FocalLength')
                        scale_factor_val = self.metadata.get('Composite:ScaleFactor35efl')
                        try:
                            import math
                            import re
                            if focal_length and scale_factor_val:
                                # Parse focal length
                                if isinstance(focal_length, tuple) and len(focal_length) == 2:
                                    fl = focal_length[0] / focal_length[1] if focal_length[1] != 0 else 0
                                elif isinstance(focal_length, str):
                                    match = re.search(r'[\d.]+', focal_length)
                                    fl = float(match.group()) if match else 0
                                else:
                                    fl = float(focal_length)
                                
                                # Parse scale factor
                                if isinstance(scale_factor_val, str):
                                    match = re.search(r'[\d.]+', scale_factor_val)
                                    sf = float(match.group()) if match else None
                                else:
                                    sf = float(scale_factor_val) if scale_factor_val else None
                                
                                if fl > 0 and sf and sf > 0:
                                    # Sensor width = full frame width (36mm) / scale factor
                                    sensor_width_mm = 36.0 / sf
                                    # FOV = 2 * atan(sensor_width_mm / (2 * focal_length)) * 180 / pi
                                    fov_rad = 2 * math.atan(sensor_width_mm / (2 * fl))
                                    fov_deg = fov_rad * 180.0 / math.pi
                                    self.metadata['Composite:FOV'] = f"{fov_deg:.1f} deg"
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                except Exception:
                    pass  # ScaleFactor35efl calculation is optional
        
        except Exception:
            pass  # Composite tags are optional
    
    def _calculate_duration_from_metadata(self) -> Optional[Union[str, float]]:
        """
        Calculate duration from file metadata when duration tags are not present.
        
        Supports:
        - MP3: From file size and bitrate
        - FLAC: From TotalSamples and SampleRate (already calculated in parser)
        - WAV: From data chunk size and audio format (already calculated in parser)
        - AVI: From TotalFrames and VideoFrameRate
        - OGG/Opus: From file size and bitrate (if available)
        
        Returns:
            Duration as string (formatted) or float (seconds), or None if cannot calculate
        """
        try:
            # AVI: Calculate from TotalFrames and VideoFrameRate
            total_frames = self.metadata.get('Video:AVI:TotalFrames')
            frame_rate_str = self.metadata.get('Video:AVI:VideoFrameRate', '')
            if total_frames and frame_rate_str:
                try:
                    # Extract frame rate from string like "30.00" or "30.00 fps"
                    import re
                    fps_match = re.search(r'(\d+\.?\d*)', frame_rate_str)
                    if fps_match:
                        fps = float(fps_match.group(1))
                        if fps > 0 and total_frames > 0:
                            duration_sec = total_frames / fps
                            if duration_sec >= 60:
                                hours = int(duration_sec // 3600)
                                minutes = int((duration_sec % 3600) // 60)
                                secs = int(duration_sec % 60)
                                return f"{hours}:{minutes:02d}:{secs:02d}"
                            elif duration_sec == 0:
                                return "0 s"
                            else:
                                return f"{duration_sec:.2f} s"
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # MP3: Calculate from file size and bitrate
            bitrate_str = self.metadata.get('Audio:MP3:AudioBitrate', '')
            if bitrate_str and self.file_path:
                try:
                    # Extract bitrate from string like "128 kbps"
                    import re
                    bitrate_match = re.search(r'(\d+)', bitrate_str)
                    if bitrate_match:
                        bitrate_kbps = int(bitrate_match.group(1))
                        if bitrate_kbps > 0:
                            # Get file size
                            file_size = os.path.getsize(self.file_path)
                            # Estimate audio data size (skip ID3 tags)
                            # ID3v2 tag size if present
                            id3_size = 0
                            if self.file_data and self.file_data.startswith(b'ID3'):
                                if len(self.file_data) >= 10:
                                    size_bytes = self.file_data[6:10]
                                    id3_size = 10 + ((size_bytes[0] << 21) | (size_bytes[1] << 14) | 
                                                    (size_bytes[2] << 7) | size_bytes[3])
                            # Also check for ID3v1 tag at end (128 bytes)
                            audio_data_size = file_size - id3_size - 128  # Subtract ID3v1 if present
                            if audio_data_size > 0:
                                # Duration = (file_size - tags) * 8 / (bitrate * 1000)
                                duration_sec = (audio_data_size * 8) / (bitrate_kbps * 1000)
                                if duration_sec > 0:
                                    if duration_sec >= 60:
                                        hours = int(duration_sec // 3600)
                                        minutes = int((duration_sec % 3600) // 60)
                                        secs = int(duration_sec % 60)
                                        return f"{hours}:{minutes:02d}:{secs:02d}"
                                    elif duration_sec == 0:
                                        return "0 s"
                                    else:
                                        return f"{duration_sec:.2f} s"
                except (ValueError, TypeError, ZeroDivisionError, OSError):
                    pass
            
            # OGG/Opus: Calculate from file size and bitrate (if available)
            nominal_bitrate_str = (self.metadata.get('Audio:OGG:NominalBitrate') or 
                                  self.metadata.get('Audio:OPUS:NominalBitrate', ''))
            if nominal_bitrate_str and self.file_path:
                try:
                    # Extract bitrate from string like "128000 bps" or "128 kbps"
                    import re
                    bitrate_match = re.search(r'(\d+)', nominal_bitrate_str)
                    if bitrate_match:
                        bitrate_bps = int(bitrate_match.group(1))
                        # If value is small (< 1000), assume it's in kbps, convert to bps
                        if bitrate_bps < 1000:
                            bitrate_bps = bitrate_bps * 1000
                        if bitrate_bps > 0:
                            file_size = os.path.getsize(self.file_path)
                            # OGG has overhead, estimate ~5% overhead
                            audio_data_size = file_size * 0.95
                            duration_sec = (audio_data_size * 8) / bitrate_bps
                            if duration_sec > 0:
                                if duration_sec >= 60:
                                    hours = int(duration_sec // 3600)
                                    minutes = int((duration_sec % 3600) // 60)
                                    secs = int(duration_sec % 60)
                                    return f"{hours}:{minutes:02d}:{secs:02d}"
                                elif duration_sec == 0:
                                    return "0 s"
                                else:
                                    return f"{duration_sec:.2f} s"
                except (ValueError, TypeError, ZeroDivisionError, OSError):
                    pass
            
        except Exception:
            pass
        
        return None
    
    def get_all_metadata(self, format_values: bool = True) -> Dict[str, Any]:
        """
        Get all metadata from the file, including modified tags.
        
        Tags matching IgnoreTags option patterns will be excluded from the result.
        
        Args:
            format_values: If True, format values to standard format output format
        
        Returns:
            Dictionary containing all metadata tags and values (excluding ignored tags)
        """
        result = self.metadata.copy()
        # Include modified tags (overwriting existing values)
        for tag_name, value in self.modified_tags.items():
            if value is None:
                # Tag deletion
                result.pop(tag_name, None)
            else:
                result[tag_name] = value
        
        # Apply IgnoreTags option - filter out ignored tags
        filtered_result = {}
        for tag_name, value in result.items():
            if not self.should_ignore_tag(tag_name):
                filtered_result[tag_name] = value
        
        # Apply NoPDFList option - filter out PDF object tags
        no_pdf_list = self.get_option('NoPDFList', False)
        if no_pdf_list:
            # Filter out PDF object-related tags
            pdf_filtered_result = {}
            for tag_name, value in filtered_result.items():
                # Skip tags that are PDF object references or object listings
                # Common patterns: PDF:Object, PDF:ObjectN, PDF:*Object*, etc.
                if tag_name.startswith('PDF:') and ('Object' in tag_name or 'object' in tag_name.lower()):
                    continue
                # Also filter tags that explicitly list PDF objects
                if 'PDFObject' in tag_name or 'pdfobject' in tag_name.lower():
                    continue
                pdf_filtered_result[tag_name] = value
            filtered_result = pdf_filtered_result
        
        # Format values to standard format output
        if format_values:
            formatted_result = {}
            # Build context for format-specific decisions
            context = {
                'Make': filtered_result.get('EXIF:Make', filtered_result.get('Make', '')),
                'FileType': filtered_result.get('File:FileType', ''),
                'FocalPlaneYResolution': filtered_result.get('EXIF:FocalPlaneYResolution', filtered_result.get('FocalPlaneYResolution')),
                # Expose core EXIF date fields so the value formatter can
                # synthesize or normalize DateTimeOriginal/CreateDate when
                # some cameras/scanners store only partial values.
                'EXIF:DateTime': filtered_result.get('EXIF:DateTime', filtered_result.get('DateTime')),
                'EXIF:CreateDate': filtered_result.get('EXIF:CreateDate'),
            }
            for tag_name, value in filtered_result.items():
                formatted_value = format_exif_value(tag_name, value, context=context)
                formatted_result[tag_name] = formatted_value
            return formatted_result
        
        return filtered_result
    
    def has_metadata_group(self, group: str) -> bool:
        """
        Check if metadata contains tags from a specific group.
        
        This is a quick check to determine if metadata from a specific
        metadata group (EXIF, IPTC, XMP, GPS, etc.) exists without
        needing to load or check individual tags.
        
        Args:
            group: Metadata group name (e.g., 'EXIF', 'IPTC', 'XMP', 'GPS')
                  Case-insensitive
        
        Returns:
            True if at least one tag from the specified group exists, False otherwise
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     if exif.has_metadata_group('EXIF'):
            ...         print("File contains EXIF metadata")
            ...     if exif.has_metadata_group('IPTC'):
            ...         print("File contains IPTC metadata")
        """
        group_upper = group.upper()
        group_prefix = f"{group_upper}:"
        
        # Quick check: look for any tag starting with the group prefix
        for tag_name in self.metadata.keys():
            if tag_name.upper().startswith(group_prefix):
                return True
        
        return False
    
    def get_metadata_count_by_group(self, group: str) -> int:
        """
        Get the count of metadata tags from a specific group.
        
        This method counts how many tags belong to a specific metadata group
        (EXIF, IPTC, XMP, GPS, etc.) without needing to load individual tags.
        
        Args:
            group: Metadata group name (e.g., 'EXIF', 'IPTC', 'XMP', 'GPS')
                  Case-insensitive
        
        Returns:
            Number of tags from the specified group (0 if none exist)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     exif_count = exif.get_metadata_count_by_group('EXIF')
            ...     print(f"File contains {exif_count} EXIF tags")
            ...     iptc_count = exif.get_metadata_count_by_group('IPTC')
            ...     print(f"File contains {iptc_count} IPTC tags")
        """
        group_upper = group.upper()
        group_prefix = f"{group_upper}:"
        
        # Count tags starting with the group prefix
        count = 0
        for tag_name in self.metadata.keys():
            if tag_name.upper().startswith(group_prefix):
                count += 1
        
        return count
    
    def get_metadata_summary(self, include_group_counts: bool = True) -> Dict[str, Any]:
        """
        Get summary statistics about the loaded metadata.
        
        This method provides a quick overview of the metadata in the current file,
        including total tag count and counts by metadata group.
        
        Args:
            include_group_counts: If True, include tag counts by group
        
        Returns:
            Dictionary with summary information:
            - total_tags: Total number of metadata tags
            - groups: Dictionary mapping group names to tag counts (if include_group_counts=True)
            - has_exif: Boolean indicating if EXIF metadata exists
            - has_iptc: Boolean indicating if IPTC metadata exists
            - has_xmp: Boolean indicating if XMP metadata exists
            - has_gps: Boolean indicating if GPS metadata exists
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     summary = exif.get_metadata_summary()
            ...     print(f"Total tags: {summary['total_tags']}")
            ...     print(f"EXIF tags: {summary['groups'].get('EXIF', 0)}")
        """
        summary = {
            'total_tags': len(self.metadata),
            'has_exif': self.has_metadata_group('EXIF'),
            'has_iptc': self.has_metadata_group('IPTC'),
            'has_xmp': self.has_metadata_group('XMP'),
            'has_gps': self.has_metadata_group('GPS'),
        }
        
        if include_group_counts:
            group_counts = {}
            for tag_name in self.metadata.keys():
                if ':' in tag_name:
                    group = tag_name.split(':', 1)[0]
                else:
                    group = 'Unknown'
                group_counts[group] = group_counts.get(group, 0) + 1
            summary['groups'] = group_counts
        
        return summary
    
    def get_tag_names(self, group: Optional[str] = None) -> List[str]:
        """
        Get a list of all tag names in the metadata.
        
        This method returns all tag names from the loaded metadata, optionally
        filtered by metadata group.
        
        Args:
            group: Optional metadata group name to filter by (e.g., 'EXIF', 'IPTC', 'XMP', 'GPS').
                  If None, returns all tag names. Case-insensitive.
        
        Returns:
            List of tag names, optionally filtered by group
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     all_tags = exif.get_tag_names()
            ...     print(f"Total tags: {len(all_tags)}")
            ...     exif_tags = exif.get_tag_names('EXIF')
            ...     print(f"EXIF tags: {exif_tags}")
        """
        if group is None:
            # Return all tag names
            return list(self.metadata.keys())
        
        # Filter by group
        group_upper = group.upper()
        group_prefix = f"{group_upper}:"
        
        tag_names = []
        for tag_name in self.metadata.keys():
            if tag_name.upper().startswith(group_prefix):
                tag_names.append(tag_name)
        
        return tag_names
    
    def search_tags(self, pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
        """
        Search for tags matching a pattern.
        
        This method searches for tags whose names contain the specified pattern
        (substring match) and returns a dictionary of matching tags.
        
        Args:
            pattern: Pattern to search for in tag names (substring match)
            case_sensitive: If True, search is case-sensitive; if False (default), case-insensitive
        
        Returns:
            Dictionary of matching tags (tag_name -> value)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     # Search for tags containing "Make"
            ...     make_tags = exif.search_tags('Make')
            ...     # Search for tags containing "Date" (case-insensitive)
            ...     date_tags = exif.search_tags('Date')
        """
        matching_tags = {}
        pattern_lower = pattern.lower() if not case_sensitive else pattern
        
        for tag_name, value in self.metadata.items():
            tag_name_to_check = tag_name if case_sensitive else tag_name.lower()
            if pattern_lower in tag_name_to_check:
                matching_tags[tag_name] = value
        
        return matching_tags
    
    def filter_metadata_by_groups(self, groups: List[str], include: bool = True) -> Dict[str, Any]:
        """
        Filter metadata by group names.
        
        This method filters the current metadata to include or exclude tags
        from specified metadata groups (EXIF, IPTC, XMP, GPS, etc.).
        
        Args:
            groups: List of group names to filter by (e.g., ['EXIF', 'IPTC'])
            include: If True, include only tags from specified groups;
                    if False, exclude tags from specified groups
        
        Returns:
            Filtered metadata dictionary
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     # Get only EXIF tags
            ...     exif_only = exif.filter_metadata_by_groups(['EXIF'], include=True)
            ...     # Get all tags except IPTC
            ...     no_iptc = exif.filter_metadata_by_groups(['IPTC'], include=False)
        """
        filtered = {}
        
        for tag_name, value in self.metadata.items():
            tag_group = tag_name.split(':', 1)[0] if ':' in tag_name else ''
            
            if include:
                if tag_group in groups:
                    filtered[tag_name] = value
            else:
                if tag_group not in groups:
                    filtered[tag_name] = value
        
        return filtered
    
    def has_tag(self, tag_name: str) -> bool:
        """
        Check if a specific tag exists in the metadata.
        
        This method checks if a tag exists in the current metadata, including
        modified tags. It returns True if the tag exists (even if value is None),
        and False if the tag doesn't exist.
        
        Args:
            tag_name: Name of the tag to check (e.g., 'EXIF:Make', 'IPTC:Keywords')
        
        Returns:
            True if tag exists, False otherwise
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     if exif.has_tag('EXIF:Make'):
            ...         make = exif.get_tag('EXIF:Make')
            ...         print(f"Camera: {make}")
        """
        # Check modified tags first (including None values which indicate deletion)
        if tag_name in self.modified_tags:
            # If value is None, tag is marked for deletion, so it doesn't exist
            return self.modified_tags[tag_name] is not None
        
        # Check metadata dictionary
        return tag_name in self.metadata
    
    def filter_by_value(self, condition: Callable[[Any], bool], use_formatted_values: bool = False) -> Dict[str, Any]:
        """
        Filter metadata tags by their values using a condition function.
        
        This method filters the current metadata to include only tags whose
        values satisfy the specified condition function.
        
        Args:
            condition: A callable function that takes a tag value and returns
                     True if the tag should be included, False otherwise
            use_formatted_values: If True, uses formatted values (default standard format);
                                if False, uses raw unformatted values
        
        Returns:
            Filtered metadata dictionary containing only tags that match the condition
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     # Find tags with numeric values greater than 100 (using raw values)
            ...     large_values = exif.filter_by_value(lambda v: isinstance(v, (int, float)) and v > 100)
            ...     # Find tags containing 'Canon' in their value (works with formatted or raw)
            ...     canon_tags = exif.filter_by_value(lambda v: isinstance(v, str) and 'Canon' in v)
            ...     # Find tags with non-empty string values
            ...     non_empty = exif.filter_by_value(lambda v: isinstance(v, str) and len(v) > 0)
        """
        filtered = {}
        
        # Get current metadata including modified tags
        # Use format_values=False to get raw values for better filtering control
        current_metadata = self.get_all_metadata(format_values=use_formatted_values)
        
        for tag_name, value in current_metadata.items():
            try:
                if condition(value):
                    filtered[tag_name] = value
            except Exception:
                # Skip tags that cause errors in condition evaluation
                continue
        
        return filtered
    
    def get_tags_by_value(self, value: Any, case_sensitive: bool = True) -> Dict[str, Any]:
        """
        Find all tags that have a specific value.
        
        This method searches through all metadata tags and returns those
        that match the specified value. Useful for finding tags with
        exact value matches.
        
        Args:
            value: The value to search for (exact match)
            case_sensitive: If True (default), string comparison is case-sensitive;
                          if False, string comparison is case-insensitive
        
        Returns:
            Dictionary of tags that match the specified value (tag_name -> value)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     # Find all tags with value 'Canon'
            ...     canon_tags = exif.get_tags_by_value('Canon')
            ...     # Find all tags with value 100 (case-insensitive for strings)
            ...     value_100_tags = exif.get_tags_by_value(100)
            ...     # Find tags with value 'test' (case-insensitive)
            ...     test_tags = exif.get_tags_by_value('test', case_sensitive=False)
        """
        matching_tags = {}
        
        # Get current metadata including modified tags
        current_metadata = self.get_all_metadata(format_values=False)
        
        for tag_name, tag_value in current_metadata.items():
            try:
                # Handle string comparison with case sensitivity option
                if isinstance(value, str) and isinstance(tag_value, str):
                    if case_sensitive:
                        if tag_value == value:
                            matching_tags[tag_name] = tag_value
                    else:
                        if tag_value.lower() == value.lower():
                            matching_tags[tag_name] = tag_value
                else:
                    # For non-string values, use direct comparison
                    if tag_value == value:
                        matching_tags[tag_name] = tag_value
            except Exception:
                # Skip tags that cause errors in comparison
                continue
        
        return matching_tags
    
    def copy_metadata_from(self, source: Union['DNExif', Dict[str, Any]], tags: Optional[List[str]] = None, overwrite: bool = True) -> int:
        """
        Copy metadata from another DNExif instance or a metadata dictionary.
        
        This method copies metadata tags from a source (either another DNExif
        instance or a metadata dictionary) to the current instance. Useful for
        cloning metadata or copying metadata between files.
        
        Args:
            source: Source of metadata - either a DNExif instance or a metadata dictionary
            tags: Optional list of specific tag names to copy (if None, copies all)
            overwrite: If True (default), overwrites existing tags; if False, skips existing tags
        
        Returns:
            Number of tags copied
        
        Examples:
            >>> with DNExif('source.jpg') as source_exif:
            ...     with DNExif('target.jpg', read_only=False) as target_exif:
            ...         count = target_exif.copy_metadata_from(source_exif)
            ...         print(f"Copied {count} tags")
            ...         target_exif.save()
            >>> # Or copy from a metadata dictionary
            >>> metadata_dict = {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS'}
            >>> with DNExif('target.jpg', read_only=False) as exif:
            ...     count = exif.copy_metadata_from(metadata_dict)
            ...     exif.save()
        
        Raises:
            MetadataWriteError: If in read-only mode
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot copy metadata: File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        # Get source metadata
        if isinstance(source, DNExif):
            # Source is a DNExif instance
            if tags:
                source_metadata = {tag: source.get_tag(tag) for tag in tags}
            else:
                source_metadata = source.get_all_metadata(format_values=False)
        elif isinstance(source, dict):
            # Source is a metadata dictionary
            if tags:
                source_metadata = {tag: source.get(tag) for tag in tags if tag in source}
            else:
                source_metadata = source.copy()
        else:
            raise TypeError(f"Source must be a DNExif instance or a dictionary, got {type(source)}")
        
        # Copy tags
        copied_count = 0
        for tag_name, value in source_metadata.items():
            if value is None:
                continue
            
            # Skip tags without namespace prefix (e.g., SourceFile, FileName)
            if ':' not in tag_name:
                continue
            
            # Skip if tag exists and overwrite is False
            if not overwrite and self.has_tag(tag_name):
                continue
            
            try:
                self.set_tag(tag_name, value)
                copied_count += 1
            except Exception:
                # Skip tags that can't be set (e.g., invalid tag names)
                continue
        
        return copied_count
    
    def merge_metadata_from(
        self,
        source: Union['DNExif', Dict[str, Any]],
        tags: Optional[List[str]] = None,
        overwrite: bool = False,
        priority: Optional[List[str]] = None
    ) -> int:
        """
        Merge metadata from another DNExif instance or dictionary into the current instance.
        
        This method merges metadata from a source, resolving conflicts based on priority
        order. Unlike copy_metadata_from(), this method merges values rather than simply
        overwriting, and can resolve conflicts between different metadata sources.
        
        Args:
            source: DNExif instance or metadata dictionary to merge from
            tags: Optional list of tag names to merge (if None, merges all tags)
            overwrite: If True, overwrite existing tags; if False, only add missing tags (default: False)
            priority: Optional list of group names in priority order (e.g., ['EXIF', 'XMP', 'IPTC'])
                    Used to resolve conflicts when overwrite=False
        
        Returns:
            Number of tags merged
        
        Examples:
            >>> with DNExif('image1.jpg') as exif1, DNExif('image2.jpg') as exif2:
            ...     merged_count = exif1.merge_metadata_from(exif2)
            ...     print(f"Merged {merged_count} tags")
        """
        from dnexif.metadata_utils import merge_metadata
        
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot merge metadata: File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        # Get source metadata
        if isinstance(source, DNExif):
            source_metadata = source.get_all_metadata(format_values=False)
        elif isinstance(source, dict):
            source_metadata = source
        else:
            raise TypeError(f"Source must be DNExif instance or dict, got {type(source)}")
        
        # Filter tags if specified
        if tags:
            filtered_source = {tag: source_metadata.get(tag) for tag in tags if tag in source_metadata}
            source_metadata = filtered_source
        
        # Get current metadata
        current_metadata = self.get_all_metadata(format_values=False)
        
        # Merge metadata
        if overwrite:
            # Simple merge: overwrite existing tags
            merged_count = 0
            for tag, value in source_metadata.items():
                # Skip tags without namespace prefix
                if ':' not in tag:
                    continue
                # Skip None values
                if value is None:
                    continue
                # Set tag (will overwrite if exists)
                try:
                    self.set_tag(tag, value)
                    merged_count += 1
                except Exception:
                    # Skip invalid tags
                    pass
            return merged_count
        else:
            # Smart merge: resolve conflicts based on priority
            # Use merge_metadata utility if priority is specified
            if priority:
                merged_dict = merge_metadata(current_metadata, source_metadata, priority=priority)
            else:
                # Default: merge without overwriting existing tags
                merged_dict = current_metadata.copy()
                for tag, value in source_metadata.items():
                    if ':' not in tag or value is None:
                        continue
                    # Only add if tag doesn't exist
                    if tag not in merged_dict:
                        merged_dict[tag] = value
            
            # Apply merged metadata
            merged_count = 0
            for tag, value in merged_dict.items():
                if ':' not in tag or value is None:
                    continue
                # Only set tags that are new or changed
                current_value = current_metadata.get(tag)
                if current_value != value:
                    try:
                        self.set_tag(tag, value)
                        merged_count += 1
                    except Exception:
                        pass
            
            return merged_count
    
    def diff_with(self, other: Union['DNExif', Dict[str, Any]], ignore_tags: Optional[List[str]] = None, ignore_groups: Optional[List[str]] = None):
        """
        Compare metadata with another DNExif instance or a metadata dictionary.
        
        This method compares the current instance's metadata with another source
        and returns a DiffResult object showing the differences.
        
        Args:
            other: Source to compare with - either a DNExif instance or a metadata dictionary
            ignore_tags: Optional list of tag names to ignore in comparison
            ignore_groups: Optional list of group names to ignore (e.g., ['standard format'])
        
        Returns:
            DiffResult object with comparison results (from metadata_diff module)
        
        Examples:
            >>> with DNExif('image1.jpg') as exif1:
            ...     with DNExif('image2.jpg') as exif2:
            ...         diff = exif1.diff_with(exif2)
            ...         print(f"Added tags: {len(diff.added_tags)}")
            ...         print(f"Removed tags: {len(diff.removed_tags)}")
            ...         print(f"Changed tags: {len(diff.changed_tags)}")
            >>> # Or compare with a metadata dictionary
            >>> metadata_dict = {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS'}
            >>> with DNExif('image.jpg') as exif:
            ...     diff = exif.diff_with(metadata_dict)
        
        Raises:
            TypeError: If other is not a DNExif instance or a dictionary
        """
        from dnexif.metadata_diff import diff_metadata
        
        # Get current metadata
        current_metadata = self.get_all_metadata(format_values=False)
        
        # Get other metadata
        if isinstance(other, DNExif):
            other_metadata = other.get_all_metadata(format_values=False)
        elif isinstance(other, dict):
            other_metadata = other
        else:
            raise TypeError(f"Other must be a DNExif instance or a dictionary, got {type(other)}")
        
        # Compare metadata
        return diff_metadata(
            current_metadata,
            other_metadata,
            file1_path=self.file_path,
            file2_path=other.file_path if isinstance(other, DNExif) else None,
            ignore_tags=ignore_tags,
            ignore_groups=ignore_groups
        )
    
    def get_modified_tags(self) -> Dict[str, Any]:
        """
        Get all tags that have been modified (set or deleted) but not yet saved.
        
        This method returns a dictionary of all tags that have been modified
        since the file was opened. Tags set to None indicate deletions.
        
        Returns:
            Dictionary of modified tags (tag_name -> value, None for deletions)
        
        Examples:
            >>> with DNExif('image.jpg', read_only=False) as exif:
            ...     exif.set_tag('EXIF:Artist', 'John Doe')
            ...     exif.delete_tag('EXIF:Copyright')
            ...     modified = exif.get_modified_tags()
            ...     print(f"Modified tags: {modified}")
        """
        return self.modified_tags.copy()
    
    def has_pending_changes(self) -> bool:
        """
        Check if there are any pending changes (modified tags) that haven't been saved.
        
        This method returns True if any tags have been modified (set or deleted)
        since the file was opened, and False if there are no pending changes.
        
        Returns:
            True if there are pending changes, False otherwise
        
        Examples:
            >>> with DNExif('image.jpg', read_only=False) as exif:
            ...     if exif.has_pending_changes():
            ...         print("File has unsaved changes")
            ...     exif.set_tag('EXIF:Artist', 'John Doe')
            ...     if exif.has_pending_changes():
            ...         print("File has unsaved changes")
        """
        return len(self.modified_tags) > 0
    
    def clear_modified_tags(self) -> int:
        """
        Clear all modified tags, discarding any unsaved changes.
        
        This method removes all pending changes (both set and deleted tags)
        without saving them to the file. Useful for discarding changes and
        starting over.
        
        Returns:
            Number of modified tags that were cleared
        
        Examples:
            >>> with DNExif('image.jpg', read_only=False) as exif:
            ...     exif.set_tag('EXIF:Artist', 'John Doe')
            ...     exif.delete_tag('EXIF:Copyright')
            ...     count = exif.clear_modified_tags()
            ...     print(f"Cleared {count} modified tags")
        
        Raises:
            MetadataWriteError: If in read-only mode
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot clear modified tags: File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        count = len(self.modified_tags)
        self.modified_tags.clear()
        return count
    
    def is_tag_writable(self, tag_name: str) -> bool:
        """
        Check if a tag is writable.
        
        This method checks if a tag can be written to files. Some tags
        are read-only (e.g., computed tags, file system tags).
        
        Args:
            tag_name: Name of the tag to check (e.g., 'EXIF:Make', 'IPTC:Keywords')
        
        Returns:
            True if tag is writable, False otherwise
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     if exif.is_tag_writable('EXIF:Artist'):
            ...         exif.set_tag('EXIF:Artist', 'John Doe')
        """
        from dnexif.tag_lister import TagLister
        
        writable_tags = TagLister.list_writable_tags()
        return tag_name in writable_tags
    
    def validate_tag_name(self, tag_name: str) -> bool:
        """
        Validate a tag name format.
        
        This method checks if a tag name has the correct format (group:name).
        Tag names must include a namespace prefix (e.g., 'EXIF:Make').
        
        Args:
            tag_name: Tag name to validate
        
        Returns:
            True if tag name format is valid, False otherwise
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     if exif.validate_tag_name('EXIF:Make'):
            ...         print("Valid tag name")
        """
        # Tag names must include namespace prefix (group:name)
        if ':' not in tag_name:
            return False
        
        # Should have exactly one colon
        parts = tag_name.split(':')
        if len(parts) != 2:
            return False
        
        # Group and name should not be empty
        group, name = parts
        if not group.strip() or not name.strip():
            return False
        
        return True
    
    def validate_metadata(self) -> List[str]:
        """
        Validate metadata and return list of errors/warnings.
        
        This method checks the current metadata for common issues such as
        invalid date formats, out-of-range GPS coordinates, invalid image
        dimensions, and empty/null values in important tags.
        
        Returns:
            List of validation error/warning messages (empty list if no issues)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     errors = exif.validate_metadata()
            ...     if errors:
            ...         for error in errors:
            ...             print(f"Warning: {error}")
        """
        errors = []
        metadata = self.get_all_metadata(format_values=False)
        
        # Check for common metadata issues
        # 1. Check for invalid date formats
        date_tags = ['EXIF:DateTime', 'EXIF:DateTimeOriginal', 'EXIF:DateTimeDigitized',
                     'IPTC:DateCreated', 'IPTC:TimeCreated', 'XMP:CreateDate']
        for tag in date_tags:
            if tag in metadata:
                value = str(metadata[tag])
                # Basic date validation - check if it looks like a valid date
                if value and len(value) > 0:
                    # Check for obviously invalid dates
                    if value == '0000:00:00 00:00:00' or value.startswith('0000'):
                        errors.append(f"Warning: {tag} has invalid date value: {value}")
        
        # 2. Check for GPS coordinate validity
        if 'GPS:GPSLatitude' in metadata and 'GPS:GPSLongitude' in metadata:
            try:
                lat_str = str(metadata['GPS:GPSLatitude'])
                lon_str = str(metadata['GPS:GPSLongitude'])
                # Try to extract numeric values
                lat = self.get_tag_as_float('GPS:GPSLatitude')
                lon = self.get_tag_as_float('GPS:GPSLongitude')
                if abs(lat) > 90:
                    errors.append(f"Warning: GPS:GPSLatitude out of range: {lat}")
                if abs(lon) > 180:
                    errors.append(f"Warning: GPS:GPSLongitude out of range: {lon}")
            except (ValueError, TypeError):
                pass
        
        # 3. Check for required EXIF tags consistency
        if 'EXIF:ExifImageWidth' in metadata and 'EXIF:ExifImageHeight' in metadata:
            try:
                width = self.get_tag_as_int('EXIF:ExifImageWidth')
                height = self.get_tag_as_int('EXIF:ExifImageHeight')
                if width <= 0 or height <= 0:
                    errors.append(f"Warning: Invalid image dimensions: {width}x{height}")
            except (ValueError, TypeError):
                pass
        
        # 4. Check for empty or null values in important tags
        important_tags = ['EXIF:Make', 'EXIF:Model', 'EXIF:Artist']
        for tag in important_tags:
            if tag in metadata:
                value = str(metadata[tag]).strip()
                if not value or value.lower() in ['none', 'null', '']:
                    errors.append(f"Warning: {tag} appears to be empty or null")
        
        return errors
    
    def get_metadata_completeness(self) -> Dict[str, Any]:
        """
        Calculate metadata completeness score based on presence of important tags.
        
        This method evaluates the completeness of metadata by checking for the
        presence of important tags across different categories (camera info,
        image properties, GPS, dates, etc.) and calculates a score from 0-100.
        
        Returns:
            Dictionary with completeness information:
            - score: Overall completeness score (0-100)
            - categories: Dictionary with scores per category
            - missing_tags: List of important tags that are missing
            - present_tags: List of important tags that are present
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     completeness = exif.get_metadata_completeness()
            ...     print(f"Completeness: {completeness['score']}%")
        """
        # Define important tags by category
        important_tags = {
            'camera_info': [
                'EXIF:Make',
                'EXIF:Model',
                'EXIF:LensModel',
                'EXIF:LensMake'
            ],
            'image_properties': [
                'EXIF:ImageWidth',
                'EXIF:ImageHeight',
                'EXIF:Orientation',
                'EXIF:ColorSpace',
                'EXIF:BitsPerSample'
            ],
            'exposure': [
                'EXIF:ISO',
                'EXIF:ExposureTime',
                'EXIF:FNumber',
                'EXIF:ExposureProgram',
                'EXIF:MeteringMode'
            ],
            'dates': [
                'EXIF:DateTime',
                'EXIF:DateTimeOriginal',
                'EXIF:DateTimeDigitized'
            ],
            'gps': [
                'GPS:GPSLatitude',
                'GPS:GPSLongitude',
                'GPS:GPSAltitude'
            ],
            'iptc': [
                'IPTC:Keywords',
                'IPTC:Caption',
                'IPTC:Headline',
                'IPTC:Byline'
            ],
            'xmp': [
                'XMP:Title',
                'XMP:Description',
                'XMP:Creator',
                'XMP:CreateDate'
            ]
        }
        
        # Calculate scores per category
        category_scores = {}
        missing_tags = []
        present_tags = []
        
        for category, tags in important_tags.items():
            present_count = 0
            category_missing = []
            
            for tag in tags:
                if self.has_tag(tag):
                    value = self.get_tag(tag)
                    # Check if value is not empty/null
                    if value is not None and str(value).strip() not in ['', 'None', 'null']:
                        present_count += 1
                        present_tags.append(tag)
                    else:
                        category_missing.append(tag)
                        missing_tags.append(tag)
                else:
                    category_missing.append(tag)
                    missing_tags.append(tag)
            
            # Calculate category score (percentage)
            total_tags = len(tags)
            category_score = (present_count / total_tags * 100) if total_tags > 0 else 0
            category_scores[category] = {
                'score': category_score,
                'present': present_count,
                'total': total_tags,
                'missing': category_missing
            }
        
        # Calculate overall score (weighted average)
        # Weights: camera_info (20%), image_properties (15%), exposure (20%),
        #          dates (15%), gps (10%), iptc (10%), xmp (10%)
        weights = {
            'camera_info': 0.20,
            'image_properties': 0.15,
            'exposure': 0.20,
            'dates': 0.15,
            'gps': 0.10,
            'iptc': 0.10,
            'xmp': 0.10
        }
        
        overall_score = sum(
            category_scores[cat]['score'] * weights.get(cat, 0)
            for cat in category_scores.keys()
        )
        
        return {
            'score': round(overall_score, 2),
            'categories': category_scores,
            'missing_tags': missing_tags,
            'present_tags': present_tags
        }
    
    def get_normalized_metadata(
        self,
        unify_dates: bool = True,
        resolve_conflicts: bool = True
    ) -> Dict[str, Any]:
        """
        Get normalized metadata with unified dates and resolved conflicts.
        
        This method returns metadata that has been normalized using the
        metadata normalization utilities. It unifies date fields across
        different sources (EXIF, IPTC, XMP) and resolves priority conflicts
        for common tags.
        
        Args:
            unify_dates: If True, unify date fields across sources (default: True)
            resolve_conflicts: If True, resolve priority conflicts for common tags (default: True)
        
        Returns:
            Dictionary with normalized metadata (includes original tags plus normalized fields)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     normalized = exif.get_normalized_metadata()
            ...     # Unified date fields and resolved conflicts are added
        """
        from dnexif.metadata_normalizer import normalize_metadata
        
        # Get all metadata including modified tags
        metadata = self.get_all_metadata(format_values=False)
        
        # Normalize metadata
        normalized = normalize_metadata(
            metadata,
            config=None,
            unify_dates=unify_dates,
            resolve_conflicts=resolve_conflicts
        )
        
        return normalized
    
    def get_metadata_as_list(
        self,
        format_values: bool = True,
        sort_by_tag: bool = True
    ) -> List[Tuple[str, Any]]:
        """
        Get metadata as a list of (tag, value) tuples.
        
        This method returns metadata in a list format, which can be useful
        for iteration, sorting, filtering, and other list-based operations.
        
        Args:
            format_values: If True, format values to standard format output format (default: True)
            sort_by_tag: If True, sort the list by tag name (default: True)
        
        Returns:
            List of tuples, where each tuple is (tag_name, value)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     metadata_list = exif.get_metadata_as_list()
            ...     for tag, value in metadata_list:
            ...         print(f"{tag}: {value}")
        """
        metadata = self.get_all_metadata(format_values=format_values)
        
        # Convert to list of tuples
        metadata_list = [(tag, value) for tag, value in metadata.items()]
        
        # Sort by tag name if requested
        if sort_by_tag:
            metadata_list.sort(key=lambda x: x[0])
        
        return metadata_list
    
    def get_metadata_grouped(
        self,
        format_values: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata grouped by namespace/group.
        
        This method returns metadata organized by group (EXIF, IPTC, XMP, GPS, etc.),
        making it easy to access all tags from a specific namespace.
        
        Args:
            format_values: If True, format values to standard format output format (default: True)
        
        Returns:
            Dictionary mapping group names to dictionaries of tags in that group
            Format: {'EXIF': {'EXIF:Make': 'Canon', ...}, 'IPTC': {...}, ...}
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     grouped = exif.get_metadata_grouped()
            ...     exif_tags = grouped.get('EXIF', {})
            ...     print(f"EXIF tags: {len(exif_tags)}")
        """
        metadata = self.get_all_metadata(format_values=format_values)
        grouped = {}
        
        for tag_name, value in metadata.items():
            if ':' in tag_name:
                group = tag_name.split(':', 1)[0]
            else:
                group = 'Unknown'
            
            if group not in grouped:
                grouped[group] = {}
            
            grouped[group][tag_name] = value
        
        return grouped
    
    def get_metadata_keys(
        self,
        format_values: bool = True,
        sort: bool = False
    ) -> List[str]:
        """
        Get list of all metadata tag names (keys).
        
        This method returns a list of all tag names in the metadata,
        which can be useful for iteration, filtering, and other operations.
        
        Args:
            format_values: If True, uses formatted metadata (default: True)
            sort: If True, sort the keys alphabetically (default: False)
        
        Returns:
            List of tag names (keys)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     keys = exif.get_metadata_keys()
            ...     print(f"Found {len(keys)} tags")
        """
        metadata = self.get_all_metadata(format_values=format_values)
        keys = list(metadata.keys())
        
        if sort:
            keys.sort()
        
        return keys
    
    def get_metadata_values(
        self,
        format_values: bool = True,
        sort_by_tag: bool = False
    ) -> List[Any]:
        """
        Get list of all metadata values.
        
        This method returns a list of all tag values in the metadata,
        which can be useful for value-based operations and analysis.
        
        Args:
            format_values: If True, uses formatted metadata (default: True)
            sort_by_tag: If True, sort values by their corresponding tag names (default: False)
        
        Returns:
            List of tag values
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     values = exif.get_metadata_values()
            ...     print(f"Found {len(values)} values")
        """
        metadata = self.get_all_metadata(format_values=format_values)
        
        if sort_by_tag:
            # Sort by tag name, then extract values
            sorted_items = sorted(metadata.items())
            values = [value for _, value in sorted_items]
        else:
            values = list(metadata.values())
        
        return values
    
    def is_metadata_empty(self) -> bool:
        """
        Check if metadata is empty (no tags present).
        
        This method provides a quick check to determine if the file
        has any metadata tags.
        
        Returns:
            True if metadata is empty (no tags), False otherwise
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     if not exif.is_metadata_empty():
            ...         print("File has metadata")
        """
        metadata = self.get_all_metadata(format_values=False)
        return len(metadata) == 0
    
    def get_metadata_count(self) -> int:
        """
        Get the total count of metadata tags.
        
        This method returns the number of metadata tags present in the file,
        including modified tags.
        
        Returns:
            Total number of metadata tags
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     count = exif.get_metadata_count()
            ...     print(f"Found {count} metadata tags")
        """
        metadata = self.get_all_metadata(format_values=False)
        return len(metadata)
    
    def get_metadata_as_string(self, format_values: bool = True, sort_by_tag: bool = True, separator: str = ": ") -> str:
        """
        Get metadata as a formatted string representation.
        
        This method returns metadata formatted as a human-readable string,
        similar to standard text output format.
        
        Args:
            format_values: If True, uses formatted metadata (default: True)
            sort_by_tag: If True, sort tags alphabetically (default: True)
            separator: String separator between tag name and value (default: ": ")
        
        Returns:
            Formatted string with one tag per line
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     metadata_str = exif.get_metadata_as_string()
            ...     print(metadata_str)
        """
        metadata = self.get_all_metadata(format_values=format_values)
        
        if sort_by_tag:
            items = sorted(metadata.items())
        else:
            items = metadata.items()
        
        lines = []
        for tag_name, value in items:
            # Convert value to string, handling None and special cases
            if value is None:
                value_str = ""
            elif isinstance(value, (list, tuple)):
                value_str = ", ".join(str(v) for v in value)
            else:
                value_str = str(value)
            
            lines.append(f"{tag_name}{separator}{value_str}")
        
        return "\n".join(lines)
    
    def get_metadata_statistics(self) -> Dict[str, Any]:
        """
        Get detailed statistics about the metadata.
        
        This method provides comprehensive statistics about the metadata,
        including counts by group, value types, and other metadata characteristics.
        
        Returns:
            Dictionary with detailed statistics:
            - total_tags: Total number of metadata tags
            - groups: Dictionary mapping group names to tag counts
            - value_types: Dictionary mapping value types to counts
            - has_exif: Boolean indicating if EXIF metadata exists
            - has_iptc: Boolean indicating if IPTC metadata exists
            - has_xmp: Boolean indicating if XMP metadata exists
            - has_gps: Boolean indicating if GPS metadata exists
            - has_makernote: Boolean indicating if MakerNote metadata exists
            - empty_tags: Number of tags with empty/None values
            - list_tags: Number of tags with list/array values
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     stats = exif.get_metadata_statistics()
            ...     print(f"Total tags: {stats['total_tags']}")
            ...     print(f"EXIF tags: {stats['groups'].get('EXIF', 0)}")
        """
        metadata = self.get_all_metadata(format_values=False)
        
        stats = {
            'total_tags': len(metadata),
            'groups': {},
            'value_types': {},
            'has_exif': False,
            'has_iptc': False,
            'has_xmp': False,
            'has_gps': False,
            'has_makernote': False,
            'empty_tags': 0,
            'list_tags': 0,
        }
        
        # Analyze each tag
        for tag_name, value in metadata.items():
            # Group statistics
            if ':' in tag_name:
                group = tag_name.split(':', 1)[0]
            else:
                group = 'Unknown'
            
            stats['groups'][group] = stats['groups'].get(group, 0) + 1
            
            # Set group flags
            if group == 'EXIF':
                stats['has_exif'] = True
            elif group == 'IPTC':
                stats['has_iptc'] = True
            elif group == 'XMP':
                stats['has_xmp'] = True
            elif group == 'GPS':
                stats['has_gps'] = True
            elif 'MakerNote' in group or 'MakerNotes' in tag_name:
                stats['has_makernote'] = True
            
            # Value type statistics
            value_type = type(value).__name__
            stats['value_types'][value_type] = stats['value_types'].get(value_type, 0) + 1
            
            # Empty tags
            if value is None or value == '' or (isinstance(value, (list, tuple)) and len(value) == 0):
                stats['empty_tags'] += 1
            
            # List tags
            if isinstance(value, (list, tuple)):
                stats['list_tags'] += 1
        
        return stats
    
    def get_tag_value_type(self, tag_name: str) -> Optional[str]:
        """
        Get the type of a tag's value.
        
        This method returns the Python type name of a tag's value,
        which can be useful for type checking and validation.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:Make', 'EXIF:ISO')
        
        Returns:
            Type name as string (e.g., 'str', 'int', 'float', 'list', 'tuple', 'NoneType'),
            or None if tag does not exist
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     value_type = exif.get_tag_value_type('EXIF:Make')
            ...     print(f"Make tag type: {value_type}")  # 'str'
            ...     value_type = exif.get_tag_value_type('EXIF:ISO')
            ...     print(f"ISO tag type: {value_type}")  # 'int'
        """
        value = self.get_tag(tag_name)
        
        if value is None:
            # Check if tag exists but has None value
            if tag_name in self.metadata or tag_name in self.modified_tags:
                return 'NoneType'
            # Tag doesn't exist
            return None
        
        return type(value).__name__
    
    def get_tags_by_value_type(self, value_type: str) -> Dict[str, Any]:
        """
        Get all tags that have a specific value type.
        
        This method returns all metadata tags whose values match the specified
        Python type name. Useful for filtering tags by type.
        
        Args:
            value_type: Python type name (e.g., 'str', 'int', 'float', 'list', 'tuple', 'NoneType')
        
        Returns:
            Dictionary of tags with the specified value type (tag_name -> value)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     # Get all string tags
            ...     string_tags = exif.get_tags_by_value_type('str')
            ...     # Get all integer tags
            ...     int_tags = exif.get_tags_by_value_type('int')
            ...     # Get all list tags
            ...     list_tags = exif.get_tags_by_value_type('list')
        """
        matching_tags = {}
        
        # Get current metadata including modified tags
        metadata = self.get_all_metadata(format_values=False)
        
        for tag_name, value in metadata.items():
            tag_type = type(value).__name__
            if tag_type == value_type:
                matching_tags[tag_name] = value
        
        return matching_tags
    
    def get_empty_tags(self) -> Dict[str, Any]:
        """
        Get all tags that have empty values.
        
        This method returns all metadata tags whose values are considered empty,
        including None, empty strings, empty lists, and empty tuples.
        
        Returns:
            Dictionary of tags with empty values (tag_name -> value)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     empty_tags = exif.get_empty_tags()
            ...     print(f"Found {len(empty_tags)} empty tags")
        """
        empty_tags = {}
        
        # Get current metadata including modified tags
        metadata = self.get_all_metadata(format_values=False)
        
        for tag_name, value in metadata.items():
            # Check if value is empty
            if value is None:
                empty_tags[tag_name] = value
            elif isinstance(value, str) and value == '':
                empty_tags[tag_name] = value
            elif isinstance(value, (list, tuple)) and len(value) == 0:
                empty_tags[tag_name] = value
            elif isinstance(value, dict) and len(value) == 0:
                empty_tags[tag_name] = value
        
        return empty_tags
    
    def get_tag_info(self, tag_name: str) -> Dict[str, Any]:
        """
        Get information about a specific tag.
        
        This method returns information about a tag including whether it exists,
        is writable, its group, and other metadata.
        
        Args:
            tag_name: Name of the tag to get information about
        
        Returns:
            Dictionary with tag information (name, group, writable, exists, type)
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     info = exif.get_tag_info('EXIF:Make')
            ...     print(f"Writable: {info['writable']}")
            ...     print(f"Group: {info['group']}")
        """
        from dnexif.tag_lister import TagLister
        
        return TagLister.get_tag_info(tag_name)
    
    def get_tag(self, tag_name: str, default: Any = None) -> Any:
        """
        Get a specific metadata tag value.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:Make', 'IPTC:Keywords')
            default: Default value if tag is not found
            
        Returns:
            Tag value or default if not found
        """
        # Check modified tags first
        if tag_name in self.modified_tags:
            return self.modified_tags[tag_name]
        
        return self.metadata.get(tag_name, default)
    
    def get_formatted_tag(self, tag_name: str, default: str = '') -> str:
        """
        Get a specific metadata tag value as a formatted string.
        
        This method returns the tag value formatted to standard format output format,
        which is useful for display purposes and ensuring consistent formatting.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:Make', 'EXIF:Orientation')
            default: Default string value if tag is not found (default: empty string)
            
        Returns:
            Formatted tag value as string, or default if tag not found
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     orientation = exif.get_formatted_tag('EXIF:Orientation')
            ...     print(f"Orientation: {orientation}")
            ...     # Returns: "Orientation: Normal" (formatted string)
        """
        from dnexif.value_formatter import format_exif_value
        
        # Get raw tag value
        raw_value = self.get_tag(tag_name)
        
        # If tag not found, return default
        if raw_value is None:
            return default
        
        # Format the value
        try:
            formatted = format_exif_value(tag_name, raw_value, context=self.metadata)
            return formatted if formatted is not None else str(raw_value)
        except Exception:
            # If formatting fails, return string representation of raw value
            return str(raw_value) if raw_value is not None else default
    
    def get_tag_as_int(self, tag_name: str, default: int = 0) -> int:
        """
        Get a metadata tag value as an integer.
        
        This method retrieves a tag value and converts it to an integer.
        Useful for numeric tags like EXIF:ISO, EXIF:Orientation, etc.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:ISO', 'EXIF:Orientation')
            default: Default integer value if tag is not found or cannot be converted
        
        Returns:
            Tag value as integer, or default if not found or conversion fails
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     iso = exif.get_tag_as_int('EXIF:ISO')
            ...     print(f"ISO: {iso}")
        """
        value = self.get_tag(tag_name)
        if value is None:
            return default
        
        try:
            # Try direct conversion
            if isinstance(value, (int, float)):
                return int(value)
            # Try string conversion
            if isinstance(value, str):
                # Remove common formatting (e.g., "100" -> 100)
                cleaned = value.strip().replace(',', '')
                # Try to parse as integer
                return int(float(cleaned)) if '.' in cleaned else int(cleaned)
            # Try list/tuple (take first element)
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return self.get_tag_as_int(tag_name, default) if isinstance(value[0], str) else int(value[0])
        except (ValueError, TypeError, IndexError):
            pass
        
        return default
    
    def get_tag_as_float(self, tag_name: str, default: float = 0.0) -> float:
        """
        Get a metadata tag value as a float.
        
        This method retrieves a tag value and converts it to a float.
        Useful for numeric tags with decimal values like GPS coordinates, focal length, etc.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:FocalLength', 'GPS:GPSLatitude')
            default: Default float value if tag is not found or cannot be converted
        
        Returns:
            Tag value as float, or default if not found or conversion fails
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     focal_length = exif.get_tag_as_float('EXIF:FocalLength')
            ...     print(f"Focal Length: {focal_length}mm")
        """
        value = self.get_tag(tag_name)
        if value is None:
            return default
        
        try:
            # Try direct conversion
            if isinstance(value, (int, float)):
                return float(value)
            # Try string conversion
            if isinstance(value, str):
                # Remove common formatting (e.g., "100.5" -> 100.5)
                cleaned = value.strip().replace(',', '')
                return float(cleaned)
            # Try list/tuple (take first element)
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return self.get_tag_as_float(tag_name, default) if isinstance(value[0], str) else float(value[0])
            # Try rational (numerator/denominator)
            if isinstance(value, tuple) and len(value) == 2:
                num, den = value
                if den != 0:
                    return float(num) / float(den)
        except (ValueError, TypeError, IndexError, ZeroDivisionError):
            pass
        
        return default
    
    def get_tag_as_date(self, tag_name: str, default: Optional[datetime] = None) -> Optional[datetime]:
        """
        Get a metadata tag value as a datetime object.
        
        This method retrieves a tag value and converts it to a datetime object.
        Useful for date/time tags like EXIF:DateTimeOriginal, EXIF:CreateDate, etc.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:DateTimeOriginal', 'EXIF:CreateDate')
            default: Default datetime value if tag is not found or cannot be converted (None)
        
        Returns:
            Tag value as datetime object, or default if not found or conversion fails
        
        Examples:
            >>> from datetime import datetime
            >>> with DNExif('image.jpg') as exif:
            ...     date_taken = exif.get_tag_as_date('EXIF:DateTimeOriginal')
            ...     if date_taken:
            ...         print(f"Date taken: {date_taken}")
        """
        from datetime import datetime
        
        value = self.get_tag(tag_name)
        if value is None:
            return default
        
        try:
            # Try direct datetime conversion
            if isinstance(value, datetime):
                return value
            
            # Try string conversion (common EXIF date format: "YYYY:MM:DD HH:MM:SS")
            if isinstance(value, str):
                # Try EXIF format: "YYYY:MM:DD HH:MM:SS"
                if ':' in value and ' ' in value:
                    date_str, time_str = value.split(' ', 1)
                    year, month, day = date_str.split(':')
                    hour, minute, second = time_str.split(':')[:3]
                    return datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute), int(second.split('.')[0]) if '.' in second else int(second)
                    )
                # Try ISO format: "YYYY-MM-DDTHH:MM:SS"
                if 'T' in value or '-' in value:
                    # Try parsing as ISO format
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        pass
                # Try other common formats
                # Format: "YYYY-MM-DD HH:MM:SS"
                if len(value) >= 19 and value[4] == '-' and value[7] == '-':
                    return datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')
            
            # Try list/tuple (take first element)
            if isinstance(value, (list, tuple)) and len(value) > 0:
                return self.get_tag_as_date(tag_name, default)
        except (ValueError, TypeError, IndexError, AttributeError):
            pass
        
        return default
    
    def get_tags_as_int(self, tag_names: List[str], default: int = 0) -> Dict[str, int]:
        """
        Get multiple metadata tag values as integers.
        
        This method retrieves multiple tag values and converts them to integers.
        Useful for batch processing of numeric tags.
        
        Args:
            tag_names: List of tag names to retrieve (e.g., ['EXIF:ISO', 'EXIF:Orientation'])
            default: Default integer value if tag is not found or cannot be converted
        
        Returns:
            Dictionary mapping tag names to integer values
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     values = exif.get_tags_as_int(['EXIF:ISO', 'EXIF:Orientation'])
            ...     print(f"ISO: {values['EXIF:ISO']}, Orientation: {values['EXIF:Orientation']}")
        """
        result = {}
        for tag_name in tag_names:
            result[tag_name] = self.get_tag_as_int(tag_name, default=default)
        return result
    
    def get_tags_as_float(self, tag_names: List[str], default: float = 0.0) -> Dict[str, float]:
        """
        Get multiple metadata tag values as floats.
        
        This method retrieves multiple tag values and converts them to floats.
        Useful for batch processing of numeric tags with decimal values.
        
        Args:
            tag_names: List of tag names to retrieve (e.g., ['EXIF:FocalLength', 'GPS:GPSLatitude'])
            default: Default float value if tag is not found or cannot be converted
        
        Returns:
            Dictionary mapping tag names to float values
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     values = exif.get_tags_as_float(['EXIF:FocalLength', 'GPS:GPSLatitude'])
            ...     print(f"Focal Length: {values['EXIF:FocalLength']}mm")
        """
        result = {}
        for tag_name in tag_names:
            result[tag_name] = self.get_tag_as_float(tag_name, default=default)
        return result
    
    def get_tags_as_date(self, tag_names: List[str], default: Optional[datetime] = None) -> Dict[str, Optional[datetime]]:
        """
        Get multiple metadata tag values as datetime objects.
        
        This method retrieves multiple tag values and converts them to datetime objects.
        Useful for batch processing of date/time tags.
        
        Args:
            tag_names: List of tag names to retrieve (e.g., ['EXIF:DateTimeOriginal', 'EXIF:CreateDate'])
            default: Default datetime value if tag is not found or cannot be converted (None)
        
        Returns:
            Dictionary mapping tag names to datetime objects (or None)
        
        Examples:
            >>> from datetime import datetime
            >>> with DNExif('image.jpg') as exif:
            ...     dates = exif.get_tags_as_date(['EXIF:DateTimeOriginal', 'EXIF:CreateDate'])
            ...     if dates['EXIF:DateTimeOriginal']:
            ...         print(f"Date taken: {dates['EXIF:DateTimeOriginal']}")
        """
        result = {}
        for tag_name in tag_names:
            result[tag_name] = self.get_tag_as_date(tag_name, default=default)
        return result
    
    def set_tags_helper(self, tags: Dict[str, Any]) -> int:
        """
        Helper function for use in advanced formatting expressions.
        
        This method allows setting tags dynamically from within formatting expressions,
        enabling conditional tag setting and computed tag values.
        
        Args:
            tags: Dictionary of tag names to values to set
            
        Returns:
            Number of tags successfully set
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> # In a formatting expression context:
            >>> exif.set_tags_helper({'EXIF:Artist': 'John Doe', 'EXIF:Copyright': '2025'})
            2
        """
        count = 0
        for tag_name, value in tags.items():
            try:
                self.set_tag(tag_name, value)
                count += 1
            except Exception:
                # Ignore errors in helper function (formatting expressions should be resilient)
                pass
        return count
    
    def set_alternate_file(self, index: int, file_path: Union[str, Path]) -> None:
        """
        Set an alternate file to load tags from.
        
        Alternate files can be used to load metadata from additional files
        (e.g., sidecar files, backup files) and merge them with the main file's metadata.
        This is useful for workflows where metadata may be stored in multiple files.
        
        Args:
            index: Index of the alternate file (0-4, matching standard format -file0 to -file4)
            file_path: Path to the alternate file
            
        Raises:
            FileNotFoundError: If the alternate file does not exist
            ValueError: If index is not in range 0-4
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_alternate_file(0, 'image.jpg.xmp')  # Load XMP sidecar
            >>> exif.set_alternate_file(1, 'backup.jpg')     # Load backup file
        """
        if not (0 <= index <= 4):
            raise ValueError(f"Alternate file index must be between 0 and 4, got {index}")
        
        alt_path = Path(file_path)
        if not alt_path.exists():
            raise FileNotFoundError(f"Alternate file not found: {file_path}")
        
        self.alternate_files[index] = alt_path
        
        # Load metadata from alternate file and merge with current metadata
        try:
            alt_exif = DNExif(alt_path, read_only=True, fast_mode=self.fast_mode,
                            scan_for_xmp=self.scan_for_xmp,
                            ignore_minor_errors=self.ignore_minor_errors)
            alt_metadata = alt_exif.get_all_metadata(format_values=False)
            
            # Merge alternate file metadata (alternate file tags take precedence if conflict)
            for tag_name, tag_value in alt_metadata.items():
                # Prefix alternate file tags with "AlternateFileN:" namespace
                prefixed_tag = f"AlternateFile{index}:{tag_name}"
                self.metadata[prefixed_tag] = tag_value
            
            # Also add summary tag
            self.metadata[f"AlternateFile{index}:HasAlternateFile"] = True
            self.metadata[f"AlternateFile{index}:AlternateFilePath"] = str(alt_path)
            self.metadata[f"AlternateFile{index}:AlternateFileTags"] = len(alt_metadata)
        except Exception as e:
            # If loading alternate file fails, still record that it was set
            self.metadata[f"AlternateFile{index}:HasAlternateFile"] = True
            self.metadata[f"AlternateFile{index}:AlternateFilePath"] = str(alt_path)
            self.metadata[f"AlternateFile{index}:LoadError"] = str(e)
            if not self.ignore_minor_errors:
                raise
    
    @staticmethod
    def ordered_keys(structure_value: Any, sort: bool = False) -> List[str]:
        """
        Return the ordered or sorted keys from a returned structure value.
        
        This method extracts keys from structured metadata values (dictionaries, lists, etc.)
        and returns them in their original order or sorted order.
        
        Args:
            structure_value: The structure value to extract keys from (dict, list, tuple, etc.)
            sort: If True, return keys in sorted order. If False, return in original order.
            
        Returns:
            List of keys from the structure value
            
        Examples:
            >>> metadata = {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS 5D', 'EXIF:ISO': 100}
            >>> DNExif.ordered_keys(metadata)
            ['EXIF:Make', 'EXIF:Model', 'EXIF:ISO']
            >>> DNExif.ordered_keys(metadata, sort=True)
            ['EXIF:ISO', 'EXIF:Make', 'EXIF:Model']
        """
        if structure_value is None:
            return []
        
        # Handle dictionaries
        if isinstance(structure_value, dict):
            keys = list(structure_value.keys())
            if sort:
                return sorted(keys)
            return keys
        
        # Handle lists and tuples
        if isinstance(structure_value, (list, tuple)):
            # For lists/tuples, return indices as keys
            keys = [str(i) for i in range(len(structure_value))]
            if sort:
                return sorted(keys, key=int)
            return keys
        
        # Handle other iterable types
        if hasattr(structure_value, '__iter__') and not isinstance(structure_value, (str, bytes)):
            try:
                keys = list(structure_value)
                if sort:
                    return sorted(str(k) for k in keys)
                return [str(k) for k in keys]
            except Exception:
                pass
        
        # For non-structured values, return empty list
        return []
    
    @staticmethod
    def available_options() -> Dict[str, Dict[str, Any]]:
        """
        Return a dictionary of available API options.
        
        This method provides information about all available API options that can be
        set via the API or configuration. Each option includes its name, description,
        type, default value, and whether it's currently supported.
        
        Returns:
            Dictionary mapping option names to their metadata:
            {
                'OptionName': {
                    'description': 'Description of the option',
                    'type': 'bool|str|int|float',
                    'default': default_value,
                    'supported': True|False
                },
                ...
            }
        """
        return {
            'NoWarning': {
                'description': 'Suppress warning messages during metadata operations',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'NoMandatory': {
                'description': 'Skip mandatory tag validation checks',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'ByteUnit': {
                'description': 'Unit for byte values (B, KB, MB, GB)',
                'type': 'str',
                'default': 'B',
                'supported': True
            },
            'ImageHashType': {
                'description': 'Hash algorithm for image data (MD5, SHA1, SHA256)',
                'type': 'str',
                'default': 'MD5',
                'supported': True
            },
            'StructFormat': {
                'description': 'Format for structured values (JSON, JSONQ)',
                'type': 'str',
                'default': 'JSON',
                'supported': True
            },
            'NoDups': {
                'description': 'Eliminate duplicate items from list-type tags when writing',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'BlockExtract': {
                'description': 'Extract metadata blocks as binary data',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'FilterW': {
                'description': 'Filter tags when writing metadata',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'NoPDFList': {
                'description': 'Do not list PDF objects in metadata output',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'QuickTimePad': {
                'description': 'Pad QuickTime atoms to specific boundaries',
                'type': 'int',
                'default': 0,
                'supported': True
            },
            'QuickTimeHandler': {
                'description': 'Specify QuickTime handler type',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'IgnoreGroups': {
                'description': 'Ignore specific metadata groups during operations',
                'type': 'list',
                'default': [],
                'supported': True
            },
            'IgnoreTags': {
                'description': 'Ignore specific tags during operations',
                'type': 'list',
                'default': [],
                'supported': True
            },
            'WindowsLongPath': {
                'description': 'Enable Windows long path support (>260 characters)',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'WindowsWideFile': {
                'description': 'Use wide character file paths on Windows',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'KeepUTCTime': {
                'description': 'Keep UTC timezone in date/time values',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'LimitLongValues': {
                'description': 'Maximum length for long tag values',
                'type': 'int',
                'default': 0,
                'supported': True
            },
            'GeolocAltNames': {
                'description': 'Use alternate names for geolocation lookup',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'GeolocFeature': {
                'description': 'Feature type for geolocation (city, country, etc.)',
                'type': 'str',
                'default': 'city',
                'supported': True
            },
            'GeolocMaxDist': {
                'description': 'Maximum distance for geolocation search (km)',
                'type': 'float',
                'default': 0.0,
                'supported': True
            },
            'GeolocMinPop': {
                'description': 'Minimum population for geolocation results',
                'type': 'int',
                'default': 0,
                'supported': True
            },
            'GeoSpeedRef': {
                'description': 'Reference for GPS speed values',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'SavePath': {
                'description': 'Path for saving files',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'SaveFormat': {
                'description': 'Format for saving files',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'SymLink': {
                'description': 'Follow symbolic links',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'UndefTags': {
                'description': 'Allow undefined tags in expressions',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'PrintCSV': {
                'description': 'Print output in CSV format',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'Compact': {
                'description': 'Use compact output format',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'XMPShorthand': {
                'description': 'Use XMP shorthand notation',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'LargeFileSupport': {
                'description': 'Enable support for large files (>2GB)',
                'type': 'bool',
                'default': True,
                'supported': True
            },
            'FastScan': {
                'description': 'Use fast scanning mode (skip some metadata)',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'ListJoin': {
                'description': 'Join list values with separator',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'HexTagIDs': {
                'description': 'Show tag IDs in hexadecimal format',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'ExtractEmbedded': {
                'description': 'Extract embedded files and images',
                'type': 'bool',
                'default': False,
                'supported': True
            },
            'GlobalTimeShift': {
                'description': 'Shift all timestamps by specified amount',
                'type': 'str',
                'default': '',
                'supported': True
            },
            'CharsetFileName': {
                'description': 'Character set for file names',
                'type': 'str',
                'default': 'UTF8',
                'supported': True
            },
            'UserParam': {
                'description': 'User-defined parameters',
                'type': 'dict',
                'default': {},
                'supported': True
            }
        }
    
    def export_to_json(
        self,
        output_path: Optional[Union[str, Path]] = None,
        indent: int = 2,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_groups: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        wildcard_pattern: Optional[str] = None
    ) -> str:
        """
        Export metadata to JSON format with tag filtering support.
        
        If Compact option is enabled, uses indent=0 for compact JSON output.
        
        Args:
            output_path: Optional path to write JSON file (if None, returns JSON string)
            indent: JSON indentation level (default: 2, overridden to 0 if Compact is enabled)
            include_tags: Optional list of tag names to include (supports wildcards with *)
            exclude_tags: Optional list of tag names to exclude (supports wildcards with *)
            include_groups: Optional list of group names to include (e.g., ['EXIF', 'IPTC'])
            exclude_groups: Optional list of group names to exclude (e.g., ['EXIF', 'IPTC'])
            wildcard_pattern: Optional wildcard pattern to match tags (e.g., 'EXIF:*', '*:ISO')
            
        Returns:
            JSON string representation of metadata
        """
        import json
        import re
        from fnmatch import fnmatch
        
        metadata = self.get_all_metadata(format_values=True)
        filtered_metadata = {}
        
        for tag, value in metadata.items():
            # Apply include_tags filter
            if include_tags:
                matched = False
                for pattern in include_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        matched = True
                        break
                if not matched:
                    continue
            
            # Apply exclude_tags filter
            if exclude_tags:
                excluded = False
                for pattern in exclude_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        excluded = True
                        break
                if excluded:
                    continue
            
            # Apply include_groups filter
            if include_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group not in include_groups:
                    continue
            
            # Apply exclude_groups filter
            if exclude_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group in exclude_groups:
                    continue
            
            # Apply wildcard_pattern filter
            if wildcard_pattern:
                if not fnmatch(tag, wildcard_pattern):
                    continue
            
            filtered_metadata[tag] = value
        
        # Apply Compact option - use indent=0 for compact JSON
        if self.get_option('Compact', False):
            indent = 0
        
        json_str = json.dumps(filtered_metadata, indent=indent, default=str, ensure_ascii=False)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        
        return json_str
    
    def export_to_csv(
        self,
        output_path: Optional[Union[str, Path]] = None,
        delimiter: Optional[str] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_groups: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        wildcard_pattern: Optional[str] = None
    ) -> str:
        """
        Export metadata to CSV format with tag filtering support.
        
        If PrintCSV option is enabled, uses CSV format optimized for GM PDR data extraction.
        The delimiter defaults to ',' unless PrintCSV is enabled, which may use optimized settings.
        
        Args:
            output_path: Optional path to write CSV file (if None, returns CSV string)
            delimiter: CSV delimiter character (default: ',' or from PrintCSV option)
            include_tags: Optional list of tag names to include (supports wildcards with *)
            exclude_tags: Optional list of tag names to exclude (supports wildcards with *)
            include_groups: Optional list of group names to include (e.g., ['EXIF', 'IPTC'])
            exclude_groups: Optional list of group names to exclude (e.g., ['EXIF', 'IPTC'])
            wildcard_pattern: Optional wildcard pattern to match tags (e.g., 'EXIF:*', '*:ISO')
            
        Returns:
            CSV string representation of metadata
        """
        import re
        from fnmatch import fnmatch
        
        # Check PrintCSV option
        print_csv = self.get_option('PrintCSV', False)
        
        # Use delimiter from parameter or default to ','
        if delimiter is None:
            delimiter = ','
        
        # When PrintCSV is enabled, optimize for GM PDR data extraction
        # This may include filtering to GPS/GM-related tags or using optimized formatting
        lines = [f"Tag{delimiter}Value"]
        metadata = self.get_all_metadata(format_values=True)
        
        # If PrintCSV is enabled, prioritize GPS/GM PDR data tags
        if print_csv:
            # Filter to GPS/GM-related tags for optimized PDR extraction
            # Include GPS tags, GM tags, and location-related tags
            gps_tags = [tag for tag in metadata.keys() if any(
                prefix in tag.upper() for prefix in ['GPS', 'GM', 'LOCATION', 'LATITUDE', 'LONGITUDE', 'ALTITUDE']
            )]
            # If GPS tags found, prioritize them; otherwise use all metadata
            if gps_tags:
                # Sort GPS tags first, then other tags
                sorted_tags = sorted(gps_tags) + sorted([tag for tag in metadata.keys() if tag not in gps_tags])
            else:
                sorted_tags = sorted(metadata.keys())
        else:
            sorted_tags = sorted(metadata.keys())
        
        for tag in sorted_tags:
            value = metadata[tag]
            # Apply include_tags filter
            if include_tags:
                matched = False
                for pattern in include_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        matched = True
                        break
                if not matched:
                    continue
            
            # Apply exclude_tags filter
            if exclude_tags:
                excluded = False
                for pattern in exclude_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        excluded = True
                        break
                if excluded:
                    continue
            
            # Apply include_groups filter
            if include_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group not in include_groups:
                    continue
            
            # Apply exclude_groups filter
            if exclude_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group in exclude_groups:
                    continue
            
            # Apply wildcard_pattern filter
            if wildcard_pattern:
                if not fnmatch(tag, wildcard_pattern):
                    continue
            
            # Escape quotes and wrap in quotes
            value_str = str(value).replace('"', '""')
            lines.append(f'"{tag}"{delimiter}"{value_str}"')
        
        csv_str = "\n".join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(csv_str)
        
        return csv_str
    
    def export_to_xml(
        self,
        output_path: Optional[Union[str, Path]] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_groups: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        wildcard_pattern: Optional[str] = None,
        root_element: str = 'metadata',
        indent: int = 2
    ) -> str:
        """
        Export metadata to XML format with tag filtering support.
        
        Args:
            output_path: Optional path to write XML file (if None, returns XML string)
            include_tags: Optional list of tag names to include (supports wildcards with *)
            exclude_tags: Optional list of tag names to exclude (supports wildcards with *)
            include_groups: Optional list of group names to include (e.g., ['EXIF', 'IPTC'])
            exclude_groups: Optional list of group names to exclude (e.g., ['EXIF', 'IPTC'])
            wildcard_pattern: Optional wildcard pattern to match tags (e.g., 'EXIF:*', '*:ISO')
            root_element: Name of the root XML element (default: 'metadata')
            indent: XML indentation level (default: 2)
            
        Returns:
            XML string representation of metadata
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     xml_str = exif.export_to_xml()
            ...     print(xml_str)
        """
        import re
        from fnmatch import fnmatch
        from xml.sax.saxutils import escape
        
        def escape_xml(text: str) -> str:
            """Escape XML special characters."""
            return escape(str(text))
        
        def make_xml_tag_name(tag_name: str) -> str:
            """Convert tag name to valid XML element name."""
            # Replace colons with underscores, remove invalid characters
            name = tag_name.replace(':', '_')
            # Remove invalid XML name characters (keep alphanumeric, underscore, hyphen)
            name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
            # Ensure it starts with a letter or underscore
            if name and name[0].isdigit():
                name = '_' + name
            return name if name else 'tag'
        
        metadata = self.get_all_metadata(format_values=True)
        filtered_metadata = {}
        
        for tag, value in metadata.items():
            # Apply include_tags filter
            if include_tags:
                matched = False
                for pattern in include_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        matched = True
                        break
                if not matched:
                    continue
            
            # Apply exclude_tags filter
            if exclude_tags:
                excluded = False
                for pattern in exclude_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        excluded = True
                        break
                if excluded:
                    continue
            
            # Apply include_groups filter
            if include_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group not in include_groups:
                    continue
            
            # Apply exclude_groups filter
            if exclude_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group in exclude_groups:
                    continue
            
            # Apply wildcard_pattern filter
            if wildcard_pattern:
                if not fnmatch(tag, wildcard_pattern):
                    continue
            
            filtered_metadata[tag] = value
        
        # Build XML string
        indent_str = ' ' * indent
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append(f'<{root_element}>')
        
        for tag, value in sorted(filtered_metadata.items()):
            xml_tag_name = make_xml_tag_name(tag)
            escaped_value = escape_xml(value)
            # Add original tag name as attribute
            escaped_tag = escape_xml(tag)
            lines.append(f'{indent_str}<{xml_tag_name} name="{escaped_tag}">{escaped_value}</{xml_tag_name}>')
        
        lines.append(f'</{root_element}>')
        
        xml_str = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)
        
        return xml_str
    
    def import_from_json(
        self,
        json_path: Union[str, Path],
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_groups: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        wildcard_pattern: Optional[str] = None,
        redirections: Optional[List[str]] = None,
        format_expressions: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Import metadata from JSON file with tag filtering, redirection, and formatting support.
        
        Args:
            json_path: Path to JSON file containing metadata
            include_tags: Optional list of tag names to include (supports wildcards with *)
            exclude_tags: Optional list of tag names to exclude (supports wildcards with *)
            include_groups: Optional list of group names to include (e.g., ['EXIF', 'IPTC'])
            exclude_groups: Optional list of group names to exclude (e.g., ['EXIF', 'IPTC'])
            wildcard_pattern: Optional wildcard pattern to match tags (e.g., 'EXIF:*', '*:ISO')
            redirections: Optional list of redirection strings (e.g., ['-TAG1<-TAG2', '-TAG1<+TAG2'])
            format_expressions: Optional dict mapping tag names to format expressions (e.g., {'EXIF:DateTime': '%Y-%m-%d %H:%M:%S'})
            
        Returns:
            Dictionary with import statistics
        """
        import json
        from fnmatch import fnmatch
        from pathlib import Path
        from dnexif.tag_operations import TagOperations
        
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            imported_metadata = json.load(f)
        
        filtered_metadata = {}
        imported_count = 0
        skipped_count = 0
        
        for tag, value in imported_metadata.items():
            # Apply include_tags filter
            if include_tags:
                matched = False
                for pattern in include_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        matched = True
                        break
                if not matched:
                    skipped_count += 1
                    continue
            
            # Apply exclude_tags filter
            if exclude_tags:
                excluded = False
                for pattern in exclude_tags:
                    if fnmatch(tag, pattern) or tag == pattern:
                        excluded = True
                        break
                if excluded:
                    skipped_count += 1
                    continue
            
            # Apply include_groups filter
            if include_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group not in include_groups:
                    skipped_count += 1
                    continue
            
            # Apply exclude_groups filter
            if exclude_groups:
                tag_group = tag.split(':')[0] if ':' in tag else ''
                if tag_group in exclude_groups:
                    skipped_count += 1
                    continue
            
            # Apply wildcard_pattern filter
            if wildcard_pattern:
                if not fnmatch(tag, wildcard_pattern):
                    skipped_count += 1
                    continue
            
            # Apply format expression if specified
            if format_expressions and tag in format_expressions:
                try:
                    format_expr = format_expressions[tag]
                    # Basic formatting: date/time formatting, string formatting, etc.
                    if isinstance(value, str):
                        # Try to parse and reformat dates
                        from datetime import datetime
                        try:
                            # Try common date formats
                            for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                                try:
                                    dt = datetime.strptime(value, fmt)
                                    value = dt.strftime(format_expr)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            # If date parsing fails, try string formatting
                            try:
                                value = format_expr.format(value)
                            except Exception:
                                pass
                except Exception:
                    pass
            
            # Import tag
            try:
                self.set_tag(tag, value)
                filtered_metadata[tag] = value
                imported_count += 1
            except Exception:
                skipped_count += 1
        
        # Apply redirections if specified
        redirected_count = 0
        if redirections:
            for redirection_str in redirections:
                try:
                    target_tag, source_tag, delete_source, only_if_missing = TagOperations.parse_redirection_syntax(redirection_str)
                    if source_tag in filtered_metadata:
                        source_value = filtered_metadata[source_tag]
                        try:
                            if only_if_missing and target_tag in self.metadata:
                                continue
                            self.set_tag(target_tag, source_value)
                            if delete_source:
                                self.delete_tag(source_tag)
                            redirected_count += 1
                        except Exception:
                            pass
                except Exception:
                    pass
        
        return {
            'imported': imported_count,
            'skipped': skipped_count,
            'redirected': redirected_count,
            'total': len(imported_metadata)
        }
    
    def import_from_csv(
        self,
        csv_path: Union[str, Path],
        delimiter: str = ',',
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        include_groups: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        wildcard_pattern: Optional[str] = None,
        redirections: Optional[List[str]] = None,
        format_expressions: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Import metadata from CSV file with tag filtering, redirection, and formatting support.
        
        Args:
            csv_path: Path to CSV file containing metadata (format: Tag,Value)
            delimiter: CSV delimiter character (default: ',')
            include_tags: Optional list of tag names to include (supports wildcards with *)
            exclude_tags: Optional list of tag names to exclude (supports wildcards with *)
            include_groups: Optional list of group names to include (e.g., ['EXIF', 'IPTC'])
            exclude_groups: Optional list of group names to exclude (e.g., ['EXIF', 'IPTC'])
            wildcard_pattern: Optional wildcard pattern to match tags (e.g., 'EXIF:*', '*:ISO')
            redirections: Optional list of redirection strings (e.g., ['-TAG1<-TAG2', '-TAG1<+TAG2'])
            format_expressions: Optional dict mapping tag names to format expressions (e.g., {'EXIF:DateTime': '%Y-%m-%d %H:%M:%S'})
            
        Returns:
            Dictionary with import statistics
        """
        import csv
        from fnmatch import fnmatch
        from pathlib import Path
        from dnexif.tag_operations import TagOperations
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        imported_metadata = {}
        imported_count = 0
        skipped_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                if 'Tag' not in row or 'Value' not in row:
                    continue
                
                tag = row['Tag'].strip('"')
                value = row['Value'].strip('"')
                
                # Apply include_tags filter
                if include_tags:
                    matched = False
                    for pattern in include_tags:
                        if fnmatch(tag, pattern) or tag == pattern:
                            matched = True
                            break
                    if not matched:
                        skipped_count += 1
                        continue
                
                # Apply exclude_tags filter
                if exclude_tags:
                    excluded = False
                    for pattern in exclude_tags:
                        if fnmatch(tag, pattern) or tag == pattern:
                            excluded = True
                            break
                    if excluded:
                        skipped_count += 1
                        continue
                
                # Apply include_groups filter
                if include_groups:
                    tag_group = tag.split(':')[0] if ':' in tag else ''
                    if tag_group not in include_groups:
                        skipped_count += 1
                        continue
                
                # Apply exclude_groups filter
                if exclude_groups:
                    tag_group = tag.split(':')[0] if ':' in tag else ''
                    if tag_group in exclude_groups:
                        skipped_count += 1
                        continue
                
                # Apply wildcard_pattern filter
                if wildcard_pattern:
                    if not fnmatch(tag, wildcard_pattern):
                        skipped_count += 1
                        continue
                
                # Apply format expression if specified
                if format_expressions and tag in format_expressions:
                    try:
                        format_expr = format_expressions[tag]
                        # Basic formatting: date/time formatting, string formatting, etc.
                        if isinstance(value, str):
                            # Try to parse and reformat dates
                            from datetime import datetime
                            try:
                                # Try common date formats
                                for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                                    try:
                                        dt = datetime.strptime(value, fmt)
                                        value = dt.strftime(format_expr)
                                        break
                                    except ValueError:
                                        continue
                            except Exception:
                                # If date parsing fails, try string formatting
                                try:
                                    value = format_expr.format(value)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                
                # Import tag
                try:
                    self.set_tag(tag, value)
                    imported_metadata[tag] = value
                    imported_count += 1
                except Exception:
                    skipped_count += 1
        
        # Apply redirections if specified
        redirected_count = 0
        if redirections:
            for redirection_str in redirections:
                try:
                    target_tag, source_tag, delete_source, only_if_missing = TagOperations.parse_redirection_syntax(redirection_str)
                    if source_tag in imported_metadata:
                        source_value = imported_metadata[source_tag]
                        try:
                            if only_if_missing and target_tag in self.metadata:
                                continue
                            self.set_tag(target_tag, source_value)
                            if delete_source:
                                self.delete_tag(source_tag)
                            redirected_count += 1
                        except Exception:
                            pass
                except Exception:
                    pass
        
        return {
            'imported': imported_count,
            'skipped': skipped_count,
            'redirected': redirected_count,
            'total': imported_count + skipped_count
        }
    
    def get_tags(self, tag_names: List[str]) -> Dict[str, Any]:
        """
        Get multiple metadata tags at once.
        
        Args:
            tag_names: List of tag names to retrieve
            
        Returns:
            Dictionary mapping tag names to their values
        """
        result = {}
        for tag_name in tag_names:
            result[tag_name] = self.get_tag(tag_name)
        return result
    
    def get_tags_by_group(self, group: str, include_modified: bool = True) -> Dict[str, Any]:
        """
        Get all tags from a specific metadata group.
        
        This method efficiently retrieves all tags belonging to a specific
        metadata group (EXIF, IPTC, XMP, GPS, etc.) without needing to
        iterate through all tags manually.
        
        Args:
            group: Name of the metadata group (e.g., 'EXIF', 'IPTC', 'XMP', 'GPS')
            include_modified: If True, includes modified tags in the result
        
        Returns:
            Dictionary mapping tag names to their values for the specified group
        
        Examples:
            >>> with DNExif('image.jpg') as exif:
            ...     exif_tags = exif.get_tags_by_group('EXIF')
            ...     print(f"Found {len(exif_tags)} EXIF tags")
            ...     # Returns: {'EXIF:Make': 'Canon', 'EXIF:Model': 'EOS', ...}
        """
        result = {}
        group_upper = group.upper()
        
        # Get all metadata (including modified tags if requested)
        all_metadata = self.get_all_metadata(format_values=False)
        if include_modified:
            # Merge modified tags
            for tag_name, value in self.modified_tags.items():
                if value is not None:  # Skip deleted tags (None values)
                    all_metadata[tag_name] = value
        
        # Filter by group
        for tag_name, value in all_metadata.items():
            if ':' in tag_name:
                tag_group = tag_name.split(':', 1)[0].upper()
                if tag_group == group_upper:
                    result[tag_name] = value
        
        return result
    
    def set_tag(self, tag_name: str, value: Any) -> None:
        """
        Set a metadata tag value.
        
        The change will be applied when save() is called.
        
        Args:
            tag_name: Name of the tag (e.g., 'EXIF:Artist', 'IPTC:Keywords')
            value: Value to set for the tag
            
        Raises:
            InvalidTagError: If the tag name is invalid
            MetadataWriteError: If in read-only mode
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot set tag '{tag_name}': File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        # Validate tag name format
        if ':' not in tag_name:
            raise InvalidTagError(
                f"Tag name must include namespace prefix (e.g., 'EXIF:Make'): {tag_name}"
            )
        
        # Apply NoDups option if enabled
        value = self.remove_duplicates_from_list(value)
        
        self.modified_tags[tag_name] = value
    
    def set_tags(self, tags: Dict[str, Any]) -> None:
        """
        Set multiple metadata tags at once.
        
        Args:
            tags: Dictionary mapping tag names to values
        """
        for tag_name, value in tags.items():
            self.set_tag(tag_name, value)
    
    def delete_tag(self, tag_name: str) -> None:
        """
        Delete a metadata tag.
        
        The change will be applied when save() is called.
        
        Args:
            tag_name: Name of the tag to delete
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot delete tag '{tag_name}': File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        # Mark for deletion by setting to None
        self.modified_tags[tag_name] = None
    
    def delete_tags(self, tag_names: List[str]) -> None:
        """
        Delete multiple metadata tags at once.
        
        This method deletes multiple tags in a single call, which is more
        efficient than calling delete_tag() multiple times.
        
        The changes will be applied when save() is called.
        
        Args:
            tag_names: List of tag names to delete
        
        Examples:
            >>> with DNExif('image.jpg', read_only=False) as exif:
            ...     exif.delete_tags(['EXIF:Artist', 'EXIF:Copyright', 'IPTC:Keywords'])
            ...     exif.save()
        
        Raises:
            MetadataWriteError: If in read-only mode
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot delete tags: File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        # Mark all tags for deletion by setting to None
        for tag_name in tag_names:
            self.modified_tags[tag_name] = None
    
    def _write_sidecar_files(self, metadata: Dict[str, Any], output_path: Optional[Path] = None) -> None:
        """
        Write metadata to sidecar files when main file format doesn't support embedded metadata.
        
        Args:
            metadata: Metadata dictionary to write
            output_path: Output file path (if None, uses self.file_path)
        """
        if output_path is None:
            output_path = self.file_path
        else:
            output_path = Path(output_path)
        
        file_dir = output_path.parent
        file_stem = output_path.stem
        file_ext = output_path.suffix.lower()
        
        # Determine if main file format supports embedded metadata
        formats_with_embedded_metadata = {
            '.jpg', '.jpeg', '.tif', '.tiff', '.png', '.heic', '.heif',
            '.psd', '.webp', '.cr2', '.nef', '.arw', '.dng', '.orf', '.raf',
            '.rw2', '.pef', '.x3f', '.crw', '.mrw', '.nrw', '.3fr', '.erf',
            '.mef', '.mos', '.srw', '.pdf'
        }
        
        supports_embedded = file_ext in formats_with_embedded_metadata
        
        # Extract XMP metadata for sidecar file
        xmp_metadata = {
            k: v for k, v in metadata.items()
            if k.startswith('XMP:') and not k.startswith('Sidecar:')
        }
        
        # Extract EXIF metadata for sidecar file
        exif_metadata = {
            k: v for k, v in metadata.items()
            if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:')) and not k.startswith('Sidecar:')
        }
        
        # Extract IPTC metadata for sidecar file
        iptc_metadata = {
            k: v for k, v in metadata.items()
            if k.startswith('IPTC:') and not k.startswith('Sidecar:')
        }
        
        # Write XMP sidecar file if:
        # 1. Main file doesn't support embedded metadata, OR
        # 2. XMP metadata exists and should be written to sidecar
        if xmp_metadata and (not supports_embedded or self._should_write_sidecar()):
            # Determine sidecar file path (prefer filename.ext.xmp convention)
            if file_ext:
                sidecar_path = file_dir / f"{file_stem}{file_ext}.xmp"
            else:
                sidecar_path = file_dir / f"{file_stem}.xmp"
            
            try:
                # Build XMP packet
                xmp_writer = XMPWriter()
                xmp_packet = xmp_writer.build_xmp_packet(xmp_metadata)
                
                if xmp_packet:
                    # Write XMP sidecar file
                    with open(sidecar_path, 'wb') as f:
                        f.write(xmp_packet)
                    
                    # Add sidecar file info to metadata
                    self.metadata['Sidecar:XMP:SidecarFile'] = str(sidecar_path)
                    self.metadata['Sidecar:XMP:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar writing - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
        
        # Write EXIF sidecar file if:
        # 1. Main file doesn't support embedded metadata, OR
        # 2. EXIF metadata exists and should be written to sidecar
        if exif_metadata and (not supports_embedded or self._should_write_sidecar()):
            # Determine sidecar file path (prefer filename.ext.exif convention)
            if file_ext:
                sidecar_path = file_dir / f"{file_stem}{file_ext}.exif"
            else:
                sidecar_path = file_dir / f"{file_stem}.exif"
            
            try:
                # Build EXIF/TIFF file
                # Determine endianness from existing metadata or default to little-endian
                endian = '<'
                if self._exif_parser and hasattr(self._exif_parser, 'endian'):
                    endian = self._exif_parser.endian
                
                # Determine EXIF version from existing metadata or default to 3.0
                exif_version = '0300'  # Default to EXIF 3.0 for UTF-8 support
                if 'EXIF:ExifVersion' in metadata:
                    exif_version = str(metadata['EXIF:ExifVersion'])
                
                exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
                
                # Build EXIF segment (contains TIFF structure)
                exif_segment = exif_writer.build_exif_segment(exif_metadata)
                
                if exif_segment:
                    # Extract TIFF data from APP1 segment (skip APP1 marker and length)
                    # APP1 segment format: 0xFFE1 [length] [data]
                    # EXIF data starts after "Exif\0\0" identifier (6 bytes)
                    if len(exif_segment) > 10:
                        # Find "Exif\0\0" identifier
                        exif_start = exif_segment.find(b'Exif\x00\x00')
                        if exif_start >= 0:
                            # Extract TIFF data (starts after "Exif\0\0")
                            tiff_data = exif_segment[exif_start + 6:]
                            
                            # Write EXIF sidecar file (as TIFF)
                            with open(sidecar_path, 'wb') as f:
                                f.write(tiff_data)
                            
                            # Add sidecar file info to metadata
                            self.metadata['Sidecar:EXIF:SidecarFile'] = str(sidecar_path)
                            self.metadata['Sidecar:EXIF:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar writing - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
        
        # Write IPTC sidecar file if:
        # 1. Main file doesn't support embedded metadata, OR
        # 2. IPTC metadata exists and should be written to sidecar
        if iptc_metadata and (not supports_embedded or self._should_write_sidecar()):
            # Determine sidecar file path (prefer filename.ext.iptc convention)
            if file_ext:
                sidecar_path = file_dir / f"{file_stem}{file_ext}.iptc"
            else:
                sidecar_path = file_dir / f"{file_stem}.iptc"
            
            try:
                # Build IPTC data
                iptc_writer = IPTCWriter()
                iptc_data = iptc_writer.build_iptc_data(iptc_metadata)
                
                if iptc_data:
                    # Write IPTC sidecar file
                    with open(sidecar_path, 'wb') as f:
                        f.write(iptc_data)
                    
                    # Add sidecar file info to metadata
                    self.metadata['Sidecar:IPTC:SidecarFile'] = str(sidecar_path)
                    self.metadata['Sidecar:IPTC:HasSidecar'] = True
            except Exception as e:
                # Silently fail sidecar writing - it's optional
                if not self.ignore_minor_errors:
                    pass  # Could log warning here
    
    def _should_write_sidecar(self) -> bool:
        """
        Determine if sidecar file should be written even if main file supports embedded metadata.
        
        Returns:
            True if sidecar should be written
        """
        # For now, only write sidecar if main file doesn't support embedded metadata
        # This can be extended with user preferences later
        return False
    
    def save(self, output_path: Optional[Union[str, Path]] = None) -> None:
        """
        Save metadata changes to file.
        
        If SavePath option is set, it will be used as the base directory for saving.
        If SaveFormat option is set, it will be used to determine the output format.
        
        Args:
            output_path: Optional output path. If None, saves to original file.
                        SavePath option is prepended if set.
                        SaveFormat option changes extension if set.
            
        Raises:
            MetadataWriteError: If metadata cannot be written
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot save changes: File '{self.file_path}' is opened in read-only mode. "
                "Open the file without read_only=True to enable writing."
            )
        
        if not self.modified_tags:
            return  # No changes to save
        
        # Apply SavePath option if set
        save_path_option = self.get_option('SavePath', '')
        if save_path_option and not output_path:
            # Use SavePath as base directory
            save_path_dir = Path(save_path_option)
            if save_path_dir.exists() and save_path_dir.is_dir():
                output = save_path_dir / self.file_path.name
            else:
                output = Path(output_path) if output_path else self.file_path
        else:
            output = Path(output_path) if output_path else self.file_path
        
        # Apply SaveFormat option if set
        save_format_option = self.get_option('SaveFormat', '')
        if save_format_option:
            # Change file extension based on SaveFormat
            output = output.with_suffix(f'.{save_format_option.lstrip(".")}')
        
        # Merge modified tags with existing metadata
        merged_metadata = self.metadata.copy()
        for tag_name, value in self.modified_tags.items():
            if value is None:
                # Tag deletion
                merged_metadata.pop(tag_name, None)
            else:
                merged_metadata[tag_name] = value
        
        # Apply FilterW option if enabled - filter tags when writing
        filter_w = self.get_option('FilterW', False)
        if filter_w:
            # Filter tags using IgnoreTags and IgnoreGroups options
            filtered_metadata = {}
            for tag_name, value in merged_metadata.items():
                # Check if tag should be ignored
                if not self.should_ignore_tag(tag_name):
                    filtered_metadata[tag_name] = value
            merged_metadata = filtered_metadata
        
        # Add XMP-et:OriginalImageMD5 if Composite:ImageDataMD5 exists
        # This stores the ImageDataMD5 value in XMP metadata
        if 'Composite:ImageDataMD5' in merged_metadata:
            image_data_md5 = merged_metadata['Composite:ImageDataMD5']
            if image_data_md5:
                merged_metadata['XMP-et:OriginalImageMD5'] = image_data_md5
        
        # Determine file format and write accordingly
        file_ext = self.file_path.suffix.lower()
        
        if file_ext in ('.jpg', '.jpeg'):
            self._save_jpeg(merged_metadata, output)
        elif file_ext in ('.tif', '.tiff'):
            self._save_tiff(merged_metadata, output)
        elif file_ext == '.png':
            self._save_png(merged_metadata, output)
        elif file_ext == '.webp':
            self._save_webp(merged_metadata, output)
        elif file_ext == '.gif':
            self._save_gif(merged_metadata, output)
        elif file_ext in {'.cr2', '.cr3', '.crw', '.nef', '.arw', '.dng', 
                          '.orf', '.raf', '.rw2', '.srw', '.pef', '.x3f',
                          '.3fr', '.ari', '.bay', '.cap', '.dcs', '.dcr',
                          '.drf', '.eip', '.erf', '.fff', '.iiq', '.mef',
                          '.mos', '.mrw', '.nrw', '.rwl', '.srf'}:
            self._save_raw(merged_metadata, output)
        elif file_ext in {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.m4a', '.aac', '.3gp', '.3g2'}:
            self._save_video(merged_metadata, output)
        elif file_ext in {'.mp3', '.wav', '.flac', '.ogg', '.wma', '.opus'}:
            self._save_audio(merged_metadata, output)
        elif file_ext == '.pdf':
            self._save_pdf(merged_metadata, output)
        elif file_ext in {'.heic', '.heif'}:
            self._save_heic(merged_metadata, output)
        elif file_ext == '.bmp':
            self._save_bmp(merged_metadata, output)
        elif file_ext in {'.tga', '.targa'}:
            self._save_tga(merged_metadata, output)
        elif file_ext == '.svg':
            self._save_svg(merged_metadata, output)
        elif file_ext == '.psd':
            self._save_psd(merged_metadata, output)
        elif file_ext in ('.ico', '.cur'):
            self._save_ico(merged_metadata, output)
        elif file_ext in {'.dcm', '.dicom'}:
            self._save_dicom(merged_metadata, output)
        else:
            # For other formats, try JPEG-style writing
            # (RAW formats may need special handling)
            try:
                self._save_jpeg(merged_metadata, output)
            except Exception as e:
                if isinstance(e, MetadataWriteError):
                    raise
                raise MetadataWriteError(
                    f"Writing to {file_ext} format is not yet fully supported. "
                    f"JPEG, TIFF, PNG, WebP, GIF, RAW, PDF, HEIC, BMP, SVG, PSD, and ICO writing is available. "
                    f"Error: {str(e)}"
                ) from e
        
        # Write sidecar files if needed (for formats that don't support embedded metadata)
        self._write_sidecar_files(merged_metadata, output)
        
        # Update internal state
        self.metadata = merged_metadata
        self.modified_tags.clear()
    
    def _save_jpeg(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a JPEG file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Read original file
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        jpeg_modifier = JPEGModifier(file_data)
        modified_data = file_data
        
        # Handle EXIF tags
        exif_metadata = {
            k: v for k, v in metadata.items()
            if k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:')
        }
        
        if exif_metadata:
            # Determine endianness from existing EXIF or default to little-endian
            endian = '<'
            if self._exif_parser and hasattr(self._exif_parser, 'endian'):
                endian = self._exif_parser.endian
            
            # Build new EXIF segment
            # Determine EXIF version from existing metadata or default to 3.0
            exif_version = '0300'  # Default to EXIF 3.0 for UTF-8 support
            if 'EXIF:ExifVersion' in metadata:
                exif_version = str(metadata['EXIF:ExifVersion'])
            elif 'IFD0:ExifVersion' in metadata:
                exif_version = str(metadata['IFD0:ExifVersion'])
            
            exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
            new_exif_segment = exif_writer.build_exif_segment(exif_metadata)
            
            # Modify JPEG file
            if new_exif_segment:
                if any(marker == JPEGModifier.APP1 for marker, _, _ in jpeg_modifier.segments):
                    modified_data = jpeg_modifier.replace_app1_segment(new_exif_segment)
                else:
                    modified_data = jpeg_modifier.add_app1_segment(new_exif_segment)
                jpeg_modifier = JPEGModifier(modified_data)  # Re-parse after modification
            else:
                # No EXIF data, remove APP1 if it exists
                modified_data = jpeg_modifier.remove_app1_segment()
                jpeg_modifier = JPEGModifier(modified_data)
        else:
            # Check if we need to remove EXIF
            if any(marker == JPEGModifier.APP1 for marker, _, _ in jpeg_modifier.segments):
                # Check if EXIF should be removed (all EXIF tags deleted)
                has_exif_tags = any(
                    k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:')
                    for k in self.metadata.keys()
                )
                if not has_exif_tags:
                    modified_data = jpeg_modifier.remove_app1_segment()
                    jpeg_modifier = JPEGModifier(modified_data)
        
        # Handle IPTC tags
        iptc_metadata = {
            k: v for k, v in metadata.items()
            if k.startswith('IPTC:')
        }
        
        if iptc_metadata:
            # Build IPTC segment
            iptc_writer = IPTCWriter()
            iptc_data = iptc_writer.build_iptc_data(iptc_metadata)
            if iptc_data:
                new_app13_segment = iptc_writer.build_photoshop_app13_segment(iptc_data)
                if new_app13_segment:
                    if any(marker == JPEGModifier.APP13 for marker, _, _ in jpeg_modifier.segments):
                        modified_data = jpeg_modifier.replace_app13_segment(new_app13_segment)
                    else:
                        modified_data = jpeg_modifier.add_app13_segment(new_app13_segment)
                    jpeg_modifier = JPEGModifier(modified_data)
        else:
            # Check if IPTC should be removed
            has_iptc_tags = any(k.startswith('IPTC:') for k in self.metadata.keys())
            if not has_iptc_tags and any(marker == JPEGModifier.APP13 for marker, _, _ in jpeg_modifier.segments):
                # Remove APP13 if no IPTC tags remain
                modified_data = jpeg_modifier.replace_app13_segment(b'')
                jpeg_modifier = JPEGModifier(modified_data)
        
        # Handle XMP tags
        xmp_metadata = {
            k: v for k, v in metadata.items()
            if k.startswith('XMP:')
        }
        
        if xmp_metadata:
            # Build XMP segment
            xmp_writer = XMPWriter()
            xmp_packet = xmp_writer.build_xmp_packet(xmp_metadata)
            if xmp_packet:
                new_xmp_segment = xmp_writer.build_app1_xmp_segment(xmp_packet)
                if new_xmp_segment:
                    # XMP is in APP1 (separate from EXIF APP1)
                    # Use is_xmp=True to distinguish XMP APP1 from EXIF APP1
                    modified_data = jpeg_modifier.add_app1_segment(new_xmp_segment, is_xmp=True)
                    jpeg_modifier = JPEGModifier(modified_data)
        
        # Handle additional metadata standards (JFIF, ICC, Photoshop IRB, AFCP)
        standards_writer = MetadataStandardsWriter()

        def _apply_standards_writer(write_func, *writer_args):
            """
            Run a standards writer using the current in-memory JPEG data as input.
            """
            nonlocal modified_data, jpeg_modifier

            with tempfile.NamedTemporaryFile(delete=False, suffix=output_path.suffix) as temp_input:
                temp_input.write(modified_data)
                temp_input_path = Path(temp_input.name)

            temp_output_path = output_path.parent / f"{output_path.stem}_temp{output_path.suffix}"
            try:
                write_func(str(temp_input_path), *writer_args, str(temp_output_path))
                if temp_output_path.exists():
                    with open(temp_output_path, 'rb') as f:
                        modified_data = f.read()
                    temp_output_path.unlink()
                    jpeg_modifier = JPEGModifier(modified_data)
            finally:
                if temp_input_path.exists():
                    temp_input_path.unlink()
        
        # Check for JFIF metadata
        jfif_metadata = {k: v for k, v in metadata.items() if k.startswith('JFIF:')}
        if jfif_metadata:
            _apply_standards_writer(standards_writer.write_jfif, jfif_metadata)
        
        # Check for ICC profile
        if 'ICC:ProfileData' in metadata:
            icc_data = metadata['ICC:ProfileData']
            if isinstance(icc_data, bytes):
                _apply_standards_writer(standards_writer.write_icc_profile, icc_data)
        
        # Check for Photoshop IRB metadata
        ps_irb_metadata = {k: v for k, v in metadata.items() if k.startswith('PS:')}
        if ps_irb_metadata:
            _apply_standards_writer(standards_writer.write_photoshop_irb, ps_irb_metadata)
        
        # Check for AFCP metadata
        afcp_metadata = {k: v for k, v in metadata.items() if k.startswith('AFCP:')}
        if afcp_metadata:
            _apply_standards_writer(standards_writer.write_afcp, afcp_metadata)
        
        # Write modified file
        with open(output_path, 'wb') as f:
            f.write(modified_data)
    
    def _save_png(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a PNG file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Read original file
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        # Use PNG writer
        png_writer = PNGWriter()
        png_writer.write_png(file_data, metadata, str(output_path))
    
    def _save_webp(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a WebP file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Read original file
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        # Use WebP writer
        webp_writer = WebPWriter()
        webp_writer.write_webp(file_data, metadata, str(output_path))
    
    def _save_gif(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a GIF file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Read original file
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        # Use GIF writer
        gif_writer = GIFWriter()
        gif_writer.write_gif(file_data, metadata, str(output_path))
    
    def _save_raw(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a RAW file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Use RAW writer
        raw_writer = RAWWriter()
        raw_writer.write_raw(str(self.file_path), metadata, str(output_path))
    
    def _save_video(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a video file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Use video writer
        video_writer = VideoWriter()
        # Pass QuickTimePad option to video writer
        quicktime_pad = self.get_option('QuickTimePad', 0)
        video_writer.set_quicktime_pad(quicktime_pad)
        # Pass QuickTimeHandler option to video writer
        quicktime_handler = self.get_option('QuickTimeHandler', '')
        video_writer.set_quicktime_handler(quicktime_handler)
        video_writer.write_video(str(self.file_path), metadata, str(output_path))
    
    def _save_audio(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to an audio file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Use audio writer
        audio_writer = AudioWriter()
        audio_writer.write_audio(str(self.file_path), metadata, str(output_path))
    
    def _save_pdf(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a PDF file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        writer = PDFWriter()
        writer.write_pdf(str(self.file_path), metadata, str(output_path))
    
    def _save_heic(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a HEIC/HEIF file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Determine EXIF version from existing metadata
        exif_version = '0300'  # Default to EXIF 3.0
        if hasattr(self, '_exif_parser') and self._exif_parser:
            exif_version = getattr(self._exif_parser, 'exif_version', '0300')
        
        writer = HEICWriter(exif_version=exif_version)
        writer.write_heic(str(self.file_path), metadata, str(output_path))
    
    def _save_bmp(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a BMP file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        writer = BMPWriter()
        writer.write_bmp(str(self.file_path), metadata, str(output_path))
    
    def _save_svg(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to an SVG file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        writer = SVGWriter()
        writer.write_svg(str(self.file_path), metadata, str(output_path))
    
    def _save_tga(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a TGA file by updating the TGA 2.0 extension area.
        """
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        writer = TGAWriter()
        writer.write_tga(file_data, metadata, str(output_path))
    
    def _save_psd(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a PSD file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Determine EXIF version from existing metadata
        exif_version = '0300'  # Default to EXIF 3.0
        if hasattr(self, '_exif_parser') and self._exif_parser:
            exif_version = getattr(self._exif_parser, 'exif_version', '0300')
        
        writer = PSDWriter(exif_version=exif_version)
        writer.write_psd(str(self.file_path), metadata, str(output_path))
    
    def _save_ico(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to an ICO/CUR file.
        
        Note: ICO/CUR files don't support standard metadata storage.
        This method preserves the file structure.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        from dnexif.ico_writer import ICOWriter
        writer = ICOWriter()
        writer.write_ico(str(self.file_path), metadata, str(output_path))
    
    def _save_tiff(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a TIFF file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Read original file
        with open(self.file_path, 'rb') as f:
            file_data = f.read()
        
        # Determine endianness
        endian = '<'
        if file_data[:2] == b'MM':
            endian = '>'
        elif file_data[:2] != b'II':
            raise MetadataWriteError(
                f"Invalid TIFF file '{self.file_path}': Missing TIFF header signature. "
                "Expected 'II' (little-endian) or 'MM' (big-endian) at offset 0."
            )
        
        # Determine EXIF version from existing metadata or default to 3.0
        exif_version = '0300'  # Default to EXIF 3.0 for UTF-8 support
        if 'EXIF:ExifVersion' in metadata:
            exif_version = str(metadata['EXIF:ExifVersion'])
        elif 'IFD0:ExifVersion' in metadata:
            exif_version = str(metadata['IFD0:ExifVersion'])
        
        # Use TIFF writer
        tiff_writer = TIFFWriter(endian=endian)
        # Update EXIFWriter in TIFFWriter to use correct EXIF version
        tiff_writer.exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
        tiff_writer.write_tiff(file_data, metadata, str(output_path))
    
    def _save_dicom(self, metadata: Dict[str, Any], output_path: Path) -> None:
        """
        Save metadata to a DICOM file.
        
        Args:
            metadata: Complete metadata dictionary
            output_path: Output file path
        """
        # Use DICOM writer
        from dnexif.dicom_writer import DICOMWriter
        dicom_writer = DICOMWriter()
        dicom_writer.write_dicom(str(self.file_path), metadata, str(output_path))
    
    def get_dict(self) -> Dict[str, Any]:
        """
        Get all metadata as a dictionary (alias for get_all_metadata).
        
        Returns:
            Dictionary containing all metadata
        """
        return self.get_all_metadata()
    
    def get_metadata_batch(self, files: List[Union[str, Path]]) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata from multiple files at once.
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary mapping file paths to their metadata dictionaries
        """
        result = {}
        for file_path in files:
            try:
                with DNExif(file_path, read_only=True) as exif:
                    result[str(file_path)] = exif.get_all_metadata()
            except Exception as e:
                result[str(file_path)] = {"Error": str(e)}
        return result
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Auto-save is not enabled by default
        # User must explicitly call save()
        pass
    
    def _add_canon_composite_tags(self) -> None:
        """
        Add Canon-specific composite tags for CR2 files.
        These tags standard format's Canon/MakerNotes tags.
        """
        try:
            # CanonImageWidth and CanonImageHeight from EXIF dimensions
            if 'MakerNotes:CanonImageWidth' not in self.metadata:
                width = (self.metadata.get('EXIF:ImageWidth') or 
                        self.metadata.get('EXIF:ExifImageWidth') or
                        self.metadata.get('EXIF:PixelXDimension') or
                        self.metadata.get('File:ImageWidth'))
                if width:
                    try:
                        if isinstance(width, (list, tuple)):
                            width = int(width[0]) if width else None
                        else:
                            width = int(width)
                        if width:
                            self.metadata['MakerNotes:CanonImageWidth'] = width
                    except (ValueError, TypeError):
                        pass
            
            if 'MakerNotes:CanonImageHeight' not in self.metadata:
                height = (self.metadata.get('EXIF:ImageHeight') or 
                         self.metadata.get('EXIF:ExifImageHeight') or
                         self.metadata.get('EXIF:PixelYDimension') or
                         self.metadata.get('File:ImageHeight'))
                if height:
                    try:
                        if isinstance(height, (list, tuple)):
                            height = int(height[0]) if height else None
                        else:
                            height = int(height)
                        if height:
                            self.metadata['MakerNotes:CanonImageHeight'] = height
                    except (ValueError, TypeError):
                        pass
            
            # CanonImageSize from ImageWidth and ImageHeight
            if 'MakerNotes:CanonImageSize' not in self.metadata:
                canon_width = self.metadata.get('MakerNotes:CanonImageWidth')
                canon_height = self.metadata.get('MakerNotes:CanonImageHeight')
                if canon_width and canon_height:
                    # Map to common Canon image sizes
                    size_map = {
                        (5184, 3456): 'Large',
                        (3456, 2304): 'Medium',
                        (2592, 1728): 'Small',
                        (1920, 1280): 'Small',
                    }
                    size = size_map.get((canon_width, canon_height), 'Large')
                    self.metadata['MakerNotes:CanonImageSize'] = size
            
            # CanonImageType from Model
            if 'MakerNotes:CanonImageType' not in self.metadata:
                model = self.metadata.get('EXIF:Model') or self.metadata.get('Make')
                if model:
                    model_str = str(model).strip()
                    if 'Canon' in model_str or 'EOS' in model_str:
                        self.metadata['MakerNotes:CanonImageType'] = model_str
            
            # CanonModelID from Model
            if 'MakerNotes:CanonModelID' not in self.metadata:
                model = self.metadata.get('EXIF:Model')
                if model:
                    model_str = str(model).strip()
                    # Extract model ID (e.g., "EOS Rebel T2i / 550D / Kiss X4")
                    if 'EOS' in model_str:
                        self.metadata['MakerNotes:CanonModelID'] = model_str
            
            # CanonExposureMode from EXIF:ExposureMode
            if 'MakerNotes:CanonExposureMode' not in self.metadata:
                exp_mode = self.metadata.get('EXIF:ExposureMode')
                if exp_mode:
                    # Map exposure mode values
                    mode_map = {
                        0: 'Auto',
                        1: 'Manual',
                        2: 'Auto bracket',
                    }
                    if isinstance(exp_mode, (int, float)):
                        self.metadata['MakerNotes:CanonExposureMode'] = mode_map.get(int(exp_mode), str(exp_mode))
                    else:
                        self.metadata['MakerNotes:CanonExposureMode'] = str(exp_mode)
            
            # CanonFlashMode from EXIF:Flash
            if 'MakerNotes:CanonFlashMode' not in self.metadata:
                flash = self.metadata.get('EXIF:Flash')
                if flash is not None:
                    # Map flash values
                    if isinstance(flash, (int, float)):
                        flash_val = int(flash)
                        if flash_val == 0:
                            self.metadata['MakerNotes:CanonFlashMode'] = 'Off'
                        elif flash_val & 0x01:
                            self.metadata['MakerNotes:CanonFlashMode'] = 'On'
                        else:
                            self.metadata['MakerNotes:CanonFlashMode'] = 'Off'
                    else:
                        flash_str = str(flash).lower()
                        if 'off' in flash_str or flash_str == '0':
                            self.metadata['MakerNotes:CanonFlashMode'] = 'Off'
                        else:
                            self.metadata['MakerNotes:CanonFlashMode'] = 'On'
            
            # CanonFirmwareVersion from MakerNotes:FirmwareVersion or EXIF:Software
            if 'MakerNotes:CanonFirmwareVersion' not in self.metadata:
                fw_version = (self.metadata.get('MakerNotes:FirmwareVersion') or 
                            self.metadata.get('EXIF:Software'))
                if fw_version:
                    fw_str = str(fw_version).strip()
                    if fw_str:
                        # Format as "Firmware Version X.X.X"
                        if 'Firmware' not in fw_str and 'Version' not in fw_str:
                            self.metadata['MakerNotes:CanonFirmwareVersion'] = f"Firmware Version {fw_str}"
                        else:
                            self.metadata['MakerNotes:CanonFirmwareVersion'] = fw_str
            
            # Composite:DriveMode from Canon MakerNote or EXIF:ContinuousDrive
            if 'Composite:DriveMode' not in self.metadata:
                drive_mode = (self.metadata.get('MakerNotes:ContinuousDrive') or 
                            self.metadata.get('EXIF:ContinuousDrive'))
                if drive_mode:
                    self.metadata['Composite:DriveMode'] = str(drive_mode)
            
            # Composite:FileNumber - typically from Canon MakerNote or sequential numbering
            if 'Composite:FileNumber' not in self.metadata:
                file_number = self.metadata.get('MakerNotes:FileNumber')
                if file_number:
                    self.metadata['Composite:FileNumber'] = str(file_number)
            
            # Composite:Lens from EXIF:LensModel or MakerNotes:LensModel
            if 'Composite:Lens' not in self.metadata:
                lens = (self.metadata.get('EXIF:LensModel') or 
                       self.metadata.get('MakerNotes:LensModel') or
                       self.metadata.get('MakerNotes:Lens'))
                if lens:
                    self.metadata['Composite:Lens'] = str(lens)
            
            # Composite:LensID from Canon MakerNote
            if 'Composite:LensID' not in self.metadata:
                lens_id = self.metadata.get('MakerNotes:LensID')
                if lens_id:
                    self.metadata['Composite:LensID'] = str(lens_id)
            
            # Composite:Lens35efl from EXIF:FocalLengthIn35mmFilm or calculated
            if 'Composite:Lens35efl' not in self.metadata:
                focal_35 = self.metadata.get('EXIF:FocalLengthIn35mmFilm')
                if focal_35:
                    try:
                        if isinstance(focal_35, (list, tuple)):
                            focal_35 = focal_35[0]
                        focal_val = float(focal_35)
                        self.metadata['Composite:Lens35efl'] = f"{focal_val:.1f} mm"
                    except (ValueError, TypeError):
                        pass
                else:
                    # Fallback to Composite:FocalLength35efl if available
                    focal_35efl = self.metadata.get('Composite:FocalLength35efl')
                    if focal_35efl:
                        # Extract 35mm equivalent from string like "17.0 mm (35 mm equivalent: 26.7 mm)"
                        import re
                        match = re.search(r'\(35 mm equivalent:\s*([\d.]+)', str(focal_35efl))
                        if match:
                            try:
                                focal_val = float(match.group(1))
                                self.metadata['Composite:Lens35efl'] = f"{focal_val:.1f} mm"
                            except (ValueError, TypeError):
                                pass
                        else:
                            # If no 35mm equivalent, use the focal length directly
                            match = re.search(r'([\d.]+)', str(focal_35efl))
                            if match:
                                try:
                                    focal_val = float(match.group(1))
                                    self.metadata['Composite:Lens35efl'] = f"{focal_val:.1f} mm"
                                except (ValueError, TypeError):
                                    pass
            
            # Composite:WB_RGGBLevels from Canon MakerNote WB levels
            if 'Composite:WB_RGGBLevels' not in self.metadata:
                # Try multiple sources for WB_RGGBLevels (prefer AsShot, then Auto, then others)
                wb_rggb = (self.metadata.get('MakerNotes:WB_RGGBLevels') or 
                          self.metadata.get('MakerNotes:WB_RGGBLevelsAsShot') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsAuto') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsDaylight') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsCloudy') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsTungsten') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsFlash') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsFluorescent') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsShade') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsKelvin') or
                          self.metadata.get('MakerNotes:WB_RGGBLevelsMeasured'))
                if wb_rggb:
                    self.metadata['Composite:WB_RGGBLevels'] = str(wb_rggb)
                else:
                    # Try to construct from individual WB levels
                    wb_red = self.metadata.get('MakerNotes:WBRedLevel') or self.metadata.get('EXIF:WBRedLevel')
                    wb_green = self.metadata.get('MakerNotes:WBGreenLevel') or self.metadata.get('EXIF:WBGreenLevel')
                    wb_blue = self.metadata.get('MakerNotes:WBBlueLevel') or self.metadata.get('EXIF:WBBlueLevel')
                    if wb_red and wb_green and wb_blue:
                        try:
                            r = float(str(wb_red).strip())
                            g = float(str(wb_green).strip())
                            b = float(str(wb_blue).strip())
                            # Format as "R G G B" (green appears twice)
                            self.metadata['Composite:WB_RGGBLevels'] = f"{int(r)} {int(g)} {int(g)} {int(b)}"
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass  # Canon composite tags are optional
    
    def geolocate_city(self, city_name: str) -> Optional[Dict[str, Any]]:
        """
        Geolocate a city name to GPS coordinates.
        
        Uses GeolocAltNames option to determine whether to use alternate names
        for geolocation lookup. If GeolocAltNames is enabled, tries alternate
        names if direct lookup fails.
        
        Uses GeolocFeature option to determine feature type (city, country, etc.)
        for geolocation. Defaults to 'city' if not specified.
        
        Args:
            city_name: Name of the city to geolocate
            
        Returns:
            Dictionary with GPS coordinates and location information, or None if not found
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('GeolocAltNames', True)
            >>> exif.set_option('GeolocFeature', 'city')
            >>> location = exif.geolocate_city('NYC')  # Uses alternate name
        """
        try:
            from dnexif.geolocation import Geolocation
            
            geoloc = Geolocation()
            geoloc_alt_names = self.get_option('GeolocAltNames', False)
            geoloc_feature = self.get_option('GeolocFeature', 'city')
            
            # Get geolocation result
            if geoloc_alt_names:
                # Use alternate names if option is enabled
                result = geoloc.geolocate_with_alternate_names(city_name)
            else:
                # Use standard geolocation without alternate names
                result = geoloc.geolocate(city_name)
            
            # Add feature type information if result found
            if result and geoloc_feature:
                # Use geolocate_with_feature_type if feature type is specified
                if geoloc_feature != 'city':
                    # For non-city features, try feature-specific geolocation
                    feature_result = geoloc.geolocate_with_feature_type(city_name)
                    if feature_result:
                        # Update feature type based on option
                        feature_result['Geolocation:FeatureType'] = geoloc_feature
                        result = feature_result
                else:
                    # For city feature, add feature type info
                    result['Geolocation:FeatureType'] = geoloc_feature
                    result['Geolocation:FeatureCode'] = 'PPL'  # Place code
            
            # Apply GeolocMaxDist filter if set
            if result:
                geoloc_max_dist = self.get_option('GeolocMaxDist', 0.0)
                if geoloc_max_dist > 0.0:
                    # Check if result is within maximum distance
                    # Note: This is a simplified check - full implementation would calculate
                    # distance from a reference point. For now, we'll add the max distance
                    # to the result for reference.
                    result['Geolocation:MaxDistance'] = geoloc_max_dist
                    # In a full implementation, results outside max distance would be filtered out
                    # For now, we just add the max distance info to the result
            
            # Apply GeolocMinPop filter if set
            if result:
                geoloc_min_pop = self.get_option('GeolocMinPop', 0)
                if geoloc_min_pop > 0:
                    # Check if result meets minimum population requirement
                    # Note: This requires population data in the database
                    # For now, we'll add the min population to the result for reference
                    result['Geolocation:MinPopulation'] = geoloc_min_pop
                    # In a full implementation, results below min population would be filtered out
                    # For now, we just add the min population info to the result
            
            return result
        except ImportError:
            # Geolocation module not available
            return None
        except Exception:
            # Error during geolocation
            return None
    
    def set_file_name(self, new_name: Union[str, Path]) -> None:
        """
        Set (rename) the file name.
        
        Uses SymLink option to determine whether to follow symbolic links.
        When SymLink is enabled, follows symbolic links to rename the target file.
        When SymLink is disabled, renames the file directly (may break symlinks).
        
        Args:
            new_name: New file name or path
            
        Raises:
            MetadataWriteError: If renaming fails
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('SymLink', True)
            >>> exif.set_file_name('renamed.jpg')
        """
        if self.read_only:
            raise MetadataWriteError(
                f"Cannot rename file '{self.file_path}': File is opened in read-only mode. "
                "Open the file without read_only=True to enable renaming."
            )
        
        sym_link = self.get_option('SymLink', False)
        new_path = Path(new_name)
        
        try:
            # If SymLink is enabled, resolve the target path
            if sym_link and self.file_path.is_symlink():
                # Follow symbolic link to get target
                target_path = self.file_path.resolve()
                # Rename the target file
                target_path.rename(new_path)
                # Update self.file_path to point to new location
                self.file_path = new_path
            else:
                # Direct rename (may break symlinks if SymLink is False)
                self.file_path.rename(new_path)
                self.file_path = new_path
        except OSError as e:
            raise MetadataWriteError(f"Failed to rename file '{self.file_path}' to '{new_path}': {e}")
        except Exception as e:
            raise MetadataWriteError(f"Unexpected error renaming file '{self.file_path}' to '{new_path}': {e}")
    
    def extract_binary_blocks(self, output_dir: Optional[Union[str, Path]] = None) -> Dict[str, Union[str, bytes]]:
        """
        Extract binary metadata blocks from the file.
        
        Uses BlockExtract option to determine whether to extract binary blocks.
        When BlockExtract is enabled, extracts binary data blocks (thumbnails, previews,
        embedded data, etc.) from metadata.
        
        Args:
            output_dir: Optional directory to save extracted binary blocks.
                       If None, returns binary data in dictionary.
            
        Returns:
            Dictionary mapping block names to binary data or file paths
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('BlockExtract', True)
            >>> blocks = exif.extract_binary_blocks()
        """
        block_extract = self.get_option('BlockExtract', False)
        
        if not block_extract:
            # BlockExtract not enabled, return empty dict
            return {}
        
        extracted_blocks = {}
        
        try:
            # Read file data
            file_data = self._read_file_data()
            
            # Extract thumbnail/preview images
            thumbnail_tags = ['EXIF:ThumbnailImage', 'EXIF:PreviewImage', 'Composite:ThumbnailImage']
            for tag_name in thumbnail_tags:
                tag_value = self.metadata.get(tag_name)
                if tag_value and isinstance(tag_value, bytes):
                    block_name = tag_name.replace(':', '_').replace('EXIF_', '').replace('Composite_', '')
                    if output_dir:
                        output_path = Path(output_dir) / f"{block_name}.bin"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(tag_value)
                        extracted_blocks[block_name] = str(output_path)
                    else:
                        extracted_blocks[block_name] = tag_value
            
            # Extract binary data from MakerNote tags
            for tag_name, tag_value in self.metadata.items():
                if isinstance(tag_value, bytes) and len(tag_value) > 100:
                    # Large binary blocks (likely embedded data)
                    if 'Binary' in tag_name or 'Data' in tag_name or 'Block' in tag_name:
                        block_name = tag_name.replace(':', '_')
                        if output_dir:
                            output_path = Path(output_dir) / f"{block_name}.bin"
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(output_path, 'wb') as f:
                                f.write(tag_value)
                            extracted_blocks[block_name] = str(output_path)
                        else:
                            extracted_blocks[block_name] = tag_value
            
            # Try to extract thumbnail using thumbnail extractor
            try:
                from dnexif.thumbnail_extractor import ThumbnailExtractor
                extractor = ThumbnailExtractor(file_path=str(self.file_path))
                thumbnail_data = extractor.extract_thumbnail()
                if thumbnail_data:
                    block_name = 'ThumbnailImage'
                    if output_dir:
                        output_path = Path(output_dir) / f"{block_name}.jpg"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            if isinstance(thumbnail_data, bytes):
                                f.write(thumbnail_data)
                            else:
                                f.write(bytes(thumbnail_data))
                        extracted_blocks[block_name] = str(output_path)
                    else:
                        if isinstance(thumbnail_data, bytes):
                            extracted_blocks[block_name] = thumbnail_data
                        else:
                            extracted_blocks[block_name] = bytes(thumbnail_data)
            except ImportError:
                # Thumbnail extractor not available
                pass
            except Exception:
                # Error extracting thumbnail
                pass
        
        except Exception as e:
            # Error during extraction
            if not self.get_option('NoWarning', False):
                # Only log warning if NoWarning is not enabled
                pass
        
        return extracted_blocks
    
    def extract_embedded(self, output_dir: Optional[Union[str, Path]] = None) -> Dict[str, Union[str, bytes]]:
        """
        Extract embedded files and images from the file.
        
        Uses ExtractEmbedded option to determine whether to extract embedded files.
        When ExtractEmbedded is enabled, extracts embedded files, images, thumbnails,
        previews, and other embedded data from the file.
        
        Args:
            output_dir: Optional directory to save extracted embedded files.
                       If None, returns embedded data in dictionary.
            
        Returns:
            Dictionary mapping embedded file names to binary data or file paths
            
        Examples:
            >>> exif = DNExif('image.jpg')
            >>> exif.set_option('ExtractEmbedded', True)
            >>> embedded = exif.extract_embedded()
        """
        extract_embedded = self.get_option('ExtractEmbedded', False)
        
        if not extract_embedded:
            # ExtractEmbedded not enabled, return empty dict
            return {}
        
        extracted_files = {}
        
        try:
            # Read file data
            file_data = self._read_file_data()
            
            # Extract embedded images (thumbnails, previews)
            embedded_image_tags = [
                'EXIF:ThumbnailImage', 'EXIF:PreviewImage', 'Composite:ThumbnailImage',
                'EXIF:JpgFromRaw', 'EXIF:JpgFromRawPreview', 'EXIF:PreviewImageStart',
                'EXIF:PreviewImageLength', 'FlashPix:EmbeddedImage1', 'FlashPix:EmbeddedImage2'
            ]
            for tag_name in embedded_image_tags:
                tag_value = self.metadata.get(tag_name)
                if tag_value and isinstance(tag_value, bytes):
                    # Determine file extension based on content
                    ext = '.jpg'
                    if tag_value.startswith(b'\xFF\xD8'):
                        ext = '.jpg'
                    elif tag_value.startswith(b'\x89PNG'):
                        ext = '.png'
                    elif tag_value.startswith(b'GIF'):
                        ext = '.gif'
                    
                    file_name = tag_name.replace(':', '_').replace('EXIF_', '').replace('Composite_', '').replace('FlashPix_', '')
                    if output_dir:
                        output_path = Path(output_dir) / f"{file_name}{ext}"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(tag_value)
                        extracted_files[file_name] = str(output_path)
                    else:
                        extracted_files[file_name] = tag_value
            
            # Extract embedded files from MakerNote
            for tag_name, tag_value in self.metadata.items():
                if isinstance(tag_value, bytes) and len(tag_value) > 1000:
                    # Large binary blocks might be embedded files
                    if 'Embedded' in tag_name or 'MakerNote' in tag_name:
                        file_name = tag_name.replace(':', '_')
                        if output_dir:
                            output_path = Path(output_dir) / f"{file_name}.bin"
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(output_path, 'wb') as f:
                                f.write(tag_value)
                            extracted_files[file_name] = str(output_path)
                        else:
                            extracted_files[file_name] = tag_value
            
            # Try to extract thumbnail using thumbnail extractor
            try:
                from dnexif.thumbnail_extractor import ThumbnailExtractor
                extractor = ThumbnailExtractor(file_path=str(self.file_path))
                thumbnail_data = extractor.extract_thumbnail()
                if thumbnail_data:
                    file_name = 'ThumbnailImage'
                    if output_dir:
                        output_path = Path(output_dir) / f"{file_name}.jpg"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            if isinstance(thumbnail_data, bytes):
                                f.write(thumbnail_data)
                            else:
                                f.write(bytes(thumbnail_data))
                        extracted_files[file_name] = str(output_path)
                    else:
                        if isinstance(thumbnail_data, bytes):
                            extracted_files[file_name] = thumbnail_data
                        else:
                            extracted_files[file_name] = bytes(thumbnail_data)
            except ImportError:
                # Thumbnail extractor not available
                pass
            except Exception:
                # Error extracting thumbnail
                pass
        
        except Exception as e:
            # Error during extraction
            if not self.get_option('NoWarning', False):
                # Only log warning if NoWarning is not enabled
                pass
        
        return extracted_files
    
    def __repr__(self) -> str:
        """String representation."""
        return f"DNExif(file_path='{self.file_path}', tags={len(self.metadata)})"

