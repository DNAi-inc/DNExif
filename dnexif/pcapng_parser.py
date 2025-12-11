# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PCAPNG (PCAP Next Generation) file metadata parser

This module handles reading metadata from PCAPNG packet capture files.
PCAPNG files use a block-based structure instead of a global header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from dnexif.exceptions import MetadataReadError


class PCAPNGParser:
    """
    Parser for PCAPNG (PCAP Next Generation) metadata.
    
    PCAPNG files have the following structure:
    - Section Header Block (SHB) - identifies the file format
    - Interface Description Block (IDB) - describes network interfaces
    - Enhanced Packet Block (EPB) - contains packet data
    - Simple Packet Block (SPB) - simplified packet data
    - Other block types
    """
    
    # PCAPNG block types
    BLOCK_TYPE_SHB = 0x0A0D0D0A  # Section Header Block
    BLOCK_TYPE_IDB = 0x00000001  # Interface Description Block
    BLOCK_TYPE_PB = 0x00000002  # Packet Block (deprecated)
    BLOCK_TYPE_SPB = 0x00000003  # Simple Packet Block
    BLOCK_TYPE_EPB = 0x00000006  # Enhanced Packet Block
    
    # PCAPNG magic numbers
    PCAPNG_MAGIC_LE = 0x0A0D0D0A  # Little-endian
    PCAPNG_MAGIC_BE = 0x1A2B3C4D  # Big-endian
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PCAPNG parser.
        
        Args:
            file_path: Path to PCAPNG file
            file_data: PCAPNG file data bytes
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
        Parse PCAPNG metadata.
        
        Returns:
            Dictionary of PCAPNG metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 12:
                raise MetadataReadError("Invalid PCAPNG file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PCAPNG'
            metadata['File:FileTypeExtension'] = 'pcapng'
            metadata['File:MIMEType'] = 'application/vnd.tcpdump.pcapng'
            
            # Parse blocks
            block_stats = self._parse_blocks(file_data)
            if block_stats:
                metadata.update(block_stats)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PCAPNG metadata: {str(e)}")
    
    def _parse_blocks(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse PCAPNG blocks.
        
        Each block has:
        - Block Type (4 bytes)
        - Block Total Length (4 bytes)
        - Block Body (variable)
        - Block Total Length (4 bytes, repeated)
        
        Args:
            file_data: PCAPNG file data bytes
            
        Returns:
            Dictionary of block statistics
        """
        metadata = {}
        
        try:
            if len(file_data) < 12:
                return metadata
            
            # Check for Section Header Block (SHB) at the beginning
            # SHB magic: 0x0A0D0D0A (little-endian) or 0x1A2B3C4D (big-endian)
            shb_magic_le = struct.unpack('<I', file_data[0:4])[0]
            shb_magic_be = struct.unpack('>I', file_data[0:4])[0]
            
            byte_order = None
            if shb_magic_le == self.PCAPNG_MAGIC_LE:
                byte_order = 'little'
            elif shb_magic_be == self.PCAPNG_MAGIC_BE:
                byte_order = 'big'
            else:
                raise MetadataReadError("Invalid PCAPNG file: missing Section Header Block")
            
            metadata['PCAPNG:ByteOrder'] = byte_order
            
            # Parse blocks
            offset = 0
            shb_count = 0
            idb_count = 0
            epb_count = 0
            spb_count = 0
            packet_count = 0
            total_bytes = 0
            
            # Parse up to first 100 blocks for statistics (to avoid long processing)
            max_blocks = 100
            
            block_count = 0
            while offset + 12 <= len(file_data) and block_count < max_blocks:
                # Read block type and length
                if byte_order == 'little':
                    block_type = struct.unpack('<I', file_data[offset:offset+4])[0]
                    block_length = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                else:
                    block_type = struct.unpack('>I', file_data[offset:offset+4])[0]
                    block_length = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                
                # Validate block length
                if block_length < 12 or block_length > len(file_data) - offset:
                    break
                
                # Count block types
                if block_type == self.BLOCK_TYPE_SHB:
                    shb_count += 1
                    # Parse SHB to extract version
                    if offset + 20 <= len(file_data):
                        if byte_order == 'little':
                            version_major = struct.unpack('<H', file_data[offset+12:offset+14])[0]
                            version_minor = struct.unpack('<H', file_data[offset+14:offset+16])[0]
                        else:
                            version_major = struct.unpack('>H', file_data[offset+12:offset+14])[0]
                            version_minor = struct.unpack('>H', file_data[offset+14:offset+16])[0]
                        metadata['PCAPNG:Version'] = f'{version_major}.{version_minor}'
                        metadata['PCAPNG:VersionMajor'] = version_major
                        metadata['PCAPNG:VersionMinor'] = version_minor
                
                elif block_type == self.BLOCK_TYPE_IDB:
                    idb_count += 1
                
                elif block_type == self.BLOCK_TYPE_EPB:
                    epb_count += 1
                    packet_count += 1
                    # Extract packet length from EPB
                    if offset + 20 <= len(file_data):
                        if byte_order == 'little':
                            captured_len = struct.unpack('<I', file_data[offset+16:offset+20])[0]
                        else:
                            captured_len = struct.unpack('>I', file_data[offset+16:offset+20])[0]
                        total_bytes += captured_len
                
                elif block_type == self.BLOCK_TYPE_SPB:
                    spb_count += 1
                    packet_count += 1
                    # Extract packet length from SPB
                    # SPB structure: Block Type (4) + Block Length (4) + Original Packet Length (4) + Packet Data (variable)
                    if offset + 16 <= len(file_data):
                        if byte_order == 'little':
                            original_len = struct.unpack('<I', file_data[offset+8:offset+12])[0]
                        else:
                            original_len = struct.unpack('>I', file_data[offset+8:offset+12])[0]
                        total_bytes += original_len
                
                # Move to next block
                offset += block_length
                block_count += 1
                
                # Check if we've reached end of file
                if offset >= len(file_data):
                    break
            
            # Store statistics
            metadata['PCAPNG:SectionHeaderBlockCount'] = shb_count
            metadata['PCAPNG:InterfaceDescriptionBlockCount'] = idb_count
            metadata['PCAPNG:EnhancedPacketBlockCount'] = epb_count
            metadata['PCAPNG:SimplePacketBlockCount'] = spb_count
            metadata['PCAPNG:PacketCount'] = packet_count
            metadata['PCAPNG:TotalBytes'] = total_bytes
            
            if packet_count > 0:
                metadata['PCAPNG:AveragePacketSize'] = total_bytes / packet_count
            
            # Note if we stopped early
            if block_count >= max_blocks:
                metadata['PCAPNG:Note'] = f'Statistics based on first {max_blocks} blocks'
        
        except Exception:
            pass
        
        return metadata

