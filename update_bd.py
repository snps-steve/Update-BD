import os
import requests
import subprocess
import logging
import sys

# Configure logging
LOG_FILE = "/var/log/blackduck_update.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# GitHub repository information
REPO_URL = "https://api.github.com/repos/blackducksoftware/hub/releases/latest"
DOWNLOAD_DIR = "/opt"
SYMLINK_PATH = "/opt/current"
CURRENT_VERSION_FILE = "/opt/current_version.txt"
START_SCRIPT = "/opt/bin/docker_swarm_start.sh"
STOP_SCRIPT = "/opt/bin/docker_swarm_stop.sh"

def log(level, message):
    if level == 'INFO':
        logging.info(message)
    elif level == 'ERROR':
        logging.error(message)

def check_and_install_packages():
    '''Function to check for necessary packages and install them if missing.'''
    try:
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
    except ImportError:
        missing_packages = []
        try:
            import requests
        except ImportError:
            missing_packages.append('requests')

        try:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
        except ImportError:
            if 'requests' not in missing_packages:
                missing_packages.append('requests')

        if missing_packages:
            install = input(f"The following packages are missing: {missing_packages}. Do you want to install them? Yes/no (default is Yes): ").strip().lower()
            if install in ('', 'y', 'yes'):
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
                    import requests
                    from requests.packages.urllib3.exceptions import InsecureRequestWarning
                except subprocess.CalledProcessError as e:
                    logging.error(f"Failed to install packages: {e}")
                    sys.exit()
            elif install in ('n', 'no'):
                logging.info("Installation aborted by the user.")
                sys.exit()
            else:
                logging.info("Invalid input. Installation aborted.")
                sys.exit()

# Function to get the latest release information from GitHub
def get_latest_release():
    response = requests.get(REPO_URL)
    response.raise_for_status()
    return response.json()

# Function to clone the specified version of the Black Duck Hub repository
def clone_hub_repo(version):
    repo_name = f"hub-{version}"
    log('INFO', f"Cloning Black Duck Hub repository for version {version}.")
    try:
        subprocess.run(["git", "config", "--global", "advice.detachedHead", "false"], check=True)
        subprocess.run(["git", "clone", "--branch", f"v{version}", "https://github.com/blackducksoftware/hub.git", os.path.join(DOWNLOAD_DIR, repo_name)], check=True)
        log('INFO', f"Successfully cloned Black Duck Hub repository for version {version}.")
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to clone Black Duck Hub repository: {e}")
        sys.exit(1)

