import re
import socket
import yaml
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from Core.HiManagers import PyFManager
from Core.console import Table, box
from Core.downloader import FileDownloader
from Core.request import create_session
from Core.errors_handler import Offline_err


class Distribution(ABC):
	"""Abstract base class for Linux distributions"""

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
		"""Download the distribution"""
		pass

	def is_offline(self):
		if self.is_offline_bool:
			self.console.verbose("Offline mode")
			raise Offline_err("Offline mode")

	@abstractmethod
	def get_name(self) -> str:
		"""Get distribution name"""
		pass

	@abstractmethod
	def supports_architecture(self, arch: str) -> bool:
		"""Check if architecture is supported"""
		pass

	@abstractmethod
	def get_supported_types(self) -> list:
		"""Get supported distribution types"""
		pass

	def get_display_info(self) -> Dict[str, Any]:
		"""Get distribution display information"""
		return {
			'name': self.get_name().capitalize(),
			'description': 'Linux distribution',
			'supported_archs': [],
			'supported_types': self.get_supported_types(),
			'source': 'Direct Download'
		}

	def _get_architecture(self) -> str:
		"""Get current system architecture mapped to 4 standard types"""
		import platform
		machine = platform.machine().lower()

		# Simple mapping to only 4 architectures
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
		"""Map standard architecture to distribution-specific architecture name"""
		pass

	def _verify_checksum(self, file_path: str, expected_hash: str, hash_type: str = "sha256") -> bool:
		"""Verify file checksum using PyFManager"""
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

	def _load_distro_data(self) -> None:
		"""Load distribution data from GitHub or cache"""
		distro_name = self.get_name()

		# Try to get from cache first
		cached_data = self.db.get(f"distro_{distro_name}")
		if cached_data:
			self.distro_data = cached_data
			self.console.verbose(f"Loaded {distro_name} data from cache")
			return

		# Fetch from GitHub
		try:
			self.is_offline()
			script_url = f"https://raw.githubusercontent.com/termux/proot-distro/refs/heads/master/distro-plugins/{distro_name}.sh"
			response = self.session.get(script_url)
			response.raise_for_status()

			script_content = response.text
			self.distro_data = self._parse_distro_script(script_content)

			# Cache the data
			self.db.add(f"distro_{distro_name}", self.distro_data)
			self.console.verbose(f"Fetched and cached {distro_name} data from GitHub")

		except Offline_err:
			self.distro_data = {
									'name': '',
									'comment': '',
									'tarballs': {}
								}

		except Exception as e:
			self.console.error(f"Failed to fetch {distro_name} data: {e}")
			raise

	def _parse_distro_script(self, script_content: str) -> Dict[str, Any]:
		"""Parse Termux/proot-distro shell script to extract distribution data"""
		data = {
			'name': '',
			'comment': '',
			'tarballs': {}
		}

		# Extract DISTRO_NAME
		name_match = re.search(r'DISTRO_NAME="([^"]+)"', script_content)
		if name_match:
			data['name'] = name_match.group(1)

		# Extract DISTRO_COMMENT
		comment_match = re.search(r'DISTRO_COMMENT="([^"]+)"', script_content)
		if comment_match:
			data['comment'] = comment_match.group(1)

		# Extract TARBALL_URL and TARBALL_SHA256
		url_matches = re.findall(r"TARBALL_URL\['([^']+)'\]=\"([^\"]+)\"", script_content)
		sha_matches = re.findall(r"TARBALL_SHA256\['([^']+)'\]=\"([^\"]+)\"", script_content)

		# Create tarball dictionary
		for arch, url in url_matches:
			if arch not in data['tarballs']:
				data['tarballs'][arch] = {}
			data['tarballs'][arch]['url'] = url

		for arch, sha256 in sha_matches:
			if arch in data['tarballs']:
				data['tarballs'][arch]['sha256'] = sha256

		return data

	def get_display_info(self) -> Dict[str, Any]:
		"""Get distribution display information"""
		base_info = super().get_display_info()
		base_info.update({
			'name': self.distro_data.get('name', self.get_name().capitalize()),
			'description': self.distro_data.get('comment', 'Termux/proot-distro package'),
			'supported_archs': list(self.distro_data.get('tarballs', {}).keys()),
			'source': 'Termux/proot-distro'
		})
		return base_info

	def supports_architecture(self, arch: str) -> bool:
		"""Check if architecture is supported"""
		termux_arch = self._map_architecture(arch)
		return termux_arch in self.distro_data.get('tarballs', {})

	def get_supported_types(self) -> List[str]:
		"""Get supported distribution types"""
		return ["stable"]

	def download(self, file_name: str = None, distro_type: str = "stable") -> Optional[Any]:
		"""Download the distribution"""
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
			# Extract filename from URL
			file_name = tarball_info['url'].split('/')[-1]

		self.console.info(f"Starting {self.distro_data['name']} download")

		file_path = f"{self.resources}/{file_name}"

		# Check if already downloaded
		if self.fm.exists(file_path):
			self.console.info(f"{self.distro_data['name']} already downloaded")
			return file_name

		url = tarball_info['url']
		expected_hash = tarball_info.get('sha256')

		self.console.verbose(f"Download URL: {url}")
		self.console.verbose(f"Target file: {file_path}")

		try:
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			# Verify checksum if available
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


