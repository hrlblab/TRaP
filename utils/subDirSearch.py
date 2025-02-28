import os


def sub_dir_search(subdirectories, string1=None, string2=None):
    """
    Searches through a list of subdirectories for directories that contain a specific substring
    and/or end with a specific string.

    Parameters:
    subdirectories : list of str
        List of subdirectories to search through.
    string1 : str, optional
        Substring that should be contained in the directory names.
    string2 : str, optional
        String with which the directory names should end.

    Returns:
    list of str
        List of subdirectories that meet the criteria.
    """
    target_folders = []

    # Loop through each subdirectory
    for subdirectory in subdirectories:
        match_string1 = True
        match_string2 = True

        # Check if string1 is provided and if the subdirectory contains string1
        if string1 and string1 not in subdirectory:
            match_string1 = False

        # Check if string2 is provided and if the subdirectory ends with string2
        if string2 and not subdirectory.endswith(string2):
            match_string2 = False

        # If both conditions are met, add the subdirectory to target folders
        if match_string1 and match_string2:
            target_folders.append(subdirectory)

    return target_folders