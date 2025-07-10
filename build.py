#!/usr/bin/env python3
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Constants
REGISTRY_URL = "vmapi/vml-s2"  # Changed from hubcentral to vml-s2

def run_command(cmd: List[str], cwd: str = None) -> Tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    

def remove_bom_and_read_json(file_path: str) -> dict:
    """Read JSON file and handle UTF-8 BOM if present."""
    try:
        # First try with utf-8-sig encoding
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to read JSON file {file_path}: {e}")
        raise  

def load_config(config_path: str) -> List[Dict[str, Any]]:
    """Load configuration from JSON file."""
    try:
        return remove_bom_and_read_json(config_path)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}")
        print(f"JSON Error position: Line {e.lineno}, Column {e.colno}, Position {e.pos}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to read config file: {e}")
        sys.exit(1)

def save_config(config_path: str, config: List[Dict[str, Any]]) -> None:
    """Save configuration to JSON file."""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Failed to update config file: {e}")
        sys.exit(1)

def get_app_version(app_setting_path: str) -> Optional[str]:
    """Get application version from appsettings.json."""
    try:
        app_config = remove_bom_and_read_json(app_setting_path)
        return app_config.get("Deployment", {}).get("Version")
    except Exception as e:
        print(f"Failed to read app config: {e}")
        return None

def fix_line_endings(file_path: str) -> bool:
    """Fix line endings for shell scripts to ensure Unix compatibility."""
    try:
        print(f"Fixing line endings for {file_path}")
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Replace CRLF with LF
        content = content.replace(b'\r\n', b'\n')
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Make executable
        os.chmod(file_path, 0o755)
        print(f"Fixed line endings and made executable: {file_path}")
        return True
    except Exception as e:
        print(f"Failed to fix line endings: {e}")
        return False

