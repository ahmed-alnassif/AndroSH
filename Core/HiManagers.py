import hashlib
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Union, List, Optional, Generator, Dict, Any

from Core.shizuku import Rish


class ADBFileManager:
	"""ADB/Rish level file management operations with enhanced logging and error handling"""

	def __init__(self, rish: Rish, console_instance):
		self.rish = rish
		self.console = console_instance

	def _run_command(self, command: str, timeout: int = 30) -> Any:
		"""Run command with proper quoting and timeout"""
		try:
			return self.rish.run(f"-c {repr(command)}", timeout=timeout)
		except Exception as e:
			# Return a mock result object for consistency
			class MockResult:
				def __init__(self, error_msg):
					self.stdout = ""
					self.stderr = error_msg
					self.returncode = 1

			return MockResult(str(e))

	def _log_operation(self, operation: str, path: str, success: bool, details: str = ""):
		"""Log file operations with proper escaping"""
		status = "✓" if success else "✗"
		message = f"ADB: {operation} {path} {status}"
		if details:
			message += f" - {details}"
		self.console.debug(message)

	def _get_output(self, result) -> str:
		"""Get output from result, checking both stdout and stderr"""
		output = ""
		if hasattr(result, 'stdout') and result.stdout:
			output += result.stdout.strip()
		if hasattr(result, 'stderr') and result.stderr:
			# Only append stderr if it doesn't look like an actual error
			stderr_text = result.stderr.strip()
			if stderr_text and not any(error_indicator in stderr_text.lower()
			                           for error_indicator in ['error', 'failed', 'permission denied', 'no such file']):
				if output:
					output += " " + stderr_text
				else:
					output = stderr_text
		return output

	def exists(self, path: str) -> bool:
		"""Check if path exists"""
		if not path or not path.strip():
			self._log_operation("exists", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -e {repr(path.strip())} && echo exists || echo missing")
			output = self._get_output(result)
			success = "exists" in output
			self._log_operation("exists", path, success, f"output={output}")
			return success
		except Exception as e:
			self._log_operation("exists", path, False, f"exception: {e}")
			return False

	def is_file(self, path: str) -> bool:
		"""Check if path is a file"""
		if not path or not path.strip():
			self._log_operation("is_file", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -f {repr(path.strip())} && echo file || echo not_file")
			output = self._get_output(result)
			success = "file" in output
			self._log_operation("is_file", path, success, f"output={output}")
			return success
		except Exception as e:
			self._log_operation("is_file", path, False, f"exception: {e}")
			return False

	def is_dir(self, path: str) -> bool:
		"""Check if path is a directory"""
		if not path or not path.strip():
			self._log_operation("is_dir", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"test -d {repr(path.strip())} && echo dir || echo not_dir")
			output = self._get_output(result)
			success = "dir" in output
			self._log_operation("is_dir", path, success, f"output={output}")
			return success
		except Exception as e:
			self._log_operation("is_dir", path, False, f"exception: {e}")
			return False

	def mkdir(self, path: str, parents: bool = False) -> bool:
		"""Create directory"""
		if not path or not path.strip():
			self._log_operation("mkdir", path or "empty", False, "empty path")
			return False

		try:
			cmd = f"mkdir {'-p ' if parents else ''}{repr(path.strip())}"
			result = self._run_command(cmd)
			# Check both stdout and stderr for success indicators
			output = self._get_output(result)
			# mkdir success when no error output OR when directory already exists and parents=True
			success = (not result.stderr or
			           ("File exists" in result.stderr and parents) or
			           "exists" in output)
			self._log_operation("mkdir", path, success, f"parents={parents}, output={output}")
			return success
		except Exception as e:
			self._log_operation("mkdir", path, False, f"exception: {e}")
			return False

	def remove(self, path: str, recursive: bool = False) -> bool:
		"""Remove file or directory"""
		if not path or not path.strip():
			self._log_operation("remove", path or "empty", False, "empty path")
			return False

		try:
			cmd = f"rm {'-rf ' if recursive else '-f '}{repr(path.strip())}"
			result = self._run_command(cmd)
			# rm success when no error output OR when file doesn't exist (already removed)
			success = (not result.stderr or
			           "No such file" in result.stderr or
			           "not found" in result.stderr.lower())
			self._log_operation("remove", path, success, f"recursive={recursive}, stderr={result.stderr}")
			return success
		except Exception as e:
			self._log_operation("remove", path, False, f"exception: {e}")
			return False

	def copy(self, src: str, dst: str) -> bool:
		"""Copy file"""
		if not src or not dst or not src.strip() or not dst.strip():
			self._log_operation("copy", f"{src} -> {dst}", False, "empty source or destination")
			return False

		try:
			result = self._run_command(f"cp {repr(src.strip())} {repr(dst.strip())}")
			success = not result.stderr or "exists" in result.stderr
			self._log_operation("copy", f"{src} -> {dst}", success, f"stderr={result.stderr}")
			return success
		except Exception as e:
			self._log_operation("copy", f"{src} -> {dst}", False, f"exception: {e}")
			return False

	def chmod(self, path: str, mode: str) -> bool:
		"""Change file permissions"""
		if not path or not path.strip():
			self._log_operation("chmod", path or "empty", False, "empty path")
			return False

		try:
			result = self._run_command(f"chmod {mode} {repr(path.strip())}")
			success = not result.stderr
			self._log_operation("chmod", path, success, f"mode={mode}, stderr={result.stderr}")
			return success
		except Exception as e:
			self._log_operation("chmod", path, False, f"exception: {e}")
			return False

	def read(self, path: str) -> Optional[str]:
		"""Read file content"""
		if not path or not path.strip():
			self._log_operation("read", path or "empty", False, "empty path")
			return None

		try:
			result = self._run_command(f"cat {repr(path.strip())}")
			# For read operations, we want to return content even if there's stderr
			# as long as we got some stdout content
			if result.stdout:
				success = True
				content = result.stdout
			else:
				success = False
				content = None

			self._log_operation("read", path, success,
			                    f"chars_read={len(content) if success else 0}, stderr={result.stderr}")
			return content if success else None
		except Exception as e:
			self._log_operation("read", path, False, f"exception: {e}")
			return None

	def write(self, path: str, content: str) -> bool:
		"""Write content to file"""
		if not path or not path.strip():
			self._log_operation("write", path or "empty", False, "empty path")
			return False

		try:
			# More robust content escaping
			escaped_content = content.replace("'", "'\"'\"'")
			cmd = f"echo '{escaped_content}' > {repr(path.strip())}"
			result = self._run_command(cmd)
			success = not result.stderr
			self._log_operation("write", path, success,
			                    f"chars_written={len(content)}, stderr={result.stderr}")
			return success
		except Exception as e:
			self._log_operation("write", path, False, f"exception: {e}")
			return False

	def list_dir(self, path: str) -> List[str]:
		"""List directory contents"""
		if not path or not path.strip():
			self._log_operation("list_dir", path or "empty", False, "empty path")
			return []

		try:
			result = self._run_command(f"ls -1 {repr(path.strip())} 2>/dev/null || echo")
			# Combine both stdout and stderr for directory listing
			output = self._get_output(result)
			items = [item for item in output.splitlines() if item.strip()]
			self._log_operation("list_dir", path, True, f"items_count={len(items)}")
			return items
		except Exception as e:
			self._log_operation("list_dir", path, False, f"exception: {e}")
			return []

	def checksum(self, path: str, hash_type: str = "sha512") -> Optional[str]:
		"""Calculate file checksum"""
		if not path or not path.strip():
			self._log_operation("checksum", path or "empty", False, "empty path")
			return None

		try:
			# Try the requested hash type first
			result = self._run_command(f"{hash_type}sum {repr(path.strip())} 2>/dev/null || echo")
			output = self._get_output(result)

			if output and not any(error_indicator in result.stderr.lower()
			                      for error_indicator in ['error', 'failed', 'not found']
			                      if result.stderr):
				parts = output.split()
				if parts:
					checksum = parts[0]
					self._log_operation("checksum", path, True, f"type={hash_type}, result={checksum[:16]}...")
					return checksum

			# Fallback to md5sum if requested type fails
			if hash_type != "md5":
				result = self._run_command(f"md5sum {repr(path.strip())} 2>/dev/null || echo")
				output = self._get_output(result)
				if output and not any(error_indicator in result.stderr.lower()
				                      for error_indicator in ['error', 'failed', 'not found']
				                      if result.stderr):
					parts = output.split()
					if parts:
						checksum = parts[0]
						self._log_operation("checksum", path, True, f"type=md5 (fallback), result={checksum[:16]}...")
						return checksum

			self._log_operation("checksum", path, False, f"type={hash_type}, stderr={result.stderr}")
			return None
		except Exception as e:
			self._log_operation("checksum", path, False, f"exception: {e}")
			return None


class BusyBoxManager:
	"""Enhanced BusyBox management with comprehensive file operations"""

	def __init__(self, adb_file_manager: ADBFileManager, console_instance,
	             busybox_path: str = "/data/local/tmp/busybox"):
		self.adb = adb_file_manager
		self.console = console_instance
		self.busybox_path = busybox_path
		self.busybox_cmd = f"{busybox_path}/busybox"
		self._available = True
		self._applets = None

	def _log(self, message: str, success: bool = True):
		"""Internal logging method"""
		if self.console:
			status = "✓" if success else "✗"
			self.console.debug(f"BusyBox: {message} {status}")

	def _run_command(self, command: str, use_busybox: bool = True, timeout: int = 30) -> str:
		"""Run command and return combined output"""
		try:
			if use_busybox and self.is_available():
				cmd = f"{self.busybox_cmd} {command}"
			else:
				cmd = command

			result = self.adb._run_command(cmd)

			# Combine stdout and stderr, filtering actual errors
			output = ""
			if hasattr(result, 'stdout') and result.stdout:
				output += result.stdout.strip()

			if hasattr(result, 'stderr') and result.stderr:
				stderr_text = result.stderr.strip()
				# Only include stderr if it doesn't look like an actual error
				if stderr_text and not any(error_indicator in stderr_text.lower()
				                           for error_indicator in
				                           ['error', 'failed', 'permission denied', 'cannot', 'no such']):
					if output:
						output += " " + stderr_text
					else:
						output = stderr_text

			return output

		except Exception as e:
			self._log(f"Command failed: {command} - {e}", False)
			return ""

	def is_available(self) -> bool:
		"""Check if BusyBox is available and executable"""
		if self._available is not None:
			return self._available

		# Check if busybox exists and is executable
		if not self.adb.exists(self.busybox_cmd):
			self._available = False
			self._log("BusyBox not found at specified path", False)
			return False

		# Test if busybox works
		result = self._run_command(f"{self.busybox_cmd} --help", use_busybox=False)
		success = "BusyBox" in result

		self._available = success
		if success:
			self._log(f"Available - {result.splitlines()[0] if result else 'Unknown version'}")
		else:
			self._log("Not executable or broken", False)

		return success

	def get_applets(self) -> List[str]:
		"""Get list of available BusyBox applets"""
		if self._applets is not None:
			return self._applets

		if not self.is_available():
			return []

		result = self._run_command(f"{self.busybox_cmd} --list", use_busybox=False)
		self._applets = [applet.strip() for applet in result.splitlines() if applet.strip()]
		return self._applets

	def has_applet(self, applet: str) -> bool:
		"""Check if specific BusyBox applet is available"""
		return applet in self.get_applets()

	# ========== DIRECTORY OPERATIONS ==========

	def mkdir(self, path: str, parents: bool = False, mode: str = None) -> bool:
		"""Create directory using BusyBox"""
		cmd = f"mkdir {'-p ' if parents else ''}"
		if mode and self.has_applet('mkdir'):
			cmd += f"-m {mode} "
		cmd += f"{repr(path)}"

		result = self._run_command(cmd)
		success = not any(error in result.lower() for error in ['error', 'cannot', 'failed'])
		self._log(f"mkdir: {path} (parents={parents}, mode={mode})", success)
		return success

	def mkdirs(self, *paths: str) -> bool:
		"""Create multiple directories"""
		success = True
		for path in paths:
			if not self.mkdir(path, parents=True):
				success = False
		self._log(f"mkdirs: {len(paths)} directories", success)
		return success

	def rmdir(self, path: str, recursive: bool = False) -> bool:
		"""Remove directory"""
		if recursive:
			return self.remove(path, recursive=True)
		else:
			result = self._run_command(f"rmdir {repr(path)}")
			success = "error" not in result.lower()
			self._log(f"rmdir: {path} (recursive={recursive})", success)
			return success

	# ========== FILE OPERATIONS ==========

	def remove(self, path: str, recursive: bool = False, force: bool = True) -> bool:
		"""Remove file or directory using BusyBox"""
		cmd = f"rm {'-r ' if recursive else ''}{'-f ' if force else ''}{repr(path)}"
		result = self._run_command(cmd)
		success = "error" not in result.lower() or "no such file" in result.lower()
		self._log(f"remove: {path} (recursive={recursive}, force={force})", success)
		return success

	def copy(self, src: str, dst: str, recursive: bool = False, preserve: bool = True) -> bool:
		"""Copy file or directory using BusyBox"""
		cmd = f"cp {'-r ' if recursive else ''}{'-p ' if preserve else ''}{repr(src)} {repr(dst)}"
		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"copy: {src} -> {dst} (recursive={recursive})", success)
		return success

	def move(self, src: str, dst: str, force: bool = True) -> bool:
		"""Move file or directory using BusyBox with wildcard support"""
		# If source contains wildcards, use shell expansion
		if '*' in src or '?' in src:
			cmd = f"sh -c 'mv {'-f ' if force else ''}{src} {dst}'"
		else:
			cmd = f"mv {'-f ' if force else ''}{repr(src)} {repr(dst)}"

		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"move: {src} -> {dst}", success)
		return success

	def rename(self, path: str, new_name: str) -> bool:
		"""Rename file or directory"""
		import os
		dir_name = os.path.dirname(path)
		new_path = os.path.join(dir_name, new_name) if dir_name else new_name
		return self.move(path, new_path)

	# ========== PERMISSIONS OPERATIONS ==========

	def chmod(self, path: str, mode: str, recursive: bool = False) -> bool:
		"""Change file permissions using BusyBox"""
		cmd = f"chmod {'-R ' if recursive else ''}{mode} {repr(path)}"
		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"chmod: {path} {mode} (recursive={recursive})", success)
		return success

	def chown(self, path: str, owner: str, group: str = None, recursive: bool = False) -> bool:
		"""Change file owner using BusyBox"""
		if not self.has_applet('chown'):
			self._log("chown applet not available", False)
			return False

		ownership = f"{owner}:{group}" if group else owner
		cmd = f"chown {'-R ' if recursive else ''}{ownership} {repr(path)}"
		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"chown: {path} {ownership} (recursive={recursive})", success)
		return success

	def make_readonly(self, path: str) -> bool:
		"""Make file read-only"""
		return self.chmod(path, "444")

	def make_writable(self, path: str) -> bool:
		"""Make file writable"""
		return self.chmod(path, "644")

	def make_executable(self, path: str) -> bool:
		"""Make file executable"""
		return self.chmod(path, "755")

	# ========== FILE INFORMATION ==========

	def exists(self, path: str) -> bool:
		"""Check if path exists"""
		result = self._run_command(f"test -e {repr(path)} && echo exists || echo missing")
		success = "exists" in result
		self._log(f"exists: {path}", success)
		return success

	def is_file(self, path: str) -> bool:
		"""Check if path is a file"""
		result = self._run_command(f"test -f {repr(path)} && echo file || echo not_file")
		success = "file" in result
		self._log(f"is_file: {path}", success)
		return success

	def is_dir(self, path: str) -> bool:
		"""Check if path is a directory"""
		result = self._run_command(f"test -d {repr(path)} && echo dir || echo not_dir")
		success = "dir" in result
		self._log(f"is_dir: {path}", success)
		return success

	def get_size(self, path: str) -> Optional[int]:
		"""Get file size in bytes"""
		result = self._run_command(f"stat -c %s {repr(path)} 2>/dev/null || echo")
		if result and result.strip().isdigit():
			size = int(result.strip())
			self._log(f"get_size: {path} -> {size} bytes", True)
			return size
		self._log(f"get_size failed: {path}", False)
		return None

	def get_mtime(self, path: str) -> Optional[float]:
		"""Get modification time"""
		result = self._run_command(f"stat -c %Y {repr(path)} 2>/dev/null || echo")
		if result and result.strip().isdigit():
			mtime = float(result.strip())
			self._log(f"get_mtime: {path} -> {mtime}", True)
			return mtime
		self._log(f"get_mtime failed: {path}", False)
		return None

	def get_info(self, path: str) -> Optional[Dict[str, Any]]:
		"""Get comprehensive file information"""
		if not self.exists(path):
			return None

		try:
			# Try to get detailed info using stat
			result = self._run_command(f"stat -c '%n|%s|%F|%U|%G|%a|%Y|%X|%Z' {repr(path)}")
			if result and '|' in result:
				parts = result.strip().split('|')
				if len(parts) == 9:
					info = {
						'name': parts[0],
						'size': int(parts[1]),
						'type': parts[2],
						'owner': parts[3],
						'group': parts[4],
						'permissions': parts[5],
						'mtime': float(parts[6]),
						'atime': float(parts[7]),
						'ctime': float(parts[8]),
						'is_file': self.is_file(path),
						'is_dir': self.is_dir(path)
					}
					self._log(f"get_info: {path}", True)
					return info

			# Fallback to basic info
			info = {
				'path': path,
				'exists': True,
				'is_file': self.is_file(path),
				'is_dir': self.is_dir(path),
				'size': self.get_size(path),
				'mtime': self.get_mtime(path)
			}
			self._log(f"get_info: {path} (basic)", True)
			return info

		except Exception as e:
			self._log(f"get_info failed: {path} - {e}", False)
			return None

	# ========== SEARCH AND LISTING ==========

	def list_dir(self, path: str, pattern: str = "*") -> List[str]:
		"""List directory contents with optional pattern matching"""
		try:
			cmd = f"ls -1 {repr(path)}/{pattern} 2>/dev/null || echo"
			result = self._run_command(cmd)
			items = [item for item in result.splitlines() if item.strip()]
			self._log(f"list_dir: {path} -> {len(items)} items", True)
			return items
		except Exception as e:
			self._log(f"list_dir failed: {path} - {e}", False)
			return []

	def find_files(self, root: str, pattern: str = "*", recursive: bool = True) -> List[str]:
		"""Find files matching pattern"""
		try:
			if recursive:
				cmd = f"find {repr(root)} -name {repr(pattern)} -type f 2>/dev/null || echo"
			else:
				cmd = f"find {repr(root)} -maxdepth 1 -name {repr(pattern)} -type f 2>/dev/null || echo"

			result = self._run_command(cmd)
			files = [file for file in result.splitlines() if file.strip()]
			self._log(f"find_files: {root} -> {len(files)} files", True)
			return files
		except Exception as e:
			self._log(f"find_files failed: {root} - {e}", False)
			return []

	def glob(self, pattern: str) -> List[str]:
		"""Find files matching glob pattern"""
		return self.list_dir(".", pattern)

	# ========== ARCHIVE OPERATIONS ==========

	def tar_extract(self, archive: str, target_dir: str, preserve_permissions: bool = True) -> bool:
		"""Extract tar archive using BusyBox"""
		cmd = f"tar -xf {repr(archive)} -C {repr(target_dir)}"
		if preserve_permissions:
			cmd += " -p"
		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"tar_extract: {archive} -> {target_dir}", success)
		return success

	def tar_create(self, source: str, archive: str, compression: str = "") -> bool:
		"""Create tar archive using BusyBox"""
		compression_flag = {
			"gz": "z", "gzip": "z",
			"bz2": "j", "bzip2": "j",
			"xz": "J",
			"": ""
		}.get(compression.lower(), "")

		cmd = f"tar -c{compression_flag}f {repr(archive)} {repr(source)}"
		result = self._run_command(cmd)
		success = "error" not in result.lower()
		self._log(f"tar_create: {source} -> {archive} (compression={compression})", success)
		return success

	# ========== CHECKSUM AND HASHING ==========

	def checksum(self, path: str, hash_type: str = "sha256") -> Optional[str]:
		"""Calculate file checksum using BusyBox"""
		supported_hashes = {
			"md5": "md5sum",
			"sha1": "sha1sum",
			"sha256": "sha256sum",
			"sha512": "sha512sum"
		}

		hash_cmd = supported_hashes.get(hash_type.lower())
		if not hash_cmd or not self.has_applet(hash_cmd):
			self._log(f"Hash type {hash_type} not supported", False)
			return None

		result = self._run_command(f"{hash_cmd} {repr(path)}")
		if result and not any(error in result.lower() for error in ['error', 'no such file']):
			parts = result.split()
			if parts:
				checksum = parts[0]
				self._log(f"checksum: {path} -> {checksum[:16]}... ({hash_type})", True)
				return checksum
		self._log(f"checksum failed: {path}", False)
		return None

	def verify_checksum(self, path: str, expected_hash: str, hash_type: str = "sha256") -> bool:
		"""Verify file against expected checksum"""
		actual_hash = self.checksum(path, hash_type)
		return actual_hash == expected_hash if actual_hash else False

	# ========== CONTENT OPERATIONS ==========

	def read_text(self, path: str, encoding: str = "utf-8") -> Optional[str]:
		"""Read text file content"""
		result = self._run_command(f"cat {repr(path)}")
		if result or result == "":  # Allow empty files
			self._log(f"read_text: {path} -> {len(result)} chars", True)
			return result
		self._log(f"read_text failed: {path}", False)
		return None

	def write_text(self, path: str, content: str) -> bool:
		"""Write text to file"""
		# Escape content properly for shell
		escaped_content = content.replace("'", "'\"'\"'")
		result = self._run_command(f"echo '{escaped_content}' > {repr(path)}")
		success = "error" not in result.lower()
		self._log(f"write_text: {path} -> {len(content)} chars", success)
		return success

	def read_bytes(self, path: str) -> Optional[bytes]:
		"""Read binary file content (base64 encoded for transfer)"""
		if not self.has_applet('base64'):
			self._log("base64 applet not available for binary read", False)
			return None

		result = self._run_command(f"base64 {repr(path)}")
		if result:
			try:
				import base64
				content = base64.b64decode(result)
				self._log(f"read_bytes: {path} -> {len(content)} bytes", True)
				return content
			except Exception as e:
				self._log(f"read_bytes decode failed: {path} - {e}", False)
		return None

	def append_text(self, path: str, content: str) -> bool:
		"""Append text to file"""
		escaped_content = content.replace("'", "'\"'\"'")
		result = self._run_command(f"echo '{escaped_content}' >> {repr(path)}")
		success = "error" not in result.lower()
		self._log(f"append_text: {path} -> +{len(content)} chars", success)
		return success

	# ========== BATCH OPERATIONS ==========

	def bulk_copy(self, sources: List[str], target_dir: str) -> bool:
		"""Copy multiple files to target directory"""
		success = True
		for src in sources:
			dst = f"{target_dir.rstrip('/')}/{src.split('/')[-1]}"
			if not self.copy(src, dst):
				success = False
		self._log(f"bulk_copy: {len(sources)} files -> {target_dir}", success)
		return success

	def bulk_remove(self, paths: List[str]) -> bool:
		"""Remove multiple files/directories"""
		success = True
		for path in paths:
			if not self.remove(path, recursive=True, force=True):
				success = False
		self._log(f"bulk_remove: {len(paths)} items", success)
		return success

	def clean_dir(self, path: str) -> bool:
		"""Clean directory contents without removing the directory itself"""
		result = self._run_command(f"rm -rf {repr(path)}/* {repr(path)}/.* 2>/dev/null && echo cleaned")
		success = "cleaned" in result or "error" not in result.lower()
		self._log(f"clean_dir: {path}", success)
		return success

	# ========== SYMLINK OPERATIONS ==========

	def create_symlink(self, target: str, link_path: str) -> bool:
		"""Create symbolic link"""
		if not self.has_applet('ln'):
			self._log("ln applet not available", False)
			return False

		result = self._run_command(f"ln -sf {repr(target)} {repr(link_path)}")
		success = "error" not in result.lower()
		self._log(f"create_symlink: {target} -> {link_path}", success)
		return success

	def read_symlink(self, link_path: str) -> Optional[str]:
		"""Read symbolic link target"""
		if not self.has_applet('readlink'):
			self._log("readlink applet not available", False)
			return None

		result = self._run_command(f"readlink {repr(link_path)}")
		if result and "error" not in result.lower():
			self._log(f"read_symlink: {link_path} -> {result}", True)
			return result.strip()
		return None

	# ========== SYSTEM INFORMATION ==========

	def get_disk_usage(self, path: str = "/") -> Optional[Dict[str, Any]]:
		"""Get disk usage information"""
		if not self.has_applet('df'):
			return None

		result = self._run_command(f"df -k {repr(path)}")
		if result and len(result.splitlines()) > 1:
			lines = result.splitlines()
			parts = lines[1].split()
			if len(parts) >= 6:
				return {
					'filesystem': parts[0],
					'total_blocks': int(parts[1]),
					'used_blocks': int(parts[2]),
					'available_blocks': int(parts[3]),
					'use_percent': parts[4],
					'mount_point': parts[5]
				}
		return None

	def get_memory_info(self) -> Optional[Dict[str, Any]]:
		"""Get memory information"""
		if not self.has_applet('free'):
			return None

		result = self._run_command("free -k")
		if result and len(result.splitlines()) > 1:
			lines = result.splitlines()
			parts = lines[1].split()
			if len(parts) >= 7:
				return {
					'total': int(parts[1]),
					'used': int(parts[2]),
					'free': int(parts[3]),
					'shared': int(parts[4]),
					'buffers': int(parts[5]),
					'available': int(parts[6])
				}
		return None

