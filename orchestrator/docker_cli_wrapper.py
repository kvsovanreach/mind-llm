"""
Docker CLI Wrapper - bypasses the Python docker library issues
by using the docker CLI directly via subprocess
"""

import subprocess
import json
import logging

logger = logging.getLogger(__name__)

class DockerCLIWrapper:
    """Wrapper around Docker CLI commands"""

    def __init__(self):
        # Test if docker CLI works
        try:
            self.run_command(['docker', 'version'])
            logger.info("Docker CLI wrapper initialized successfully")
            self.available = True
        except Exception as e:
            logger.error(f"Docker CLI not available: {e}")
            self.available = False

    def run_command(self, cmd, timeout=30):
        """Run a docker command and return the result"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                raise Exception(f"Command failed: {result.stderr}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise Exception(f"Command timed out: {' '.join(cmd)}")
        except Exception as e:
            raise Exception(f"Command failed: {e}")

    def ping(self):
        """Test if Docker is responsive"""
        try:
            self.run_command(['docker', 'info'], timeout=5)
            return True
        except:
            return False

    def container_run(self, image, name, command=None, environment=None,
                     volumes=None, network=None, device_requests=None,
                     restart_policy=None, detach=True, ports=None):
        """Run a new container"""
        cmd = ['docker', 'run']

        if detach:
            cmd.append('-d')

        if name:
            cmd.extend(['--name', name])

        if network:
            cmd.extend(['--network', network])

        if restart_policy:
            cmd.extend(['--restart', restart_policy.get('Name', 'unless-stopped')])

        if environment:
            for key, value in environment.items():
                cmd.extend(['-e', f'{key}={value}'])

        if volumes:
            for host_path, config in volumes.items():
                bind = config['bind']
                mode = config.get('mode', 'rw')
                cmd.extend(['-v', f'{host_path}:{bind}:{mode}'])

        if ports:
            for container_port, host_port in ports.items():
                cmd.extend(['-p', f'{host_port}:{container_port}'])

        # GPU support
        if device_requests:
            cmd.extend(['--gpus', 'all'])

        cmd.append(image)

        if command:
            cmd.extend(command)

        output = self.run_command(cmd)
        # Return the container ID
        return output.strip()

    def container_stop(self, name_or_id):
        """Stop a container"""
        try:
            self.run_command(['docker', 'stop', name_or_id])
            return True
        except:
            return False

    def container_remove(self, name_or_id, force=False):
        """Remove a container"""
        cmd = ['docker', 'rm']
        if force:
            cmd.append('-f')
        cmd.append(name_or_id)

        try:
            self.run_command(cmd)
            return True
        except:
            return False

    def container_list(self, all=False):
        """List containers"""
        cmd = ['docker', 'ps', '--format', 'json']
        if all:
            cmd.insert(2, '-a')

        try:
            output = self.run_command(cmd)
            containers = []
            for line in output.strip().split('\n'):
                if line:
                    containers.append(json.loads(line))
            return containers
        except:
            return []

    def container_exists(self, name):
        """Check if a container exists"""
        try:
            self.run_command(['docker', 'inspect', name], timeout=5)
            return True
        except:
            return False

    def container_logs(self, name_or_id, tail=50):
        """Get container logs"""
        try:
            output = self.run_command(
                ['docker', 'logs', '--tail', str(tail), name_or_id]
            )
            return output
        except:
            return ""

    def container_exec(self, name_or_id, command):
        """Execute a command in a container"""
        cmd = ['docker', 'exec', name_or_id] + command
        try:
            return self.run_command(cmd)
        except:
            return None

    def container_stats(self, name_or_id):
        """Get container stats"""
        try:
            output = self.run_command(
                ['docker', 'stats', '--no-stream', '--format', 'json', name_or_id]
            )
            return json.loads(output)
        except:
            return None

    def container_status(self, name_or_id):
        """Get container status (running, exited, etc)"""
        try:
            output = self.run_command(
                ['docker', 'inspect', '-f', '{{.State.Status}}', name_or_id],
                timeout=5
            )
            return output.strip()
        except:
            return "unknown"

# Create a global instance
docker_cli = DockerCLIWrapper()