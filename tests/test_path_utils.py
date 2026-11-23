"""Unit tests for shared_drive_manager.core.path_utils module."""
import os

import pytest

from shared_drive_manager.core.path_utils import (
    format_bytes,
    normalize_path_for_hash,
    path_depth,
    path_hash,
)


class TestNormalizePathForHash:
    """Tests for normalize_path_for_hash()."""

    def test_normalizes_forward_slashes(self):
        """Forward slashes should be normalized to backslashes on Windows."""
        path = r"C:/Users/Test/file.txt"
        normalized = normalize_path_for_hash(path)
        # On Windows, normpath converts forward slashes to backslashes
        assert "\\" in normalized or "/" in normalized
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_normalizes_backslashes(self):
        """Backslashes should be preserved and normalized."""
        path = r"C:\Users\Test\file.txt"
        normalized = normalize_path_for_hash(path)
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_removes_trailing_slashes(self):
        """Trailing slashes should be removed."""
        path = r"C:\Users\Test\\"
        normalized = normalize_path_for_hash(path)
        assert not normalized.endswith(("\\", "/"))

    def test_normalizes_unc_paths(self):
        r"""UNC paths like \\server\share should be normalized correctly."""
        path = r"\\server\share\folder\file.txt"
        normalized = normalize_path_for_hash(path)
        # Should be normalized but still valid
        assert len(normalized) > 0
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_normalizes_mixed_separators(self):
        """Paths with mixed separators should be normalized."""
        path = r"C:/Users\Test/folder\file.txt"
        normalized = normalize_path_for_hash(path)
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_normalizes_case_on_windows(self):
        """Path case should be normalized (uppercase on Windows)."""
        path1 = r"C:\users\test\file.txt"
        path2 = r"C:\USERS\TEST\FILE.TXT"
        norm1 = normalize_path_for_hash(path1)
        norm2 = normalize_path_for_hash(path2)
        # On Windows, normcase makes them equal
        if os.name == "nt":
            assert norm1 == norm2

    def test_handles_dot_references(self):
        """Paths with . and .. should be resolved."""
        path = r"C:\Users\Test\folder\.\subfolder\..\file.txt"
        normalized = normalize_path_for_hash(path)
        assert ".." not in normalized
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_handles_empty_string(self):
        """Empty string should be handled gracefully."""
        path = ""
        normalized = normalize_path_for_hash(path)
        assert isinstance(normalized, str)
        assert normalized == os.path.normcase(os.path.normpath(path))

    def test_is_deterministic(self):
        """Same input should always produce same normalized output."""
        path = r"C:/Users\Test\folder\..\file.txt"
        norm1 = normalize_path_for_hash(path)
        norm2 = normalize_path_for_hash(path)
        assert norm1 == norm2


class TestPathHash:
    """Tests for path_hash()."""

    def test_generates_hash_string(self):
        """path_hash should return a non-empty string."""
        path = r"C:\Users\Test\file.txt"
        hash_result = path_hash(path)
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_hash_is_sha256_hex(self):
        """Hash should be SHA-256 hex string (64 characters)."""
        path = r"C:\Users\Test\file.txt"
        hash_result = path_hash(path)
        assert len(hash_result) == 64
        try:
            int(hash_result, 16)
        except ValueError:
            pytest.fail("Hash is not a valid hex string")

    def test_same_path_produces_same_hash(self):
        """Same path should always produce the same hash."""
        path = r"C:\Users\Test\file.txt"
        hash1 = path_hash(path)
        hash2 = path_hash(path)
        assert hash1 == hash2

    def test_normalized_equivalent_paths_produce_same_hash(self):
        """Paths that normalize to the same value should produce the same hash."""
        # On Windows, these normalize to the same thing
        path1 = r"C:\Users\Test\file.txt"
        path2 = r"C:/Users/Test/file.txt"
        hash1 = path_hash(path1)
        hash2 = path_hash(path2)
        assert hash1 == hash2

    def test_different_paths_produce_different_hashes(self):
        """Different paths should produce different hashes."""
        path1 = r"C:\Users\Test\file1.txt"
        path2 = r"C:\Users\Test\file2.txt"
        hash1 = path_hash(path1)
        hash2 = path_hash(path2)
        assert hash1 != hash2

    def test_case_insensitive_hash_equality_on_windows(self):
        """On Windows, case-different paths should hash to the same value."""
        if os.name == "nt":
            path1 = r"C:\users\test\file.txt"
            path2 = r"C:\USERS\TEST\FILE.TXT"
            hash1 = path_hash(path1)
            hash2 = path_hash(path2)
            assert hash1 == hash2

    def test_hash_unc_path(self):
        """UNC paths should be hashable."""
        path = r"\\server\share\folder\file.txt"
        hash_result = path_hash(path)
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)

    def test_hash_unicode_path(self):
        """Paths with unicode characters should be hashable."""
        path = r"C:\Users\Tëst\файл_文件.txt"
        hash_result = path_hash(path)
        assert len(hash_result) == 64
        # Same path should produce same hash
        assert path_hash(path) == hash_result

    def test_hash_with_dots_and_dashes(self):
        """Paths with special filename characters should hash correctly."""
        path = r"C:\Users\Test\my-file_v2.5.0-beta.txt"
        hash_result = path_hash(path)
        assert len(hash_result) == 64

    def test_hash_with_spaces(self):
        """Paths with spaces should hash correctly."""
        path = r"C:\Program Files\My App\my document.txt"
        hash_result = path_hash(path)
        assert len(hash_result) == 64


