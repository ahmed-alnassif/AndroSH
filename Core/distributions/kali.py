from Core.distributions.base import *

class KaliNethunterDistribution(Distribution):

	def __init__(self, fm: PyFManager, downloader: FileDownloader, console,
			resources: str, db, check_storage_func=None, **kwargs):
		super().__init__(fm, downloader, console, resources, db, check_storage_func, **kwargs)
		self.supported_archs = ['amd64', 'arm64', 'armhf', 'i386']
		self.supported_types = ["minimal", "nano", "full"]
		self.base_url = "https://kali.download/nethunter-images/current/rootfs"
		self.file_sizes = {}

	def get_name(self) -> str:
		return "kali-nethunter"

	def _map_architecture(self, arch: str) -> str:

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
				filename = match[0]
				size = match[2].strip()
				file_sizes[filename] = size

			self.console.verbose(f"Parsed {len(file_sizes)} file sizes from directory listing")

		except Exception as e:
			self.console.warning(f"Failed to parse HTML directory: {e}")

		return file_sizes

	def _fetch_file_sizes(self) -> Dict[str, str]:
		"""Fetch and parse the directory listing to get file sizes"""

		if self.file_sizes:
			return self.file_sizes

		try:
			self.is_offline()
			response = self.session.get(self.base_url + "/")
			response.raise_for_status()

			self.file_sizes = self._parse_html_directory(response.text)

			self.db.add("kali_file_sizes", self.file_sizes)

			return self.file_sizes

		except Exception as e:
			self.console.warning(f"Failed to fetch file sizes: {e}")
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
		checksums = self._get_checksums()

		pattern = f"kali-nethunter-*-rootfs-{distro_type}-{arch}.tar.xz"
		for filename in checksums.keys():
			if f"rootfs-{distro_type}-{arch}.tar.xz" in filename:
				return filename

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

		expected_filename = self._get_expected_filename(arch, distro_type)

		if file_name is None:
			file_name = expected_filename

		file_size = self.get_file_size(arch, distro_type)

		self.console.info(f"Starting Kali Nethunter ({distro_type}) download process")
		if file_size != "Unknown":
			self.console.info(f"Estimated download size: {file_size}")

		file_path = f"{self.resources}/{file_name}"

		if self.fm.exists(file_path):
			self.console.info("Kali Nethunter already downloaded")
			return file_name

		checksums = self._get_checksums()
		if not checksums:
			self.console.warning("Could not fetch checksums, downloading without verification")

		url = self._get_download_url(kali_arch, distro_type)
		self.console.verbose(f"Download URL: {url}")

		try:
			self.downloader.download_file(url, file_path)
			self.console.verbose(f"Download completed: {file_path}")

			if checksums and expected_filename in checksums:
				expected_hash = checksums[expected_filename]
				if not self._verify_checksum(file_path, expected_hash, "sha256"):
					self.console.warning("Checksum verification failed, retrying download")
					self.fm.remove(file_path)
					self.download(file_name, distro_type)
				else:
					self.console.verbose("Checksum verification passed")
			else:
				self.console.warning("Checksum verification skipped (no checksum available)")

		except Exception as e:
			self.console.error(f"Failed to download Kali Nethunter: {e}")
			raise

		return file_name
