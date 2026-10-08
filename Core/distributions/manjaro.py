from Core.distributions.base import *

class ManjaroDistribution(DockerDistribution):
	IMAGE = "manjarolinux/base"
	TAG = "latest"
	DISPLAY_NAME = "Manjaro"
	DESCRIPTION = "Official Manjaro base image (Docker Hub)."

	def get_name(self) -> str:
		return "manjaro"
