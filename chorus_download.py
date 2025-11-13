#!/usr/bin/env python3

import os
import re
import time
import argparse
import json
import configparser
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)

# TODO Extend capability to folder song structure, not just .sng files as the file to keep
def find_duplicates_of_sng_in_library(song_filepath, directories, charter_verification):
    song_name = os.path.basename(song_filepath)

    # Extract artist, name, and charter from the .sng file name format "<Artist> - <Name> (<Charter>) (N).sng"
    match = re.match(r"(.+?) - (.+?) \((.+?)\)(?: \(\d+\))?\.sng", song_name)
    if not match:
        logger.debug(f'No regular expression match for {song_filepath}')
        return False  # If the filename doesn't match the expected format, return False

    artist, name, charter = match.groups()

    for directory in directories:
        for root, dirs, files in os.walk(directory):

            # Skip any files that are exactly the filepath being compared with
            found_exact_filepath = False
            for file in files:
                # Skip if the current file matches the input song filepath
                if os.path.abspath(os.path.join(root, file)) == os.path.abspath(song_filepath):
                    found_exact_filepath = True
            
            if found_exact_filepath:
                continue

            if song_name in files:
                # Check for exact matching .sng files
                logger.debug(f'Walking Directory: {directory}')
                logger.debug(f'For {song_name}')
                logger.debug('All files to search:')
                logger.debug(files)
                logger.info(f'Found exact duplicate {song_name}!')
                return True

            for dir_name in dirs:
                if f"{artist} - {name}".lower() in dir_name.lower(): # case-insensitive
                    song_ini_path = os.path.join(root, dir_name, "song.ini")
                    if os.path.exists(song_ini_path):
                        config = configparser.ConfigParser()
                        try:
                            # Check for 'song' section, regardless of case
                            config.read(song_ini_path)
                            song_section = None
                            for section in config.sections():
                                if section.lower() == 'song':
                                    song_section = section
                                    break
                            
                            ini_name = config.get(song_section, "name", fallback=None)
                            ini_artist = config.get(song_section, "artist", fallback=None)
                            ini_charter = config.get(song_section, "charter", fallback=None)

                            # Verify if ini_name and ini_artist match the expected song name and artist
                            if (
                                ini_name and ini_artist and ini_charter and
                                ini_name.lower() == name.lower() and
                                ini_artist.lower() == artist.lower() and
                                charter.lower() in ini_charter.lower()
                            ):
                                logger.info(f'Found duplicate song folder containing similar name: {ini_name}, artist: {ini_artist}, charter: {ini_charter}')
                                return True  # Duplicate found
                        except:
                            logger.debug(f"UnicodeDecodeError reading {song_ini_path}; Attempting additional charter verification methods...")
                            
                            # Attempt verification using charter_verification
                            charter_config = charter_verification.get(charter, {})
                            parent_dir_substring = charter_config.get("parent_dir_substring", "")

                            # Check if the directory name matches the expected substring for this charter
                            if parent_dir_substring and parent_dir_substring in os.path.join(root, dir_name):
                                logging.info(f"parent_dir_substring charter verification successful for {song_name} with charter {charter}.")
                                return True
                            else:
                                logging.debug(f'parent_dir_substring charter verification failed for {dir_name}')

                            # Check if the charter name exists in the directory (it should if properly named)
                            if charter in dir_name:
                                logging.info(f"charter in dir_name verification successful for {song_name} with charter {charter}.")
                                return True
                            else:
                                logging.error(f'Need to implement another alternate charter verification method for {dir_name}. {charter} not found!')

    return False

