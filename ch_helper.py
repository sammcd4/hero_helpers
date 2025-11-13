#!/usr/bin/env python3

import os
import argparse
import json
import stat
import re

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
            dirpath = os.path.dirname(file_path)
            # ensure directory writable (rename needs directory write permission)
            try:
                if not os.access(dirpath, os.W_OK):
                    st = os.stat(dirpath)
                    os.chmod(dirpath, st.st_mode | stat.S_IWUSR)
            except PermissionError:
                print(f"Cannot make directory writable: {dirpath} (need sudo)")
                raise
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

def archive_charts_with_language(chart_dirs):
    """Rename notes.chart -> notes.chart.bak.lang for each directory in chart_dirs."""
    for dir_path in chart_dirs:
        notes = os.path.join(dir_path, "notes.chart")
        bak = notes + ".bak.lang"
        if os.path.exists(notes):
            # ensure directory writable (rename needs directory write permission)
            try:
                if not os.access(dir_path, os.W_OK):
                    st = os.stat(dir_path)
                    os.chmod(dir_path, st.st_mode | stat.S_IWUSR)
            except PermissionError:
                print(f"Cannot make directory writable: {dir_path} (need sudo)")
                raise
            if not os.path.exists(bak):
                os.rename(notes, bak)
                print(f"Archived chart: {notes} -> {bak}")
            else:
                print(f"Already archived: {bak}")
        else:
            if os.path.exists(bak):
                print(f"Already archived (original missing): {bak}")
            else:
                print(f"No notes.chart found in: {dir_path}")

def unarchive_charts_with_language(chart_dirs):
    """Restore notes.chart.bak.lang -> notes.chart for each directory in chart_dirs."""
    for dir_path in chart_dirs:
        notes = os.path.join(dir_path, "notes.chart")
        bak = notes + ".bak.lang"
        if os.path.exists(bak):
            # ensure directory writable (rename needs directory write permission)
            try:
                if not os.access(dir_path, os.W_OK):
                    st = os.stat(dir_path)
                    os.chmod(dir_path, st.st_mode | stat.S_IWUSR)
            except PermissionError:
                print(f"Cannot make directory writable: {dir_path} (need sudo)")
                raise
            if not os.path.exists(notes):
                os.rename(bak, notes)
                print(f"Restored chart: {bak} -> {notes}")
            else:
                print(f"Original already exists, skipping restore: {notes}")
        else:
            print(f"No archived chart to restore in: {dir_path}")

def detect_explicit_charts(search_dirs, explicit_words):
    """Scan search_dirs for notes.chart files containing any explicit_words.
    Adds matching song folder paths to the config's charts_with_language list."""
    if not explicit_words:
        print("No explicit words configured; nothing to do.")
        return

    # build regex for whole-word matching (case-insensitive)
    escaped = [re.escape(w) for w in explicit_words if w.strip()]
    pattern = re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)

    matches = set()
    for parent_dir in search_dirs:
        for root, dirs, files in os.walk(parent_dir):
            if "notes.chart" in files:
                notes_path = os.path.join(root, "notes.chart")
                try:
                    with open(notes_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    continue
                if pattern.search(content):
                    print(f"Explicit language found in: {notes_path}")
                    matches.add(root)

    if not matches:
        print("No explicit charts found.")
        return

    # update config file: merge matches into charts_with_language
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Failed to read config: {e}")
        return

    existing = set(config.get("charts_with_language", []))
    new_set = existing.union(sorted(matches))
    if new_set != existing:
        config["charts_with_language"] = sorted(new_set)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            print(f"Updated {CONFIG_FILE}: added {len(new_set - existing)} explicit chart folders.")
        except Exception as e:
            print(f"Failed to write config: {e}")
    else:
        print("No new explicit chart folders to add.")

def main():
    parser = argparse.ArgumentParser(description="Archive/unarchive album artwork files.")
    parser.add_argument("-aa", "--archive-album-artwork", action="store_true", help="Archive album artwork files")
    parser.add_argument("-ua", "--unarchive-album-artwork", action="store_true", help="Restore archived album artwork files")
    parser.add_argument("-s", "--album-artwork-search", action="store_true", help="Recursively search configured song directories for matching album artwork")
    parser.add_argument("-al", "--archive-charts-lang", action="store_true", help="Rename notes.chart -> notes.chart.bak.lang for charts_with_language entries")
    parser.add_argument("-ul", "--unarchive-charts-lang", action="store_true", help="Restore notes.chart.bak.lang -> notes.chart for charts_with_language entries")
    parser.add_argument("-e", "--detect-explicit", action="store_true", help="Scan song_directories for notes.chart files with explicit language and add them to charts_with_language")
    args = parser.parse_args()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        file_list = config.get("album_artwork_files", [])
        song_dirs = config.get("song_directories", [])
        charts_with_language = config.get("charts_with_language", [])
        explicit_words = config.get("explicit_language", [])

    if args.archive_album_artwork:
        archive_files(file_list)
    elif args.unarchive_album_artwork:
        unarchive_files(file_list)
    elif args.album_artwork_search:
        album_artwork_search(file_list, song_dirs)
    elif args.detect_explicit:
        detect_explicit_charts(song_dirs, explicit_words)
    elif args.archive_charts_lang:
        archive_charts_with_language(charts_with_language)
    elif args.unarchive_charts_lang:
        unarchive_charts_with_language(charts_with_language)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()