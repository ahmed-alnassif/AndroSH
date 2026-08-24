from Core.distributions.base import *

class FedoraDistribution(TermuxDistribution):

	def get_name(self) -> str:
		return "fedora"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'x86_64': 'x86_64'
		}

		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)

class Fedora42Distribution(TermuxDistribution):

	def get_name(self) -> str:
		return "fedora-42"

	def _get_script_url(self) -> str:
		return "https://raw.githubusercontent.com/termux/proot-distro/v4.25.0/distro-plugins/fedora.sh"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'x86_64': 'x86_64'
		}

		return termux_arch_map.get(arch, arch)

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Fedora 42',
			'description': 'Version 42 (stable on Android 15+).',
			'source': 'Termux/proot-distro v4.25.0'
		})

		return base_info
