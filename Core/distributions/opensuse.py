from Core.distributions.base import *

class OpenSUSE_Distribution(TermuxDistribution):

	def get_name(self) -> str:
		return "opensuse"

	def _map_architecture(self, arch: str) -> str:
		termux_arch_map = {
			'arm64': 'aarch64',
			'x86_64': 'x86_64'
		}

		return termux_arch_map.get(arch, arch)

	def supports_architecture(self, arch: str) -> bool:
		termux_arch = self._map_architecture(arch)
		return super().supports_architecture(termux_arch)
