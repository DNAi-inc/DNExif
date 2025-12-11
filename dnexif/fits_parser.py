# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
FITS (Flexible Image Transport System) file metadata parser

This module handles reading metadata from FITS files.
FITS is a standard format used in astronomy for storing images and data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class FITSParser:
    """
    Parser for FITS (Flexible Image Transport System) metadata.
    
    FITS files consist of:
    - Header Data Unit (HDU) with keyword-value pairs
    - Comment keywords (COMMENT, HISTORY)
    - Data unit (optional)
    
    FITS header cards are 80 bytes each, organized in blocks of 2880 bytes (36 cards).
    """
    
    # FITS header card size
    CARD_SIZE = 80
    BLOCK_SIZE = 2880  # 36 cards per block
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize FITS parser.
        
        Args:
            file_path: Path to FITS file
            file_data: FITS file data bytes
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
        Parse FITS metadata.
        
        Returns:
            Dictionary of FITS metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < self.BLOCK_SIZE:
                raise MetadataReadError("Invalid FITS file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'FITS'
            metadata['File:FileTypeExtension'] = 'fits'
            metadata['File:MIMEType'] = 'application/fits'
            
            # Parse FITS header
            header_data = self._parse_header(file_data)
            if header_data:
                metadata.update(header_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse FITS metadata: {str(e)}")
    
    def _parse_header(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse FITS header section.
        
        FITS headers consist of 80-byte cards organized in blocks of 2880 bytes.
        Header ends with END card.
        
        Args:
            file_data: FITS file data bytes
            
        Returns:
            Dictionary of parsed header metadata
        """
        metadata = {}
        
        try:
            # Read header blocks until END card is found
            header_cards = []
            offset = 0
            
            while offset + self.CARD_SIZE <= len(file_data):
                # Read one card (80 bytes)
                card = file_data[offset:offset+self.CARD_SIZE]
                
                # Check for END card
                if card[:3] == b'END':
                    break
                
                header_cards.append(card)
                offset += self.CARD_SIZE
                
                # Limit to prevent excessive parsing
                if len(header_cards) > 1000:  # Max 1000 cards
                    break
            
            # Parse cards
            comments = []
            history = []
            keywords = {}
            
            for card in header_cards:
                try:
                    # Decode card as ASCII
                    card_str = card.decode('ascii', errors='ignore').rstrip()
                    
                    if not card_str:
                        continue
                    
                    # Parse keyword-value card
                    # Format: KEYWORD = 'value' / comment
                    # Or: COMMENT / comment text
                    # Or: HISTORY / history text
                    
                    if card_str.startswith('COMMENT'):
                        # COMMENT card
                        comment_text = self._extract_comment_text(card_str)
                        if comment_text:
                            comments.append(comment_text)
                    
                    elif card_str.startswith('HISTORY'):
                        # HISTORY card
                        history_text = self._extract_history_text(card_str)
                        if history_text:
                            history.append(history_text)
                    
                    else:
                        # Regular keyword-value card
                        keyword, value, comment = self._parse_keyword_card(card_str)
                        if keyword:
                            keywords[keyword] = value
                            if comment:
                                # Store comment with keyword
                                keywords[f'{keyword}:Comment'] = comment
                
                except Exception:
                    # Skip invalid cards
                    continue
            
            # Store comments
            if comments:
                metadata['FITS:Comment'] = comments
                metadata['FITS:CommentCount'] = len(comments)
                # Also store individual comments
                for i, comment in enumerate(comments[:50], 1):  # Limit to 50 comments
                    metadata[f'FITS:Comment{i}'] = comment
            
            # Store history
            if history:
                metadata['FITS:History'] = history
                metadata['FITS:HistoryCount'] = len(history)
                # Also store individual history entries
                for i, hist_entry in enumerate(history[:50], 1):  # Limit to 50 history entries
                    metadata[f'FITS:History{i}'] = hist_entry
            
            # Store other keywords
            for keyword, value in keywords.items():
                # Sanitize keyword name for metadata tag
                tag_key = keyword.replace(' ', '').replace('-', '').replace(':', '')
                metadata[f'FITS:{tag_key}'] = value
            
            # Extract common FITS keywords
            if 'SIMPLE' in keywords:
                metadata['FITS:Simple'] = keywords['SIMPLE']
            if 'BITPIX' in keywords:
                metadata['FITS:BitsPerPixel'] = keywords['BITPIX']
            if 'NAXIS' in keywords:
                metadata['FITS:NAXIS'] = keywords['NAXIS']
            if 'NAXIS1' in keywords:
                metadata['FITS:NAXIS1'] = keywords['NAXIS1']
            if 'NAXIS2' in keywords:
                metadata['FITS:NAXIS2'] = keywords['NAXIS2']
            if 'DATE' in keywords:
                metadata['FITS:Date'] = keywords['DATE']
            if 'DATE-OBS' in keywords:
                metadata['FITS:DateObs'] = keywords['DATE-OBS']
            if 'OBJECT' in keywords:
                metadata['FITS:Object'] = keywords['OBJECT']
            if 'TELESCOP' in keywords:
                metadata['FITS:Telescope'] = keywords['TELESCOP']
            if 'INSTRUME' in keywords:
                metadata['FITS:Instrument'] = keywords['INSTRUME']
            if 'OBSERVER' in keywords:
                metadata['FITS:Observer'] = keywords['OBSERVER']
        
        except Exception:
            pass
        
        return metadata
    
    def _extract_comment_text(self, card_str: str) -> Optional[str]:
        """
        Extract comment text from COMMENT card.
        
        Format: COMMENT / comment text
        
        Args:
            card_str: COMMENT card string
            
        Returns:
            Comment text or None
        """
        try:
            # COMMENT card format: "COMMENT / comment text"
            if '/' in card_str:
                parts = card_str.split('/', 1)
                if len(parts) > 1:
                    comment_text = parts[1].strip()
                    return comment_text if comment_text else None
            else:
                # COMMENT without separator
                if len(card_str) > 8:
                    return card_str[8:].strip()
        except Exception:
            pass
        
        return None
    
    def _extract_history_text(self, card_str: str) -> Optional[str]:
        """
        Extract history text from HISTORY card.
        
        Format: HISTORY / history text
        
        Args:
            card_str: HISTORY card string
            
        Returns:
            History text or None
        """
        try:
            # HISTORY card format: "HISTORY / history text"
            if '/' in card_str:
                parts = card_str.split('/', 1)
                if len(parts) > 1:
                    history_text = parts[1].strip()
                    return history_text if history_text else None
            else:
                # HISTORY without separator
                if len(card_str) > 7:
                    return card_str[7:].strip()
        except Exception:
            pass
        
        return None
    
    def _parse_keyword_card(self, card_str: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse keyword-value card.
        
        Format: KEYWORD = 'value' / comment
        Or: KEYWORD = value / comment
        Or: KEYWORD = T / comment (boolean true)
        Or: KEYWORD = F / comment (boolean false)
        
        Args:
            card_str: Card string
            
        Returns:
            Tuple of (keyword, value, comment) or (None, None, None)
        """
        try:
            # Split by '=' to separate keyword and value
            if '=' not in card_str:
                return None, None, None
            
            parts = card_str.split('=', 1)
            if len(parts) < 2:
                return None, None, None
            
            keyword = parts[0].strip()
            value_part = parts[1].strip()
            
            # Extract comment (after '/')
            comment = None
            value = value_part
            
            if '/' in value_part:
                comment_parts = value_part.split('/', 1)
                value = comment_parts[0].strip()
                if len(comment_parts) > 1:
                    comment = comment_parts[1].strip()
            
            # Parse value
            # Remove quotes if present
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            
            # Handle boolean values
            if value == 'T':
                value = True
            elif value == 'F':
                value = False
            
            # Try to parse as number
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                pass  # Keep as string
            
            return keyword, value, comment
        
        except Exception:
            return None, None, None

