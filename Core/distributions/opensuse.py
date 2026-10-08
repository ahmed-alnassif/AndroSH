from Core.distributions.base import *

class OpenSUSE_Distribution(DockerDistribution):
	IMAGE = "opensuse/tumbleweed"
	TAG = "latest"
	DISPLAY_NAME = "openSUSE Tumbleweed"
	DESCRIPTION = "Rolling release (Docker Hub)."

	def get_supported_types(self) -> List[str]:
		return ["rolling"]

	def get_name(self) -> str:
		return "opensuse"
