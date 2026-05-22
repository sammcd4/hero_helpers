#!/usr/bin/env python

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chorus_download import find_duplicates_of_sng_in_library, remove_duplicates, move_sng_files


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "files")
SONG_LIBRARY = os.path.join(FIXTURES_DIR, "SongLibrary")
OUTSIDE_ARTIST_DIR = os.path.join(FIXTURES_DIR, "TestArtist")


def _write_file(path, size=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * size)


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


class TestRemoveDuplicatesDedup(unittest.TestCase):
    """Covers the destructive size/suffix dedup branches of remove_duplicates."""

    def setUp(self):
        self.downloads = tempfile.mkdtemp()
        self.empty_lib = tempfile.mkdtemp()  # so find_duplicates_of_sng_in_library always returns False

    def tearDown(self):
        shutil.rmtree(self.downloads, ignore_errors=True)
        shutil.rmtree(self.empty_lib, ignore_errors=True)

    def _path(self, name):
        return os.path.join(self.downloads, name)

    def test_larger_file_kept_smaller_removed(self):
        # Two files sharing a base name; the larger one wins regardless of the (N) suffix.
        plain = self._path("Artist - Song (Charter).sng")
        suffixed = self._path("Artist - Song (Charter) (1).sng")
        _write_file(plain, size=100)
        _write_file(suffixed, size=200)

        remove_duplicates(self.downloads, [self.empty_lib], {})

        self.assertTrue(os.path.exists(suffixed), "Larger file should be kept")
        self.assertFalse(os.path.exists(plain), "Smaller duplicate should be removed")

    def test_equal_size_prefers_unsuffixed(self):
        plain = self._path("Artist - Song (Charter).sng")
        suffixed = self._path("Artist - Song (Charter) (1).sng")
        _write_file(plain, size=100)
        _write_file(suffixed, size=100)

        remove_duplicates(self.downloads, [self.empty_lib], {})

        self.assertTrue(os.path.exists(plain), "Unsuffixed file should be kept on size tie")
        self.assertFalse(os.path.exists(suffixed), "Suffixed duplicate should be removed on size tie")

    def test_existing_in_library_is_removed(self):
        # SONG_LIBRARY already contains "TestArtist - TestSong 1 (TestCharter).sng".
        dup = self._path("TestArtist - TestSong 1 (TestCharter).sng")
        _write_file(dup, size=50)

        remove_duplicates(self.downloads, [SONG_LIBRARY], {})

        self.assertFalse(os.path.exists(dup), "Download already in library should be removed")

    def test_dry_run_keeps_library_duplicate(self):
        dup = self._path("TestArtist - TestSong 1 (TestCharter).sng")
        _write_file(dup, size=50)

        remove_duplicates(self.downloads, [SONG_LIBRARY], {}, dry_run=True)

        self.assertTrue(os.path.exists(dup), "dry_run must not delete library duplicates")

    def test_dry_run_keeps_size_duplicates(self):
        # dry_run must protect the size/suffix dedup branches too, not just the
        # library-removal branch: nothing should be deleted under dry_run.
        plain = self._path("Artist - Song (Charter).sng")
        suffixed = self._path("Artist - Song (Charter) (1).sng")
        _write_file(plain, size=100)
        _write_file(suffixed, size=200)

        remove_duplicates(self.downloads, [self.empty_lib], {}, dry_run=True)

        self.assertTrue(os.path.exists(plain), "dry_run must not delete size duplicates")
        self.assertTrue(os.path.exists(suffixed), "dry_run must not delete size duplicates")


class TestMoveSngFiles(unittest.TestCase):
    """Covers move_sng_files: normal move, abort-on-existing, same-path skip, non-.sng skip."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.src = os.path.join(self.root, "downloads")
        self.dest = os.path.join(self.root, "library")
        os.makedirs(self.src)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_moves_sng_to_dest(self):
        src_file = os.path.join(self.src, "song.sng")
        _write_file(src_file, size=10)

        move_sng_files(self.src, self.dest)

        self.assertFalse(os.path.exists(src_file), "Source file should be moved out")
        self.assertTrue(os.path.exists(os.path.join(self.dest, "song.sng")), "File should land in dest")

    def test_non_sng_files_are_ignored(self):
        other = os.path.join(self.src, "notes.txt")
        _write_file(other, size=10)

        move_sng_files(self.src, self.dest)

        self.assertTrue(os.path.exists(other), "Non-.sng files must be left untouched")

    def test_dest_exists_aborts_and_removes_source(self):
        os.makedirs(self.dest)
        dest_file = os.path.join(self.dest, "song.sng")
        src_file = os.path.join(self.src, "song.sng")
        _write_file(dest_file, size=999)   # pre-existing copy in the library
        _write_file(src_file, size=10)     # the download we are sorting

        with self.assertLogs("chorus_download", level="WARNING") as cm:
            move_sng_files(self.src, self.dest)

        self.assertFalse(os.path.exists(src_file), "Source should be removed when dest already exists")
        self.assertEqual(os.path.getsize(dest_file), 999, "Existing dest file must not be overwritten")
        self.assertTrue(
            any("Abort move" in msg for msg in cm.output),
            f"Expected an abort warning; got: {cm.output}",
        )

    def test_same_src_and_dest_is_skipped(self):
        src_file = os.path.join(self.src, "song.sng")
        _write_file(src_file, size=10)

        move_sng_files(self.src, self.src)

        self.assertTrue(os.path.exists(src_file), "File must remain when src and dest are the same dir")


if __name__ == "__main__":
    unittest.main()
