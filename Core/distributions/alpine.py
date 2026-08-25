from Core.distributions.base import *

class AlpineDistribution(Distribution):

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
			resources: str, db, check_storage_func=None, **kwargs):
		super().__init__(fm, downloader, console, resources, db, check_storage_func, **kwargs)
		self.supported_archs = ['x86_64', 'x86', 'aarch64', 'armv7', 'armhf']
		self.available_flavors = {}
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

		if self.available_flavors:
			return

		arch = self._get_architecture()
		alpine_arch = self._map_architecture(arch)
		metadata_url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{alpine_arch}/latest-releases.yaml"

		try:
			self.is_offline()
			response = self.session.get(metadata_url)
			response.raise_for_status()
			self.metadata = yaml.safe_load(response.text)

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
			self.console.error(f"Failed to load Alpine metadata: {e}")
			raise

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
		return any(filename.endswith(ext) for ext in ['.tar.gz', '.tar.xz', '.img.gz'])

	def _get_flavor_info(self, distro_type: str) -> Dict[str, str]:
		self._load_alpine_metadata()
		return self.available_flavors.get(distro_type, {})

	def _find_metadata_for_flavor(self, arch: str, distro_type: str) -> Optional[Dict[str, Any]]:
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

		self._load_alpine_metadata()

		if distro_type not in self.available_flavors:
			raise ValueError(
				f"Type '{distro_type}' not supported for Alpine. Available: {', '.join(self.available_flavors.keys())}")

		flavor_info = self.available_flavors[distro_type]
		if not flavor_info.get('is_tarball', True):
			self.console.warning(f"Note: {distro_type} is an ISO image, not a tarball")

		distro_metadata = self._find_metadata_for_flavor(alpine_arch, distro_type)
		if not distro_metadata:
			raise ValueError(f"No download available for {distro_type} on architecture {arch}")

		if file_name is None:
			file_name = distro_metadata['file']

		self.console.info(f"Starting Alpine Linux ({flavor_info['title']}) download")

		file_path = f"{self.resources}/{file_name}"

		expected_hash = distro_metadata.get("sha512") or distro_metadata.get("sha256")
		hash_type = "sha512" if distro_metadata.get("sha512") else "sha256"

		if self.fm.exists(file_path):
			download_needed = False
			if expected_hash and\
			not self._verify_checksum(file_path, expected_hash, hash_type):
				self.console.warning(f"Checksum mismatch for [blue]{file_name}[/blue]")
				self.console.warning("File may be corrupted or tampered with.")
				download_needed = self.console.input("Do you want to download the file again? [cyan][Y|n]:[/cyan] ").strip().lower() in ["y", "yes"]
			if not download_needed:
				self.console.info(f"Alpine {distro_type} already downloaded")
				return file_name

		version = distro_metadata.get("version")
		if not version:
			raise Exception("The version hasn't been detected.")

		url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{alpine_arch}/{distro_metadata['file']}"

		file_size = self.get_file_size(alpine_arch, distro_type)
		if file_size != "Unknown":
			self.console.info(f"Download size: {file_size}")

		self.console.verbose(f"Download URL: {url}")
		self.console.verbose(f"Target file: {file_path}")

		try:
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			if expected_hash:
				if not self._verify_checksum(file_path, expected_hash, hash_type):
					self.console.warning("Checksum verification failed, retrying download")
					self.fm.remove(file_path)
					self.download(file_name, distro_type)
				else:
					self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download Alpine {distro_type}: {e}")
			raise

		return file_name
