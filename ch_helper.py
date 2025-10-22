#!/usr/bin/env python3

import os
import argparse
import json
import stat

CONFIG_FILE = "ch_helper_config.json"

def get_album_from_ini(ini_path):
    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().lower().startswith("album ="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None

def album_artwork_search(file_list, search_dirs):
    # Step 1: Build set of albums from config
    album_to_paths = {}
    for album_img in file_list:
        song_ini = os.path.join(os.path.dirname(album_img), "song.ini")
        album = get_album_from_ini(song_ini)
        if album:
            album_to_paths.setdefault(album, set()).add(album_img)

    # Step 2: Recursively search for matching albums
    found_paths = set(file_list)
    for parent_dir in search_dirs:
        for root, dirs, files in os.walk(parent_dir):
            if "song.ini" in files:
                ini_path = os.path.join(root, "song.ini")
                album = get_album_from_ini(ini_path)
                if album and album in album_to_paths:
                    for ext in [".png", ".jpg"]:
                        album_img_path = os.path.join(root, f"album{ext}")
                        if os.path.exists(album_img_path) and album_img_path not in found_paths:
                            print(f"Found matching album artwork: {album_img_path} (album: {album})")
                            found_paths.add(album_img_path)

    # Step 3: Update config file if new paths were found
    if found_paths != set(file_list):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        config["album_artwork_files"] = sorted(found_paths)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Updated {CONFIG_FILE} with {len(found_paths)} album artwork files.")
    else:
        print("No new album artwork files found.")

def archive_files(file_list):
    for file_path in file_list:
        # Archive album image (png or jpg)
        bak_path = file_path + ".bak"
        bak_img_path = file_path + ".bak" + os.path.splitext(file_path)[1]
        if os.path.exists(file_path):
            if not os.access(file_path, os.W_OK):
                os.chmod(file_path, stat.S_IWUSR)
            if not os.path.exists(bak_path) and not os.path.exists(bak_img_path):
                os.rename(file_path, bak_path)
                print(f"Archived: {file_path} -> {bak_path}")
            else:
                print(f"Already archived: {bak_path} or {bak_img_path}")

        # Archive background image (png or jpg) in the same directory, if it exists
        for ext in [".png", ".jpg"]:
            background_path = os.path.join(os.path.dirname(file_path), f"background{ext}")
            background_bak_path = background_path + ".bak"
            background_bak_img_path = background_path + ".bak" + ext
            if os.path.exists(background_path):
                if not os.access(background_path, os.W_OK):
                    os.chmod(background_path, stat.S_IWUSR)
                if not os.path.exists(background_bak_path) and not os.path.exists(background_bak_img_path):
                    os.rename(background_path, background_bak_path)
                    print(f"Archived: {background_path} -> {background_bak_path}")
                else:
                    print(f"Already archived: {background_bak_path} or {background_bak_img_path}")

def unarchive_files(file_list):
    for file_path in file_list:
        # Unarchive album image (png or jpg)
        bak_path = file_path + ".bak"
        bak_img_path = file_path + ".bak" + os.path.splitext(file_path)[1]
        if os.path.exists(bak_path):
            if not os.access(bak_path, os.W_OK):
                os.chmod(bak_path, stat.S_IWUSR)
            if not os.path.exists(file_path):
                os.rename(bak_path, file_path)
                print(f"Restored: {bak_path} -> {file_path}")
            else:
                print(f"Original already exists, skipping restore: {file_path}")
        elif os.path.exists(bak_img_path):
            if not os.access(bak_img_path, os.W_OK):
                os.chmod(bak_img_path, stat.S_IWUSR)
            if not os.path.exists(file_path):
                os.rename(bak_img_path, file_path)
                print(f"Restored: {bak_img_path} -> {file_path}")
            else:
                print(f"Original already exists, skipping restore: {file_path}")
        else:
            print(f"No archive to restore: {bak_path} or {bak_img_path}")

        # Unarchive background image (png or jpg) in the same directory, if it exists
        for ext in [".png", ".jpg"]:
            background_path = os.path.join(os.path.dirname(file_path), f"background{ext}")
            background_bak_path = background_path + ".bak"
            background_bak_img_path = background_path + ".bak" + ext
            if os.path.exists(background_bak_path):
                if not os.access(background_bak_path, os.W_OK):
                    os.chmod(background_bak_path, stat.S_IWUSR)
                if not os.path.exists(background_path):
                    os.rename(background_bak_path, background_path)
                    print(f"Restored: {background_bak_path} -> {background_path}")
                else:
                    print(f"Original already exists, skipping restore: {background_path}")
            elif os.path.exists(background_bak_img_path):
                if not os.access(background_bak_img_path, os.W_OK):
                    os.chmod(background_bak_img_path, stat.S_IWUSR)
                if not os.path.exists(background_path):
                    os.rename(background_bak_img_path, background_path)
                    print(f"Restored: {background_bak_img_path} -> {background_path}")
                else:
                    print(f"Original already exists, skipping restore: {background_path}")

def main():
    parser = argparse.ArgumentParser(description="Archive/unarchive album artwork files.")
    parser.add_argument("--archive-album-artwork", action="store_true", help="Archive album artwork files")
    parser.add_argument("--unarchive-album-artwork", action="store_true", help="Restore archived album artwork files")
    parser.add_argument("--album-artwork-search", action="store_true", help="Recursively search configured song directories for matching album artwork")
    args = parser.parse_args()

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        file_list = config.get("album_artwork_files", [])
        song_dirs = config.get("song_directories", [])

    if args.archive_album_artwork:
        archive_files(file_list)
    elif args.unarchive_album_artwork:
        unarchive_files(file_list)
    elif args.album_artwork_search:
        album_artwork_search(file_list, song_dirs)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()