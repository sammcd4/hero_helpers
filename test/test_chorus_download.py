#!/usr/bin/env python

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chorus_download import find_duplicates_of_sng_in_library, remove_duplicates


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "files")
SONG_LIBRARY = os.path.join(FIXTURES_DIR, "SongLibrary")
OUTSIDE_ARTIST_DIR = os.path.join(FIXTURES_DIR, "TestArtist")


class TestFindDuplicatesOfSngInLibrary(unittest.TestCase):
    """Real-filesystem tests against test/files/SongLibrary fixtures."""

    def setUp(self):
        self.directories = [SONG_LIBRARY]

    def test_exact_sng_file_match_in_playlist(self):
        # Library contains "Existing Playlist/TestArtist - TestSong 1 (TestCharter).sng".
        # Query is the same name from an unrelated directory so the exact-path skip doesn't fire.
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 1 (TestCharter).sng")
        self.assertTrue(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_exact_sng_file_match_in_chorus_subfolder(self):
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 2 (TestCharter).sng")
        self.assertTrue(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_folder_with_song_ini_match(self):
        # Library has "Existing Playlist/TestArtist - TestSong 3/song.ini" (no .sng file).
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 3 (TestCharter).sng")
        self.assertTrue(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_no_duplicate_found(self):
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 4 (TestCharter).sng")
        self.assertFalse(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_same_filepath_is_skipped(self):
        # When the query path is itself inside the library, the function should not flag itself as a duplicate.
        in_library = os.path.join(SONG_LIBRARY, "Existing Playlist", "TestArtist - TestSong 1 (TestCharter).sng")
        self.assertFalse(find_duplicates_of_sng_in_library(in_library, self.directories, {}))

    def test_unparseable_filename_returns_false(self):
        query = os.path.join(OUTSIDE_ARTIST_DIR, "not a real song name.sng")
        self.assertFalse(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_numbered_suffix_matches_via_folder_fallback(self):
        # "Artist - Song (Charter) (1).sng" still matches when the library has a folder + song.ini
        # for the same song (TestSong 3), because the folder-name + ini comparison ignores the (N) suffix.
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 3 (TestCharter) (1).sng")
        self.assertTrue(find_duplicates_of_sng_in_library(query, self.directories, {}))

    def test_numbered_suffix_misses_plain_sng_library_copy(self):
        # Known limitation: when the library copy is a plain ".sng" file (no folder/ini fallback),
        # a "(1).sng" query won't match because the exact-filename lookup includes the suffix.
        # Captured as a test so the day this is fixed, the assertion can be flipped.
        query = os.path.join(OUTSIDE_ARTIST_DIR, "TestArtist - TestSong 1 (TestCharter) (1).sng")
        self.assertFalse(find_duplicates_of_sng_in_library(query, self.directories, {}))


class TestRemoveDuplicatesEmptyDirectory(unittest.TestCase):
    """Covers the empty-folder log path added to remove_duplicates."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_directory_logs_and_returns(self):
        with self.assertLogs("chorus_download", level="INFO") as cm:
            remove_duplicates(self.tmpdir, [SONG_LIBRARY], {})
        self.assertTrue(
            any("No files to check" in msg for msg in cm.output),
            f"Expected an empty-folder log message; got: {cm.output}",
        )


if __name__ == "__main__":
    unittest.main()
