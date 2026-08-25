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

class TermuxDistribution(Distribution):
	"""Base class for Termux/proot-distro based distributions"""

	def _get_script_url(self) -> str:
		distro_name = self.get_name()
		return f"https://raw.githubusercontent.com/termux/proot-distro/v4.38.0/distro-plugins/{distro_name}.sh"

	def _load_distro_data(self) -> None:
		distro_name = self.get_name()

		try:
			self.is_offline()
			script_url = self._get_script_url()
			response = self.session.get(script_url)
			response.raise_for_status()

			script_content = response.text
			self.distro_data = self._parse_distro_script(script_content)

		except Offline_err:
			self.console.error("You're offline")
			raise

		except Exception as e:
			self.console.error(f"Failed to fetch {distro_name} data: {e}")
			raise

	def _parse_distro_script(self, script_content: str) -> Dict[str, Any]:
		data = {
			'name': '',
			'comment': '',
			'tarballs': {}
		}

		name_match = re.search(r'DISTRO_NAME="([^"]+)"', script_content)
		if name_match:
			data['name'] = name_match.group(1)

		comment_match = re.search(r'DISTRO_COMMENT="([^"]+)"', script_content)
		if comment_match:
			data['comment'] = comment_match.group(1)

		url_matches = re.findall(r"TARBALL_URL\['([^']+)'\]=\"([^\"]+)\"", script_content)
		sha_matches = re.findall(r"TARBALL_SHA256\['([^']+)'\]=\"([^\"]+)\"", script_content)

		for arch, url in url_matches:
			if arch not in data['tarballs']:
				data['tarballs'][arch] = {}
			data['tarballs'][arch]['url'] = url

		for arch, sha256 in sha_matches:
			if arch in data['tarballs']:
				data['tarballs'][arch]['sha256'] = sha256

		return data

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': self.distro_data.get('name', self.get_name().capitalize()),
			'description': self.distro_data.get('comment', 'Termux/proot-distro package'),
			'supported_archs': list(self.distro_data.get('tarballs', {}).keys()),
			'source': 'Termux/proot-distro'
		})

		return base_info

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return termux_arch in self.distro_data.get('tarballs', {})

	def get_supported_types(self) -> List[str]:
		return ["stable"]

	def download(self, file_name: str = None, distro_type: str = "stable") -> Optional[Any]:
		if self.check_storage:
			self.check_storage()

		arch = self._map_architecture(self._get_architecture())

		if not self.supports_architecture(arch):
			raise ValueError(
				f"Architecture {arch} not supported for {self.get_name()}. Available: {', '.join(self.distro_data.get('tarballs', {}).keys())}")

		tarball_info = self.distro_data['tarballs'].get(arch)
		if not tarball_info:
			raise ValueError(f"No tarball available for architecture {arch}")

		if file_name is None:
			file_name = tarball_info['url'].split('/')[-1]

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
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			if expected_hash:
				if not self._verify_checksum(file_path, expected_hash, "sha256"):
					self.console.warning("Checksum verification failed, retrying download")
					self.fm.remove(file_path)
					self.download(file_name, distro_type)  # Retry download
				else:
					self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download {self.distro_data['name']}: {e}")
			raise
		return file_name
