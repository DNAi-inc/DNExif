# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PCAP (Packet Capture) file metadata parser

This module handles reading metadata from PCAP packet capture files.
PCAP files contain network packet data with timestamps and protocol information.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from dnexif.exceptions import MetadataReadError


class PCAPParser:
    """
    Parser for PCAP (Packet Capture) metadata.
    
    PCAP files have the following structure:
    - Global header (24 bytes)
    - Packet records (16-byte header + packet data)
    """
    
    # PCAP magic numbers (endianness indicators)
    PCAP_MAGIC_NATIVE = 0xA1B2C3D4  # Native byte order
    PCAP_MAGIC_SWAPPED = 0xD4C3B2A1  # Swapped byte order
    PCAP_MAGIC_NANOSEC = 0xA1B23C4D  # Nanosecond timestamps, native
    PCAP_MAGIC_NANOSEC_SWAPPED = 0x4D3CB2A1  # Nanosecond timestamps, swapped
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PCAP parser.
        
        Args:
            file_path: Path to PCAP file
            file_data: PCAP file data bytes
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
        Parse PCAP metadata.
        
        Returns:
            Dictionary of PCAP metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 24:
                raise MetadataReadError("Invalid PCAP file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PCAP'
            metadata['File:FileTypeExtension'] = 'pcap'
            metadata['File:MIMEType'] = 'application/vnd.tcpdump.pcap'
            
            # Parse global header (24 bytes)
            header_data = self._parse_global_header(file_data)
            if header_data:
                metadata.update(header_data)
            
            # Parse packet records to extract statistics
            packet_stats = self._parse_packet_records(file_data, header_data.get('PCAP:ByteOrder', 'little'))
            if packet_stats:
                metadata.update(packet_stats)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PCAP metadata: {str(e)}")
    
    def _parse_global_header(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse PCAP global header.
        
        PCAP global header structure (24 bytes):
        - Magic number: 4 bytes (0xA1B2C3D4 or swapped)
        - Version major: 2 bytes
        - Version minor: 2 bytes
        - Timezone: 4 bytes (GMT offset in seconds)
        - Sigfigs: 4 bytes (accuracy of timestamps)
        - Snaplen: 4 bytes (max packet length)
        - Network: 4 bytes (data link type)
        
        Args:
            file_data: PCAP file data bytes
            
        Returns:
            Dictionary of header metadata
        """
        metadata = {}
        
        try:
            if len(file_data) < 24:
                return metadata
            
            # Read magic number
            magic = struct.unpack('<I', file_data[0:4])[0]
            
            # Determine byte order and timestamp precision
            if magic == self.PCAP_MAGIC_NATIVE:
                byte_order = 'little'
                nanosecond_precision = False
            elif magic == self.PCAP_MAGIC_SWAPPED:
                byte_order = 'big'
                nanosecond_precision = False
            elif magic == self.PCAP_MAGIC_NANOSEC:
                byte_order = 'little'
                nanosecond_precision = True
            elif magic == self.PCAP_MAGIC_NANOSEC_SWAPPED:
                byte_order = 'big'
                nanosecond_precision = True
            else:
                raise MetadataReadError("Invalid PCAP file: invalid magic number")
            
            metadata['PCAP:ByteOrder'] = byte_order
            metadata['PCAP:NanosecondPrecision'] = nanosecond_precision
            
            # Parse header fields based on byte order
            if byte_order == 'little':
                version_major = struct.unpack('<H', file_data[4:6])[0]
                version_minor = struct.unpack('<H', file_data[6:8])[0]
                timezone = struct.unpack('<i', file_data[8:12])[0]  # Signed integer
                sigfigs = struct.unpack('<I', file_data[12:16])[0]
                snaplen = struct.unpack('<I', file_data[16:20])[0]
                network = struct.unpack('<I', file_data[20:24])[0]
            else:
                version_major = struct.unpack('>H', file_data[4:6])[0]
                version_minor = struct.unpack('>H', file_data[6:8])[0]
                timezone = struct.unpack('>i', file_data[8:12])[0]
                sigfigs = struct.unpack('>I', file_data[12:16])[0]
                snaplen = struct.unpack('>I', file_data[16:20])[0]
                network = struct.unpack('>I', file_data[20:24])[0]
            
            metadata['PCAP:Version'] = f'{version_major}.{version_minor}'
            metadata['PCAP:VersionMajor'] = version_major
            metadata['PCAP:VersionMinor'] = version_minor
            metadata['PCAP:Timezone'] = timezone
            metadata['PCAP:Sigfigs'] = sigfigs
            metadata['PCAP:Snaplen'] = snaplen
            metadata['PCAP:Network'] = network
            
            # Map common network types
            network_types = {
                0: 'BSD loopback',
                1: 'Ethernet',
                6: 'IEEE 802.5 Token Ring',
                7: 'ARCnet',
                8: 'SLIP',
                9: 'PPP',
                10: 'FDDI',
                100: 'LLC/SNAP',
                101: 'Raw IP',
                104: 'Linux cooked capture',
                113: 'Linux cooked capture v2',
            }
            network_name = network_types.get(network, f'Unknown ({network})')
            metadata['PCAP:NetworkType'] = network_name
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_packet_records(self, file_data: bytes, byte_order: str) -> Dict[str, Any]:
        """
        Parse packet records to extract statistics.
        
        Packet record structure (16 bytes header):
        - Timestamp seconds: 4 bytes
        - Timestamp microseconds/nanoseconds: 4 bytes
        - Captured length: 4 bytes
        - Original length: 4 bytes
        - Packet data: variable length
        
        Args:
            file_data: PCAP file data bytes
            byte_order: Byte order ('little' or 'big')
            
        Returns:
            Dictionary of packet statistics
        """
        metadata = {}
        
        try:
            if len(file_data) < 24:
                return metadata
            
            # Start after global header (24 bytes)
            offset = 24
            packet_count = 0
            total_bytes = 0
            first_timestamp = None
            last_timestamp = None
            
            # Protocol statistics
            protocol_counts = {}
            ip_packet_count = 0
            tcp_packet_count = 0
            udp_packet_count = 0
            icmp_packet_count = 0
            
            # Parse up to first 1000 packets for statistics (to avoid long processing)
            max_packets = 1000
            
            while offset + 16 <= len(file_data) and packet_count < max_packets:
                # Read packet header
                if byte_order == 'little':
                    ts_sec = struct.unpack('<I', file_data[offset:offset+4])[0]
                    ts_usec = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                    captured_len = struct.unpack('<I', file_data[offset+8:offset+12])[0]
                    original_len = struct.unpack('<I', file_data[offset+12:offset+16])[0]
                else:
                    ts_sec = struct.unpack('>I', file_data[offset:offset+4])[0]
                    ts_usec = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                    captured_len = struct.unpack('>I', file_data[offset+8:offset+12])[0]
                    original_len = struct.unpack('>I', file_data[offset+12:offset+16])[0]
                
                # Calculate timestamp
                timestamp = ts_sec + (ts_usec / 1000000.0)
                
                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp
                
                # Update statistics
                packet_count += 1
                total_bytes += captured_len
                
                # Extract protocol information from packet data (if available)
                if captured_len >= 14:  # Minimum Ethernet header size
                    packet_data_start = offset + 16
                    if packet_data_start + captured_len <= len(file_data):
                        packet_data = file_data[packet_data_start:packet_data_start + min(captured_len, 100)]  # First 100 bytes
                        
                        # Check for Ethernet frame (EtherType at offset 12-13)
                        if len(packet_data) >= 14:
                            ethertype = struct.unpack('>H', packet_data[12:14])[0]
                            
                            # IPv4 (0x0800) or IPv6 (0x86DD)
                            if ethertype == 0x0800 and len(packet_data) >= 34:  # IPv4
                                ip_packet_count += 1
                                # IP protocol field is at offset 23 (9 bytes into IP header)
                                ip_protocol = packet_data[23]
                                
                                if ip_protocol == 6:  # TCP
                                    tcp_packet_count += 1
                                    protocol_counts['TCP'] = protocol_counts.get('TCP', 0) + 1
                                elif ip_protocol == 17:  # UDP
                                    udp_packet_count += 1
                                    protocol_counts['UDP'] = protocol_counts.get('UDP', 0) + 1
                                elif ip_protocol == 1:  # ICMP
                                    icmp_packet_count += 1
                                    protocol_counts['ICMP'] = protocol_counts.get('ICMP', 0) + 1
                                else:
                                    protocol_counts[f'IP-{ip_protocol}'] = protocol_counts.get(f'IP-{ip_protocol}', 0) + 1
                                
                                protocol_counts['IPv4'] = protocol_counts.get('IPv4', 0) + 1
                            elif ethertype == 0x86DD:  # IPv6
                                protocol_counts['IPv6'] = protocol_counts.get('IPv6', 0) + 1
                            elif ethertype == 0x0806:  # ARP
                                protocol_counts['ARP'] = protocol_counts.get('ARP', 0) + 1
                            else:
                                protocol_counts[f'EtherType-0x{ethertype:04X}'] = protocol_counts.get(f'EtherType-0x{ethertype:04X}', 0) + 1
                
                # Move to next packet
                offset += 16 + captured_len
                
                # Check if we've reached end of file
                if offset >= len(file_data):
                    break
            
            if packet_count > 0:
                metadata['PCAP:PacketCount'] = packet_count
                metadata['PCAP:TotalBytes'] = total_bytes
                metadata['PCAP:AveragePacketSize'] = total_bytes / packet_count if packet_count > 0 else 0
                
                if first_timestamp:
                    try:
                        dt_first = datetime.fromtimestamp(first_timestamp, tz=None)
                        metadata['PCAP:FirstPacketTime'] = dt_first.strftime('%Y:%m:%d %H:%M:%S')
                    except Exception:
                        pass
                
                if last_timestamp:
                    try:
                        dt_last = datetime.fromtimestamp(last_timestamp, tz=None)
                        metadata['PCAP:LastPacketTime'] = dt_last.strftime('%Y:%m:%d %H:%M:%S')
                    except Exception:
                        pass
                
                if first_timestamp and last_timestamp:
                    duration = last_timestamp - first_timestamp
                    if duration > 0:
                        metadata['PCAP:Duration'] = f"{duration:.2f} s"
                        metadata['PCAP:PacketsPerSecond'] = f"{packet_count / duration:.2f}"
            
            # Add protocol statistics
            if protocol_counts:
                metadata['PCAP:ProtocolCount'] = len(protocol_counts)
                # Add top protocols
                sorted_protocols = sorted(protocol_counts.items(), key=lambda x: x[1], reverse=True)
                for i, (protocol, count) in enumerate(sorted_protocols[:10]):  # Top 10 protocols
                    metadata[f'PCAP:Protocol{i+1}'] = protocol
                    metadata[f'PCAP:Protocol{i+1}:Count'] = count
            
            if ip_packet_count > 0:
                metadata['PCAP:IPPacketCount'] = ip_packet_count
            if tcp_packet_count > 0:
                metadata['PCAP:TCPPacketCount'] = tcp_packet_count
            if udp_packet_count > 0:
                metadata['PCAP:UDPPacketCount'] = udp_packet_count
            if icmp_packet_count > 0:
                metadata['PCAP:ICMPPacketCount'] = icmp_packet_count
            
            # Note if we stopped early
            if packet_count >= max_packets:
                metadata['PCAP:Note'] = f'Statistics based on first {max_packets} packets'
        
        except Exception:
            pass
        
        return metadata

