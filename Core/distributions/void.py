from Core.distributions.base import *

class VoidDistribution(DockerDistribution):
	IMAGE = "voidlinux/voidlinux"
	TAG = "latest"
	DISPLAY_NAME = "Void Linux"
	DESCRIPTION = "Void Linux (glibc) image (Docker Hub)."

	def get_name(self) -> str:
		return "void"
