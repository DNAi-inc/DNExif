# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Exception classes for DNExif

This module defines custom exceptions for the DNExif library.
All exceptions are part of the pure Python implementation.

Copyright 2025 DNAi inc.
"""


class DNExifError(Exception):
    """
    Base exception for all DNExif errors.
    
    All DNExif exceptions inherit from this class, allowing
    catch-all error handling for any DNExif-related errors.
    """
    def __init__(self, message: str = ""):
        """
        Initialize the exception with an optional error message.
        
        Args:
            message: Descriptive error message explaining what went wrong
        """
        self.message = message
        super().__init__(message)


class MetadataReadError(DNExifError):
    """
    Raised when metadata cannot be read from a file.
    
    This exception is raised when:
    - File format is invalid or corrupted
    - Metadata structure cannot be parsed
    - Required metadata blocks are missing
    - File permissions prevent reading
    """
    pass


class MetadataWriteError(DNExifError):
    """
    Raised when metadata cannot be written to a file.
    
    This exception is raised when:
    - File is opened in read-only mode
    - File format does not support metadata writing
    - Metadata structure cannot be modified
    - File permissions prevent writing
    - Disk space is insufficient
    """
    pass


class UnsupportedFormatError(DNExifError):
    """
    Raised when the file format is not supported.
    
    This exception is raised when:
    - File extension is not in the supported formats list
    - File signature does not match any known format
    - Format-specific parser is not implemented
    """
    pass


class InvalidTagError(DNExifError):
    """
    Raised when an invalid tag is specified.
    
    This exception is raised when:
    - Tag name format is incorrect (e.g., missing group prefix)
    - Tag does not exist for the given file format
    - Tag value type is incompatible with the tag definition
    - Tag cannot be written to the specified format
    """
    pass