class PyFManager:

	def __init__(self, console=None):
		self.console = console

	def _log(self, message: str, success: bool = True):
		"""Internal logging method"""
		if self.console:
			status = "✓" if success else "✗"
			self.console.debug(f"PyFManager: {message} {status}")

	# ========== DIRECTORY OPERATIONS ==========

	def mkdir(self, path: Union[str, Path], parents: bool = False, exist_ok: bool = True) -> bool:
		"""Create directory with optional parent creation"""
		try:
			path = Path(path)
			path.mkdir(parents=parents, exist_ok=exist_ok)
			self._log(f"mkdir: {path} (parents={parents})")
			return True
		except Exception as e:
			self._log(f"mkdir failed: {path} - {e}", False)
			return False

	def mkdirs(self, *paths: Union[str, Path]) -> bool:
		"""Create multiple directories"""
		success = True
		for path in paths:
			if not self.mkdir(path, parents=True, exist_ok=True):
				success = False
		return success

	def rmdir(self, path: Union[str, Path], recursive: bool = False) -> bool:
		"""Remove directory"""
		try:
			path = Path(path)
			if recursive:
				shutil.rmtree(path)
			else:
				path.rmdir()
			self._log(f"rmdir: {path} (recursive={recursive})")
			return True
		except Exception as e:
			self._log(f"rmdir failed: {path} - {e}", False)
			return False

	# ========== FILE OPERATIONS ==========

	def remove(self, path: Union[str, Path], missing_ok: bool = True) -> bool:
		"""Remove file or directory"""
		try:
			path = Path(path)
			if path.is_dir():
				shutil.rmtree(path)
			else:
				path.unlink(missing_ok=missing_ok)
			self._log(f"remove: {path}")
			return True
		except Exception as e:
			self._log(f"remove failed: {path} - {e}", False)
			return False

	def copy(self, src: Union[str, Path], dst: Union[str, Path],
			 overwrite: bool = True, preserve_metadata: bool = True) -> bool:
		"""Copy file or directory"""
		try:
			src, dst = Path(src), Path(dst)

			if src.is_dir():
				if dst.exists() and not overwrite:
					return False
				if preserve_metadata:
					shutil.copytree(src, dst, dirs_exist_ok=overwrite)
				else:
					shutil.copytree(src, dst, dirs_exist_ok=overwrite,
								  copy_function=shutil.copy)
			else:
				if dst.exists() and not overwrite:
					return False
				if preserve_metadata:
					shutil.copy2(src, dst)
				else:
					shutil.copy(src, dst)

			self._log(f"copy: {src} -> {dst}")
			return True
		except Exception as e:
			self._log(f"copy failed: {src} -> {dst} - {e}", False)
			return False

	def move(self, src: Union[str, Path], dst: Union[str, Path],
			 overwrite: bool = True) -> bool:
		"""Move file or directory"""
		try:
			src, dst = Path(src), Path(dst)

			if dst.exists():
				if overwrite:
					self.remove(dst)
				else:
					return False

			shutil.move(str(src), str(dst))
			self._log(f"move: {src} -> {dst}")
			return True
		except Exception as e:
			self._log(f"move failed: {src} -> {dst} - {e}", False)
			return False

	def rename(self, path: Union[str, Path], new_name: str) -> bool:
		"""Rename file or directory"""
		try:
			path = Path(path)
			new_path = path.with_name(new_name)
			path.rename(new_path)
			self._log(f"rename: {path} -> {new_name}")
			return True
		except Exception as e:
			self._log(f"rename failed: {path} - {e}", False)
			return False

	# ========== PERMISSIONS OPERATIONS ==========

	def chmod(self, path: Union[str, Path], mode: Union[int, str]) -> bool:
		"""Change file permissions"""
		try:
			path = Path(path)
			if isinstance(mode, str):
				mode = int(mode, 8)  # Convert octal string to int
			path.chmod(mode)
			self._log(f"chmod: {path} {oct(mode)}")
			return True
		except Exception as e:
			self._log(f"chmod failed: {path} - {e}", False)
			return False

	def chown(self, path: Union[str, Path], uid: int = -1, gid: int = -1) -> bool:
		"""Change file owner (Unix only)"""
		try:
			import os
			path = Path(path)
			os.chown(path, uid, gid)
			self._log(f"chown: {path} uid={uid} gid={gid}")
			return True
		except Exception as e:
			self._log(f"chown failed: {path} - {e}", False)
			return False

	def make_readonly(self, path: Union[str, Path]) -> bool:
		"""Make file read-only"""
		return self.chmod(path, 0o444)

	def make_writable(self, path: Union[str, Path]) -> bool:
		"""Make file writable"""
		return self.chmod(path, 0o644)

	def make_executable(self, path: Union[str, Path]) -> bool:
		"""Make file executable"""
		return self.chmod(path, 0o755)

	# ========== FILE INFORMATION ==========

	def exists(self, path: Union[str, Path]) -> bool:
		"""Check if path exists"""
		return Path(path).exists()

	def is_file(self, path: Union[str, Path]) -> bool:
		"""Check if path is a file"""
		return Path(path).is_file()

	def is_dir(self, path: Union[str, Path]) -> bool:
		"""Check if path is a directory"""
		return Path(path).is_dir()

	def get_size(self, path: Union[str, Path]) -> int:
		"""Get file size in bytes"""
		return Path(path).stat().st_size

	def get_mtime(self, path: Union[str, Path]) -> float:
		"""Get modification time"""
		return Path(path).stat().st_mtime

	def get_info(self, path: Union[str, Path]) -> Dict[str, Any]:
		"""Get comprehensive file information"""
		path = Path(path)
		stat_info = path.stat()
		return {
			'path': str(path),
			'name': path.name,
			'parent': str(path.parent),
			'size': stat_info.st_size,
			'mtime': datetime.fromtimestamp(stat_info.st_mtime),
			'ctime': datetime.fromtimestamp(stat_info.st_ctime),
			'atime': datetime.fromtimestamp(stat_info.st_atime),
			'is_file': path.is_file(),
			'is_dir': path.is_dir(),
			'permissions': oct(stat_info.st_mode)[-3:],
		}

	# ========== SEARCH AND LISTING ==========

	def list_dir(self, path: Union[str, Path], pattern: str = "*") -> List[Path]:
		"""List directory contents with optional pattern matching"""
		try:
			path = Path(path)
			return sorted([p for p in path.glob(pattern)])
		except Exception as e:
			self._log(f"list_dir failed: {path} - {e}", False)
			return []

	def find_files(self, root: Union[str, Path], pattern: str = "*",
				   recursive: bool = True) -> List[Path]:
		"""Find files matching pattern"""
		try:
			root = Path(root)
			if recursive:
				return sorted([p for p in root.rglob(pattern) if p.is_file()])
			else:
				return sorted([p for p in root.glob(pattern) if p.is_file()])
		except Exception as e:
			self._log(f"find_files failed: {root} - {e}", False)
			return []

	def walk(self, root: Union[str, Path]) -> Generator[tuple, None, None]:
		"""Walk directory tree (like os.walk but with Path objects)"""
		root = Path(root)
		for path in root.rglob('*'):
			if path.is_dir():
				dirs = [p for p in path.iterdir() if p.is_dir()]
				files = [p for p in path.iterdir() if p.is_file()]
				yield path, dirs, files

	# ========== ARCHIVE OPERATIONS ==========

	def tar_extract(self, archive: Union[str, Path], target_dir: Union[str, Path]) -> bool:
		"""Extract tar archive"""
		try:
			archive, target_dir = Path(archive), Path(target_dir)
			with tarfile.open(archive) as tar:
				tar.extractall(target_dir)
			self._log(f"tar_extract: {archive} -> {target_dir}")
			return True
		except Exception as e:
			self._log(f"tar_extract failed: {archive} - {e}", False)
			return False

	def tar_create(self, source: Union[str, Path], archive: Union[str, Path],
				   compression: str = "") -> bool:
		"""Create tar archive"""
		try:
			source, archive = Path(source), Path(archive)
			mode = f"w:{compression}" if compression else "w"
			with tarfile.open(archive, mode) as tar:
				tar.add(source, arcname=source.name)
			self._log(f"tar_create: {source} -> {archive}")
			return True
		except Exception as e:
			self._log(f"tar_create failed: {source} - {e}", False)
			return False

	def zip_extract(self, archive: Union[str, Path], target_dir: Union[str, Path]) -> bool:
		"""Extract zip archive"""
		try:
			archive, target_dir = Path(archive), Path(target_dir)
			with zipfile.ZipFile(archive, 'r') as zip_ref:
				zip_ref.extractall(target_dir)
			self._log(f"zip_extract: {archive} -> {target_dir}")
			return True
		except Exception as e:
			self._log(f"zip_extract failed: {archive} - {e}", False)
			return False

	def zip_create(self, source: Union[str, Path], archive: Union[str, Path]) -> bool:
		"""Create zip archive"""
		try:
			source, archive = Path(source), Path(archive)
			with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
				if source.is_file():
					zipf.write(source, source.name)
				else:
					for file_path in source.rglob('*'):
						if file_path.is_file():
							arcname = file_path.relative_to(source)
							zipf.write(file_path, arcname)
			self._log(f"zip_create: {source} -> {archive}")
			return True
		except Exception as e:
			self._log(f"zip_create failed: {source} - {e}", False)
			return False

	# ========== CHECKSUM AND HASHING ==========

	def checksum(self, path: Union[str, Path], hash_type: str = "sha512") -> Optional[str]:
		"""Calculate file checksum"""
		try:
			path = Path(path)
			hash_func = getattr(hashlib, hash_type)()

			with open(path, 'rb') as f:
				for chunk in iter(lambda: f.read(4096), b""):
					hash_func.update(chunk)

			checksum = hash_func.hexdigest()
			self._log(f"checksum: {path} -> {checksum[:16]}...")
			return checksum
		except Exception as e:
			self._log(f"checksum failed: {path} - {e}", False)
			return None

	def verify_checksum(self, path: Union[str, Path], expected_hash: str,
					   hash_type: str = "sha256") -> bool:
		"""Verify file against expected checksum"""
		actual_hash = self.checksum(path, hash_type)
		return actual_hash == expected_hash if actual_hash else False

	# ========== CONTENT OPERATIONS ==========

	def read_text(self, path: Union[str, Path], encoding: str = "utf-8") -> Optional[str]:
		"""Read text file content"""
		try:
			content = Path(path).read_text(encoding=encoding)
			self._log(f"read_text: {path} ({len(content)} chars)")
			return content
		except Exception as e:
			self._log(f"read_text failed: {path} - {e}", False)
			return None

	def write_text(self, path: Union[str, Path], content: str,
				   encoding: str = "utf-8") -> bool:
		"""Write text to file"""
		try:
			Path(path).write_text(content, encoding=encoding)
			self._log(f"write_text: {path} ({len(content)} chars)")
			return True
		except Exception as e:
			self._log(f"write_text failed: {path} - {e}", False)
			return False

	def read_bytes(self, path: Union[str, Path]) -> Optional[bytes]:
		"""Read binary file content"""
		try:
			content = Path(path).read_bytes()
			self._log(f"read_bytes: {path} ({len(content)} bytes)")
			return content
		except Exception as e:
			self._log(f"read_bytes failed: {path} - {e}", False)
			return None

	def write_bytes(self, path: Union[str, Path], content: bytes) -> bool:
		"""Write bytes to file"""
		try:
			Path(path).write_bytes(content)
			self._log(f"write_bytes: {path} ({len(content)} bytes)")
			return True
		except Exception as e:
			self._log(f"write_bytes failed: {path} - {e}", False)
			return False

	# ========== TEMPORARY FILES ==========

	def create_temp_file(self, suffix: str = "", prefix: str = "tmp") -> Path:
		"""Create temporary file"""
		temp_file = Path(tempfile.mktemp(suffix=suffix, prefix=prefix))
		self._log(f"create_temp_file: {temp_file}")
		return temp_file

	def create_temp_dir(self, suffix: str = "", prefix: str = "tmp") -> Path:
		"""Create temporary directory"""
		temp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix))
		self._log(f"create_temp_dir: {temp_dir}")
		return temp_dir

	# ========== SYMLINK OPERATIONS ==========

	def create_symlink(self, target: Union[str, Path], link_path: Union[str, Path]) -> bool:
		"""Create symbolic link"""
		try:
			target, link_path = Path(target), Path(link_path)
			link_path.symlink_to(target)
			self._log(f"create_symlink: {target} -> {link_path}")
			return True
		except Exception as e:
			self._log(f"create_symlink failed: {target} - {e}", False)
			return False

	def read_symlink(self, link_path: Union[str, Path]) -> Optional[Path]:
		"""Read symbolic link target"""
		try:
			link_path = Path(link_path)
			target = link_path.readlink()
			self._log(f"read_symlink: {link_path} -> {target}")
			return target
		except Exception as e:
			self._log(f"read_symlink failed: {link_path} - {e}", False)
			return None

	# ========== BATCH OPERATIONS ==========

	def bulk_copy(self, sources: List[Union[str, Path]], target_dir: Union[str, Path]) -> bool:
		"""Copy multiple files to target directory"""
		try:
			target_dir = Path(target_dir)
			target_dir.mkdir(parents=True, exist_ok=True)

			success = True
			for src in sources:
				src = Path(src)
				dst = target_dir / src.name
				if not self.copy(src, dst):
					success = False

			self._log(f"bulk_copy: {len(sources)} files -> {target_dir}")
			return success
		except Exception as e:
			self._log(f"bulk_copy failed: {e}", False)
			return False

	def bulk_remove(self, paths: List[Union[str, Path]]) -> bool:
		"""Remove multiple files/directories"""
		success = True
		for path in paths:
			if not self.remove(path):
				success = False

		self._log(f"bulk_remove: {len(paths)} items")
		return success
