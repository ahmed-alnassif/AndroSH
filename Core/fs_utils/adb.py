from Core.fs_utils.imports import *

class ADBFileManager:
	def __init__(self, rish: Rish, console_instance):
		self.rish = rish
		self.console = console_instance

	def _run_command(self, command: str, timeout: Any = None) -> Any:
		try:
			return self.rish.run(command, timeout=timeout)
		except Exception as e:
			class MockResult:
				def __init__(self, error_msg):
					self.stdout = ""
					self.stderr = error_msg
					self.returncode = 1
			return MockResult(str(e))

	def _log_operation(self, operation: str, path: str, success: bool, details: str = ""):
		status = "✓" if success else "✗"
		message = f"ADB: {operation} {path} {status}"
		if details:
			message += f" - {details}"
		self.console.debug(message)

	def exists(self, path: str) -> bool:
		if not path or not path.strip():
			self._log_operation("exists", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -e {shlex.quote(path.strip())} && echo exists || echo missing")
			success = (result.returncode == 0 and "exists" in (result.stdout or ""))
			self._log_operation("exists", path, success)
			return success
		except Exception as e:
			self._log_operation("exists", path, False, f"exception: {e}")
			return False

	def is_file(self, path: str) -> bool:
		if not path or not path.strip():
			self._log_operation("is_file", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -f {shlex.quote(path.strip())} && echo file || echo not")
			success = (result.returncode == 0 and "file" in (result.stdout or ""))
			self._log_operation("is_file", path, success)
			return success
		except Exception as e:
			self._log_operation("is_file", path, False, f"exception: {e}")
			return False

	def is_dir(self, path: str) -> bool:
		if not path or not path.strip():
			self._log_operation("is_dir", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -d {shlex.quote(path.strip())} && echo dir || echo not")
			success = (result.returncode == 0 and "dir" in (result.stdout or ""))
			self._log_operation("is_dir", path, success)
			return success
		except Exception as e:
			self._log_operation("is_dir", path, False, f"exception: {e}")
			return False

	def mkdir(self, path: str, parents: bool = False) -> bool:
		if not path or not path.strip():
			self._log_operation("mkdir", path or "empty", False, "empty path")
			return False

		try:
			cmd = f"mkdir {'-p ' if parents else ''}{shlex.quote(path.strip())}"
			result = self._run_command(cmd)
			success = result.returncode == 0
			self._log_operation("mkdir", path, success, f"parents={parents}")
			return success
		except Exception as e:
			self._log_operation("mkdir", path, False, f"exception: {e}")
			return False

	def remove(self, path: str, recursive: bool = False, force: bool = False) -> bool:
		if not path or not path.strip():
			self._log_operation("remove", path or "empty", False, "empty path")
			return False

		try:
			flags = ""
			if recursive:
				flags += "r"
			if force:
				flags += "f"
			cmd = f"rm {'-' + flags + ' ' if flags else ''}{shlex.quote(path.strip())}"
			result = self._run_command(cmd)
			success = result.returncode == 0
			self._log_operation("remove", path, success, f"recursive={recursive}, force={force}")
			return success
		except Exception as e:
			self._log_operation("remove", path, False, f"exception: {e}")
			return False

	def copy(self, src: str, dst: str, recursive: bool = False) -> bool:
		if not src or not dst or not src.strip() or not dst.strip():
			self._log_operation("copy", f"{src} -> {dst}", False, "empty source or destination")
			return False

		try:
			cmd = f"cp {'-r ' if recursive else ''}{shlex.quote(src.strip())} {shlex.quote(dst.strip())}"
			result = self._run_command(cmd)
			success = result.returncode == 0
			self._log_operation("copy", f"{src} -> {dst}", success, f"recursive={recursive}")
			return success
		except Exception as e:
			self._log_operation("copy", f"{src} -> {dst}", False, f"exception: {e}")
			return False

	def chmod(self, path: str, mode: str, recursive: bool = False) -> bool:
		if not path or not path.strip():
			self._log_operation("chmod", path or "empty", False, "empty path")
			return False

		try:
			cmd = f"chmod {'-R ' if recursive else ''}{mode} {shlex.quote(path.strip())}"
			result = self._run_command(cmd)
			success = result.returncode == 0
			self._log_operation("chmod", path, success, f"mode={mode}, recursive={recursive}")
			return success
		except Exception as e:
			self._log_operation("chmod", path, False, f"exception: {e}")
			return False

	def read(self, path: str) -> Optional[str]:
		if not path or not path.strip():
			self._log_operation("read", path or "empty", False, "empty path")
			return None

		try:
			result = self._run_command(f"cat {shlex.quote(path.strip())}")
			if result.stdout:
				success = True
				content = result.stdout
			else:
				success = False
				content = None

			self._log_operation("read", path, success, f"chars_read={len(content) if success else 0}")
			return content if success else None
		except Exception as e:
			self._log_operation("read", path, False, f"exception: {e}")
			return None

	def write(self, path: str, content: str) -> bool:
		if not path or not path.strip():
			self._log_operation("write", path or "empty", False, "empty path")
			return False

		try:
			escaped_content = content.replace("'", "'\"'\"'")
			cmd = f"echo '{escaped_content}' > {shlex.quote(path.strip())}"
			result = self._run_command(cmd)
			success = result.returncode == 0
			self._log_operation("write", path, success, f"chars_written={len(content)}")
			return success
		except Exception as e:
			self._log_operation("write", path, False, f"exception: {e}")
			return False

	def list_dir(self, path: str) -> List[str]:
		if not path or not path.strip():
			self._log_operation("list_dir", path or "empty", False, "empty path")
			return []

		try:
			result = self._run_command(f"ls -1 {shlex.quote(path.strip())} 2>/dev/null || echo")
			output = result.stdout or ""
			items = [item for item in output.splitlines() if item.strip()]
			self._log_operation("list_dir", path, True, f"items_count={len(items)}")
			return items
		except Exception as e:
			self._log_operation("list_dir", path, False, f"exception: {e}")
			return []

	def checksum(self, path: str, hash_type: str = "sha512") -> Optional[str]:
		if not path or not path.strip():
			self._log_operation("checksum", path or "empty", False, "empty path")
			return None

		try:
			result = self._run_command(f"{hash_type}sum {shlex.quote(path.strip())} 2>/dev/null")
			output = result.stdout or ""

			if result.returncode == 0 and output:
				parts = output.split()
				if parts:
					checksum = parts[0]
					self._log_operation("checksum", path, True, f"type={hash_type}, result={checksum}")
					return checksum

			if hash_type != "md5":
				result = self._run_command(f"md5sum {shlex.quote(path.strip())} 2>/dev/null")
				output = result.stdout or ""
				if result.returncode == 0 and output:
					parts = output.split()
					if parts:
						checksum = parts[0]
						self._log_operation("checksum", path, True, f"type=md5 (fallback), result={checksum}")
						return checksum

			self._log_operation("checksum", path, False, f"type={hash_type}")
			return None
		except Exception as e:
			self._log_operation("checksum", path, False, f"exception: {e}")
			return None
