# Update BD Script

## Overview

- This script is meant to be run as a daily cron job; it checks the Hub repo for new versions.
- If a new version is available, it does everything necessary to replace the old version with the new version. 

The script does not require any credentials for authentication.

## Features

- **New Version**: Clones the new version with Git instead of downloading a .tar.gz.
- **Symlink**: Creates a symlink from "current" to the new version so that we can manage the Swarm with shell scripts.
- **Docker Swarm Management Scripts**: Stops the old Docker Swarm with `/opt/bin/docker_swarm_stop.sh`; starts it with `/opt/bin/docker_swarm_start.sh`.
- **Container Pruning**: Removes old Containers with the Docker prune command so nothing old persists.
- **SSL Certificate**: Uncomments out the sections in `docker-compose.local-overrides.yml` that we need for to support SSL encrypted web browsing.
- **Log**: Logs INFO and ERROR messages to `/var/log/blackduck_update.log`.

## Requirements

- Python 3.x
- `requests` library

You can install the required Python packages using pip or let the script install them for you:

```bash
pip install requests
```

## Installation

Clone this repository:

```bash
git clone https://github.com/snps-steve/Update-BD
```

Navigate to the project directory:

```bash
cd Update-BD
```

## Usage

1) Make the script executable (if it isn't already)

```bash
chmod +x /path/to/update_bd.py
```

2) Edit crontab

```bash
crontab -e
```

3) Add the cronjob so it runs daily 

```bash
0 2 * * * /usr/bin/python3 /path/to/update_bd.py
```

Note: 

Breakdown of the cron expression:

- 0 2 * * *: Runs the script daily at 2:00 AM.
- /usr/bin/python3: The path to the Python 3 interpreter.
- /path/to/update_bd.py: The full path to your Python script.

4) Sett up log rotation for the log file (optional)

```bash
sudo nano /etc/logrotate.d/blackduck_update
```

Add configs for the rotation of the logs.

```bash
/var/log/blackduck_update.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>/dev/null || true
    endscript
}
```

5) Verify the crontab

```bash
crontab -l
```

## Configuration

REPO_URL = "https://api.github.com/repos/blackducksoftware/hub/releases/latest"<br>
DOWNLOAD_DIR = "/opt"<br>
SYMLINK_PATH = "/opt/current"<br>
CURRENT_VERSION_FILE = "/opt/current_version.txt"<br>
START_SCRIPT = "/opt/bin/docker_swarm_start.sh"<br>
STOP_SCRIPT = "/opt/bin/docker_swarm_stop.sh"<br>

## License

This project is licensed under the MIT License.

## Contributing

If you would like to contribute to this project, please fork the repository and submit a pull request.

## Contact

For any questions or issues, please contact [Steve R. Smith](mailto:ssmith@blackduck.com).
