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
			result = self._run_command(f"test -e {repr(path.strip())} && echo exists || echo missing")
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
			result = self._run_command(f"test -f {repr(path.strip())} && echo file || echo not_file")
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
			result = self._run_command(f"test -d {repr(path.strip())} && echo dir || echo not_dir")
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
			cmd = f"mkdir {'-p ' if parents else ''}{repr(path.strip())}"
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
			cmd = f"rm {'-' + flags + ' ' if flags else ''}{repr(path.strip())}"
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
			cmd = f"cp {'-r ' if recursive else ''}{repr(src.strip())} {repr(dst.strip())}"
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
			cmd = f"chmod {'-R ' if recursive else ''}{mode} {repr(path.strip())}"
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
			result = self._run_command(f"cat {repr(path.strip())}")
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
			cmd = f"echo '{escaped_content}' > {repr(path.strip())}"
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
			result = self._run_command(f"ls -1 {repr(path.strip())} 2>/dev/null || echo")
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
			result = self._run_command(f"{hash_type}sum {repr(path.strip())} 2>/dev/null")
			output = result.stdout or ""

			if result.returncode == 0 and output:
				parts = output.split()
				if parts:
					checksum = parts[0]
					self._log_operation("checksum", path, True, f"type={hash_type}, result={checksum}")
					return checksum

			if hash_type != "md5":
				result = self._run_command(f"md5sum {repr(path.strip())} 2>/dev/null")
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


