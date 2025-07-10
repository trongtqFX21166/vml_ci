#!/usr/bin/env python3
import os
import sys

def convert_line_endings(file_path):
    """Convert Windows line endings (CRLF) to Unix line endings (LF)."""
    print(f"Converting line endings for {file_path}")
    
    try:
        # Read the file with Windows line endings
        with open(file_path, 'rb') as file:
            content = file.read()
        
        # Replace CRLF with LF
        content = content.replace(b'\r\n', b'\n')
        
        # Write the file with Unix line endings
        with open(file_path, 'wb') as file:
            file.write(content)
        
        print(f"Successfully converted line endings for {file_path}")
        return True
    except Exception as e:
        print(f"Error converting line endings: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python fix_line_endings.py <path_to_build_sh>")
        sys.exit(1)
    
    build_sh_path = sys.argv[1]
    
    if not os.path.exists(build_sh_path):
        print(f"Error: File {build_sh_path} does not exist")
        sys.exit(1)
    
    if convert_line_endings(build_sh_path):
        print("Line endings conversion completed successfully")
        # Make the file executable
        os.chmod(build_sh_path, 0o755)
        print(f"Made {build_sh_path} executable")
    else:
        print("Line endings conversion failed")
        sys.exit(1)

if __name__ == "__main__":
    main()