class DebianDistribution(TermuxDistribution):
	def get_name(self) -> str:
		return "debian"


	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Termux-specific names"""
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64',
			'x86': 'i686'
		}
		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)


class UbuntuDistribution(TermuxDistribution):
	def get_name(self) -> str:
		return "ubuntu"

	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Termux-specific names"""
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64'
		}
		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)


class ArchLinuxDistribution(TermuxDistribution):
	def get_name(self) -> str:
		return "archlinux"


	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Termux-specific names"""
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64',
			'x86': 'i686'
		}
		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)

class FedoraDistribution(TermuxDistribution):
	def get_name(self) -> str:
		return "fedora"


	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Termux-specific names"""
		termux_arch_map = {
			'arm64': 'aarch64',
			'x86_64': 'x86_64'
		}
		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)

class VoidDistribution(TermuxDistribution):
	def get_name(self) -> str:
		return "void"


	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Termux-specific names"""
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64',
			'x86': 'i686'
		}
		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)

class AlpineDistribution(Distribution):
	"""Alpine Linux distribution"""

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
	             resources: str, db, check_storage_func=None, **kwargs):
		super().__init__(fm, downloader, console, resources, db, check_storage_func, **kwargs)
		self.supported_archs = ['x86_64', 'x86', 'aarch64', 'armv7', 'armhf']
		self.available_flavors = {}  # Will be populated from metadata
		self.metadata = None

	def get_name(self) -> str:
		return "alpine"

	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Alpine-specific names"""
		alpine_arch_map = {
			'arm64': 'aarch64',
			'arm': 'armv7',
			'x86_64': 'x86_64',
			'x86': 'x86'
		}
		return alpine_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		alpine_arch = self._map_architecture(arch)
		return alpine_arch in self.supported_archs

	def get_supported_types(self) -> list:
		"""Get all available Alpine flavors/types"""
		if not self.available_flavors:
			self._load_alpine_metadata()

		return list(self.available_flavors.keys())

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Alpine Linux',
			'description': 'Lightweight security-oriented distribution',
			'supported_archs': self.supported_archs,
			'supported_types': self.get_supported_types(),
			'source': 'Alpine Official'
		})
		return base_info

	def _load_alpine_metadata(self) -> None:
		"""Load Alpine metadata from YAML and populate available flavors"""
		if self.available_flavors:
			return

		arch = self._get_architecture()
		alpine_arch = self._map_architecture(arch)  # Use mapped architecture for URL
		metadata_url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{alpine_arch}/latest-releases.yaml"

		try:
			# Try cache first
			cached_metadata = self.db.get(f"alpine_metadata_{alpine_arch}")
			if cached_metadata:
				self.metadata = cached_metadata
				self.console.verbose(f"Loaded Alpine metadata for {alpine_arch} from cache")
			else:
				self.is_offline()
				response = self.session.get(metadata_url)
				response.raise_for_status()
				raw_metadata = yaml.safe_load(response.text)

				# Clean the metadata before caching
				self.metadata = self._clean_metadata(raw_metadata)

				# Cache the cleaned metadata
				self.db.add(f"alpine_metadata_{alpine_arch}", self.metadata)
				self.console.verbose(f"Fetched and cached Alpine metadata for {alpine_arch}")

			# Populate available flavors
			if self.metadata:
				for item in self.metadata:
					flavor = item.get('flavor', '')
					if flavor and flavor not in self.available_flavors:
						self.available_flavors[flavor] = {
							'title': item.get('title', ''),
							'desc': item.get('desc', ''),
							'file_extension': self._get_file_extension(item.get('file', '')),
							'is_tarball': self._is_tarball(item.get('file', ''))
						}

		except Exception as e:
			self.console.warning(f"Failed to load Alpine metadata: {e}")
			# Fallback to basic flavors if metadata loading fails
			self.available_flavors = {
				'alpine-minirootfs': {'title': 'Mini root filesystem',
				                      'desc': 'Minimal root filesystem for containers and chroots',
				                      'file_extension': '.tar.gz', 'is_tarball': True},
				'alpine-standard': {'title': 'Standard', 'desc': 'Alpine as it was intended', 'file_extension': '.iso',
				                    'is_tarball': False},
				'alpine-virt': {'title': 'Virtual', 'desc': 'Optimized for virtual systems', 'file_extension': '.iso',
				                'is_tarball': False},
				'alpine-uboot': {'title': 'Generic U-Boot', 'desc': 'Includes U-Boot bootloader',
				                 'file_extension': '.tar.gz', 'is_tarball': True},
				'alpine-netboot': {'title': 'Netboot', 'desc': 'Kernel and initramfs for netboot',
				                   'file_extension': '.tar.gz', 'is_tarball': True},
				'alpine-rpi': {'title': 'Raspberry Pi', 'desc': 'For Raspberry Pi devices', 'file_extension': '.tar.gz',
				               'is_tarball': True}
			}

	def _clean_metadata(self, metadata):
		"""Clean metadata by converting non-serializable objects"""
		import datetime
		cleaned = []
		for item in metadata:
			cleaned_item = {}
			for key, value in item.items():
				if isinstance(value, (datetime.date, datetime.datetime)):
					cleaned_item[key] = value.isoformat()
				else:
					cleaned_item[key] = value
			cleaned.append(cleaned_item)
		return cleaned

	def _get_file_extension(self, filename: str) -> str:
		"""Extract file extension from filename"""
		if filename.endswith('.tar.gz'):
			return '.tar.gz'
		elif filename.endswith('.tar.xz'):
			return '.tar.xz'
		elif filename.endswith('.img.gz'):
			return '.img.gz'
		elif filename.endswith('.iso'):
			return '.iso'
		return '.tar.gz'  # default

	def _is_tarball(self, filename: str) -> bool:
		"""Check if file is a tarball (not ISO)"""
		return any(filename.endswith(ext) for ext in ['.tar.gz', '.tar.xz', '.img.gz'])

	def _get_flavor_info(self, distro_type: str) -> Dict[str, str]:
		"""Get information about a specific Alpine flavor"""
		self._load_alpine_metadata()
		return self.available_flavors.get(distro_type, {})

	def _find_metadata_for_flavor(self, arch: str, distro_type: str) -> Optional[Dict[str, Any]]:
		"""Find metadata for specific architecture and flavor"""
		if not self.metadata:
			self._load_alpine_metadata()

		if self.metadata:
			for item in self.metadata:
				if (item.get('arch') == arch and
						item.get('flavor') == distro_type and
						self._is_tarball(item.get('file', ''))):
					return item
		return None

	def get_file_size(self, arch: str, distro_type: str) -> str:
		"""Get file size for specific architecture and type"""
		if not self.metadata:
			self._load_alpine_metadata()

		if self.metadata:
			item = self._find_metadata_for_flavor(arch, distro_type)
			if item and 'size' in item:
				size_bytes = item['size']
				# Convert to human readable
				if size_bytes >= 1024 ** 3:  # GB
					return f"{size_bytes / 1024 ** 3:.1f} GiB"
				elif size_bytes >= 1024 ** 2:  # MB
					return f"{size_bytes / 1024 ** 2:.1f} MiB"
				elif size_bytes >= 1024:  # KB
					return f"{size_bytes / 1024:.1f} KiB"
				else:
					return f"{size_bytes} B"

		return "Unknown"

	def download(self, file_name: str = None, distro_type: str = "alpine-minirootfs") -> Optional[Any]:
		if self.check_storage:
			self.check_storage()

		arch = self._get_architecture()
		standard_arch = self._get_architecture()
		alpine_arch = self._map_architecture(standard_arch)
		if not self.supports_architecture(arch):
			raise ValueError(
				f"Architecture {arch} not supported for Alpine. Available: {', '.join(self.supported_archs)}")

		# Load metadata to validate type
		self._load_alpine_metadata()

		if distro_type not in self.available_flavors:
			raise ValueError(
				f"Type '{distro_type}' not supported for Alpine. Available: {', '.join(self.available_flavors.keys())}")

		flavor_info = self.available_flavors[distro_type]
		if not flavor_info.get('is_tarball', True):
			self.console.warning(f"Note: {distro_type} is an ISO image, not a tarball")

		# Find metadata for this flavor and architecture
		distro_metadata = self._find_metadata_for_flavor(alpine_arch, distro_type)
		if not distro_metadata:
			raise ValueError(f"No download available for {distro_type} on architecture {arch}")

		if file_name is None:
			file_name = distro_metadata['file']

		self.console.info(f"Starting Alpine Linux ({flavor_info['title']}) download")

		file_path = f"{self.resources}/{file_name}"

		# Check if already downloaded
		if self.fm.exists(file_path):
			self.console.info(f"Alpine {distro_type} already downloaded")
			return file_name

		# Build download URL
		version = distro_metadata.get("version")
		if not version:
			raise Exception("The version hasn't been detected.")

		url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{alpine_arch}/{distro_metadata['file']}"

		# Show file size if available
		file_size = self.get_file_size(alpine_arch, distro_type)
		if file_size != "Unknown":
			self.console.info(f"Download size: {file_size}")

		self.console.verbose(f"Download URL: {url}")
		self.console.verbose(f"Target file: {file_path}")

		try:
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			# Verify checksum (prefer sha512, fallback to sha256)
			expected_hash = distro_metadata.get("sha512") or distro_metadata.get("sha256")
			hash_type = "sha512" if distro_metadata.get("sha512") else "sha256"

			if expected_hash:
				if not self._verify_checksum(file_path, expected_hash, hash_type):
					self.console.warning("Checksum verification failed, retrying download")
					self.fm.remove(file_path)
					self.download(file_name, distro_type)  # Retry download
				else:
					self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download Alpine {distro_type}: {e}")
			raise
		return file_name


