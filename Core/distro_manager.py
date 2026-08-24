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
		table.add_column("Distribution", style="green")  # Display name
		table.add_column("Type", style="magenta", no_wrap=True)
		table.add_column("Size", style="blue")

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
