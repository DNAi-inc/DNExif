# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PDF metadata writer

This module provides metadata writing for PDF files.
PDF files can contain XMP metadata and Document Info Dictionary.

Copyright 2025 DNAi inc.
"""

import re
import zlib
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.xmp_writer import XMPWriter


class PDFWriter:
    """
    Writer for PDF metadata.
    
    PDF files can contain:
    - XMP metadata (in /Metadata stream)
    - Document Info Dictionary (Title, Author, Subject, Keywords, Creator, Producer, etc.)
    """
    
    def __init__(self):
        """Initialize PDF writer."""
        self.xmp_writer = XMPWriter()
    
    def write_pdf(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to PDF file.
        
        Args:
            file_path: Path to input PDF file
            metadata: Dictionary of metadata to write
            output_path: Path to output PDF file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                pdf_data = f.read()
            
            if not pdf_data.startswith(b'%PDF'):
                raise MetadataWriteError("Invalid PDF file: missing PDF signature")
            
            # Separate metadata by type
            xmp_metadata = {}
            doc_info = {}
            
            for key, value in metadata.items():
                if key.startswith('XMP:'):
                    xmp_metadata[key] = value
                elif key.startswith('PDF:'):
                    doc_info[key[4:]] = value
                elif key.startswith('Document:'):
                    doc_info[key[9:]] = value
                else:
                    # Default to XMP for unknown prefixes
                    xmp_metadata[key] = value
            
            # Write XMP metadata if present
            if xmp_metadata:
                pdf_data = self._write_xmp_metadata(pdf_data, xmp_metadata)
            
            # Write Document Info Dictionary if present
            if doc_info:
                pdf_data = self._write_doc_info(pdf_data, doc_info)
            
            # Write output file
            with open(output_path, 'wb') as f:
                f.write(pdf_data)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write PDF metadata: {str(e)}")
    
    def _write_xmp_metadata(self, pdf_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Write XMP metadata to PDF.
        
        Args:
            pdf_data: Original PDF data
            metadata: XMP metadata dictionary
            
        Returns:
            Modified PDF data with XMP metadata
        """
        try:
            # Generate XMP packet
            xmp_packet = self.xmp_writer.build_xmp_packet(metadata)
            
            # Find existing /Metadata object or create new one
            # Look for /Metadata reference in catalog
            metadata_obj_pattern = rb'(\d+)\s+\d+\s+obj\s+<<\s*/Type\s*/Metadata'
            match = re.search(metadata_obj_pattern, pdf_data)
            
            if match:
                # Update existing metadata object
                obj_start = match.start()
                obj_end = pdf_data.find(b'endobj', obj_start)
                if obj_end == -1:
                    obj_end = len(pdf_data)
                else:
                    obj_end += len(b'endobj')
                
                dict_start = pdf_data.find(b'<<', obj_start, obj_end)
                dict_end = pdf_data.find(b'>>', dict_start, obj_end)
                if dict_start == -1 or dict_end == -1:
                    raise MetadataWriteError("Malformed PDF metadata dictionary")
                dict_end += 2
                dict_bytes = pdf_data[dict_start:dict_end]
                has_flate = b'/FlateDecode' in dict_bytes
                
                stream_start = pdf_data.find(b'stream', dict_end, obj_end)
                if stream_start == -1:
                    raise MetadataWriteError("Metadata stream not found in PDF")
                stream_start += len(b'stream')
                if pdf_data[stream_start:stream_start+2] == b'\r\n':
                    stream_start += 2
                elif pdf_data[stream_start:stream_start+1] in (b'\r', b'\n'):
                    stream_start += 1
                
                stream_end = pdf_data.find(b'endstream', stream_start, obj_end)
                if stream_end == -1:
                    raise MetadataWriteError("Metadata stream terminator missing")
                
                xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
                stream_bytes = zlib.compress(xmp_bytes) if has_flate else xmp_bytes
                
                updated_pdf = (
                    pdf_data[:stream_start] +
                    stream_bytes +
                    pdf_data[stream_end:]
                )
                
                # Update /Length (direct) and any referenced length object
                updated_pdf = self._update_metadata_lengths(
                    updated_pdf,
                    dict_start,
                    dict_end,
                    dict_bytes,
                    len(stream_bytes)
                )
                
                return updated_pdf
            
            # If no existing metadata object, append a new one using an incremental update
            xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
            updater = _PDFIncrementalUpdater(pdf_data)
            pdf_data = updater.add_metadata_stream(xmp_bytes)
            return pdf_data
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write XMP metadata: {str(e)}")
    
    def _write_doc_info(self, pdf_data: bytes, doc_info: Dict[str, Any]) -> bytes:
        """
        Write Document Info Dictionary to PDF.
        
        Args:
            pdf_data: Original PDF data
            doc_info: Document info dictionary
            
        Returns:
            Modified PDF data with Document Info
        """
        try:
            # Map metadata keys to PDF info dictionary keys
            pdf_info_keys = {
                'Title': '/Title',
                'Author': '/Author',
                'Subject': '/Subject',
                'Keywords': '/Keywords',
                'Creator': '/Creator',
                'Producer': '/Producer',
                'CreationDate': '/CreationDate',
                'ModDate': '/ModDate',
            }
            
            # Find existing Info object
            info_pattern = rb'(\d+)\s+\d+\s+obj\s+<<\s*/Type\s*/Info'
            match = re.search(info_pattern, pdf_data)
            
            info_dict = b'<<\n'
            for key, value in doc_info.items():
                pdf_key = pdf_info_keys.get(key, f'/{key}')
                # Escape PDF string
                value_str = str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                info_dict += pdf_key.encode('utf-8') + b' (' + value_str.encode('utf-8') + b')\n'
            info_dict += b'>>\n'
            
            if match:
                # Update existing Info object
                obj_start = match.start()
                obj_end = pdf_data.find(b'endobj', obj_start)
                if obj_end == -1:
                    obj_end = len(pdf_data)
                else:
                    obj_end += 6
                
                # Find the dictionary in the object
                dict_start = pdf_data.find(b'<<', obj_start, obj_end)
                dict_end = pdf_data.find(b'>>', dict_start, obj_end)
                if dict_end != -1:
                    dict_end += 2
                    new_pdf = (
                        pdf_data[:dict_start] +
                        info_dict +
                        pdf_data[dict_end:]
                    )
                    return new_pdf
            
            # If no Info object, append one with an incremental update
            updater = _PDFIncrementalUpdater(pdf_data)
            pdf_data = updater.add_info_dictionary(info_dict)
            return pdf_data
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write Document Info: {str(e)}")

    def _update_metadata_lengths(
        self,
        pdf_data: bytes,
        dict_start: int,
        dict_end: int,
        original_dict: bytes,
        new_length: int
    ) -> bytes:
        """
        Update /Length entries (direct or indirect) for a metadata stream.
        """
        dict_bytes = original_dict
        updated_data = pdf_data
        
        direct_pattern = re.compile(rb'(/Length\s+)(\d+)(?!\s+\d+\s+R)')
        direct_match = direct_pattern.search(dict_bytes)
        if direct_match:
            replacement = direct_pattern.sub(
                lambda m: m.group(1) + str(new_length).encode('ascii'),
                dict_bytes,
                count=1
            )
            updated_data = (
                updated_data[:dict_start] +
                replacement +
                updated_data[dict_end:]
            )
            dict_bytes = replacement
        else:
            # Handle indirect reference e.g., /Length 3 0 R
            indirect_match = re.search(rb'/Length\s+(\d+)\s+0\s+R', dict_bytes)
            if indirect_match:
                obj_num = int(indirect_match.group(1))
                updated_data = self._update_length_object(updated_data, obj_num, new_length)
        
        return updated_data

    @staticmethod
    def _update_length_object(pdf_data: bytes, obj_number: int, new_length: int) -> bytes:
        """Update the value of an indirect length object."""
        pattern = f"{obj_number} 0 obj".encode('ascii')
        obj_index = pdf_data.find(pattern)
        if obj_index == -1:
            return pdf_data
        
        value_start = pdf_data.find(b'\n', obj_index)
        if value_start == -1:
            return pdf_data
        value_start += 1
        value_end = pdf_data.find(b'endobj', value_start)
        if value_end == -1:
            return pdf_data
        
        new_value = f"{new_length}\n".encode('ascii')
        return pdf_data[:value_start] + new_value + pdf_data[value_end:]