class TestPathDepth:
    """Tests for path_depth()."""

    def test_depth_simple_relative_path(self):
        """Simple relative paths should calculate depth correctly."""
        depth = path_depth(r"C:\Root\file.txt", r"C:\Root")
        assert depth == 1

    def test_depth_nested_path(self):
        """Nested paths should calculate depth correctly."""
        depth = path_depth(r"C:\Root\Level1\Level2\file.txt", r"C:\Root")
        assert depth == 3

    def test_depth_deep_nesting(self):
        """Deeply nested paths should calculate correct depth."""
        depth = path_depth(
            r"C:\Root\L1\L2\L3\L4\L5\file.txt", r"C:\Root"
        )
        assert depth == 6

    def test_depth_file_at_root(self):
        """File directly at root should have depth 1."""
        depth = path_depth(r"C:\Root\file.txt", r"C:\Root")
        assert depth == 1

    def test_depth_path_not_under_root(self):
        """Path not under root should calculate parts in full path."""
        # When path is not under root, returns full parts count
        depth = path_depth(r"D:\Other\file.txt", r"C:\Root")
        # Should return length of full path parts
        assert depth > 0

    def test_depth_with_trailing_slash(self):
        """Trailing slashes should not affect depth calculation."""
        depth1 = path_depth(r"C:\Root\Level1\file.txt", r"C:\Root")
        depth2 = path_depth(r"C:\Root\Level1\file.txt", r"C:\Root\\")
        assert depth1 == depth2

    def test_depth_handles_normalized_paths(self):
        """Normalized and non-normalized paths should calculate same depth."""
        depth1 = path_depth(r"C:\Root\Level1\file.txt", r"C:\Root")
        depth2 = path_depth(r"C:\Root/Level1\file.txt", r"C:/Root")
        assert depth1 == depth2

    def test_depth_unc_paths(self):
        """UNC paths should calculate depth correctly."""
        depth = path_depth(
            r"\\server\share\folder\file.txt", r"\\server\share"
        )
        assert depth > 0

    def test_depth_empty_string(self):
        """Empty string path should be handled."""
        depth = path_depth("", r"C:\Root")
        assert depth >= 0

    def test_depth_absolute_path(self):
        """Absolute paths should calculate depth correctly."""
        depth = path_depth(r"C:\Users\Admin\file.txt", r"C:\Users")
        assert depth == 2


class TestFormatBytes:
    """Tests for format_bytes()."""

    def test_format_bytes_zero(self):
        """Zero bytes should format as 0.0 B."""
        result = format_bytes(0)
        assert result == "0.0 B"

    def test_format_bytes_unit(self):
        """Bytes under 1024 should stay in B unit."""
        result = format_bytes(512)
        assert "B" in result
        assert "512" in result or "512.0" in result

    def test_format_kilobytes(self):
        """Bytes >= 1024 should format as KB."""
        result = format_bytes(1024)
        assert "KB" in result

    def test_format_megabytes(self):
        """Bytes >= 1024^2 should format as MB."""
        result = format_bytes(1024 * 1024)
        assert "MB" in result

    def test_format_gigabytes(self):
        """Bytes >= 1024^3 should format as GB."""
        result = format_bytes(1024 * 1024 * 1024)
        assert "GB" in result

    def test_format_terabytes(self):
        """Bytes >= 1024^4 should format as TB."""
        result = format_bytes(1024 * 1024 * 1024 * 1024)
        assert "TB" in result

    def test_format_petabytes(self):
        """Very large bytes should format as PB."""
        result = format_bytes(1024 * 1024 * 1024 * 1024 * 1024)
        assert "PB" in result

    def test_format_precision(self):
        """Result should include one decimal place."""
        result = format_bytes(1536)  # 1.5 KB
        assert "." in result  # Should have decimal point

    def test_format_negative_bytes(self):
        """Negative bytes should be handled gracefully."""
        # Function should still work (may produce negative values)
        result = format_bytes(-1024)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_large_numbers(self):
        """Very large numbers should format without error."""
        result = format_bytes(10**15)
        assert isinstance(result, str)
        assert len(result) > 0


class TestPathIntegration:
    """Integration tests combining multiple functions."""

    def test_same_path_different_format_same_hash(self):
        """Paths with different formatting should hash identically."""
        path1 = r"C:\Users\Test\file.txt"
        path2 = r"C:/Users/Test/file.txt"
        hash1 = path_hash(path1)
        hash2 = path_hash(path2)
        assert hash1 == hash2

    def test_normalize_and_hash_idempotent(self):
        """Normalizing then hashing should be idempotent."""
        path = r"C:\Users\Test\file.txt"
        normalized1 = normalize_path_for_hash(path)
        hash1 = path_hash(normalized1)
        hash2 = path_hash(path)
        assert hash1 == hash2

    def test_depth_calculation_with_deeply_nested_path(self):
        """Complex real-world path should calculate depth correctly."""
        full_path = r"C:\Users\CompanyShares\ProjectFolder\Archive\2024\Q1\January\Reports\Final\report.xlsx"
        root = r"C:\Users\CompanyShares"
        depth = path_depth(full_path, root)
        # Count parts: ProjectFolder, Archive, 2024, Q1, January, Reports, Final, report.xlsx = 8
        assert depth == 8
