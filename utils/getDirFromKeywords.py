import os
import fnmatch


def get_dir_by_keywords(directory, keywords=None):
    """
    Recursively searches for directories that contain all specified keywords in their path.

    Parameters:
        directory (str): The root directory from which to start the search.
        keywords (list of str): Keywords to filter the directories. If None, all directories are returned.

    Returns:
        list of str: A list of directory paths that match the given keywords.
    """
    folders = []

    # Iterate through all items in the current directory
    for item in os.listdir(directory):
        folder_path = os.path.join(directory, item)

        # Check if the item is a directory and not a symbolic link
        if os.path.isdir(folder_path) and not os.path.islink(folder_path):
            # If no keywords provided, add all directories
            if keywords is None:
                folders.append(folder_path)
            else:
                # Check if all keywords are in the folder path
                if all(fnmatch.fnmatch(folder_path, '*' + keyword + '*') for keyword in keywords):
                    folders.append(folder_path)

            # Recursively search in subdirectories
            sub_folders = get_dir_by_keywords(folder_path, keywords)
            folders.extend(sub_folders)  # Add found subdirectories to the list

    return folders