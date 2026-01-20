import requests
import os
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
import time
from Core.console import console

class FileDownloader:
	def __init__(self, custom_console = None):
		self.chunk_size = 8192  # 8KB chunks
		self.console = Console()
		self.custom_console = custom_console if custom_console else console()
		
		# Configure the progress display - FIXED layout
		self.progress = Progress(
			#TextColumn("[bold blue]{task.fields[filename]}"),
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
		"""
		Download a file with a rich progress bar
		
		Args:
			url (str): URL of the file to download
			destination (str, optional): Path to save the file. If None, uses the filename from URL
			
		Returns:
			str: Path to the downloaded file or None if failed
		"""
		try:
			# Get filename from URL if destination not provided
			if destination is None:
				filename = url.split('/')[-1].split('?')[0]  # Remove query params
				destination = filename
			else:
				# Ensure destination directory exists
				if os.path.dirname(destination):
					os.makedirs(os.path.dirname(destination), exist_ok=True)
				filename = os.path.basename(destination)
			
			# Some servers block HEAD requests, so we'll try GET with stream and range 0-0
			total_size = 0
			try:
				# Try HEAD first
				with requests.head(url, timeout=10) as response:
					response.raise_for_status()
					total_size = int(response.headers.get('content-length', 0))
			except (requests.RequestException, ValueError):
				# If HEAD fails or no content-length, try Range request
				try:
					headers = {'Range': 'bytes=0-0'}
					with requests.get(url, headers=headers, timeout=10, stream=True) as response:
						if response.status_code == 206:  # Partial Content
							content_range = response.headers.get('content-range', '')
							if '/' in content_range:
								total_size = int(content_range.split('/')[-1])
				except (requests.RequestException, ValueError):
					# If we can't get file size, we'll download without known total
					total_size = 0
			
			self.custom_console.info(f"File name: [bold blue]{filename}[/bold blue]")
			# Start the progress display
			self.progress.start()
			
			# Create download task - FIXED: removed description that showed "bytes"
			task_id = self.progress.add_task(
				"",  # Empty description to avoid showing "download"
				#filename=filename, 
				total=total_size,
				start=False
			)
			
			# Download the file
			with requests.get(url, stream=True, timeout=30) as response:
				response.raise_for_status()
				
				# If we couldn't get size from HEAD, try from GET headers
				if total_size == 0:
					total_size = int(response.headers.get('content-length', 0))
					self.progress.update(task_id, total=total_size)
				
				# Start the task (shows the progress bar)
				self.progress.start_task(task_id)
				
				with open(destination, 'wb') as file:
					for chunk in response.iter_content(chunk_size=self.chunk_size):
						if chunk:
							file.write(chunk)
							self.progress.update(task_id, advance=len(chunk))
			
			# Complete the task
			self.progress.stop()
			
			# Verify file size if we knew the expected size
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
		except Exception as e:
			self.progress.stop()
			self.custom_console.error(f"[red]Unexpected error: {e}[/red]")
			raise
	
	def download_multiple(self, urls: list, destinations: list = None):
		"""
		Download multiple files with concurrent progress bars
		
		Args:
			urls (list): List of URLs to download
			destinations (list, optional): List of destination paths
		"""
		if destinations is None:
			destinations = [None] * len(urls)
		
		results = []
		for url, destination in zip(urls, destinations):
			result = self.download_file(url, destination)
			results.append(result)
		
		return results