class BusyBoxManager:
	def __init__(self, adb_file_manager: ADBFileManager, console_instance,
				 busybox_path: str = "/data/local/tmp/busybox"):
		self.adb = adb_file_manager
		self.console = console_instance
		self.busybox_path = busybox_path
		self.busybox_cmd = f"{busybox_path}/busybox"
		self._available = True
		self._applets = None

	def _log(self, message: str, success: bool = True):
		if self.console:
			status = "✓" if success else "✗"
			self.console.debug(f"BusyBox: {message} {status}")

	def _run_command(self, command: str, use_busybox: bool = True, timeout: int = 30) -> Any:
		try:
			if use_busybox and self.is_available():
				cmd = f"{self.busybox_cmd} {command}"
			else:
				cmd = command
			
			return self.adb._run_command(cmd)
			
		except Exception as e:
			class MockResult:
				def __init__(self, error_msg):
					self.stdout = ""
					self.stderr = error_msg
					self.returncode = 1
			return MockResult(str(e))

	def is_available(self) -> bool:
		if self._available is not None:
			return self._available

		if not self.adb.exists(self.busybox_cmd):
			self._available = False
			self._log("BusyBox not found at specified path", False)
			return False

		result = self._run_command(f"{self.busybox_cmd} --help", use_busybox=False)
		success = result.returncode == 0 and "BusyBox" in (result.stdout or "")

		self._available = success
		if success:
			version_line = (result.stdout or "").splitlines()[0] if result.stdout else 'Unknown version'
			self._log(f"Available - {version_line}")
		else:
			self._log("Not executable or broken", False)

		return success

	def get_applets(self) -> List[str]:
		if self._applets is not None:
			return self._applets

		if not self.is_available():
			return []

		result = self._run_command(f"{self.busybox_cmd} --list", use_busybox=False)
		output = result.stdout or ""
		self._applets = [applet.strip() for applet in output.splitlines() if applet.strip()]
		return self._applets

	def has_applet(self, applet: str) -> bool:
		return applet in self.get_applets()

	def mkdir(self, path: str, parents: bool = False, mode: str = None) -> bool:
		cmd = f"mkdir {'-p ' if parents else ''}"
		if mode and self.has_applet('mkdir'):
			cmd += f"-m {mode} "
		cmd += f"{repr(path)}"

		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"mkdir: {path} (parents={parents}, mode={mode})", success)
		return success

	def mkdirs(self, *paths: str) -> bool:
		success = True
		for path in paths:
			if not self.mkdir(path, parents=True):
				success = False
		self._log(f"mkdirs: {len(paths)} directories", success)
		return success

	def rmdir(self, path: str, recursive: bool = False) -> bool:
		if recursive:
			return self.remove(path, recursive=True)
		else:
			result = self._run_command(f"rmdir {repr(path)}")
			success = result.returncode == 0
			self._log(f"rmdir: {path} (recursive={recursive})", success)
			return success

	def remove(self, path: str, recursive: bool = False, force: bool = True) -> bool:
		cmd = f"rm {'-r ' if recursive else ''}{'-f ' if force else ''}{repr(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"remove: {path} (recursive={recursive}, force={force})", success)
		return success

	def copy(self, src: str, dst: str, recursive: bool = False, preserve: bool = True) -> bool:
		cmd = f"cp {'-r ' if recursive else ''}{'-p ' if preserve else ''}{repr(src)} {repr(dst)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"copy: {src} -> {dst} (recursive={recursive})", success)
		return success

	def move(self, src: str, dst: str, force: bool = True) -> bool:
		if '*' in src or '?' in src:
			cmd = f"sh -c 'mv {'-f ' if force else ''}{src} {dst}'"
		else:
			cmd = f"mv {'-f ' if force else ''}{repr(src)} {repr(dst)}"

		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"move: {src} -> {dst}", success)
		return success

	def rename(self, path: str, new_name: str) -> bool:
		import os
		dir_name = os.path.dirname(path)
		new_path = os.path.join(dir_name, new_name) if dir_name else new_name
		return self.move(path, new_path)

	def chmod(self, path: str, mode: str, recursive: bool = False) -> bool:
		cmd = f"chmod {'-R ' if recursive else ''}{mode} {repr(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"chmod: {path} {mode} (recursive={recursive})", success)
		return success

	def chown(self, path: str, owner: str, group: str = None, recursive: bool = False) -> bool:
		if not self.has_applet('chown'):
			self._log("chown applet not available", False)
			return False

		ownership = f"{owner}:{group}" if group else owner
		cmd = f"chown {'-R ' if recursive else ''}{ownership} {repr(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"chown: {path} {ownership} (recursive={recursive})", success)
		return success

	def make_readonly(self, path: str) -> bool:
		return self.chmod(path, "444")

	def make_writable(self, path: str) -> bool:
		return self.chmod(path, "644")

	def make_executable(self, path: str) -> bool:
		return self.chmod(path, "755")

	def exists(self, path: str) -> bool:
		result = self._run_command(f"test -e {repr(path)} && echo exists || echo missing")
		success = result.returncode == 0 and "exists" in (result.stdout or "")
		self._log(f"exists: {path}", success)
		return success

	def is_file(self, path: str) -> bool:
		result = self._run_command(f"test -f {repr(path)} && echo file || echo not_file")
		success = result.returncode == 0 and "file" in (result.stdout or "")
		self._log(f"is_file: {path}", success)
		return success

	def is_dir(self, path: str) -> bool:
		result = self._run_command(f"test -d {repr(path)} && echo dir || echo not_dir")
		success = result.returncode == 0 and "dir" in (result.stdout or "")
		self._log(f"is_dir: {path}", success)
		return success

	def get_size(self, path: str) -> Optional[int]:
		result = self._run_command(f"stat -c %s {repr(path)} 2>/dev/null || echo")
		output = result.stdout or ""
		if result.returncode == 0 and output.strip().isdigit():
			size = int(output.strip())
			self._log(f"get_size: {path} -> {size} bytes", True)
			return size
		self._log(f"get_size failed: {path}", False)
		return None

	def get_mtime(self, path: str) -> Optional[float]:
		result = self._run_command(f"stat -c %Y {repr(path)} 2>/dev/null || echo")
		output = result.stdout or ""
		if result.returncode == 0 and output.strip().isdigit():
			mtime = float(output.strip())
			self._log(f"get_mtime: {path} -> {mtime}", True)
			return mtime
		self._log(f"get_mtime failed: {path}", False)
		return None

	def get_info(self, path: str) -> Optional[Dict[str, Any]]:
		if not self.exists(path):
			return None

		try:
			result = self._run_command(f"stat -c '%n|%s|%F|%U|%G|%a|%Y|%X|%Z' {repr(path)}")
			output = result.stdout or ""
			if result.returncode == 0 and '|' in output:
				parts = output.strip().split('|')
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

	def list_dir(self, path: str, pattern: str = "*") -> List[str]:
		try:
			cmd = f"ls -1 {repr(path)}/{pattern} 2>/dev/null || echo"
			result = self._run_command(cmd)
			output = result.stdout or ""
			items = [item for item in output.splitlines() if item.strip()]
			self._log(f"list_dir: {path} -> {len(items)} items", True)
			return items
		except Exception as e:
			self._log(f"list_dir failed: {path} - {e}", False)
			return []

	def find_files(self, root: str, pattern: str = "*", recursive: bool = True) -> List[str]:
		try:
			if recursive:
				cmd = f"find {repr(root)} -name {repr(pattern)} -type f 2>/dev/null || echo"
			else:
				cmd = f"find {repr(root)} -maxdepth 1 -name {repr(pattern)} -type f 2>/dev/null || echo"

			result = self._run_command(cmd)
			output = result.stdout or ""
			files = [file for file in output.splitlines() if file.strip()]
			self._log(f"find_files: {root} -> {len(files)} files", True)
			return files
		except Exception as e:
			self._log(f"find_files failed: {root} - {e}", False)
			return []

	def glob(self, pattern: str) -> List[str]:
		return self.list_dir(".", pattern)

	def tar_extract(self, archive: str, target_dir: str, preserve_permissions: bool = True) -> bool:
		cmd = f"tar -xf {repr(archive)} -C {repr(target_dir)}"
		if preserve_permissions:
			cmd += " -p"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self.console.debug(f"tar_extract result: {result.stdout}")
		self._log(f"tar_extract: {archive} -> {target_dir}", success)
		return success

	def tar_create(self, source: str, archive: str, compression: str = "") -> bool:
		compression_flag = {
			"gz": "z", "gzip": "z",
			"bz2": "j", "bzip2": "j",
			"xz": "J",
			"": ""
		}.get(compression.lower(), "")

		cmd = f"tar -c{compression_flag}f {repr(archive)} {repr(source)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"tar_create: {source} -> {archive} (compression={compression})", success)
		return success

	def checksum(self, path: str, hash_type: str = "sha256") -> Optional[str]:
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
		if result.returncode == 0:
			output = result.stdout or ""
			parts = output.split()
			if parts:
				checksum = parts[0]
				self._log(f"checksum: {path} -> {checksum} ({hash_type})", True)
				return checksum
		self._log(f"checksum failed: {path}", False)
		return None

	def verify_checksum(self, path: str, expected_hash: str, hash_type: str = "sha256") -> bool:
		actual_hash = self.checksum(path, hash_type)
		return actual_hash == expected_hash if actual_hash else False

	def read_text(self, path: str, encoding: str = "utf-8") -> Optional[str]:
		result = self._run_command(f"cat {repr(path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			self._log(f"read_text: {path} -> {len(output)} chars", True)
			return output
		self._log(f"read_text failed: {path}", False)
		return None

	def write_text(self, path: str, content: str) -> bool:
		escaped_content = content.replace("'", "'\"'\"'")
		cmd = f"echo '{escaped_content}' > {repr(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"write_text: {path} -> {len(content)} chars", success)
		return success

	def read_bytes(self, path: str) -> Optional[bytes]:
		if not self.has_applet('base64'):
			self._log("base64 applet not available for binary read", False)
			return None

		result = self._run_command(f"base64 {repr(path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			try:
				import base64
				content = base64.b64decode(output)
				self._log(f"read_bytes: {path} -> {len(content)} bytes", True)
				return content
			except Exception as e:
				self._log(f"read_bytes decode failed: {path} - {e}", False)
		return None

	def append_text(self, path: str, content: str) -> bool:
		escaped_content = content.replace("'", "'\"'\"'")
		cmd = f"echo '{escaped_content}' >> {repr(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"append_text: {path} -> +{len(content)} chars", success)
		return success

	def bulk_copy(self, sources: List[str], target_dir: str) -> bool:
		success = True
		for src in sources:
			dst = f"{target_dir.rstrip('/')}/{src.split('/')[-1]}"
			if not self.copy(src, dst):
				success = False
		self._log(f"bulk_copy: {len(sources)} files -> {target_dir}", success)
		return success

	def bulk_remove(self, paths: List[str]) -> bool:
		success = True
		for path in paths:
			if not self.remove(path, recursive=True, force=True):
				success = False
		self._log(f"bulk_remove: {len(paths)} items", success)
		return success

	def clean_dir(self, path: str) -> bool:
		cmd = f"rm -rf {repr(path)}/* {repr(path)}/.* 2>/dev/null && echo cleaned"
		result = self._run_command(cmd)
		success = result.returncode == 0 or "cleaned" in (result.stdout or "")
		self._log(f"clean_dir: {path}", success)
		return success

	def create_symlink(self, target: str, link_path: str) -> bool:
		if not self.has_applet('ln'):
			self._log("ln applet not available", False)
			return False

		cmd = f"ln -sf {repr(target)} {repr(link_path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"create_symlink: {target} -> {link_path}", success)
		return success

	def read_symlink(self, link_path: str) -> Optional[str]:
		if not self.has_applet('readlink'):
			self._log("readlink applet not available", False)
			return None

		result = self._run_command(f"readlink {repr(link_path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			self._log(f"read_symlink: {link_path} -> {output}", True)
			return output.strip()
		return None

	def get_disk_usage(self, path: str = "/") -> Optional[Dict[str, Any]]:
		if not self.has_applet('df'):
			return None

		result = self._run_command(f"df -k {repr(path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			if len(output.splitlines()) > 1:
				lines = output.splitlines()
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
		if not self.has_applet('free'):
			return None

		result = self._run_command("free -k")
		if result.returncode == 0:
			output = result.stdout or ""
			if len(output.splitlines()) > 1:
				lines = output.splitlines()
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
