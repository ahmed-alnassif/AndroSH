import os
import time
import requests
from rich.progress import (
	Progress,
	BarColumn,
	DownloadColumn,
	TextColumn,
	TimeRemainingColumn,
	TransferSpeedColumn,
)
from rich.console import Console
from pathlib import Path
from Core.console import console
from Core.request import create_session

class FileDownloader:

	def __init__(self, custom_console = None):
		self.chunk_size = 8192
		self.console = Console()
		self.custom_console = custom_console if custom_console else console()
		self.session = create_session()

		self.progress = Progress(
			TextColumn(f"[cyan][{self.custom_console.time('STATUS')}][/cyan]"),
			BarColumn(bar_width=40),
			"[progress.percentage]{task.percentage:>3.1f}%",
			"•",
			DownloadColumn(),
			"•",
			TransferSpeedColumn(),
			"•",
			TimeRemainingColumn(),
			console=self.console,
			expand=True,
		)

	def download_file(self, url: str, destination: str = None):
		try:
			if destination is None:
				filename = url.split('/')[-1].split('?')[0]
				destination = filename
			else:
				if os.path.dirname(destination):
					os.makedirs(os.path.dirname(destination), exist_ok=True)
				filename = os.path.basename(destination)

			total_size = 0
			try:
				with self.session.head(url, timeout=10) as response:
					response.raise_for_status()
					total_size = int(response.headers.get('content-length', 0))
			except (requests.RequestException, ValueError):
				try:
					headers = {'Range': 'bytes=0-0'}
					with self.session.get(url, headers=headers, timeout=10, stream=True) as response:
						if response.status_code == 206:
							content_range = response.headers.get('content-range', '')
							if '/' in content_range:
								total_size = int(content_range.split('/')[-1])
				except (requests.RequestException, ValueError):
					total_size = 0

			self.custom_console.info(f"File name: [bold blue]{filename}[/bold blue]")
			self.progress.start()
			
			task_id = self.progress.add_task(
				"",
				total=total_size,
				start=False
			)

			with self.session.get(url, stream=True, timeout=30) as response:
				response.raise_for_status()

				if total_size == 0:
					total_size = int(response.headers.get('content-length', 0))
					self.progress.update(task_id, total=total_size)

				self.progress.start_task(task_id)

				with open(destination, 'wb') as file:
					for chunk in response.iter_content(chunk_size=self.chunk_size):
						if chunk:
							file.write(chunk)
							self.progress.update(task_id, advance=len(chunk))

			self.progress.stop()

			if total_size != 0 and os.path.getsize(destination) != total_size:
				self.custom_console.warning(f"[yellow]Warning: Downloaded file size doesn't match expected size[/yellow]")

			self.custom_console.success(f"[green]✓ Successfully downloaded [bold]{filename}[/bold][/green]")
			return destination

		except requests.exceptions.RequestException as e:
			self.progress.stop()
			self.custom_console.error(f"[red]Error downloading file: {e}[/red]")
			raise
		except IOError as e:
			self.progress.stop()
			self.custom_console.error(f"[red]Error saving file: {e}[/red]")
			raise
		except KeyboardInterrupt:
			self.progress.stop()
			raise
		except Exception as e:
			self.progress.stop()
			self.custom_console.error(f"[red]Unexpected error: {e}[/red]")
			raise

	def download_multiple(self, urls: list, destinations: list = None):

		if destinations is None:
			destinations = [None] * len(urls)

		results = []
		for url, destination in zip(urls, destinations):
			result = self.download_file(url, destination)
			results.append(result)

		return results
