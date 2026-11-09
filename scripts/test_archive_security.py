#!/usr/bin/env python3
"""Hostile release fixtures; never extract or execute an application."""
import io
import plistlib
import stat
import unittest
from unittest.mock import patch
import zipfile

import publish


class ArchiveSecurityTests(unittest.TestCase):
    def validate(self, entries):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name, value, kind in entries:
                entry = zipfile.ZipInfo("SpaceTab.app/" + name)
                entry.create_system = 3
                entry.external_attr = (kind | 0o755) << 16
                archive.writestr(entry, value)
        data.seek(0)
        with zipfile.ZipFile(data) as archive:
            publish.validate_archive_paths(archive)

    def test_chained_links_cannot_escape_after_parent_components(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.validate([("Contents/x", "../foo", stat.S_IFLNK),
                           ("escape", "Contents/x/../../outside", stat.S_IFLNK)])

    def test_entries_cannot_be_written_through_links_in_either_order(self):
        entries = [("alias", "Contents", stat.S_IFLNK),
                   ("alias/payload", "harmless fixture", stat.S_IFREG)]
        for order in [entries, entries[::-1]]:
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "ancestor"):
                self.validate(order)

    def test_link_aliases_use_macos_case_and_unicode_equivalence(self):
        for original, alias in [("Contents", "CONTENTS"), ("caf\u00e9", "cafe\u0301")]:
            with self.subTest(original=original), self.assertRaises(ValueError):
                self.validate([(original, "target", stat.S_IFLNK),
                               (alias + "/payload", "fixture", stat.S_IFREG)])

    def test_cycles_absolute_targets_and_link_to_root_are_rejected(self):
        for entries in [[("a", "b", stat.S_IFLNK), ("b", "a", stat.S_IFLNK)],
                        [("a", "/tmp/fixture", stat.S_IFLNK)],
                        [("", "Contents", stat.S_IFLNK)]]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.validate(entries)

    def test_real_framework_layout_and_contained_parent_link_are_allowed(self):
        self.validate([("Contents/Frameworks/Sparkle.framework/Versions/Current", "B", stat.S_IFLNK),
                       ("Contents/Frameworks/Sparkle.framework/Sparkle", "Versions/Current/Sparkle", stat.S_IFLNK),
                       ("Contents/Frameworks/Sparkle.framework/Versions/B/Sparkle", "fixture", stat.S_IFREG),
                       ("Contents/parent", "../Resources", stat.S_IFLNK)])

    def test_noncanonical_duplicate_and_special_entries_are_rejected(self):
        for name in ["../outside", "Contents/../outside", "Contents/./file", "Contents//file", "Contents\\file"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate([(name, "fixture", stat.S_IFREG)])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.validate([("caf\u00e9", "first", stat.S_IFREG), ("cafe\u0301", "second", stat.S_IFREG)])
        with self.assertRaisesRegex(ValueError, "file type"):
            self.validate([("fifo", "", stat.S_IFIFO)])

    def test_parser_resource_limits_apply_before_extraction(self):
        for limit, value in [("MAX_ARCHIVE_ENTRIES", 0), ("MAX_EXPANDED_BYTES", 3),
                             ("MAX_FILE_BYTES", 3), ("MAX_LINK_BYTES", 3)]:
            with self.subTest(limit=limit), patch.object(publish, limit, value), self.assertRaises(ValueError):
                self.validate([("link", "Contents", stat.S_IFLNK)])

    def test_oversized_manifest_is_rejected_before_parsing(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("SpaceTab.app/Contents/Info.plist", b"not a property list")
        data.seek(0)
        with patch.object(publish, "MAX_PLIST_BYTES", 3), patch.object(plistlib, "loads") as parse:
            with self.assertRaisesRegex(ValueError, "manifest"):
                publish.validate(data, {})
            parse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