def remove_duplicates(directory, song_directories, charter_verification, dry_run=False):
    files_dict = {}

    for filename in os.listdir(directory):
        if filename.endswith(".sng"):
            # Get the base name by removing suffixes like (1), (2), etc.
            base_name = re.sub(r" \(\d+\)\.sng$", ".sng", filename)
            file_path = os.path.join(directory, filename)
            file_size = os.path.getsize(file_path)

            # Check if song already exists in song directories
            sng_filepath = os.path.join(directory, filename)
            if find_duplicates_of_sng_in_library(sng_filepath, song_directories, charter_verification):
                if not dry_run:
                    logger.info(f"{filename} already exists in song library. Removing from Downloads directory.")
                    os.remove(file_path)
                else: 
                    logger.info(f"DRY-RUN: {filename} already exists in song library. Removing from Downloads directory.")

                continue

            # If base name already exists, compare sizes and suffix
            if base_name in files_dict:
                existing_file_path, existing_file_size = files_dict[base_name]

                if file_size > existing_file_size:
                    # Keep the current file, remove the previously stored one
                    os.remove(existing_file_path)
                    files_dict[base_name] = (file_path, file_size)
                elif file_size == existing_file_size:
                    # If sizes are equal, prefer file without (N) suffix
                    if re.search(r" \(\d+\)\.sng$", filename):
                        os.remove(file_path)  # Remove current file with suffix
                    else:
                        os.remove(existing_file_path)  # Remove the old file with suffix
                        files_dict[base_name] = (file_path, file_size)
                else:
                    # Remove the current file since the existing one is larger
                    os.remove(file_path)
            else:
                # Store the file as the best version so far
                files_dict[base_name] = (file_path, file_size)

    logger.info("Duplicate removal complete. Largest files (without suffixes) kept.")

def move_sng_files(chorus_download_path, dest_song_directory):
    # Ensure destination directory exists
    os.makedirs(dest_song_directory, exist_ok=True)
    
    # Loop through all files in the base download path
    mv_count = 0
    aborted_count = 0
    for filename in os.listdir(chorus_download_path):
        if filename.endswith(".sng"):
            # Define full paths for the source and destination
            src_path = os.path.join(chorus_download_path, filename)
            dest_path = os.path.join(dest_song_directory, filename)

            if src_path == dest_path:
                logger.debug(f'Skipping mv of {src_path} TO {dest_path} because same file!')
                continue

            if os.path.exists(dest_path):
                logger.warning(f'Missed duplicate .sng file check. Abort move and removing {src_path}')
                os.remove(src_path)
                aborted_count = aborted_count + 1
                continue
            
            # Move the file
            shutil.move(src_path, dest_path)
            logger.info(f"Moved: {filename} to {dest_song_directory}")
            mv_count = mv_count + 1

    if aborted_count == 0:
        if mv_count > 0:
            logger.info("\nAll .sng files have been moved successfully.")
        else:
            logger.info("\nNo new songs found. None have been moved.")
    else:
        logger.warning(f'{mv_count} .sng files have been moved. {aborted_count} aborted to avoid overwriting existing files')

