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
from Core.distributions import *

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
			"void",
			"manjaro",
			"chimera",
			"opensuse",
			"debian-12",
			"ubuntu-lts",
			"fedora-42"
		]

		self.termux_distros_list = [
			DebianDistribution,
			UbuntuDistribution,
			ArchLinuxDistribution,
			FedoraDistribution,
			VoidDistribution,
			ManjaroDistribution,
			ChimeraDistribution,
			OpenSUSE_Distribution,
			DebianBookwormDistribution,
			UbuntuLTSDistribution,
			Fedora42Distribution
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

		is_offline = not self.is_connected()
		distributions = {}

		termux_distros = list(zip(self.termux_distros_list_str, self.termux_distros_list))

		direct_distros = [
			('alpine', AlpineDistribution),
			('kali-nethunter', KaliNethunterDistribution)
		]

		for distro_name, distro_class in termux_distros + direct_distros:
			try:
				distributions[distro_name] = distro_class(
					self.fm, self.downloader, self.console,
					self.resources, self.db, self.check_storage, is_offline=is_offline
				)

				if distro_name in self.termux_distros_list_str:
					distributions[distro_name]._load_distro_data()
			except Exception as e:
				self.console.warning(f"Failed to initialize {distro_name}: {e}")

		return distributions

	def get_distribution(self, name: str) -> Optional[Distribution]:
		return self.distributions.get(name.lower())

	def list_available(self) -> List[str]:
		return list(self.distributions.keys())

	def download(self, distro_name: str, file_name: str = None, distro_type: str = None) -> Optional[Any]:
		distro = self.get_distribution(distro_name)
		if not distro:
			raise ValueError(
				f"Distribution '{distro_name}' not supported. Available: {', '.join(self.list_available())}")

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
		distro = self.get_distribution(distro_name)
		if not distro:
			return {}

		return distro.get_display_info()

	def get_current_architecture(self) -> str:
		return self.distributions['alpine']._get_architecture()

	def _get_arch_support_status(self, distro: Distribution) -> str:
		current_arch = self.current_arch

		if distro.supports_architecture(current_arch):
			return f"✓ {current_arch}"
		else:
			supported_standard = []
			display_info = distro.get_display_info()

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

			supported_standard = sorted(list(set(supported_standard)))

			if supported_standard:
				return f"✗ {current_arch}\n[dim](supports: {', '.join(supported_standard)})[/dim]"
			return f"✗ {current_arch}"

	def list_distros(self, show_details: bool = False) -> None:
		self.console.debug("Listing available distributions")

		supported_distros = {}
		for distro_name, distro in self.distributions.items():
			if distro.supports_architecture(self.current_arch):
				supported_distros[distro_name] = distro

		if not supported_distros:
			self.console.warning("No distributions available for your current architecture")
			return

		if show_details:

			for distro_name, distro in supported_distros.items():
				info = distro.get_display_info()
				self.console.success(f"[bold cyan]{info['name']}[/bold cyan] ({distro_name})")
				self.console.info(f"  Description: {info.get('description', 'N/A')}")
				self.console.info(f"  Source: {info.get('source', 'N/A')}")
				self.console.info(f"  Architecture: {', '.join(info.get('supported_archs', []) or ['All'])}")

				supported_types = info.get('supported_types', [])
				if supported_types:
					self.console.info("  Available types:")
					for distro_type in supported_types:
						size = self._get_type_size(distro_name, distro, distro_type)
						self.console.info(f"    • {distro_type}: {size}")
				else:
					self.console.info("  Available types: None")
				self.console.divider()

			return

		table = Table(title="🐧 Available Linux Distributions", box=box.ROUNDED)
		table.add_column("Name", style="cyan", no_wrap=True)
		table.add_column("Distribution", style="green")
		table.add_column("Type", style="magenta", no_wrap=True)
		table.add_column("Size", style="blue")

		for distro_name, distro in supported_distros.items():
			info = distro.get_display_info()
			supported_types = info.get('supported_types', [])

			first_type = supported_types[0] if supported_types else ""
			first_size = self._get_type_size(distro_name, distro, first_type)

			table.add_row(
				f"[bold]{distro_name}[/bold]",
				f"{info['name']}",
				f"• {first_type}" if first_type else "",
				first_size
			)

			for distro_type in supported_types[1:]:
				size = self._get_type_size(distro_name, distro, distro_type)
				table.add_row(
					"",
					"",
					f"• {distro_type}",
					size
				)

		self.console.print(table)

		self.console.info(f"Current system architecture: [bold]{self.current_arch}[/bold]")
		self.console.info("Use: [cyan]androsh setup <name> [-d <distro_name>] [-t <type>][/cyan] to install")

	def _get_type_size(self, distro_name: str, distro: Distribution, distro_type: str) -> str:

		try:
			if distro_name == "kali-nethunter":
				kali_arch = distro._map_architecture(self.current_arch)
				return distro.get_file_size(kali_arch, distro_type)
			elif distro_name == "alpine":
				alpine_arch = distro._map_architecture(self.current_arch)
				return distro.get_file_size(alpine_arch, distro_type)
			elif distro_name in self.termux_distros_list_str:

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

		self.console.debug("Fetching all distribution download URLs")

		all_urls = {}

		for distro_name, distro in self.distributions.items():
			if not distro.supports_architecture(self.current_arch):
				continue

			try:
				distro_urls = {}
				mapped_arch = distro._map_architecture(self.current_arch)

				if hasattr(distro, 'distro_data') and distro.distro_data:
					tarball_info = distro.distro_data.get('tarballs', {}).get(mapped_arch, {})
					if tarball_info.get('url'):
						distro_urls['stable'] = tarball_info['url']

				elif distro_name == "alpine":
					distro._load_alpine_metadata()
					if distro.metadata:
						for item in distro.metadata:
							if (item.get('arch') == mapped_arch and
									distro._is_tarball(item.get('file', ''))):
								flavor = item.get('flavor', 'unknown')
								url = f"https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/{mapped_arch}/{item['file']}"
								distro_urls[flavor] = url

				elif distro_name == "kali-nethunter":
					for distro_type in distro.get_supported_types():
						url = f"https://kali.download/nethunter-images/current/rootfs/kali-nethunter-rootfs-{distro_type}-{mapped_arch}.tar.xz"
						distro_urls[distro_type] = url

				if distro_urls:
					all_urls[distro_name] = distro_urls

			except Exception as e:
				self.console.warning(f"Failed to get URLs for {distro_name}: {e}")

		return all_urls

	def print_all_distro_urls(self) -> None:
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
				self.console.print(f"	[dim]{url}[/dim]")

			self.console.print("")
