import re
import socket
import platform
import yaml

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from Core.HiManagers import PyFManager
from Core.console import Table, box
from Core.downloader import FileDownloader
from Core.request import create_session
from Core.errors_handler import Offline_err

class Distribution(ABC):

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
				resources: str, db, check_storage_func=None, is_offline=None):
		self.fm = fm
		self.downloader = downloader
		self.console = console
		self.resources = resources
		self.db = db
		self.check_storage = check_storage_func
		self.session = create_session()
		self.is_offline_bool = is_offline

	@abstractmethod
	def download(self, file_name: str = None, distro_type: str = "minimal") -> None:
		pass

	def is_offline(self):
		if self.is_offline_bool:
			self.console.verbose("Offline mode")
			raise Offline_err("Offline mode")

	@abstractmethod
	def get_name(self) -> str:
		pass

	@abstractmethod
	def supports_architecture(self, arch: str) -> bool:
		pass

	@abstractmethod
	def get_supported_types(self) -> list:
		pass

	def get_display_info(self) -> Dict[str, Any]:
		return {
			'name': self.get_name().capitalize(),
			'description': 'Linux distribution',
			'supported_archs': [],
			'supported_types': self.get_supported_types(),
			'source': 'Direct Download'
		}

	@staticmethod
	def _get_architecture() -> str:
		machine = platform.machine().lower()

		arch_map = {
			'aarch64': 'arm64',
			'arm64': 'arm64',
			'armv7l': 'arm',
			'armv6l': 'arm',
			'armv8l': 'arm64',
			'i386': 'x86',
			'i686': 'x86',
			'x86_64': 'x86_64',
			'amd64': 'x86_64'
		}

		arch = arch_map.get(machine)
		if not arch:
			raise ValueError(f"Unknown architecture: {machine}. Supported: arm64, arm, x86_64, x86")

		return arch

	@abstractmethod
	def _map_architecture(self, arch: str) -> str:
		pass

	def _verify_checksum(self, file_path: str, expected_hash: str, hash_type: str = "sha256") -> bool:
		actual_hash = self.fm.checksum(file_path, hash_type)
		if actual_hash == expected_hash:
			self.console.verbose("Checksum verification passed")
			return True
		else:
			self.console.warning(
				f"Checksum verification failed. Expected: {expected_hash[:16]}..., Got: {actual_hash[:16] if actual_hash else 'None'}")
			return False
