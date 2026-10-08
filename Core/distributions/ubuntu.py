from Core.distributions.base import *

class UbuntuDistribution(DockerDistribution):
	IMAGE = "ubuntu"
	TAG = "rolling"
	DESCRIPTION = "Latest Ubuntu release (Docker Hub)."

	def get_name(self) -> str:
		return "ubuntu"

class UbuntuLTSDistribution(DockerDistribution):
	IMAGE = "ubuntu"
	TAG = "latest"

	def get_name(self) -> str:
		return "ubuntu-lts"

	def get_display_info(self) -> Dict[str, Any]:
		base_info = super().get_display_info()
		base_info.update({
			'name': 'Ubuntu LTS',
			'description': 'Latest LTS release.',
			'source': 'Docker Hub (ubuntu:latest)'
		})

		return base_info
