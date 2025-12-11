# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
EXIF 3.0 specific tag definitions

This module contains tag definitions specific to EXIF 3.0 specification
(released May 2023). EXIF 3.0 introduces UTF-8 encoding support and new tags.

Copyright 2025 DNAi inc.
"""

# EXIF 3.0 specific tags
# These tags are new or enhanced in EXIF 3.0 specification

EXIF_3_0_TAG_NAMES = {
    # EXIF 3.0 introduces UTF-8 encoding support for text fields
    # The following tags benefit from UTF-8 encoding:
    
    # ImageUniqueID (0xA420) - Enhanced in EXIF 3.0
    # This tag stores a unique identifier for each image, compliant with ISO/IEC 9834-8
    0xA420: "ImageUniqueID",
    
    # EXIF 3.0 maintains backward compatibility with EXIF 2.3 tags
    # All existing tags remain valid, but text fields can now use UTF-8
    
    # Note: ExifVersion tag (0x9000) should be set to "0300" for EXIF 3.0
    # This enables UTF-8 encoding for all ASCII text fields
}

# Merge with existing EXIF tags
# This will be imported and merged in exif_tags.py