def main():

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Download .sng files from Enchor website.")
    parser.add_argument("--search_term", type=str, required=False, help="The search term to look for on the Enchor website.")
    parser.add_argument('--advanced_search', action='store_true', help="Flag to enable advanced search.")
    parser.add_argument('--name', type=str, help="Search by Name.")
    parser.add_argument('--artist', type=str, help="Search by Artist.")
    parser.add_argument('--album', type=str, help="Search by Album.")
    parser.add_argument('--genre', type=str, help="Filter by Genre.")
    parser.add_argument('--year', type=str, help="Filter by Year.")
    parser.add_argument('--check_duplicates', type=str, help="Folder to rescan for duplicates")
    parser.add_argument('--skip-download', action=argparse.BooleanOptionalAction)
    parser.add_argument('--dry-run', action=argparse.BooleanOptionalAction)

    # Define a helper function to append argument values
    def append_to_folder(folder, value):
        if folder:
            folder += "_"
        return folder + value

    # Parse arguments
    args = parser.parse_args()
    search_term = args.search_term  # Get the search term from the argument
    download_folder = ""
    dest_folder = ""

    # Configure download and destination folders based on arguments
    if search_term:
        download_folder = search_term
        dest_folder = search_term
    elif args.advanced_search:
        if args.name:
            download_folder = append_to_folder(download_folder, args.name)
        if args.artist:
            download_folder = append_to_folder(download_folder, args.artist)
            dest_folder = args.artist  # Set destination folder to artist name
        if args.album:
            download_folder = append_to_folder(download_folder, args.album)
        if args.genre:
            download_folder = append_to_folder(download_folder, args.genre)
        if args.year:
            download_folder = append_to_folder(download_folder, args.year)

    skip_download = args.skip_download
    dry_run = args.dry_run

    # Open the JSON file
    with open('chorus_config.json', 'r') as f:
        # Load the JSON data into a Python dictionary
        config = json.load(f)

    minor_sleep = config['minor_sleep_val']
    download_sleep = config['download_check_sleep_val']
    song_directories = config['song_directories']
    charter_verification = config.get("charter_verification", {})

    base_download_path = config['base_download_path']

    if args.check_duplicates:
        skip_download = True
        download_folder = args.check_duplicates
        dest_folder = args.check_duplicates
        base_download_path = os.path.join(song_directories[config['dest_song_directory_idx']], 'Chorus')

    dest_song_directory = os.path.join(song_directories[config['dest_song_directory_idx']], 'Chorus', dest_folder)

    # Configuration
    chorus_download_path = os.path.expanduser(os.path.join(base_download_path, download_folder))

    # Create download directory if it doesn't exist
    if not os.path.exists(chorus_download_path):
        os.makedirs(chorus_download_path)

    # Set Chrome options for automatic downloads
    chrome_options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": chorus_download_path, # Set download path
        "download.prompt_for_download": False,              # Skip download prompts
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True                        # Bypass safe browsing warnings
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialize WebDriver with Chrome options
    driver = webdriver.Chrome(options=chrome_options)



    # Helper function to locate and fill fields in advanced search
    def fill_search_field(driver, placeholder, value):
        field = driver.find_element(By.XPATH, f"//input[@placeholder='{placeholder}']")
        field.send_keys(value + Keys.RETURN)
        time.sleep(minor_sleep)  # Keep minor sleep if needed

    def perform_download():
        try:
            # Navigate to the website
            driver.get("https://www.enchor.us/")
            
            # Perform the search
            if args.search_term:
                search_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='What do you feel like playing today?']"))
                )
                search_box.send_keys(search_term + Keys.RETURN)
            elif args.advanced_search:
                # Locate the "Advanced Search" button and click it to open the dropdown
                advanced_search_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-ghost.uppercase")
                advanced_search_button.click()

                # Map arguments to placeholders for the search fields
                search_fields = {
                    "Name": args.name,
                    "Artist": args.artist,
                    "Album": args.album,
                    "Genre": args.genre,
                    "Year": args.year
                }

                # Fill each search field if the argument is provided
                for placeholder, value in search_fields.items():
                    if value:
                        fill_search_field(driver, placeholder, value)

                # Click the Search button in the dropdown for good measure
                advanced_search_search_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary.btn-sm.uppercase")
                advanced_search_search_button.click()

                # Click "Advanced Search" button again to close the dropdown
                advanced_search_button.click()

            # Wait for the initial set of results to load
            time.sleep(minor_sleep)

            # Function to scroll the page and load more results
            def scroll_page():
                # Get the current scroll position
                current_scroll_position = driver.execute_script("return window.scrollY;")
                
                # Scroll down by a fixed amount
                driver.execute_script("window.scrollBy(0, 1000);")
                
                # Wait for the page to load new content
                time.sleep(minor_sleep)
                
                # Return the new scroll position to check if we've reached the bottom
                new_scroll_position = driver.execute_script("return window.scrollY;")
                return current_scroll_position, new_scroll_position

            # Keep scrolling until we reach the bottom of the page
            while True:
                current_scroll_position, new_scroll_position = scroll_page()
                
                # If we've scrolled to the bottom of the page and no new results are loaded, break out
                if current_scroll_position == new_scroll_position:
                    logger.debug("Reached the bottom of the page, no more results.")
                    break

            # Locate all download buttons for .sng files in the search results
            download_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn btn-primary join-item px-4')]")
            
            logger.info(f"Found {len(download_buttons)} songs. Starting download...")

            # Flag to track if the .sng format has been selected already
            sng_selected = False

            # Iterate over each download button
            for index, button in enumerate(download_buttons, start=1):
                if not dry_run:
                    button.click()  # Click the download button to open the format selection dialog
                    logger.debug(f"Clicked download button for file {index}")
                else:
                    logger.debug(f"DRY-RUN: Clicked download button for file {index}")

                # If the .sng format hasn't been selected yet, select it
                if not sng_selected:
                    try:
                        # Wait for the .sng format radio button to appear and select it
                        sng_radio_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//label[.//span[text()='.sng (new)']]/input[@type='radio']"))
                        )
                        sng_radio_button.click()
                        logger.debug("Selected .sng file format.")
                        sng_selected = True  # Mark the format as selected
                        
                        # Click the "Download" button to start downloading the file
                        download_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@class='btn btn-primary' and text()='Download']"))
                        )
                        if not dry_run:
                            download_button.click()
                            logger.debug("Clicked Download button to start download.")
                        else:
                            logger.debug("DRY RUN: Clicked Download button to start download.")

                    except Exception as e:
                        logger.error(f"Error selecting .sng format: {e}")
                
                # Wait a bit to ensure download starts
                time.sleep(minor_sleep)  # Adjust based on download speed
            
            time.sleep(download_sleep)  # Ensure downloads complete before exiting

        finally:
            # Close the driver after completion
            driver.quit()

        logger.info(f"Downloads complete. Files saved in {chorus_download_path}")

    if not skip_download:
        perform_download()

    # Keep only unique files
    remove_duplicates(chorus_download_path, song_directories, charter_verification, dry_run)

    # only move files when initially downloading and not checking duplicates
    if not args.check_duplicates:
        move_sng_files(chorus_download_path, dest_song_directory)

    def remove_if_empty(dir_path):
        """Removes the directory if it is empty."""

        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            if not os.listdir(dir_path):  # Check if directory is empty
                os.rmdir(dir_path) 
                print(f"Directory '{dir_path}' removed.")
            else:
                print(f"Directory '{dir_path}' is not empty.")

    # Cleanup the download directory
    remove_if_empty(chorus_download_path)

    # High priority:
    # TODO Only log/print which newly moved songs were added rather than notifying of duplicates that were skipped
    # TODO Cleanup global variables and execute main
    # TODO Display percent complete of the downloading
    # TODO Display percent complete of duplicate song checking
    # TODO Ensure that artist name is actually searched before downloading a bunch of unmatched songs
    # TODO logging rather than print statements
    
    # Medium priority:
    # TODO Mv to another folder when Artist doesn't match exactly. Overall, handle all those cases
    # TODO (Believed to be fixed) Fix .sng duplicate file check because abort should not have to happen! Risk is there are hidden .sng duplicates other than in the Chorus directory!
    # TODO parallelize the download and sorting of songs into Clone Hero Extra folder (including duplication checking)
    # TODO Display name of downloaded song rather than number index
    # TODO Ensure that I don't default to only Expert files in case there are some with full difficulty that I should download instead.
    # TODO Add tests? not so necessary but could help while iterating and adding functionality.
    # TODO permission denied: /Volumes/Crucial X8 error handling
    # TODO Log that no files to check if folder empty
    # TODO Mechanism to provide priority to newly added packs outside of Chorus artist and remove duplicate Chorus artist downloaded .sng files
    # TODO General mechanism to search for and choose priority when duplicate sng identified
    # TODO Tests to run prior to test functionality of the website again (in case html has changed)
    # TODO print help
    # TODO configurable logging levels

    # Low priority:
    # TODO optional replacement of .sng files with folder structure (document reasons I would want to do this)
    
if __name__ == "__main__":
    main()