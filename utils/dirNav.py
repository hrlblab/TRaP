import os
import fnmatch

def dir_nav(file_type, name, extension=''):
    """
    Filters directory contents based on type, name substring, and file extension.

    Parameters:
        file_type (str): 'directory' to select only directories, otherwise selects files.
        name (str): Substring to match in the file or directory names.
        extension (str): File extension to match. Empty string matches all extensions.

    Returns:
        list of os.DirEntry: Filtered directory contents, similar to os.scandir() but filtered.
    """
    folder_contents = []
    with os.scandir('.') as entries:
        for entry in entries:
            if entry.is_dir() and file_type.lower() == 'directory':
                if fnmatch.fnmatch(entry.name.lower(), f'*{name.lower()}*'):
                    folder_contents.append(entry)
            elif not entry.is_dir() and file_type.lower() != 'directory':
                if fnmatch.fnmatch(entry.name, f'*{name}*{extension}'):
                    folder_contents.append(entry)

    return folder_contents