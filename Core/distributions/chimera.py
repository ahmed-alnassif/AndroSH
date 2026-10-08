from Core.distributions.base import *

class ChimeraDistribution(DockerDistribution):
	IMAGE = "chimeralinux/chimera"
	TAG = "latest"
	DISPLAY_NAME = "Chimera Linux"
	DESCRIPTION = "Chimera Linux image (Docker Hub)."

	def get_supported_types(self) -> List[str]:
		return ["rolling"]

	def get_name(self) -> str:
		return "chimera"
