import sys
from pathlib import Path
from rich.markup import escape
from Core.console import console
import subprocess
import shlex
import stat
import tempfile
import os


class Rish:

	def dex(self, dex_name: str = "rish_shizuku.dex") -> str:

		assets_path = Path(self.assets_path)
		dex_asset = assets_path / dex_name


		if self.resources:
			resources_path = Path(self.resources) / dex_name
			if resources_path.exists():
				dex_asset = resources_path


		dex_path = Path(tempfile.gettempdir()) / dex_name


		if not dex_path.exists():

			self.fm.copy(dex_asset, dex_path)

		if not dex_path.exists() or self.fm.checksum(dex_asset) != self.fm.checksum(dex_path):

			dex_path.chmod(stat.S_IWRITE)
			self.fm.remove(dex_path)


			self.fm.copy(str(dex_asset), str(dex_path))


		if dex_path.stat().st_mode & stat.S_IWUSR:
			dex_path.chmod(stat.S_IREAD)  # Set read-only

		return str(dex_path)
	
	def rish(self, command: list):
		env = os.environ.copy()
		if not os.environ.get("RISH_APPLICATION_ID") or self.app_id_bool:
			env['RISH_APPLICATION_ID'] = self.app_id
		
		result = subprocess.run(
			[
				"/system/bin/app_process",
				f"-Djava.class.path={self.dex()}",
				"/system/bin",
				"--nice-name=rish",
				"rikka.shizuku.shell.ShizukuShellLoader"
			] + command,
			capture_output=True,
			text=True,
			env=env,
			timeout=self.timeout
		)
		return result
	
	def run(self, command_string, timeout=None):
		self.timeout = timeout
		
		wrapped_cmd = f"{command_string} 2>&1; echo RISH_EXIT_CODE:$?"
		args = ['-c', wrapped_cmd]
		result = self.rish(args)
		
		output = result.stdout + result.stderr
		
		if 'RISH_EXIT_CODE:' in output:
			parts = output.split('RISH_EXIT_CODE:', 1)
			
			before = parts[0].rstrip()
			
			after = parts[1].strip()
	
			exit_code = 0
			if after:
				exit_code_str = after.split()[0]
				try:
					exit_code = int(exit_code_str)
				except ValueError:
					self.console.error(f"RISH_EXIT_CODE: {exit_code_str}")
					exit_code = 1
	
			if after and exit_code_str:
				rest_start = len(exit_code_str)
				rest = after[rest_start:].lstrip()
			else:
				rest = ""
	
			if before and rest:
				clean_output = f"{before}\n{rest}"
			elif before:
				clean_output = before
			else:
				clean_output = rest
	
		else:
			clean_output = output.rstrip()
			exit_code = 0
	
		result.returncode = exit_code
		result.stdout = clean_output if exit_code == 0 else ""
		result.stderr = clean_output if exit_code != 0 else ""
		
		#self.console.debug(f"_run_command result: {result}")
		
		return result

	def drun(self, command_string):

		env = os.environ.copy()
		if not os.environ.get("RISH_APPLICATION_ID") or self.app_id_bool:
			env['RISH_APPLICATION_ID'] = self.app_id

		self.console.debug(f"Executing: {command_string}")

		try:
			process = subprocess.Popen(
				[
					"/system/bin/app_process",
					f"-Djava.class.path={self.dex()}",
					"/system/bin",
					"--nice-name=rish",
					"rikka.shizuku.shell.ShizukuShellLoader",
				] + shlex.split(command_string),
				env=env,
				stdout=None,
				stderr=None,
				stdin=None
			)

			# Wait for completion
			returncode = process.wait()

			if returncode != 0:
				exit(returncode)

		except subprocess.TimeoutExpired:
			self.console.error("Command timed out")
			process.kill()
			exit(1)
		except Exception as e:
			self.console.error(f"Execution failed: {e}")
			exit(1)

	def check_rish(self):
		self.console.verbose("Checking rish application")
		result = self.run("id")
		self.console.debug(escape(repr(result)))
		if result.returncode != 0:
			self.console.error(f"[red]Failed to establish connection with Shizuku API[/red]: {escape(repr(result.stderr))}")
			self.console.print("")
			self.console.print("[yellow]ACTION REQUIRED[/yellow]")
			self.console.print("• Verify Shizuku service is currently running")
			self.console.print("• Navigate to Shizuku app → Terminal apps → Export files")
			self.console.print(f"• Ensure rish_shizuku.dex is placed in resources directory: {self.resources}")
			self.console.print("")
			self.console.print("[green]RESOLUTION[/green]")
			self.console.print("After completing these steps, re-execute your command")
			self.console.print("Ensure that your terminal for example Termux is allowed in Shiuku.")
			self.console.print("The connection issue should now be resolved")
			self.console.print("")
			self.console.print("[blue]NOTE[/blue] Use debug mode for detailed diagnostics: androsh --debug \\[command]")
			sys.exit(0)

	def __init__(self, console_instance = None,
		r_path = None,
		app_id: str = "com.termux",
		app_id_bool: bool = False):
		from Core.HiManagers import PyFManager
		self.console = console_instance if console_instance else console()
		self.resources = r_path
		self.assets_path = "Assets"
		self.app_id = app_id
		self.app_id_bool = app_id_bool
		self.timeout = None
		self.fm = PyFManager()
		self.check_rish()