class KaliNethunterDistribution(Distribution):
	"""Kali Nethunter distribution implementation"""

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
	             resources: str, db, check_storage_func=None, **kwargs):
		super().__init__(fm, downloader, console, resources, db, check_storage_func, **kwargs)
		self.supported_archs = ['amd64', 'arm64', 'armhf', 'i386']
		self.supported_types = ["minimal", "nano", "full"]
		self.base_url = "https://kali.download/nethunter-images/current/rootfs"
		self.file_sizes = {}  # Cache for file sizes

	def get_name(self) -> str:
		return "kali-nethunter"

	def _map_architecture(self, arch: str) -> str:
		"""Map standard architecture to Kali-specific names"""
		kali_arch_map = {
			'arm64': 'arm64',
			'arm': 'armhf',
			'x86_64': 'amd64',
			'x86': 'i386'
		}
		return kali_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		kali_arch = self._map_architecture(arch)
		return kali_arch in self.supported_archs

	def get_supported_types(self) -> list:
		return self.supported_types

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Kali Nethunter',
			'description': 'Penetration testing distribution for mobile devices',
			'supported_archs': self.supported_archs,
			'supported_types': self.supported_types,
			'source': 'Kali Official'
		})
		return base_info

	def _parse_html_directory(self, html_content: str) -> Dict[str, str]:
		"""Parse HTML directory listing to extract file sizes"""
		import re
		file_sizes = {}

		try:
			# Pattern to match file rows: <a href="filename">filename</a> and size
			pattern = r'<a href="([^"]+\.tar\.xz)"[^>]*>([^<]+)</a>.*?<td class="size">([^<]+)</td>'
			matches = re.findall(pattern, html_content, re.DOTALL)

			for match in matches:
				filename = match[0]  # Use the href value as it's more reliable
				size = match[2].strip()
				file_sizes[filename] = size

			self.console.verbose(f"Parsed {len(file_sizes)} file sizes from directory listing")

		except Exception as e:
			self.console.warning(f"Failed to parse HTML directory: {e}")

		return file_sizes

	def _fetch_file_sizes(self) -> Dict[str, str]:
		"""Fetch and parse the directory listing to get file sizes"""
		# Try cache first
		if self.file_sizes:
			return self.file_sizes

		try:
			self.is_offline()
			response = self.session.get(self.base_url + "/")
			response.raise_for_status()

			self.file_sizes = self._parse_html_directory(response.text)

			# Cache in database for offline use
			self.db.add("kali_file_sizes", self.file_sizes)

			return self.file_sizes

		except Exception as e:
			self.console.warning(f"Failed to fetch file sizes: {e}")
			# Try to load from cache
			cached_sizes = self.db.get("kali_file_sizes")
			if cached_sizes:
				self.file_sizes = cached_sizes
				return self.file_sizes
			return {}

	def get_file_size(self, arch: str, distro_type: str) -> str:
		"""Get file size for specific architecture and type"""
		file_sizes = self._fetch_file_sizes()
		filename = f"kali-nethunter-rootfs-{distro_type}-{arch}.tar.xz"

		size = file_sizes.get(filename, "Unknown")
		return size

	def get_type_sizes(self) -> Dict[str, Dict[str, str]]:
		"""Get sizes for all types and architectures"""
		file_sizes = self._fetch_file_sizes()
		type_sizes = {}

		for distro_type in self.supported_types:
			type_sizes[distro_type] = {}
			for arch in self.supported_archs:
				filename = f"kali-nethunter-rootfs-{distro_type}-{arch}.tar.xz"
				type_sizes[distro_type][arch] = file_sizes.get(filename, "Unknown")

		return type_sizes

	def _get_checksums(self) -> Dict[str, str]:
		"""Fetch and parse SHA256SUMS file"""
		checksum_url = f"{self.base_url}/SHA256SUMS"
		self.console.verbose(f"Fetching checksums from: {checksum_url}")

		try:
			response = self.session.get(checksum_url)
			response.raise_for_status()

			checksums = {}
			for line in response.text.splitlines():
				if line.strip():
					parts = line.split()
					if len(parts) >= 2:
						hash_value = parts[0]
						filename = parts[1]
						checksums[filename] = hash_value

			self.console.verbose(f"Loaded {len(checksums)} checksums")
			return checksums

		except Exception as e:
			self.console.error(f"Failed to fetch checksums: {e}")
			return {}

	def _get_download_url(self, arch: str, distro_type: str) -> str:
		"""Build download URL based on architecture and type"""
		filename = f"kali-nethunter-rootfs-{distro_type}-{arch}.tar.xz"
		return f"{self.base_url}/{filename}"

	def _get_expected_filename(self, arch: str, distro_type: str) -> str:
		"""Get the expected filename pattern from checksums"""
		# The checksums use a different naming pattern with version
		checksums = self._get_checksums()

		# Look for matching files in checksums
		pattern = f"kali-nethunter-*-rootfs-{distro_type}-{arch}.tar.xz"
		for filename in checksums.keys():
			if f"rootfs-{distro_type}-{arch}.tar.xz" in filename:
				return filename

		# Fallback to standard naming if not found
		return f"kali-nethunter-rootfs-{distro_type}-{arch}.tar.xz"

	def download(self, file_name: str = None, distro_type: str = "minimal") -> Optional[Any]:
		if self.check_storage:
			self.check_storage()

		arch = self._get_architecture()
		standard_arch = self._get_architecture()
		kali_arch = self._map_architecture(standard_arch)

		if not self.supports_architecture(arch):
			raise ValueError(
				f"Architecture {arch} not supported for Kali Nethunter. Available: {', '.join(self.supported_archs)}")

		if distro_type not in self.supported_types:
			raise ValueError(f"Type {distro_type} not supported. Available: {', '.join(self.supported_types)}")

		# Get the actual filename from checksums
		expected_filename = self._get_expected_filename(arch, distro_type)

		if file_name is None:
			file_name = expected_filename

		# Get file size for user information
		file_size = self.get_file_size(arch, distro_type)

		self.console.info(f"Starting Kali Nethunter ({distro_type}) download process")
		if file_size != "Unknown":
			self.console.info(f"Estimated download size: {file_size}")

		file_path = f"{self.resources}/{file_name}"

		# Check if already downloaded
		if self.fm.exists(file_path):
			self.console.info("Kali Nethunter already downloaded")
			return file_name

		# Get checksums first
		checksums = self._get_checksums()
		if not checksums:
			self.console.warning("Could not fetch checksums, downloading without verification")

		# Build download URL
		url = self._get_download_url(kali_arch, distro_type)
		self.console.verbose(f"Download URL: {url}")

		try:
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			# Verify checksum if available
			if checksums and expected_filename in checksums:
				expected_hash = checksums[expected_filename]
				if not self._verify_checksum(file_path, expected_hash, "sha256"):
					self.console.warning("Checksum verification failed, retrying download")
					self.fm.remove(file_path)
					self.download(file_name, distro_type)  # Retry download
				else:
					self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download Kali Nethunter: {e}")
			raise
		return file_name


