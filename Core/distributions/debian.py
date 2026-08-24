from Core.distributions.base import *

class DebianDistribution(TermuxDistribution):

	def get_name(self) -> str:
		return "debian"

	def _map_architecture(self, arch: str) -> str:
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

class DebianBookwormDistribution(TermuxDistribution):

	def get_name(self) -> str:
		return "debian-12"

	def _get_script_url(self) -> str:
		return "https://raw.githubusercontent.com/termux/proot-distro/v4.26.0/distro-plugins/debian.sh"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64',
			'x86': 'i686'
		}

		return termux_arch_map.get(arch, arch)

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Debian 12 (Bookworm)',
			'description': 'Stable release',
			'source': 'Termux/proot-distro v4.26.0'
		})

		return base_info