# Function to check if any hub containers are running
def check_hub_containers():
    try:
        result = subprocess.run(["docker", "ps", "--filter", "name=hub_", "--format", "{{.Names}}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to check for running hub containers: {e}")
        return False

# Function to stop Docker Swarm using the custom stop script and clean up old containers and networks
def stop_docker_swarm():
    try:
        if check_hub_containers():
            subprocess.run([STOP_SCRIPT], check=True)
            log('INFO', "Stopped existing Docker Swarm using custom script")
        else:
            log('INFO', "No running hub containers found. Skipping stop script.")

        # Remove old containers
        subprocess.run(["docker", "container", "prune", "-f"], check=True)
        log('INFO', "Removed old containers")

        # Remove old networks
        subprocess.run(["docker", "network", "prune", "-f"], check=True)
        log('INFO', "Removed old networks")
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to stop Docker Swarm or clean up: {e}")
        sys.exit(1)

# Function to start Docker Swarm using the custom start script
def start_docker_swarm(compose_dir):
    try:
        os.chdir(compose_dir)  # Change to the directory containing the Docker Compose files
        subprocess.run([START_SCRIPT], check=True)
        log('INFO', f"Started Docker Swarm with new version in {compose_dir} using custom script")
    except subprocess.CalledProcessError as e:
        log('ERROR', f"Failed to start Docker Swarm: {e}")
        sys.exit(1)

# Function to update the symlink
def update_symlink(new_version_dir):
    if os.path.islink(SYMLINK_PATH):
        os.unlink(SYMLINK_PATH)
    os.symlink(new_version_dir, SYMLINK_PATH)
    log('INFO', f"Updated symlink to point to {new_version_dir}")

def replace_services_section(lines):
    services_marker = "#services:\n"
    services_replacement = "services:\n"

    result_lines = []
    for line in lines:
        if line.lstrip() == services_marker:
            result_lines.append(services_replacement)
        else:
            result_lines.append(line)
    return result_lines

def replace_webserver_section(lines):
    webserver_start = "  #webserver:\n"
    webserver_secrets_marker = "    #secrets:\n"
    webserver_cert_marker = "    #  - HUB_PROXY_PASSWORD_FILE\n"
    webserver_key_marker1 = "    #  - WEBSERVER_CUSTOM_CERT_FILE\n"
    webserver_key_marker2 = "    #  - WEBSERVER_CUSTOM_KEY_FILE\n"

    webserver_replacement = [
        "  webserver:\n",
        "    secrets:\n",
        "    #  - HUB_PROXY_PASSWORD_FILE\n",
        "      - WEBSERVER_CUSTOM_CERT_FILE\n",
        "      - WEBSERVER_CUSTOM_KEY_FILE\n"
    ]

    result_lines = []
    in_webserver_section = False

    for line in lines:
        if line == webserver_start:
            in_webserver_section = True
            result_lines.extend(webserver_replacement)
        elif in_webserver_section:
            if line in [webserver_secrets_marker, webserver_cert_marker, webserver_key_marker1, webserver_key_marker2]:
                continue
            if not line.startswith("    #"):
                in_webserver_section = False
                result_lines.append(line)
        if not in_webserver_section:
            result_lines.append(line)

    return result_lines

def replace_secrets_section(lines):
    secrets_start = "#secrets:\n"
    proxy_file_marker1 = "#  HUB_PROXY_PASSWORD_FILE:\n"
    proxy_file_marker2 = "#    external: true\n"
    proxy_file_marker3 = "#    name: \"hub_PROXY_PASSWORD_FILE\"\n"

    secrets_replacement = [
        "secrets:\n",
        "#  HUB_PROXY_PASSWORD_FILE:\n",
        "#    external: true\n",
        "#    name: \"hub_PROXY_PASSWORD_FILE\"\n",
        "  WEBSERVER_CUSTOM_CERT_FILE:\n",
        "    external: true\n",
        "    name: \"hub_WEBSERVER_CUSTOM_CERT_FILE\"\n",
        "  WEBSERVER_CUSTOM_KEY_FILE:\n",
        "    external: true\n",
        "    name: \"hub_WEBSERVER_CUSTOM_KEY_FILE\"\n"
    ]

    result_lines = []
    in_secrets_section = False

    for index, line in enumerate(lines):
        if line == secrets_start:
            if (index + 3 < len(lines) and
                lines[index + 1] == proxy_file_marker1 and
                lines[index + 2] == proxy_file_marker2 and
                lines[index + 3] == proxy_file_marker3):
                in_secrets_section = True
                result_lines.extend(secrets_replacement)
                # Skip the lines that are being replaced
                continue
        if in_secrets_section:
            if line.startswith("#"):
                continue
            else:
                in_secrets_section = False
        result_lines.append(line)

    return result_lines

def replace_ssl_cert_lines(compose_file):
    try:
        with open(compose_file, 'r') as file:
            lines = file.readlines()

        lines = replace_services_section(lines)
        lines = replace_webserver_section(lines)
        lines = replace_secrets_section(lines)

        with open(compose_file, 'w') as file:
            file.writelines(lines)

        log('INFO', f"Replaced SSL cert lines in {compose_file}")
    except Exception as e:
        log('ERROR', f"Failed to replace SSL cert lines in {compose_file}: {e}")
        sys.exit(1)

# Main script logic
def main():
    try:
        check_and_install_packages()
        latest_release = get_latest_release()
        latest_version = latest_release["tag_name"].lstrip('v')  # Remove the leading 'v' if present

        # Read the currently installed version
        if os.path.exists(CURRENT_VERSION_FILE):
            with open(CURRENT_VERSION_FILE, 'r') as file:
                current_version = file.read().strip()
        else:
            current_version = None

        # Check if there's a new version
        if latest_version != current_version:
            log('INFO', f"New version {latest_version} found. Updating from version {current_version}.")

            # Clone the new release
            clone_hub_repo(latest_version)

            new_version_dir = os.path.join(DOWNLOAD_DIR, f"hub-{latest_version}")

            # Verify the new version directory exists
            if not os.path.exists(new_version_dir):
                log('ERROR', f"New version directory {new_version_dir} does not exist after cloning.")
                return

            # Stop the existing Docker Swarm and clean up old resources
            stop_docker_swarm()

            # Update the symlink
            update_symlink(new_version_dir)

            # Update the docker-compose.local-overrides.yml file
            compose_file = os.path.join(SYMLINK_PATH, 'docker-swarm', 'docker-compose.local-overrides.yml')
            replace_ssl_cert_lines(compose_file)

            # Start the new Docker Swarm
            start_docker_swarm(os.path.join(SYMLINK_PATH, 'docker-swarm'))

            # Update the current version file
            with open(CURRENT_VERSION_FILE, 'w') as file:
                file.write(latest_version)

            log('INFO', f"Updated to version {latest_version} successfully.")
        else:
            log('INFO', "No new version found. Current version is up to date.")
    except Exception as e:
        log('ERROR', f"An error occurred: {e}")

if __name__ == "__main__":
    main()