class DistributionManager:
	"""Manager class for handling multiple distributions"""

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
	             resources: str, db, check_storage_func=None):
		self.fm = fm
		self.downloader = downloader
		self.console = console
		self.resources = resources
		self.db = db
		self.check_storage = check_storage_func
		self.termux_distros_list_str = [
			"debian",
			"ubuntu",
			"archlinux",
			"fedora",
			"void"
		]
		self.termux_distros_list = [
			DebianDistribution,
			UbuntuDistribution,
			ArchLinuxDistribution,
			FedoraDistribution,
			VoidDistribution
		]

		self.distributions: Dict[str, Distribution] = self._initialize_distributions()
		self.current_arch = self.get_current_architecture()

	@staticmethod
	def is_connected(host="1.1.1.1", port=53, timeout=2):
		try:
			socket.setdefaulttimeout(timeout)
			socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
			return True
		except socket.error:
			return False

	def _initialize_distributions(self) -> Dict[str, Distribution]:
		"""Initialize all available distributions"""
		is_offline = not self.is_connected()
		distributions = {}

		# Termux-based distributions
		termux_distros = list(zip(self.termux_distros_list_str, self.termux_distros_list))

		# Direct download distributions
		direct_distros = [
			('alpine', AlpineDistribution),
			('kali-nethunter', KaliNethunterDistribution)
		]

		# Initialize all distributions
		for distro_name, distro_class in termux_distros + direct_distros:
			try:
				distributions[distro_name] = distro_class(
					self.fm, self.downloader, self.console,
					self.resources, self.db, self.check_storage, is_offline=is_offline
				)
				# Load data for Termux distributions
				if distro_name in self.termux_distros_list_str:
					distributions[distro_name]._load_distro_data()
			except Exception as e:
				self.console.warning(f"Failed to initialize {distro_name}: {e}")

		return distributions

	def get_distribution(self, name: str) -> Optional[Distribution]:
		"""Get distribution by name"""
		return self.distributions.get(name.lower())

	def list_available(self) -> List[str]:
		"""List all available distributions"""
		return list(self.distributions.keys())

	def download(self, distro_name: str, file_name: str = None, distro_type: str = None) -> Optional[Any]:
		"""Download a distribution"""
		distro = self.get_distribution(distro_name)
		if not distro:
			raise ValueError(
				f"Distribution '{distro_name}' not supported. Available: {', '.join(self.list_available())}")

		# Set default type based on distribution
		if distro_type is None:
			if distro_name in self.termux_distros_list_str:
				distro_type = "stable"
			else:
				distro_type = "minimal"

		if distro_type not in distro.get_supported_types():
			raise ValueError(
				f"Type '{distro_type}' not supported for {distro_name}. Available: {', '.join(distro.get_supported_types())}")

		return distro.download(file_name, distro_type)

	def get_distribution_info(self, distro_name: str) -> Dict[str, Any]:
		"""Get information about a distribution"""
		distro = self.get_distribution(distro_name)
		if not distro:
			return {}

		return distro.get_display_info()

	def get_current_architecture(self) -> str:
		"""Get current system architecture"""
		return self.distributions['alpine']._get_architecture()

	def _get_arch_support_status(self, distro: Distribution) -> str:
		"""Get architecture support status for current machine"""
		current_arch = self.current_arch

		if distro.supports_architecture(current_arch):
			return f"✓ {current_arch}"
		else:
			# Get the supported architectures in standard format
			supported_standard = []
			display_info = distro.get_display_info()

			# For each distribution's supported arch, try to map it to standard name
			for distro_arch in display_info.get('supported_archs', []):
				# Simple mapping for common cases
				if distro_arch in ['aarch64', 'arm64']:
					supported_standard.append('arm64')
				elif distro_arch in ['armv7', 'armhf', 'arm']:
					supported_standard.append('arm')
				elif distro_arch in ['x86_64', 'amd64']:
					supported_standard.append('x86_64')
				elif distro_arch in ['x86', 'i386', 'i686']:
					supported_standard.append('x86')
				else:
					supported_standard.append(distro_arch)

			# Remove duplicates and sort
			supported_standard = sorted(list(set(supported_standard)))

			if supported_standard:
				return f"✗ {current_arch}\n[dim](supports: {', '.join(supported_standard)})[/dim]"
			return f"✗ {current_arch}"

	def list_distros(self, show_details: bool = False) -> None:
		"""Display available distributions in a professional table"""
		self.console.debug("Listing available distributions")

		# Filter only supported distributions
		supported_distros = {}
		for distro_name, distro in self.distributions.items():
			if distro.supports_architecture(self.current_arch):
				supported_distros[distro_name] = distro

		if not supported_distros:
			self.console.warning("No distributions available for your current architecture")
			return

		# Create table
		table = Table(title="🐧 Available Linux Distributions", box=box.ROUNDED)
		table.add_column("Name", style="cyan", no_wrap=True)  # Distribution name
		table.add_column("Distribution", style="green", no_wrap=True)  # Display name
		table.add_column("Type", style="magenta", no_wrap=True)
		table.add_column("Size", style="blue", no_wrap=True)

		for distro_name, distro in supported_distros.items():
			info = distro.get_display_info()
			supported_types = info.get('supported_types', [])

			# Add first row with distribution name
			first_type = supported_types[0] if supported_types else ""
			first_size = self._get_type_size(distro_name, distro, first_type)

			table.add_row(
				f"[bold]{distro_name}[/bold]",
				f"{info['name']}",
				f"• {first_type}" if first_type else "",
				first_size
			)

			# Add remaining types
			for distro_type in supported_types[1:]:  # All remaining types
				size = self._get_type_size(distro_name, distro, distro_type)
				table.add_row(
					"",  # Empty name
					"",  # Empty distribution display name
					f"• {distro_type}",
					size
				)

		self.console.print(table)

		# Additional information
		self.console.info(f"Current system architecture: [bold]{self.current_arch}[/bold]")
		self.console.info("Use: [cyan]androsh setup <name> [-d <distro_name>] [-t <type>][/cyan] to install")

	def _get_type_size(self, distro_name: str, distro: Distribution, distro_type: str) -> str:
		"""Get size for a specific distribution type"""
		try:
			if distro_name == "kali-nethunter":
				kali_arch = distro._map_architecture(self.current_arch)
				return distro.get_file_size(kali_arch, distro_type)
			elif distro_name == "alpine":
				alpine_arch = distro._map_architecture(self.current_arch)
				return distro.get_file_size(alpine_arch, distro_type)
			elif distro_name in self.termux_distros_list_str:
				# For Termux distros, show the single size
				size_map = {
					'arm64': '40-300MB',
					'arm': '40-300MB',
					'x86': '40-300MB',
					'x86_64': '40-300MB'
				}
				return size_map.get(self.current_arch, 'Unknown')
		except:
			pass
		return "Unknown"


	def get_all_distro_urls(self) -> Dict[str, Dict[str, str]]:
		"""Get all download URLs for supported distributions"""
		self.console.debug("Fetching all distribution download URLs")

		all_urls = {}

		for distro_name, distro in self.distributions.items():
			if not distro.supports_architecture(self.current_arch):
				continue

			try:
				distro_urls = {}
				mapped_arch = distro._map_architecture(self.current_arch)

				if hasattr(distro, 'distro_data') and distro.distro_data:
					# Termux distributions
					tarball_info = distro.distro_data.get('tarballs', {}).get(mapped_arch, {})
					if tarball_info.get('url'):
						distro_urls['stable'] = tarball_info['url']

				elif distro_name == "alpine":
					# Alpine distributions - get URLs for all flavors
					distro._load_alpine_metadata()
					if distro.metadata:
						for item in distro.metadata:
							if (item.get('arch') == mapped_arch and
									distro._is_tarball(item.get('file', ''))):
								flavor = item.get('flavor', 'unknown')
								url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{mapped_arch}/{item['file']}"
								distro_urls[flavor] = url

				elif distro_name == "kali-nethunter":
					# Kali distributions - get URLs for all types
					for distro_type in distro.get_supported_types():
						url = f"https://kali.download/nethunter-images/current/rootfs/kali-nethunter-rootfs-{distro_type}-{mapped_arch}.tar.xz"
						distro_urls[distro_type] = url

				if distro_urls:
					all_urls[distro_name] = distro_urls

			except Exception as e:
				self.console.warning(f"Failed to get URLs for {distro_name}: {e}")

		return all_urls


	def print_all_distro_urls(self) -> None:
		"""Print all distribution URLs in a formatted way"""
		urls = self.get_all_distro_urls()

		if not urls:
			self.console.warning("No distribution URLs found")
			return

		self.console.info("All Distribution Download URLs")
		self.console.info(f"Architecture: {self.current_arch}")
		self.console.print("")

		for distro_name, distro_urls in urls.items():
			distro = self.distributions[distro_name]
			info = distro.get_display_info()

			self.console.print(f"[bold cyan]{info['name']}[/bold cyan]")
			self.console.print(f"  Source: {info['source']}")

			for url_type, url in distro_urls.items():
				# Get file size if available
				size_info = ""
				if distro_name == "alpine":
					try:
						size = distro.get_file_size(self.current_arch, url_type)
						if size != "Unknown":
							size_info = f" - {size}"
					except:
						pass
				elif distro_name == "kali-nethunter":
					try:
						size = distro.get_file_size(self.current_arch, url_type)
						if size != "Unknown":
							size_info = f" - {size}"
					except:
						pass

				self.console.print(f"  • [yellow]{url_type}[/yellow]{size_info}")
				self.console.print(f"    [dim]{url}[/dim]")

			self.console.print("")