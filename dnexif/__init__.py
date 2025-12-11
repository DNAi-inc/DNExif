# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
DNExif - A 100% Pure Python Metadata Manager

A powerful library for reading and writing metadata from image files.
This is a complete native Python implementation with NO dependencies on
external standard format executables or libraries.

Supports EXIF, IPTC, and XMP metadata standards.
All metadata parsing is done by directly reading binary file structures.

Copyright 2025 DNAi inc.
"""

__version__ = "0.1.3"
__author__ = "DNAi inc."

from dnexif.core import DNExif
from dnexif.exceptions import DNExifError, MetadataReadError, MetadataWriteError
from dnexif.metadata_normalizer import (
    PriorityConfig,
    choose_best_timestamps,
    unify_date_fields,
    resolve_priority,
    normalize_metadata,
    parse_date_string,
)
from dnexif.metadata_stripper import (
    PrivacyConfig,
    PrivacyPreset,
    strip_metadata,
    strip_by_groups,
    strip_by_tags,
    PIIDetector,
    get_stripped_count,
)
from dnexif.metadata_diff import (
    diff_metadata,
    diff_files,
    format_diff_result,
    DiffResult,
    MetadataDiff,
    DiffType,
)
from dnexif.image_hash_calculator import (
    calculate_image_data_hash,
    add_image_data_hash_to_metadata,
    ImageHashCalculator,
)
from dnexif.metadata_utils import (
    batch_read_metadata,
    batch_write_metadata,
    copy_metadata,
    filter_metadata_by_groups,
    merge_metadata,
    get_metadata_summary,
    has_metadata,
)

__all__ = [
    "DNExif",
    "DNExifError",
    "MetadataReadError",
    "MetadataWriteError",
    "PriorityConfig",
    "choose_best_timestamps",
    "unify_date_fields",
    "resolve_priority",
    "normalize_metadata",
    "parse_date_string",
    "PrivacyConfig",
    "PrivacyPreset",
    "strip_metadata",
    "strip_by_groups",
    "strip_by_tags",
    "PIIDetector",
    "get_stripped_count",
    "diff_metadata",
    "diff_files",
    "format_diff_result",
    "DiffResult",
    "MetadataDiff",
    "DiffType",
    "calculate_image_data_hash",
    "add_image_data_hash_to_metadata",
    "ImageHashCalculator",
    "batch_read_metadata",
    "batch_write_metadata",
    "copy_metadata",
    "filter_metadata_by_groups",
    "merge_metadata",
    "get_metadata_summary",
    "has_metadata",
]