class _PDFIncrementalUpdater:
    """
    Minimal incremental updater for appending metadata / info objects to an
    existing PDF while keeping cross-reference tables valid.
    """

    def __init__(self, pdf_data: bytes):
        self.pdf_data = pdf_data
        self.original_size = None
        self.size = None
        self.root_obj: Optional[int] = None
        self.info_obj: Optional[int] = None
        self.prev_startxref: Optional[int] = None
        self.trailer_dict: bytes = b''
        self._parse_trailer()
        self.new_objects: Dict[int, bytes] = {}
        self.info_override: Optional[int] = None

    def _parse_trailer(self) -> None:
        startxref_pos = self.pdf_data.rfind(b'startxref')
        if startxref_pos == -1:
            raise MetadataWriteError("PDF missing startxref")
        value_start = startxref_pos + len(b'startxref')
        value_slice = self.pdf_data[value_start:]
        value_slice = value_slice.lstrip(b'\r\n \t')
        line_end = value_slice.find(b'\n')
        if line_end == -1:
            line = value_slice.strip()
        else:
            line = value_slice[:line_end].strip(b'\r\n \t')
        try:
            self.prev_startxref = int(line)
        except ValueError:
            raise MetadataWriteError("Invalid startxref value")

        trailer_pos = self.pdf_data.find(b'trailer', self.prev_startxref or 0)
        if trailer_pos == -1 or trailer_pos > startxref_pos:
            # Fallback to reverse search if forward lookup fails
            trailer_pos = self.pdf_data.rfind(b'trailer', 0, startxref_pos)
            if trailer_pos == -1:
                raise MetadataWriteError("PDF missing trailer")
        dict_start = self.pdf_data.find(b'<<', trailer_pos)
        if dict_start == -1:
            raise MetadataWriteError("Malformed trailer dictionary")
        dict_end = self._find_matching_brackets(dict_start)
        self.trailer_dict = self.pdf_data[dict_start:dict_end]

        size_match = re.search(rb'/Size\s+(\d+)', self.trailer_dict)
        root_match = re.search(rb'/Root\s+(\d+)\s+\d+\s+R', self.trailer_dict)
        if not size_match or not root_match:
            raise MetadataWriteError("Trailer missing Size or Root entries")

        self.original_size = int(size_match.group(1))
        self.size = self.original_size
        self.root_obj = int(root_match.group(1))

        info_match = re.search(rb'/Info\s+(\d+)\s+\d+\s+R', self.trailer_dict)
        if info_match:
            self.info_obj = int(info_match.group(1))

    def _find_matching_brackets(self, start_index: int) -> int:
        depth = 0
        i = start_index
        data = self.pdf_data
        length = len(data)
        while i < length - 1:
            token = data[i:i+2]
            if token == b'<<':
                depth += 1
                i += 2
                continue
            if token == b'>>':
                depth -= 1
                i += 2
                if depth == 0:
                    return i
                continue
            i += 1
        raise MetadataWriteError("Unbalanced PDF dictionary brackets")

    def _extract_object_dictionary(self, obj_number: int) -> Tuple[int, int, bytes]:
        pattern = f"{obj_number} 0 obj".encode('ascii')
        start = self.pdf_data.find(pattern)
        if start == -1:
            raise MetadataWriteError(f"Object {obj_number} not found")
        dict_start = self.pdf_data.find(b'<<', start)
        if dict_start == -1:
            raise MetadataWriteError(f"Object {obj_number} missing dictionary")
        dict_end = self._find_matching_brackets(dict_start)
        return dict_start, dict_end, self.pdf_data[dict_start:dict_end]

    def allocate_object(self) -> int:
        obj_number = self.size
        self.size += 1
        return obj_number

    def add_object(self, obj_number: int, content: bytes) -> None:
        if not content.endswith(b'\n'):
            content += b'\n'
        self.new_objects[obj_number] = content

    def add_metadata_stream(self, xmp_bytes: bytes) -> bytes:
        if self.root_obj is None:
            raise MetadataWriteError("Cannot append metadata without root object")

        metadata_obj = self.allocate_object()
        metadata_stream = (
            b'<<\n'
            b'/Type /Metadata\n'
            b'/Subtype /XML\n'
            b'/Length %d\n'
            b'>>\n'
            b'stream\n' % len(xmp_bytes)
        )
        metadata_stream += xmp_bytes
        if not xmp_bytes.endswith(b'\n'):
            metadata_stream += b'\n'
        metadata_stream += b'endstream\n'
        self.add_object(metadata_obj, metadata_stream)

        dict_start, dict_end, root_dict = self._extract_object_dictionary(self.root_obj)
        cleaned = re.sub(rb'/Metadata\s+\d+\s+\d+\s+R', b'', root_dict)
        cleaned = cleaned.rstrip()
        if not cleaned.endswith(b'>>'):
            raise MetadataWriteError("Root dictionary malformed")
        new_entry = f'\n/Metadata {metadata_obj} 0 R\n'.encode('ascii')
        updated_root = cleaned[:-2] + new_entry + b'>>\n'
        self.add_object(self.root_obj, updated_root)

        return self._build_new_pdf()

    def add_info_dictionary(self, info_dict: bytes) -> bytes:
        info_obj = self.allocate_object()
        self.add_object(info_obj, info_dict)
        self.info_override = info_obj
        return self._build_new_pdf()

    def _build_new_pdf(self) -> bytes:
        if not self.new_objects:
            return self.pdf_data

        appended = bytearray()
        offsets: Dict[int, int] = {}
        base_len = len(self.pdf_data)

        for obj_number in sorted(self.new_objects.keys()):
            offsets[obj_number] = base_len + len(appended)
            appended.extend(b'\n')
            appended.extend(f'{obj_number} 0 obj\n'.encode('ascii'))
            appended.extend(self.new_objects[obj_number])
            appended.extend(b'endobj\n')

        xref_offset = base_len + len(appended)
        xref = bytearray()
        xref.extend(b'xref\n')

        sorted_objs = sorted(offsets.keys())
        sections: List[Tuple[int, List[int]]] = []
        if sorted_objs:
            start = sorted_objs[0]
            current = [start]
            last = start
            for obj in sorted_objs[1:]:
                if obj == last + 1:
                    current.append(obj)
                else:
                    sections.append((start, current.copy()))
                    start = obj
                    current = [obj]
                last = obj
            sections.append((start, current.copy()))

        for start, objs in sections:
            xref.extend(f'{start} {len(objs)}\n'.encode('ascii'))
            for obj in objs:
                offset = offsets[obj]
                # Support huge offsets (> 9.9GB) by using extended format
                # Standard PDF xref format uses 10 digits (max 9,999,999,999)
                # For huge offsets, we need to use cross-reference streams or extended format
                if offset > 9999999999:
                    # Use extended format with more digits (up to 20 digits for very large files)
                    xref.extend(f'{offset:020d} 00000 n \n'.encode('ascii'))
                else:
                    xref.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))

        trailer_body = self.trailer_dict[2:-2]
        trailer_body = re.sub(rb'/Size\s+\d+', b'', trailer_body)
        trailer_body = re.sub(rb'/Root\s+\d+\s+\d+\s+R', b'', trailer_body)
        trailer_body = re.sub(rb'/Info\s+\d+\s+\d+\s+R', b'', trailer_body)
        trailer_body = re.sub(rb'/Prev\s+\d+', b'', trailer_body)

        entries = []
        if trailer_body.strip():
            entries.append(trailer_body.strip())
        new_size = max(self.size, self.original_size or self.size)
        entries.append(f'/Size {new_size}'.encode('ascii'))
        if self.root_obj is not None:
            entries.append(f'/Root {self.root_obj} 0 R'.encode('ascii'))
        if self.prev_startxref is not None:
            entries.append(f'/Prev {self.prev_startxref}'.encode('ascii'))
        info_target = self.info_override if self.info_override is not None else self.info_obj
        if info_target is not None:
            entries.append(f'/Info {info_target} 0 R'.encode('ascii'))

        trailer_dict = b'<<\n' + b'\n'.join(entries) + b'\n>>\n'
        trailer = b'trailer\n' + trailer_dict
        startxref_block = b'startxref\n' + f'{xref_offset}'.encode('ascii') + b'\n%%EOF\n'

        return self.pdf_data + bytes(appended) + bytes(xref) + trailer + startxref_block

