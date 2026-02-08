#!/usr/bin/env python -u
# coding: utf-8

import argparse
import os
import platform
import sys
import time

from Core import name
from Core.HiManagers import ADBFileManager, BusyBoxManager, PyFManager, Path
from Core.console import console, LogLevel, Table, box
from Core.db import DB
from Core.distro_manager import DistributionManager
from Core.downloader import FileDownloader
from Core.errors_handler import AndroSH_err
from Core.request import create_session
from Core.shizuku import Rish
from Core.template import template


class AndroSH:


	ARCH_MAPPING = {
		"arm64-v8a": "aarch64",
		"aarch64": "aarch64",
		"armeabi": "armhf",
		"armeabi-v7a": "armhf",
		"armhf": "armhf",
		"x86": "x86",
		"i686": "x86",
		"x86_64": "x86_64"
	}

	ASSETS_URLS = {
		"armhf": {
			"proot": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/arm/proot",
			"libtalloc.so.2": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/arm/libtalloc.so.2",
			"busybox": "https://github.com/ahmed-alnassif/busybox/raw/refs/heads/master/busybox-arm"
		},
		"aarch64": {
			"proot": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/aarch64/proot",
			"libtalloc.so.2": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/aarch64/libtalloc.so.2",
			"busybox": "https://github.com/ahmed-alnassif/busybox/raw/refs/heads/master/busybox-arm64"
		},
		"x86": {
			"proot": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/x86/proot",
			"libtalloc.so.2": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/x86/libtalloc.so.2",
			"busybox": "https://github.com/ahmed-alnassif/busybox/raw/refs/heads/master/busybox-x86"
		},
		"x86_64": {
			"proot": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/x86_64/proot",
			"libtalloc.so.2": "https://github.com/ahmed-alnassif/proot-bin/raw/refs/heads/main/x86_64/libtalloc.so.2",
			"busybox": "https://github.com/ahmed-alnassif/busybox/raw/refs/heads/master/busybox-x86_64"
		}
	}

	# BusyBox SHA512 checksums
	BUSYBOX_CHECKSUMS = {
		"armhf":   "bee9d333c3df0c368a1a226b0db81e2d8a13c603d997d570373579d9e6910f94df902d9753d97ffe596a8d1f91632608181fe2bf1833d857cd7fc0c18d32a6d9",
		"aarch64": "403c0a113140941d025b40e071cc48ea746a3401688f0a034f06e7b7a75fb82a586f211cd36c1e26f8cfeb053ba3c98ae75febe4ff657a870482982867e4fa32",
		"x86":     "5d001b73340972017185a0ce100bcad993a4bc6bb4ade181aa1cf0038ec9568b52008276a6044b8d78f9dc4f0ab73fff389bbe68c06af50f805c1bfdf067da62",
		"x86_64":  "2638541b434a3db8442e814724ab3f654668b2d75d0fbcb841ae52f4eff7c9b13303f6c461daeeaea1d3808ca6fad11775090a196dbfb7bb49203b97d66fbf95"
	}

	def __init__(self):

		# Configuration
		self.custom_rootfs = None
		self.custom_shell = "bash"
		self.hostname = name
		self.force_setup = False
		self.root = f"/data/local/tmp/{name}/distros"
		self.resources = f"/sdcard/Download/{name}"
		self.busybox_dir = f"/data/local/tmp/{name}/busybox"
		self.busybox_path = f"{self.busybox_dir}/busybox"
		self.assets_path = "Assets"
		self.wrapper_script = "AndroSH_wrapper.sh"
		self.distro_file = None
		self.proot = "proot"
		self.talloc = "libtalloc.so.2"
		self.sandbox_script = "proot.sh"
		self.launch_command = str()
		self.distro_type = "alpine-minirootfs"
		self.distro = "alpine"
		self.rootfs_dir = "rootfs"
		self.distros = [
							"alpine",
							"debian",
							"ubuntu",
							"kali-nethunter",
							"archlinux",
							"fedora",
							"void",
							"manjaro",
							"chimera"
						]


		parser = self._setup_argparse()
		args = parser.parse_args()
		self.resources = args.resources_dir
		self.time_style = args.time_style
		self.change_shell = args.chsh

		self.log_level = self._determine_log_level(args)
		self.console = console(self.log_level, self.time_style)

		# Initialize other components
		self.fm = PyFManager()
		self.db = DB()
		self.request = create_session()
		self.downloader = FileDownloader(self.console)
		self.rish = Rish(self.console, self.resources)
		self.adb = ADBFileManager(self.rish, self.console)
		self.distro_manager = DistributionManager(self.fm, self.downloader,
		                                          self.console, self.resources,
		                                          self.db, self.check_storage
		)


		# Initialize BusyBox manager
		self.busybox = BusyBoxManager(self.adb, self.console, self.busybox_dir)

		# State variables
		self.is_setup = False
		self.force_download = False
		self.distro_dir = None
		self.base_dir = self.root
		self.dir_name = name
		self.args = args

		self.console.banner()
		self.console.debug(f"AndroSH initialized with log_level={self.log_level}")
		self.console.verbose(f"Arguments: {vars(args)}")

		# Handle commands
		if hasattr(args, 'command') and args.command:
			self._handle_command(args)
		else:
			# Default behavior - launch existing distro or show help
			self.distro_dir = self.db.check()
			if self.distro_dir:
				self.launch()
			else:
				parser.print_help()
				sys.exit()

	def _determine_log_level(self, args) -> LogLevel:
		if args.quiet:
			return LogLevel.QUIET
		elif args.debug:
			return LogLevel.DEBUG
		elif args.verbose:
			return LogLevel.VERBOSE
		else:
			return LogLevel.NORMAL

	def _handle_command(self, args):
		self.console.debug(f"Executing command: {args.command}")

		if args.command == 'setup':
			self.setup_distro(args)
			self._execute_setup()
		elif args.command == 'remove':
			self.remove_distro(args)
		elif args.command == 'launch':
			self.launch_distro(args)
			self.launch()
		elif args.command == 'rish':
			self.rish_shell(args)
		elif args.command == 'clean':
			self.clean_distro(args)
		elif args.command == 'install':
			self.install_script(args)
		elif args.command == 'list':
			self.distro_manager.list_distros()
		elif args.command == 'lsd':
			self.list_distros(args)
		elif args.command == 'distro':
			self._handle_distro_command(args)
		elif args.command == 'download':
			self.download_distro(args)  # Direct download command

	def _handle_distro_command(self, args):
		"""Handle distro subcommands"""
		if args.distro_command == 'list':
			self.distro_manager.list_distros(getattr(args, 'details', False))
		elif args.distro_command == 'download':
			self.download_distro(args)
		elif args.distro_command == 'info':
			self.show_distro_info(args)
		elif args.distro_command == 'urls':
			self.distro_manager.print_all_distro_urls()

	def _setup_argparse(self) -> argparse.ArgumentParser:
		parser = argparse.ArgumentParser(
			description="AndroSH - Professional Multi-Distribution Linux Environments for Android",
			epilog="Complete Linux workstations with Android system integration - no root required"
		)

		subparsers = parser.add_subparsers(dest='command', help='Command to execute', required=False)

		# Setup command
		setup_parser = subparsers.add_parser('setup', help='Deploy a new Linux environment')
		setup_parser.add_argument('name', default=name,
		                          help=f'Environment name (default: {name})')
		setup_parser.add_argument("-f", "--rootfs",
		                          help="Custom rootfs file, when used you don't need to add -d/-t arguments", default=None)
		setup_parser.add_argument('-d', '--distro', default=self.distro,
		                          choices=self.distros,
		                          help=f'Linux distribution (default: {self.distro})')
		setup_parser.add_argument('-t', '--type', default=self.distro_type,
		                          help=f'Distribution variant (minimal, full, stable) - depends on distro (default: {self.distro_type})')
		setup_parser.add_argument('--hostname', default=name,
		                          help=f'Custom Hostname (default: {name})')
		setup_parser.add_argument('--resetup', action='store_true',
		                          help='Reinstall environment while preserving data')
		setup_parser.add_argument('--force', action='store_true',
		                          help='Force overwrite without confirmation')

		# Remove command
		remove_parser = subparsers.add_parser('remove', help='Remove an existing environment')
		remove_parser.add_argument('name', help='Name of the environment to remove')
		remove_parser.add_argument('--force', action='store_true',
		                           help='Force removal without confirmation')

		# Launch command
		launch_parser = subparsers.add_parser('launch', help='Start an existing environment')
		launch_parser.add_argument('name', help='Name of the environment to launch')
		launch_parser.add_argument("-c", "--command", dest="launch_command", help="launch command and exit", default="")

		# Rish command
		rish_parser = subparsers.add_parser('rish', help='Start adb shell/shizuku rish')
		rish_parser.add_argument("-c", "--command", dest="rish_command", help="launch command and exit", default="")


		# Clean command
		clean_parser = subparsers.add_parser('clean', help='Clean environment temporary files')
		clean_parser.add_argument('name', help='Environment name to clean')

		# Install command
		path = f"{Path(os.environ['PREFIX']) / 'bin'}" if os.environ.get("PREFIX") else None
		install_parser = subparsers.add_parser('install', help='Install for global system access')
		install_parser.add_argument('--path', default=path,
		                            help=f'Installation directory for global script (default: {path})')
		install_parser.add_argument('--name', default='androsh',
		                            help='Command name for global access (default: androsh)')

		# List command
		subparsers.add_parser('list', help='Show available distributions')
		subparsers.add_parser('lsd', help='List installed environments')

		# Download command
		download_parser = subparsers.add_parser('download', help='Download distribution files')
		download_parser.add_argument('distro',
		                             choices=self.distros,
		                             help='Distribution to download')
		download_parser.add_argument('--type', required=True,
		                             help='Distribution variant (required)')
		download_parser.add_argument('--file', '-f',
		                             help='Custom filename for downloaded archive')

		# Distro management command
		distro_parser = subparsers.add_parser('distro', help='Distribution management suite')
		distro_subparsers = distro_parser.add_subparsers(dest='distro_command', help='Distro subcommand', required=True)

		# distro list
		distro_list_parser = distro_subparsers.add_parser('list', help='List available distributions')
		distro_list_parser.add_argument('-d', '--details', action='store_true',
		                                help='Show detailed distribution information')

		# distro download
		distro_download_parser = distro_subparsers.add_parser('download', help='Download distribution')
		distro_download_parser.add_argument('distro_name',
		                                    choices=self.distros,
		                                    help='Name of the distribution')
		distro_download_parser.add_argument('--type', '-t',
		                                    help='Distribution variant (default depends on distro)')
		distro_download_parser.add_argument('--file', '-f',
		                                    help='Custom filename for the download')

		# distro info
		distro_info_parser = distro_subparsers.add_parser('info', help='Get distribution information')
		distro_info_parser.add_argument('distro_name',
		                                choices=self.distros,
		                                help='Name of the distribution')

		# distro urls
		distro_subparsers.add_parser('urls', help='Show download URLs')

		# Logging options
		log_group = parser.add_mutually_exclusive_group()
		log_group.add_argument('--verbose', '-v', action='store_true',
		                       help='Verbose output: detailed operation information')
		log_group.add_argument('--debug', '-d', action='store_true',
		                       help='Debug output: all operations including system commands')
		log_group.add_argument('--quiet', '-q', action='store_true',
		                       help='Quiet output: suppress non-essential information')

		# Global arguments
		parser.add_argument('--base-dir', default=self.root,
		                    help=f'Base directory for environments (default: {self.root})')
		parser.add_argument('--resources-dir', default=self.resources,
		                    help=f'Resources directory for downloads (default: {self.resources})')
		parser.add_argument("--time-style", action="store_true",
		                    help="Display time format")
		parser.add_argument("--chsh", default=None,
		                    help=f"Custom shell command (default: {self.custom_shell})")

		return parser

	def download_distro(self, args):
		"""Download a Linux distribution"""

		if hasattr(args, 'distro_name'):  # distro download command
			distro_name = args.distro_name
			distro_type = args.type
			file_name = args.file
		else:  # direct download command
			distro_name = args.distro
			distro_type = args.type
			file_name = getattr(args, 'file', None)

		try:
			self.console.info(f"Downloading {distro_name} ({distro_type})...")
			self.distro_manager.download(distro_name, file_name, distro_type)
			self.console.success(f"Successfully downloaded {distro_name}")

		except Exception as e:
			self.console.error(f"Failed to download {distro_name}: {e}")

	def show_distro_info(self, args):
		"""Show detailed information about a distribution"""
		info = self.distro_manager.get_distribution_info(args.distro_name)
		if info:
			self.console.table(info, f"Distribution Info: {args.distro_name}")
		else:
			self.console.error(f"Distribution '{args.distro_name}' not found")

	def architecture(self) -> str:
		self.console.debug("Detecting system architecture")
		machine_arch = platform.machine().lower()
		arch = self.ARCH_MAPPING.get(machine_arch)
		if arch == "x86":
			self.console.error("Sorry this architecture not supported right now.")
			sys.exit(1)

		if arch is None:
			message = f"Unknown architecture: {machine_arch}"
			self.console.error(message)
			raise AndroSH_err(message)

		self.console.verbose(f"Detected architecture: {machine_arch} -> {arch}")
		return arch

	def setup_busybox(self) -> bool:
		self.console.info("Setting up BusyBox")

		if not self.adb.mkdir(self.busybox_dir, parents=True):
			self.console.error(f"Failed to create BusyBox directory: {self.busybox_dir}")
			return False

		arch = self.architecture()
		busybox_url = self.ASSETS_URLS[arch]["busybox"]
		expected_hash = self.BUSYBOX_CHECKSUMS[arch]
		local_busybox_path = f"{self.resources}/busybox"

		if self.adb.exists(self.busybox_path):
			if self.adb.checksum(self.busybox_path) == expected_hash:
				self.console.info("BusyBox already installed")
				return True

		if not self.adb.exists(local_busybox_path):
			self.console.verbose(f"Downloading BusyBox for {arch}")
			self.downloader.download_file(busybox_url, local_busybox_path)

		actual_hash = self.fm.checksum(local_busybox_path) or \
		              self.adb.checksum(local_busybox_path)
		if actual_hash != expected_hash:
			self.console.warning("BusyBox checksum mismatch!")
			if not self.args.force:
				confirm = self.console.input(f"[?] BusyBox checksum doesn't match. Replace it? [cyan]\\[y/N]:[/cyan] ")
				if confirm.lower() != 'y':
					self.console.warning("Using existing BusyBox despite checksum mismatch")
				else:
					self.fm.remove(local_busybox_path) or \
					self.adb.remove(local_busybox_path)
					self.downloader.download_file(busybox_url, local_busybox_path)
			else:
				self.fm.remove(local_busybox_path) or \
				self.adb.remove(local_busybox_path)
				self.downloader.download_file(busybox_url, local_busybox_path)

		if not self.adb.copy(local_busybox_path, self.busybox_path):
			self.console.error("Failed to copy BusyBox to system location")
			return False

		if not self.adb.chmod(self.busybox_path, "755"):
			self.console.error("Failed to make BusyBox executable")
			return False

		# Test BusyBox
		if self.busybox.is_available():
			self.console.success("BusyBox setup completed successfully")
			return True
		else:
			self.console.error("BusyBox setup failed")
			return False

	def check_storage(self, path: str = "/sdcard/Download") -> None:
		self.console.debug(f"Checking storage path: {path}")

		if not (self.fm.exists(path) or
				self.adb.exists(path)):
			self.console.error(f"Storage path does not exist: {path}")
			sys.exit(1)

		if not (self.fm.is_dir(path) or
				self.adb.is_dir(path)):
			self.console.error(f"Storage path is not a directory: {path}")
			sys.exit(1)

		test_file = f"{path}/.androsh_test"
		test_content = "test"
		if not (self.fm.write_text(test_file, test_content) or
				self.adb.write(test_file, test_content)):
			self.console.error(f"Insufficient permissions for storage path: {path}")
			sys.exit(1)

		self.fm.remove(test_file) or \
		self.adb.remove(test_file)
		self.console.info(f"Storage path verified: {path}")

	def checksum(self, file_path: str, expected_hash: str, hash_type: str = "sha512") -> bool:
		self.console.debug(f"Verifying checksum for: {file_path}")


		actual_hash = self.fm.checksum(file_path, hash_type) or \
		self.busybox.checksum(file_path, hash_type)
		if actual_hash is None:
			actual_hash = self.adb.checksum(file_path, hash_type)

		if actual_hash is None:
			self.console.error(f"Failed to calculate checksum for: {file_path}")
			return False

		result = actual_hash == expected_hash
		if not result:
			self.console.status("The file is corrupt")
			self.console.debug(f"Checksum mismatch: expected={expected_hash[:16]}..., actual={actual_hash[:16]}...")
		else:
			self.console.verbose(f"Checksum verified: {file_path}")

		return result


	def download_assets(self) -> None:
		
		self.console.info("Downloading architecture-specific assets")
		arch = self.architecture()
		arch_assets = self.ASSETS_URLS.get(arch)

		if not arch_assets:
			self.console.error(f"No assets available for architecture: {arch}")
			return

		assets_to_download = []

		for asset_name, url in arch_assets.items():
			asset_path = f"{self.resources}/{asset_name}"
			if not (self.fm.exists(asset_path) or
					self.adb.exists(asset_path)):
				assets_to_download.append((url, asset_path))
				self.console.verbose(f"Asset needs download: {asset_name} -> {asset_path}")
			else:
				self.console.verbose(f"Asset already exists: {asset_name}")

		if assets_to_download:
			urls = [url for url, _ in assets_to_download]
			paths = [path for _, path in assets_to_download]
			self.console.info(f"Downloading {len(assets_to_download)} assets")
			self.downloader.download_multiple(urls, paths)
			self.console.verbose("Assets download completed")
		else:
			self.console.info("All assets already downloaded")

	def setup_sandbox(self) -> None:
		
		self.console.info("Starting machine setup process")

		if not self.setup_busybox():
			self.console.error("BusyBox setup failed, cannot continue")
			sys.exit(1)

		if not self.force_setup and self.busybox.exists(self.distro_dir):
			self.console.error(f"The distro directory already exists: {self.distro_dir}")
			sys.exit(1)

		bin = str(Path(self.distro_dir) / "bin")
		lib = str(Path(self.distro_dir) / "lib")
		self.console.verbose(f"Creating main directory: {self.distro_dir}")
		if not self.busybox.mkdir(self.distro_dir, parents=True):
			self.console.error(f"Failed to create directory: {self.distro_dir}")
			sys.exit(1)
		self.console.verbose(f"Creating a directory: {bin}")
		if not self.busybox.mkdir(bin, parents=True):
			self.console.error(f"Failed to create directory: {bin}")
			sys.exit(1)
		self.console.verbose(f"Creating a directory: {lib}")
		if not self.busybox.mkdir(lib, parents=True):
			self.console.error(f"Failed to create directory: {lib}")
			sys.exit(1)

		self.console.verbose("Copying assets to distro directory")
		for asset_file in [self.proot, self.talloc]:
			src_path = f"{Path(self.resources) / asset_file}"
			if asset_file == self.proot:
				asset_file = str(Path("bin") / asset_file)
			elif asset_file == self.talloc:
				asset_file = str(Path("lib") / asset_file)
			dst_path = f"{Path(self.distro_dir) / asset_file}"

			if not (self.fm.exists(src_path) or
					self.adb.exists(src_path)):
				self.console.error(f"Asset not found: {src_path}")
				sys.exit(1)

			if not self.busybox.copy(src_path, dst_path):
				self.console.error(f"Failed to copy asset: {src_path} -> {dst_path}")
				sys.exit(1)
			else:
				self.console.verbose(f"Copied asset: {asset_file}")

		proot = str(Path("bin") / self.proot)
		proot_path = f"{self.distro_dir / Path(proot)}"
		self.console.verbose(f"Making proot executable: {proot_path}")
		if not self.busybox.chmod(proot_path, "755"):
			self.console.error(f"Failed to make proot executable: {proot_path}")
			sys.exit(1)

		patched_dir = f"{self.distro_dir}/patched"
		self.console.verbose(f"Cleaning up patched directory: {patched_dir}")
		self.busybox.remove(patched_dir, recursive=True)

		linux_archive = f"{self.resources / Path(self.distro_file)}"
		linux_target = f"{self.distro_dir / Path(self.rootfs_dir)}"

		self.console.verbose(f"Creating Linux directory: {linux_target}")
		if not self.busybox.mkdir(linux_target, parents=True):
			self.console.error(f"Failed to create Linux directory: {linux_target}")
			sys.exit(1)

		self.console.verbose(f"Extracting {self.distro} rootfs: {linux_archive} -> {linux_target}")
		rootfs_len = 1
		if not self.busybox.tar_extract(linux_archive, linux_target):
			if self.busybox.tar_err and \
				"permission denied" in self.busybox.tar_err.lower():
					self.console.info("Rootfs with root permissions detected.")
					tmp = f"{linux_target / Path('tmp')}"
					self.busybox.mkdir(tmp, parents=True)
					self.busybox.proot_cmd = f"LD_LIBRARY_PATH={lib} PROOT_TMP_DIR={tmp} {proot_path} -0 "
					self.busybox.tar_err = None
					rootfs_len = 2
					if not self.busybox.tar_extract(linux_archive, linux_target):
						self.console.error(f"Failed to extract {self.distro} using Proot + BusyBox")
						sys.exit(1)
			elif "can't create node" in self.busybox.tar_err.lower():
				pass
			else:
				self.console.error(f"Failed to extract {self.distro} using BusyBox")
				sys.exit(1)

		list_dir = self.busybox.list_dir(linux_target, pattern="")
		distro_root = list_dir[0]
		distro_root_path = str(Path(linux_target) / distro_root)

		if len(list_dir) == rootfs_len:
			self.console.verbose(f"Distro patch: {list_dir}")
			content = " ".join([str(Path(distro_root_path) / _) for _ in self.busybox.list_dir(distro_root_path, pattern="")])
			self.busybox._run_command(f"sh -c 'for i in {content}; do mv $i {linux_target}; done'")
			self.busybox.remove(f"{distro_root_path}", recursive=True)
			self.console.verbose(f"Distro patch successful: {self.busybox.list_dir(linux_target)}")

		self.console.success("Sandbox setup completed successfully")

	def launch(self) -> None:
		self.console.divider()

		if not self.db.exists(self.distro_dir):
			self.console.warning(f"Distro '{self.rootfs_dir}' does not exist in {self.distro_dir}. Please setup first.")
			sys.exit(1)

		self.console.info("Starting up the machine")
		self.console.verbose(f"Distro path: {self.distro_dir}")

		self.console.verbose("Generating machine script")
		template(
			f"{Path(self.assets_path) / self.sandbox_script}",
			f"{Path(self.resources) / self.sandbox_script}",
			dir=self.distro_dir,
			distro=self.rootfs_dir,
			hostname=self.db.subget(self.distro_dir, "hostname") or name,
			chsh=self.change_shell or self.db.subget(self.distro_dir, "chsh") or self.custom_shell
		)

		sandbox_script = f"{Path(self.resources) / self.sandbox_script}"
		self.console.debug(f"Launching machine with script: {sandbox_script}")
		command = f"{sandbox_script} {self.launch_command}" if self.launch_command else sandbox_script
		self.rish.drun(command)

	def _execute_setup(self) -> None:
		self.console.divider()
		self.console.info("Starting setup process...")

		if not self.busybox.exists(self.root):
			self.console.verbose(f"{self.root} not exists trying to creating it")
			self.busybox.mkdir(self.root, parents=True)

		if self.custom_rootfs:
			self.console.info("Setting up using custom rootfs file")
			if not self.fm.exists(self.custom_rootfs):
				raise AndroSH_err("Custom rootfs file does not exist")
			self.distro_file = self.custom_rootfs
		self.console.info("Downloading distro and required resources:")
		if not self.custom_rootfs:
			self.distro_file = self.distro_manager.download(self.distro, distro_type=self.distro_type)
			if not self.distro_file:
				self.console.error(f"Failed to download distro: {self.distro_file}")
				sys.exit(1)
		self.download_assets()

		self.console.divider()

		self.setup_sandbox()

		self.console.verbose("Generating final machine script")
		template(
			f"{Path(self.assets_path) / self.sandbox_script}",
			f"{Path(self.resources) / self.sandbox_script}",
			dir=self.distro_dir,
			distro=self.rootfs_dir,
			hostname=self.hostname,
			chsh=self.change_shell
		)

		self.console.verbose("Updating database with distro information")
		self.db.update({
			self.distro_dir: {
				"name": self.dir_name,
				"hostname": self.hostname,
				"chsh": self.change_shell,
				"distro_dir": self.rootfs_dir,
				"distro": self.distro,
				"base_dir": self.base_dir,
				"date": time.strftime("%Y/%m/%d - %H:%M:%S"),
			}
		})

		self.db.setup(name=self.distro_dir)
		self.console.success("Setup completed successfully")
		self.console.info(f"Use: [cyan]androsh launch {self.dir_name}[/cyan] to launch the distro")

	def setup_distro(self, args) -> None:
		self.console.debug(f"Setup distro called with args: {vars(args)}")
		self.distro = "custom" if args.distro == self.distro and args.rootfs else args.distro
		self.distro_type = args.type
		self.distro_dir = f"{Path(args.base_dir) / args.name}"
		self.base_dir = args.base_dir
		self.dir_name = args.name if args.name else name
		self.is_setup = True
		self.force_setup = args.resetup
		self.hostname = args.hostname
		self.custom_rootfs = args.rootfs

		if args.verbose or args.debug:
			self.console.status(f"Setting up distro in {self.distro_dir}")

		if self.db.exists(self.distro_dir) and not args.resetup:
			self.console.warning(f"Distro '{self.distro_dir}' already exists. Use --resetup to reinstall.")
			sys.exit(1)

	def remove_distro(self, args) -> None:
		self.console.debug(f"Remove distro called with args: {vars(args)}")
		distro_dir = f"{Path(args.base_dir) / args.name}"

		if not self.db.exists(distro_dir) and not self.busybox.exists(distro_dir):
			self.console.error(f"Distro '{distro_dir}' does not exist.")
			sys.exit(1)

		if not args.force:
			confirm = self.console.input(f"Are you sure you want to remove '{distro_dir}'? [red]\\[y/N]:[/red] ")
			if confirm.lower() != 'y':
				self.console.warning("Removal cancelled.")
				sys.exit()

		self.console.info(f"Removing distro: {distro_dir}")

		self.busybox.chmod(distro_dir, 777, recursive=True)
		if not self.busybox.remove(distro_dir, recursive=True):
			self.console.error(f"Failed to remove distro: {distro_dir}")
			sys.exit(1)

		self.db.remove(distro_dir)
		self.console.success("Distro removed successfully")
		sys.exit()

	def launch_distro(self, args) -> None:
		self.console.debug(f"Launch distro called with args: {vars(args)}")
		self.distro_dir = f"{Path(args.base_dir) / args.name}"
		self.launch_command = args.launch_command

		if not self.db.exists(self.distro_dir):
			self.console.warning(f"Distro does not exist in {self.distro_dir}. Please setup first.")
			sys.exit(1)

		self.db.setup(name=self.distro_dir)

	def rish_shell(self, args) -> None:
		self.console.debug(f"Starting rish shell called with args: {vars(args)}")
		self.rish_command = args.rish_command
		if self.rish_command:
			self.rish.drun(f"-c {repr(self.rish_command)}")
		else:
			self.rish.drun("-c \"if command -v bash >/dev/null 2>&1; then exec bash; else exec sh; fi\"")


	def clean_distro(self, args) -> None:
		self.console.debug(f"Clean distro called with args: {vars(args)}")
		distro_dir = f"{Path(args.base_dir) / args.name}"

		if self.db.exists(distro_dir):
			self.console.info(f"Cleaning distro: {distro_dir}")

			if self.busybox.clean_dir(f"{distro_dir}/tmp"):
				self.console.success("Distro cleaned successfully")
			else:
				self.console.warning("No temporary files to clean or error occurred")
		else:
			self.console.error(f"Distro '{distro_dir}' does not exist.")

		sys.exit()

	def install_script(self, args) -> None:
		self.console.debug(f"Install script called with args: {vars(args)}")
		script_path = f"{Path(args.path) / args.name}"
		wrapper_script_path = f"{Path(self.assets_path) / self.wrapper_script}"
		absolute_path = os.path.realpath(__file__)
		path = os.path.dirname(absolute_path)
		main = os.path.basename(absolute_path)

		self.console.status(f"Installing global script to: {script_path}")
		self.console.verbose(f"Wrapper script: {wrapper_script_path}")
		self.console.verbose(f"Main script: {absolute_path}")

		template(
			wrapper_script_path,
			script_path,
			AndroSH=path,
			main=main
		)

		self.console.verbose(f"Setting permissions on local script: {script_path}")
		if not self.fm.chmod(script_path, 0o755):
			self.console.verbose(f"Setting permissions on device script: {script_path}")
			if not self.busybox.chmod(script_path, "755"):
				self.console.warning(f"Could not set permissions via BusyBox: {script_path}")
			else:
				return


		self.console.success(f"Command '[bold green]{args.name}[/bold green]' is now available globally")
		sys.exit()

	def list_distros(self, args) -> None:
		self.console.debug("Listing installed distros")
		distros = self.db.fetchall()

		# Filter only installed distros (paths that exist in base_dir)
		installed_distros = {}
		for key, value in distros.items():
			# Skip metadata and cache entries
			if any(key.startswith(prefix) for prefix in ['distro_', 'alpine_metadata_', 'kali_file_sizes', 'done']):
				continue

			# Check if it's a valid distro path
			if isinstance(value, dict) and 'name' in value and 'base_dir' in value:
				installed_distros[key] = value

		if not installed_distros:
			self.console.info("No distros installed yet")
			self.console.info("Use: [cyan]androsh setup <name>[/cyan] to install a distro")
			return

		table = Table(title="Installed Distros", box=box.ROUNDED)
		table.add_column("Name", style="cyan", no_wrap=True)
		table.add_column("Path", style="blue")
		table.add_column("Distribution", style="green")
		table.add_column("Installed", style="yellow")

		for path, info in installed_distros.items():
			name = info.get('name', 'Unknown')
			distro_type = info.get('distro', info.get('distro_dir', self.distro_dir))
			date = info.get('date', 'Unknown')

			table.add_row(
				f"[bold]{name}[/bold]",
				path,
				distro_type,
				date
			)

		self.console.print(table)

		# Additional info
		self.console.info(f"Total installed: [bold]{len(installed_distros)}[/bold] distros")
		self.console.info("Use: [cyan]androsh launch <name>[/cyan] or [cyan]<path>[/cyan] to launch a distro")
		self.console.info("Use: [cyan]androsh remove <name>[/cyan] or [cyan]<path>[/cyan] to remove a distro")


if __name__ == '__main__':
	c = console()
	try:
		main = AndroSH()
		c = main.console
	except KeyboardInterrupt:
		print()
		c.error("Operation cancelled by user")
		sys.exit(1)
	except Exception as e:
		c.error(f"Unexpected error: {e}")
		sys.exit(1)
