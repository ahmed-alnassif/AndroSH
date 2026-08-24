from Core.distributions.base import *

class UbuntuDistribution(TermuxDistribution):

	def get_name(self) -> str:
		return "ubuntu"

	def _get_script_url(self) -> str:
		return "https://raw.githubusercontent.com/termux/proot-distro/v4.30.1/distro-plugins/ubuntu.sh"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64'
		}

		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)

class UbuntuLTSDistribution(TermuxDistribution):

	def get_name(self) -> str:
		return "ubuntu-lts"

	def _get_script_url(self) -> str:
		return "https://raw.githubusercontent.com/termux/proot-distro/v4.29.0/distro-plugins/ubuntu.sh"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'arm': 'arm',
			'x86_64': 'x86_64'
		}

		return termux_arch_map.get(arch, arch)

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Ubuntu 24.04 LTS (Noble)',
			'description': 'LTS release (Noble).',
			'source': 'Termux/proot-distro v4.29.0'
		})

		return base_info
