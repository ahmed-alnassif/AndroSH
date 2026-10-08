from Core.distributions.base import *

class FedoraDistribution(DockerDistribution):
	IMAGE = "fedora"
	TAG = "latest"
	DISPLAY_NAME = "Fedora"
	DESCRIPTION = "Latest Fedora release (Docker Hub)."

	def get_supported_types(self) -> List[str]:
		return ["stable"]

	def get_name(self) -> str:
		return "fedora"

class FedoraLegacyDistribution(DockerDistribution):
	IMAGE = "fedora"
	TAG = "42"
	DISPLAY_NAME = "Fedora 42"
	DESCRIPTION = "Fedora 42 (older release, stable on Android 15+)."

	def get_supported_types(self) -> List[str]:
		return ["legacy"]

	def get_name(self) -> str:
		return "fedora-legacy"
