from Core.distributions.base import *

class ArchLinuxDistribution(DockerDistribution):
	IMAGE = "archlinux"
	TAG = "latest"
	DISPLAY_NAME = "Arch Linux"
	DESCRIPTION = "Official Arch Linux base image (Docker Hub)."

	def get_supported_types(self) -> List[str]:
		return ["rolling"]

	def get_name(self) -> str:
		return "archlinux"

class ArchLinuxARMDistribution(Distribution):
	"""Official Arch Linux ARM rootfs (direct download, md5 verified)."""

	BASE_URLS = [
		"https://de3.mirror.archlinuxarm.org/os",
		"https://de.mirror.archlinuxarm.org/os",
		"http://os.archlinuxarm.org/os",
	]
	TARBALLS = {'arm64': 'ArchLinuxARM-aarch64-latest.tar.gz'}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.distro_data: Dict[str, Any] = {
			'name': 'Arch Linux ARM',
			'comment': 'Official Arch Linux ARM rootfs for arm64.',
			'tarballs': {}
		}

	def get_name(self) -> str:
		return "archlinux-arm64"

	def _map_architecture(self, arch: str) -> str:
		return arch

	def supports_architecture(self, arch: str) -> bool:
		return arch in self.TARBALLS

	def get_supported_types(self) -> List[str]:
		return ["rolling"]

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': self.distro_data['name'],
			'description': self.distro_data['comment'],
			'supported_archs': list(self.TARBALLS.keys()),
			'source': 'Arch Linux ARM (os.archlinuxarm.org)'
		})
		return base_info

	def get_size(self, arch: str) -> str:
		return "Unknown"

	def _load_distro_data(self) -> None:
		for arch, file in self.TARBALLS.items():
			urls = [f"{base}/{file}" for base in self.BASE_URLS]
			info = {'urls': urls, 'url': urls[-1], 'file': file, 'md5': None}
			for url in urls:
				try:
					self.is_offline()
					response = self.session.get(f"{url}.md5", timeout=15)
					response.raise_for_status()
					info['md5'] = response.text.split()[0].strip().lower()
					info['urls'] = [url] + [u for u in urls if u != url]
					info['url'] = url
					break
				except Offline_err:
					break
				except Exception as e:
					self.console.verbose(f"Mirror failed for {url}: {e}")
			self.distro_data['tarballs'][arch] = info

	def download(self, file_name: str = None, distro_type: str = "rolling") -> Optional[Any]:
		if self.check_storage:
			self.check_storage()

		arch = self._get_architecture()
		if not self.supports_architecture(arch):
			raise ValueError(f"Architecture {arch} not supported for {self.get_name()}. Available: {', '.join(self.TARBALLS)}")

		info = self.distro_data['tarballs'].get(arch)
		if not info:
			self._load_distro_data()
			info = self.distro_data['tarballs'][arch]

		file_name = file_name or info['file']
		file_path = f"{self.resources}/{file_name}"
		expected_hash = info.get('md5')

		self.console.info(f"Starting {self.distro_data['name']} download")

		if self.fm.exists(file_path):
			download_needed = False
			if expected_hash and not self._verify_checksum(file_path, expected_hash, "md5"):
				self.console.warning(f"Checksum mismatch for [blue]{file_name}[/blue]")
				download_needed = self.console.input("Do you want to download the file again? [cyan][Y|n]:[/cyan] ").strip().lower() in ["y", "yes"]
			if not download_needed:
				self.console.info(f"{self.distro_data['name']} already downloaded")
				return file_name

		last_error = None
		for url in info['urls']:
			self.console.verbose(f"Download URL: {url}")
			try:
				self.downloader.download_file(url, file_path)
				break
			except Exception as e:
				last_error = e
				self.console.warning(f"Mirror failed, trying the next one: {url}")
		else:
			self.console.error(f"Failed to download {self.distro_data['name']}: {last_error}")
			raise last_error

		if expected_hash:
			if not self._verify_checksum(file_path, expected_hash, "md5"):
				self.fm.remove(file_path)
				raise ValueError("Checksum verification failed, the file was removed. Try again.")
		else:
			self.console.warning("Checksum verification skipped (no checksum available)")

		return file_name