class DockerDistribution(Distribution):
	"""Base class for distributions fetched as rootfs tarballs from Docker Hub images.

	Subclasses set IMAGE ("name" for official images, "org/name" otherwise) and TAG.
	The image's single base layer is the rootfs tarball; its digest is its sha256.
	"""

	REGISTRY = "https://registry-1.docker.io"
	AUTH_URL = "https://auth.docker.io/token"
	IMAGE: str = ""
	TAG: str = "latest"
	DESCRIPTION: str = ""
	DISPLAY_NAME: str = ""

	MANIFEST_ACCEPT = ", ".join([
		"application/vnd.oci.image.index.v1+json",
		"application/vnd.docker.distribution.manifest.list.v2+json",
		"application/vnd.oci.image.manifest.v1+json",
		"application/vnd.docker.distribution.manifest.v2+json",
	])

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._token: Optional[str] = None
		self.distro_data: Dict[str, Any] = {
			'name': self.DISPLAY_NAME or self.get_name().capitalize(),
			'comment': self.DESCRIPTION or f"Docker image {self.IMAGE}:{self.TAG}",
			'platforms': {},
			'tarballs': {}
		}

	def _get_repository(self) -> str:
		return self.IMAGE if "/" in self.IMAGE else f"library/{self.IMAGE}"

	def _get_tag(self) -> str:
		return self.TAG

	def _get_token(self) -> str:
		response = self.session.get(self.AUTH_URL, params={
			'service': 'registry.docker.io',
			'scope': f"repository:{self._get_repository()}:pull"
		})
		response.raise_for_status()
		data = response.json()
		return data.get('token') or data['access_token']

	def _auth_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
		if not self._token:
			self._token = self._get_token()
		headers = {'Authorization': f"Bearer {self._token}"}
		if extra:
			headers.update(extra)
		return headers

	def _get_manifest(self, reference: str) -> Dict[str, Any]:
		url = f"{self.REGISTRY}/v2/{self._get_repository()}/manifests/{reference}"
		headers = {'Accept': self.MANIFEST_ACCEPT}
		response = self.session.get(url, headers=self._auth_headers(headers))
		if response.status_code == 401:
			self._token = None
			response = self.session.get(url, headers=self._auth_headers(headers))
		response.raise_for_status()
		return response.json()

	def _load_distro_data(self) -> None:
		name = self.get_name()

		try:
			self.is_offline()
			index = self._get_manifest(self._get_tag())
			self._parse_distro_manifest(index)

			current = self._map_architecture(self._get_architecture())
			if current in self.distro_data['platforms']:
				self._resolve_tarball(current)

		except Offline_err:
			self.console.error("You're offline")
			raise

		except Exception as e:
			self.console.error(f"Failed to fetch {name} data: {e}")
			raise

	def _parse_distro_manifest(self, index: Dict[str, Any]) -> None:
		platforms = self.distro_data['platforms']

		if 'layers' in index:
			arch = self._map_architecture(self._get_architecture())
			platforms[arch] = None
			self._store_tarball(arch, index)
			return

		for entry in index.get('manifests', []):
			plat = entry.get('platform', {})
			arch = plat.get('architecture')
			if plat.get('os') != 'linux' or not arch or arch == 'unknown':
				continue
			if arch == 'arm' and plat.get('variant') not in (None, 'v7'):
				continue
			platforms.setdefault(arch, entry['digest'])

	def _store_tarball(self, arch: str, manifest: Dict[str, Any]) -> bool:
		layers = manifest.get('layers', [])
		if len(layers) != 1:
			return False

		layer = layers[0]
		digest = layer['digest']
		media = layer.get('mediaType', '')
		self.distro_data['tarballs'][arch] = {
			'url': f"{self.REGISTRY}/v2/{self._get_repository()}/blobs/{digest}",
			'sha256': digest.split(':', 1)[1],
			'ext': 'tar.zst' if 'zstd' in media else 'tar.gz',
			'size': layer.get('size', 0)
		}
		return True

	def _resolve_tarball(self, arch: str) -> Optional[Dict[str, Any]]:
		tarballs = self.distro_data['tarballs']
		if arch in tarballs:
			return tarballs[arch]

		digest = self.distro_data['platforms'].get(arch)
		if digest:
			self._store_tarball(arch, self._get_manifest(digest))
		return tarballs.get(arch)

	@staticmethod
	def _format_size(size: int) -> str:
		if not size:
			return "Unknown"
		if size < 1024 * 1024:
			return f"{size / 1024:.0f}KB"
		return f"{size / (1024 * 1024):.0f}MB"

	def get_size(self, arch: str) -> str:
		info = self.distro_data['tarballs'].get(self._map_architecture(arch))
		return self._format_size(info['size']) if info else "Unknown"

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': self.distro_data.get('name', self.get_name().capitalize()),
			'description': self.distro_data.get('comment', 'Docker image rootfs'),
			'supported_archs': list(self.distro_data.get('platforms', {}).keys()),
			'source': f"Docker Hub ({self.IMAGE}:{self._get_tag()})"
		})

		return base_info

	def _map_architecture(self, arch: str) -> str:
		docker_arch_map = {
			'arm64': 'arm64',
			'arm': 'arm',
			'x86_64': 'amd64',
			'x86': '386'
		}

		return docker_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		docker_arch = self._map_architecture(arch)
		return docker_arch in self.distro_data.get('platforms', {})

	def get_supported_types(self) -> List[str]:
		return ["stable"]

	def download(self, file_name: str = None, distro_type: str = "stable", _retry: bool = True) -> Optional[Any]:
		if self.check_storage:
			self.check_storage()

		arch = self._map_architecture(self._get_architecture())

		if not self.supports_architecture(arch):
			raise ValueError(
				f"Architecture {arch} not supported for {self.get_name()}. Available: {', '.join(self.distro_data.get('platforms', {}).keys()) or 'none (registry unreachable?)'}")

		tarball_info = self._resolve_tarball(arch)
		if not tarball_info:
			raise ValueError(f"No single-layer rootfs tarball available for architecture {arch}")

		if file_name is None:
			file_name = f"{self.get_name()}-{arch}-{tarball_info['sha256'][:12]}.{tarball_info['ext']}"

		self.console.info(f"Starting {self.distro_data['name']} download")

		file_path = f"{self.resources}/{file_name}"

		url = tarball_info['url']
		expected_hash = tarball_info.get('sha256')

		if self.fm.exists(file_path):
			download_needed = False
			if expected_hash and\
			not self._verify_checksum(file_path, expected_hash, "sha256"):
				self.console.warning(f"Checksum mismatch for [blue]{file_name}[/blue]")
				self.console.warning("File may be corrupted or tampered with.")
				download_needed = self.console.input("Do you want to download the file again? [cyan][Y|n]:[/cyan] ").strip().lower() in ["y", "yes"]
			if not download_needed:
				self.console.info(f"{self.distro_data['name']} already downloaded")
				return file_name

		self.console.verbose(f"Download URL: {url}")
		self.console.verbose(f"Target file: {file_path}")

		try:
			self._token = self._get_token()
			self.downloader.download_file(
				url, file_path,
				headers=self._auth_headers(),
				total_size=tarball_info.get('size', 0)
			)
			self.console.verbose(f"Download completed: {file_path}")

			if expected_hash:
				if not self._verify_checksum(file_path, expected_hash, "sha256"):
					self.fm.remove(file_path)
					if not _retry:
						raise ValueError("Checksum verification failed twice, giving up")
					self.console.warning("Checksum verification failed, retrying download")
					return self.download(file_name, distro_type, _retry=False)
				self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download {self.distro_data['name']}: {e}")
			raise
		return file_name
