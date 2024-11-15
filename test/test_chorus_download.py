#!/usr/bin/env python

import unittest
from unittest.mock import patch, mock_open
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from chorus_download import find_song_in_directories


class TestFindSongInDirectories(unittest.TestCase):
    def setUp(self):
        self.directories = [
            "test/files/SongLibrary"
        ]

    @patch('os.walk')
    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    @patch('configparser.ConfigParser.get')
    def test_exact_sng_file_match(self, mock_get, mock_read, mock_exists, mock_walk):
        # Mocking os.walk to return specific directory structure and files
        mock_walk.return_value = [
            ("test/files/SongLibrary/Existing Playlist", [], ["TestArtist - TestSong 1 (TestCharter).sng"]),
            ("test/files/SongLibrary/Chorus/TestArtist", [], ["TestArtist - TestSong 2 (TestCharter).sng"])
        ]

        # Exact match file
        song_name = "TestArtist - TestSong 1 (TestCharter).sng"
        
        result = find_song_in_directories(song_name, self.directories, {})
        self.assertTrue(result)  # Expecting True for exact match

    @patch('os.walk')
    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    @patch('configparser.ConfigParser.get')
    def test_folder_with_song_ini_match(self, mock_get, mock_read, mock_exists, mock_walk):
        # Mocking os.walk to simulate folders with song.ini files
        mock_walk.return_value = [
            ("test/files/SongLibrary/Existing Playlist", ["TestArtist - TestSong 3"], []),
        ]

        # Mock os.path.exists to simulate song.ini file presence
        mock_exists.side_effect = lambda path: path.endswith("song.ini")

        # Mock configparser to return specific song metadata
        mock_read.return_value = True
        mock_get.side_effect = lambda section, option, fallback=None: {
            "name": "TestSong 3",
            "artist": "TestArtist",
            "charter": "TestCharter"
        }.get(option, fallback)

        # Folder structure with matching song.ini file
        song_name = "TestArtist - TestSong 3 (TestCharter).sng"
        
        result = find_song_in_directories(song_name, self.directories, {})
        self.assertTrue(result)  # Expecting True for folder match with song.ini

    @patch('os.walk')
    def test_no_duplicate_found(self, mock_walk):
        # Mocking os.walk to simulate no duplicates found
        mock_walk.return_value = [
            ("test/files/SongLibrary/Existing Playlist", [], ["AnotherSong - AnotherArtist (AnotherCharter).sng"]),
        ]

        # File name not in directory
        song_name = "TestArtist - TestSong 4(TestCharter).sng"
        
        result = find_song_in_directories(song_name, self.directories, {})
        self.assertFalse(result)  # Expecting False as no duplicates exist

    @patch('os.walk')
    @patch('os.path.exists')
    @patch('configparser.ConfigParser.read')
    @patch('configparser.ConfigParser.get')
    def test_file_with_suffix_does_not_match(self, mock_get, mock_read, mock_exists, mock_walk):
        # Mocking os.walk to simulate files with suffixes
        mock_walk.return_value = [
            ("test/files/SongLibrary/Chorus/TestArtist", [], ["TestArtist - TestSong 2(TestCharter) copy.sng"])
        ]

        # Mock os.path.exists to return False for song.ini path
        mock_exists.return_value = False

        # Test file with suffix
        song_name = "TestArtist - TestSong 2(TestCharter).sng"
        
        result = find_song_in_directories(song_name, self.directories, {})
        self.assertFalse(result)  # Expecting False as copy file should not match

if __name__ == "__main__":
    unittest.main()
