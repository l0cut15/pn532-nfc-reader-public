# Docker Deployment for NFC Reader

This directory contains Docker configuration files for deploying the NFC Reader service in a containerized environment.

## Quick Start

1. **Create environment configuration:**
   ```bash
   cp .env.template .env
   # Edit .env with your Home Assistant token and settings
   ```

2. **Find your NFC device:**
   ```bash
   # macOS
   ls /dev/cu.*  # Look for /dev/cu.usbserial-*
   
   # Linux  
   ls /dev/tty*  # Look for /dev/ttyUSB0, /dev/ttyACM0, etc.
   ```

3. **Update device mapping in docker-compose.yml:**
   Replace the device path with your actual NFC device.

4. **Build and run:**
   ```bash
   docker-compose up -d
   ```

## Configuration

### Device Access
The NFC reader requires access to the host's USB/serial device. The docker-compose.yml file includes several approaches:

- **Specific device mapping** (recommended):
  ```yaml
  devices:
    - "/dev/ttyUSB0:/dev/ttyUSB0"
  ```

- **Privileged mode** (if device mapping doesn't work):
  ```yaml
  privileged: true
  ```

### Home Assistant Connection
For Docker deployments, use one of these host addresses in `.env` (`HA_HOST`):

- **Docker Desktop (Mac/Windows)**: `host.docker.internal`
- **Linux Docker**: `172.17.0.1` or your Docker bridge IP
- **Direct IP**: Use your Home Assistant server's IP address

### Environment Variables
Configuration is handled via `.env` file instead of config.yaml for security:

- **HA_TOKEN**: Your Home Assistant long-lived access token
- **HA_HOST**: Home Assistant host (use `host.docker.internal` for Docker Desktop)
- **NFC_PORT**: Device path inside container (usually `/dev/ttyUSB0`)
- **NFC_READER_ID**: Unique identifier for this reader instance

See `.env.template` for all available variables.

## Commands

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f nfc-reader

# Stop service
docker-compose down

# Rebuild after changes
docker-compose build --no-cache
docker-compose up -d

# Health check
docker-compose exec nfc-reader python nfc_reader_service.py health
```

## Troubleshooting

### Device Access Issues
- Verify device path: `ls -la /dev/tty*`
- Check permissions: `sudo chmod 666 /dev/ttyUSB0`
- Try privileged mode if device mapping fails
- On Linux, add user to dialout group: `sudo usermod -a -G dialout $USER`

### Home Assistant Connection
- Test HA API access from host: `curl http://YOUR_HA_IP:8123/api/`
- Verify token in Home Assistant Profile settings
- Check network connectivity from container

### Common Device Paths
- **macOS**: `/dev/cu.usbserial-*`, `/dev/cu.wchusbserial*`
- **Linux USB Serial**: `/dev/ttyUSB0`, `/dev/ttyUSB1`
- **Linux USB ACM**: `/dev/ttyACM0`, `/dev/ttyACM1`

## Security Notes

- **Environment Variables**: Secrets are kept in `.env` file, never copied into image
- **Device Access**: Use specific device mappings instead of privileged mode when possible
- **Token Security**: `.env` file is excluded from Docker builds via `.dockerignore`
- **Registry Safe**: No sensitive data is baked into the Docker image