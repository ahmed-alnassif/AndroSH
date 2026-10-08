from Core.distributions.base import *

class DebianDistribution(DockerDistribution):
	IMAGE = "debian"
	TAG = "latest"
	DISPLAY_NAME = "Debian"
	DESCRIPTION = "Latest Debian stable release (Docker Hub)."

	def get_supported_types(self) -> List[str]:
		return ["stable"]

	def get_name(self) -> str:
		return "debian"

class DebianBookwormDistribution(DockerDistribution):
	IMAGE = "debian"
	TAG = "bookworm"
	DISPLAY_NAME = "Debian 12 (Bookworm)"
	DESCRIPTION = "Stable release"

	def get_supported_types(self) -> List[str]:
		return ["stable"]

	def get_name(self) -> str:
		return "debian-12"

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Debian 12 (Bookworm)',
			'description': 'Stable release',
			'source': 'Docker Hub (debian:bookworm)'
		})

		return base_info
