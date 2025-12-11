# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Date formatting utilities

Provides custom date formatting capabilities compatible with standard -d option.

Copyright 2025 DNAi inc.
"""

from datetime import datetime
from typing import Optional, Union
import re


class DateFormatter:
    """
    Custom date formatting compatible with standard -d option.
    
    Supports standard format date format specifiers:
    %Y - 4-digit year
    %y - 2-digit year
    %m - Month (01-12)
    %d - Day (01-31)
    %H - Hour (00-23)
    %M - Minute (00-59)
    %S - Second (00-59)
    %f - Fractional seconds
    %z - Time zone offset
    %:z - Time zone offset with colon
    %A - Full weekday name
    %a - Abbreviated weekday name
    %B - Full month name
    %b - Abbreviated month name
    %w - Weekday number (0=Sunday)
    %j - Day of year (001-366)
    %U - Week number (00-53, Sunday first)
    %W - Week number (00-53, Monday first)
    %V - ISO week number (01-53)
    %G - ISO 4-digit year
    %g - ISO 2-digit year
    """
    
    # standard format specifiers to Python strftime format
    FORMAT_MAP = {
        '%Y': '%Y',  # 4-digit year
        '%y': '%y',  # 2-digit year
        '%m': '%m',  # Month (01-12)
        '%d': '%d',  # Day (01-31)
        '%H': '%H',  # Hour (00-23)
        '%M': '%M',  # Minute (00-59)
        '%S': '%S',  # Second (00-59)
        '%f': '%f',  # Fractional seconds (microseconds)
        '%z': '%z',  # Time zone offset
        '%:z': '%z',  # Time zone offset with colon (handled separately)
        '%A': '%A',  # Full weekday name
        '%a': '%a',  # Abbreviated weekday name
        '%B': '%B',  # Full month name
        '%b': '%b',  # Abbreviated month name
        '%w': '%w',  # Weekday number (0=Sunday)
        '%j': '%j',  # Day of year (001-366)
        '%U': '%U',  # Week number (00-53, Sunday first)
        '%W': '%W',  # Week number (00-53, Monday first)
        '%V': '%V',  # ISO week number (01-53) - not in strftime, handled separately
        '%G': '%G',  # ISO 4-digit year - not in strftime, handled separately
        '%g': '%g',  # ISO 2-digit year - not in strftime, handled separately
    }
    
    @staticmethod
    def format_date(
        date_value: Union[str, datetime],
        format_string: str
    ) -> str:
        """
        Format a date value using standard format string.
        
        Args:
            date_value: Date as string (EXIF format) or datetime object
            format_string: Format string with standard format specifiers
            
        Returns:
            Formatted date string
        """
        # Parse date if string
        if isinstance(date_value, str):
            dt = DateFormatter._parse_exif_date(date_value)
        else:
            dt = date_value
        
        if dt is None:
            return str(date_value)
        
        # Convert standard format to Python strftime format
        python_format = DateFormatter._convert_format(format_string)
        
        # Handle special cases
        formatted = DateFormatter._format_with_specials(dt, format_string, python_format)
        
        return formatted
    
    @staticmethod
    def _parse_exif_date(date_str: str) -> Optional[datetime]:
        """
        Parse EXIF date string to datetime object.
        
        Supports formats:
        - YYYY:MM:DD HH:MM:SS
        - YYYY:MM:DD HH:MM:SS.sss
        - YYYY-MM-DD HH:MM:SS
        - YYYY-MM-DD HH:MM:SS+HH:MM
        """
        # Try EXIF format first (YYYY:MM:DD HH:MM:SS)
        try:
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        except ValueError:
            pass
        
        # Try with fractional seconds
        try:
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S.%f')
        except ValueError:
            pass
        
        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace(':', '-', 2))
        except ValueError:
            pass
        
        # Try standard format
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    def _convert_format(format_string: str) -> str:
        """
        Convert standard format string to Python strftime format.
        
        Args:
            format_string: standard format string
            
        Returns:
            Python strftime format string
        """
        # Replace standard format specifiers with Python equivalents
        python_format = format_string
        
        # Handle %:z (timezone with colon) - convert to %z format
        python_format = python_format.replace('%:z', '%z')
        
        # Handle %V (ISO week number) - will be handled separately
        # Handle %G and %g (ISO year) - will be handled separately
        
        return python_format
    
    @staticmethod
    def _format_with_specials(
        dt: datetime,
        standard format_format: str,
        python_format: str
    ) -> str:
        """
        Format datetime with special handling for non-strftime specifiers.
        
        Args:
            dt: Datetime object
            standard format_format: Original standard format string
            python_format: Python strftime format string
            
        Returns:
            Formatted date string
        """
        # First, format with standard strftime
        try:
            formatted = dt.strftime(python_format)
        except ValueError:
            # Fallback if format is invalid
            return dt.isoformat()
        
        # Handle ISO week number (%V)
        if '%V' in standard format_format:
            iso_year, iso_week, iso_weekday = dt.isocalendar()
            formatted = formatted.replace('%V', f'{iso_week:02d}')
        
        # Handle ISO 4-digit year (%G)
        if '%G' in standard format_format:
            iso_year, iso_week, iso_weekday = dt.isocalendar()
            formatted = formatted.replace('%G', str(iso_year))
        
        # Handle ISO 2-digit year (%g)
        if '%g' in standard format_format:
            iso_year, iso_week, iso_weekday = dt.isocalendar()
            formatted = formatted.replace('%g', str(iso_year)[-2:])
        
        # Handle %:z (timezone with colon)
        if '%:z' in standard format_format:
            if dt.tzinfo is not None:
                offset = dt.utcoffset()
                if offset:
                    total_seconds = int(offset.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    tz_str = f"{hours:+03d}:{minutes:02d}"
                    formatted = formatted.replace('%:z', tz_str)
                else:
                    formatted = formatted.replace('%:z', '+00:00')
            else:
                formatted = formatted.replace('%:z', '')
        
        # Handle fractional seconds (%f)
        if '%f' in standard format_format:
            microseconds = dt.microsecond
            # Standard format uses 3 digits for fractional seconds
            fractional = f"{microseconds:06d}"[:3]
            formatted = formatted.replace('%f', fractional)
        
        return formatted
    
    @staticmethod
    def format_all_dates(
        metadata: dict,
        format_string: str
    ) -> dict:
        """
        Format all date/time tags in metadata.
        
        Args:
            metadata: Metadata dictionary
            format_string: Format string to apply
            
        Returns:
            New metadata dictionary with formatted dates
        """
        formatted_metadata = {}
        
        # Date/time tag patterns
        date_tags = [
            'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
            'CreateDate', 'ModifyDate', 'GPSDateStamp', 'GPSTimeStamp'
        ]
        
        for key, value in metadata.items():
            # Check if this is a date/time tag
            is_date_tag = any(tag in key for tag in date_tags)
            
            if is_date_tag and isinstance(value, str):
                # Try to format as date
                formatted_value = DateFormatter.format_date(value, format_string)
                formatted_metadata[key] = formatted_value
            else:
                formatted_metadata[key] = value
        
        return formatted_metadata