def build(path: str, image_tag: str, version: str, build_mode: str) -> bool:
    """Build VML API and create Docker image."""
    original_cwd = os.getcwd()
    try:
        os.chdir(path)
        print(f"Building VML API at {os.getcwd()}")
        
        # Check if build.sh exists
        build_script = "build.sh"
        if not os.path.exists(build_script):
            print(f"Error: {build_script} not found in {path}")
            return False
        
        # Fix line endings for the build script
        if not fix_line_endings(build_script):
            print(f"Failed to fix line endings for {build_script}")
            return False
        
        # Run build.sh with parameters
        print(f"Running build script with parameters: {image_tag} {version} {build_mode}")
        
        success = False
        output = ""
        
        # Check if we're on Windows and use bash/sh accordingly
        if os.name == 'nt':  # Windows
            # Try different ways to run bash script on Windows
            bash_commands = [
                ['bash', 'build.sh', image_tag, version, build_mode],
                ['sh', 'build.sh', image_tag, version, build_mode],
                ['wsl', 'bash', 'build.sh', image_tag, version, build_mode]
            ]
            
            for cmd in bash_commands:
                try:
                    print(f"Trying command: {' '.join(cmd)}")
                    success, output = run_command(cmd)
                    if success:
                        break
                except Exception as e:
                    print(f"Command failed: {e}")
                    continue
            
            # If bash commands failed, try to run the build process directly with Python
            if not success:
                print("Bash commands failed, trying direct build process...")
                success = build_directly(image_tag, version, build_mode)
                if success:
                    output = "Direct build completed successfully"
        else:
            # Unix-like system
            cmd = ['./build.sh', image_tag, version, build_mode]
            success, output = run_command(cmd)
        
        if not success:
            print(f"Build script failed: {output}")
            return False
        
        print(f"Build output: {output}")
        print(f"Successfully built {image_tag}:{version}")
        return True
        
    except Exception as e:
        print(f"Build failed with exception: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def build_directly(image_tag: str, version: str, build_mode: str) -> bool:
    """Direct build process for Windows without bash."""
    try:
        # Find project file
        project_files = [f for f in os.listdir('.') if f.endswith('.csproj')]
        if not project_files:
            print("Error: No .csproj file found in the directory")
            return False
        
        project_file = project_files[0]
        project_name = os.path.splitext(project_file)[0]
        print(f"Project file: {project_file}, Project name: {project_name}")
        
        # Create release folders
        release_folder = f"bin/release/{project_name}"
        release_app_folder = f"{release_folder}/app"
        
        # Remove existing release folder if it exists
        if os.path.exists(release_folder):
            print(f"Removing existing release folder: {release_folder}")
            import shutil
            shutil.rmtree(release_folder)
        
        # Create release folders
        os.makedirs(release_app_folder, exist_ok=True)
        
        # Run dotnet publish
        print("Running dotnet publish...")
        dotnet_cmd = ['dotnet', 'publish', project_file, '-c', 'release', '-o', f'./{release_app_folder}']
        success, output = run_command(dotnet_cmd)
        
        if not success:
            print(f"Dotnet publish failed: {output}")
            return False
        
        # Check if build produced output
        if not os.path.exists(release_app_folder) or not os.listdir(release_app_folder):
            print(f"Build completed but no output found in {release_app_folder}")
            return False
        
        print("Build completed successfully")
        
        # In CI mode, skip Docker build
        if build_mode.upper() == "CI":
            print(f"CI mode - skipping Docker build for {image_tag}")
            return True
        
        # Create Dockerfile
        print("Creating Dockerfile...")
        dockerfile_path = os.path.join(release_folder, "Dockerfile")
        dockerfile_content = f"""FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY /app ./
ENTRYPOINT ["dotnet", "{project_name}.dll"]"""
        
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        
        print(f"Created Dockerfile at {dockerfile_path}")
        
        # Convert image tag to lowercase for Docker
        lowercase_image_tag = image_tag.lower()
        
        # Build Docker image
        print(f"Building Docker image {lowercase_image_tag}.{version}...")
        docker_build_cmd = ['docker', 'build', '-f', dockerfile_path, '-t', f'{lowercase_image_tag}.{version}', f'{release_folder}/.']
        success, output = run_command(docker_build_cmd)
        
        if not success:
            print(f"Docker build failed: {output}")
            return False
        
        # Tag Docker image
        docker_tag_cmd = ['docker', 'tag', f'{lowercase_image_tag}.{version}', f'{REGISTRY_URL}:{lowercase_image_tag}.{version}']
        success, output = run_command(docker_tag_cmd)
        
        if not success:
            print(f"Docker tag failed: {output}")
            return False
        
        # Push Docker image
        docker_push_cmd = ['docker', 'push', f'{REGISTRY_URL}:{lowercase_image_tag}.{version}']
        success, output = run_command(docker_push_cmd)
        
        if not success:
            print(f"Docker push failed: {output}")
            return False
        
        print(f"Successfully built and pushed {lowercase_image_tag}:{version}")
        return True
        
    except Exception as e:
        print(f"Direct build failed: {e}")
        return False

def update_yaml_files(env: str, yaml_files: List[str], image_tag: str, version: str) -> bool:
    """Update the image version in yaml files using yq."""
    for yaml_file in yaml_files:
        yaml_file = yaml_file.strip()
        
        # Try multiple possible locations for YAML files
        possible_paths = [
            Path(f"../vml_argocd/vml/{env.lower()}/base/{yaml_file}"),
            Path(f"modules/vml/{env.lower()}/base/{yaml_file}"),
            Path(f"vml_argocd/vml/{env.lower()}/base/{yaml_file}"),
            Path(f"../vml/{env.lower()}/base/{yaml_file}")
        ]
        
        yaml_path = None
        for path in possible_paths:
            if path.exists():
                yaml_path = path
                break
        
        if not yaml_path:
            print(f"Warning: YAML file {yaml_file} not found in any of these locations:")
            for path in possible_paths:
                print(f"  {path.absolute()}")
            continue
            
        # Format Docker image tag for VML
        # Format: {registry}/{image_tag}.{version}
        # Example: vmapi/vml-s2:vietmapcloud.vietmaplive.api.14.8.125
        image_value = f"{REGISTRY_URL}:{image_tag}.{version}"
        
        print(f"Updating {yaml_path} with image: {image_value}")
        
        # Update the deployment YAML file
        cmd = [
            "yq", "-i",
            f'.spec.template.spec.containers[0].image = "{image_value}"',
            str(yaml_path)
        ]
        
        success, output = run_command(cmd)
        if not success:
            print(f"Failed to update yaml file {yaml_file}: {output}")
            return False
            
    return True

def commit_changes(env: str, config: List[Dict[str, Any]]) -> bool:
    """Commit and push changes to Git."""
    commit_msg = " ".join([f"{item['app']}::{item.get('version', '1.0.0')}" for item in config])
    
    # Find the actual paths for git operations
    config_paths = []
    yaml_paths = []
    
    # Look for config file in possible locations
    possible_config_paths = [
        f"modules/vml/{env.lower()}/build.config.json",
        f"vml_ci/modules/vml/{env.lower()}/build.config.json"
    ]
    
    for config_path in possible_config_paths:
        if os.path.exists(config_path):
            config_paths.append(config_path)
    
    # Look for YAML files in possible locations
    possible_yaml_dirs = [
        f"../vml_argocd/vml/{env.lower()}/base/",
        f"vml_argocd/vml/{env.lower()}/base/",
        f"../vml/{env.lower()}/base/"
    ]
    
    for yaml_dir in possible_yaml_dirs:
        if os.path.exists(yaml_dir):
            yaml_paths.append(f"{yaml_dir}*.yaml")
    
    if not config_paths:
        print("Warning: No config file found to commit")
    
    if not yaml_paths:
        print("Warning: No YAML directory found to commit")
    
    # Build git commands
    git_commands = []
    
    # Add config files
    for config_path in config_paths:
        git_commands.append(['git', 'add', config_path])
    
    # Add YAML files
    for yaml_path in yaml_paths:
        git_commands.append(['git', 'add', yaml_path])
    
    # Commit and push
    git_commands.extend([
        ['git', 'commit', '-m', f"Update VML {env} deployments: {commit_msg}"],
        ['git', 'push']
    ])

    print(f"Git operations to perform:")
    for cmd in git_commands:
        print(f"  {' '.join(cmd)}")

    for cmd in git_commands:
        success, output = run_command(cmd)
        if not success:
            print(f"Git operation failed: {output}")
            # Don't fail the entire process for git issues, just warn
            print(f"Warning: Git command failed: {' '.join(cmd)}")
            continue
    
    return True

def filter_projects(config: List[Dict[str, Any]], projects: List[str]) -> List[Dict[str, Any]]:
    """Filter configuration to only include specified projects."""
    if not projects:
        return config  # Return all projects if none specified
    
    filtered_config = []
    for item in config:
        if item['app'] in projects:
            filtered_config.append(item)
    
    if not filtered_config:
        print(f"Warning: None of the specified projects {projects} found in configuration")
    
    return filtered_config

def main():
    """Main function to build and deploy the VML API."""
    # Check for required arguments
    if len(sys.argv) < 4:
        print("Usage: python build.py <ENV> <BUILD_MODE> <REPO> [PROJECT1 PROJECT2 ...]")
        sys.exit(1)

    env = sys.argv[1]  # dev, prod
    build_mode = sys.argv[2]  # CI, CICD
    repo = sys.argv[3]  # vml
    
    # Get optional project names to build (if any)
    projects_to_build = sys.argv[4:] if len(sys.argv) > 4 else []
    
    original_path = os.getcwd()
    print(f"Starting build process for {repo} in {env} environment with mode {build_mode}")
    if projects_to_build:
        print(f"Building specific projects: {', '.join(projects_to_build)}")
    else:
        print("Building all projects")
    print(f"Current directory: {original_path}")

    # Read configuration file - updated path for VML structure
    config_path = Path(f"modules/{repo}/{env.lower()}/build.config.json")
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path.absolute()}")
        sys.exit(1)
    
    config = load_config(str(config_path))
    print(f"Successfully loaded config with {len(config)} items")
    
    # Create a copy of the original config for all cases to avoid reference errors
    original_config = config.copy()
    
    # Filter projects if specific ones were requested
    if projects_to_build:
        config = filter_projects(config, projects_to_build)
        print(f"Filtered to {len(config)} projects to build")
    
    build_results = []
    built_projects = []
    
    # Process each item in configuration
    for index, item in enumerate(config):
        print("\n" + "#" * 80)
        print(f"Building item {index+1}: {item['app']}")
        
        # Extract configuration values
        path = item['path']
        old_version = item.get('version', '1.0.0')
        yaml_files = item['yaml'].split('|') if '|' in item['yaml'] else [item['yaml']]
        image_tag = item['app']
        
        # Find the original index in the full config for updating later
        original_index = None
        for i, orig_item in enumerate(original_config):
            if orig_item['app'] == item['app']:
                original_index = i
                break

        # Convert relative path to absolute
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(original_path, path))
        
        # Verify path exists
        if not os.path.isdir(path):
            print(f"Error: Path {path} does not exist")
            print(f"Current working directory: {original_path}")
            print(f"Relative path from config: {item['path']}")
            print(f"Computed absolute path: {path}")
            
            # Try to find the correct path
            possible_paths = [
                os.path.join(original_path, "vml", "be_auth_sso_service", "VietmapCloud.VietmapLive.Api"),
                os.path.join(original_path, "..", "vml", "be_auth_sso_service", "VietmapCloud.VietmapLive.Api"),
                os.path.join(original_path, "modules", "vml", "be_auth_sso_service", "VietmapCloud.VietmapLive.Api")
            ]
            
            print("Checking possible paths:")
            for possible_path in possible_paths:
                normalized_path = os.path.normpath(possible_path)
                exists = os.path.isdir(normalized_path)
                print(f"  {normalized_path}: {'EXISTS' if exists else 'NOT FOUND'}")
                if exists:
                    print(f"Found correct path: {normalized_path}")
                    path = normalized_path
                    break
            else:
                print("Could not find the project directory")
                continue

        # Get application version from appsettings
        app_setting_path = os.path.join(path, "appsettings.json")
        if env.lower() in ["staging", "dev"]:
            env_setting_path = os.path.join(path, f"appsettings.{env.title()}.json")
            if os.path.exists(env_setting_path):
                app_setting_path = env_setting_path

        print(f"Reading version from: {app_setting_path}")
        app_version = get_app_version(app_setting_path)
        if app_version is None:
            print(f"Warning: {image_tag} is missing deployment version config, using {old_version}")
            app_version = old_version
        else:
            print(f"Found application version: {app_version}")
            
        # Set new version
        version = str(app_version)
        
        # In CI mode, always build regardless of version change
        # In CICD mode, skip build if version hasn't changed
        if build_mode == "CICD" and old_version == version:
            print(f"Version {version} unchanged - skipping build for {image_tag}")
            build_results.append(True)
            continue
            
        print(f"Version changed from {old_version} to {version} - building {image_tag}")
        
        # Build the application
        if not build(path, image_tag, version, build_mode):
            print(f"Failed to build {image_tag}")
            build_results.append(False)
            continue
        
        # Return to original directory
        os.chdir(original_path)
        
        # In CI mode, skip updating YAML files and config
        if build_mode == "CI":
            print(f"CI mode - skipping YAML and config updates for {image_tag}")
            build_results.append(True)
            built_projects.append(image_tag)
            continue
        
        # Update YAML files with the new image tag (only in CICD mode)
        if not update_yaml_files(env, yaml_files, image_tag, version):
            print(f"Failed to update YAML files for {image_tag}")
            build_results.append(False)
            continue
        
        # Update configuration with new version and set readytodeploy = 1 after successful build (only in CICD mode)
        if original_index is not None:
            original_config[original_index]['version'] = version
            original_config[original_index]['readytodeploy'] = 1
            save_config(str(config_path), original_config)
            print(f"Set readytodeploy = 1 for {image_tag} version {version}")
        else:
            print(f"Warning: Could not find {image_tag} in original configuration, not updating version")
            
        print(f"Updated build.config.json with new version {version} for {image_tag}")
        
        # Commit changes (only in CICD mode)
        print("Committing changes to Git...")
        if not commit_changes(env, original_config):
            print("Failed to commit changes")
            build_results.append(False)
            continue
        
        build_results.append(True)
        built_projects.append(image_tag)
        print(f"Successfully processed {image_tag}")
        print("#" * 80)

    # Check if any build failed
    if False in build_results:
        print("One or more builds failed")
        sys.exit(1)
    
    if built_projects:
        print(f"\nSuccessfully built projects: {', '.join(built_projects)}")
    else:
        print("\nNo projects were built (no version changes or no matching projects found)")
        
    print("\nAll operations completed successfully")
    sys.exit(0)

if __name__ == "__main__":
    main()