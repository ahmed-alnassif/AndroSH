from Core.distributions.base import *

class ArchLinuxDistribution(DockerDistribution):
	IMAGE = "archlinux"
	TAG = "latest"
	DISPLAY_NAME = "Arch Linux"
	DESCRIPTION = "Official Arch Linux base image (Docker Hub)."

	def get_name(self) -> str:
		return "archlinux"
