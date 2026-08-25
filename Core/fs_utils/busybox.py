from Core.fs_utils.imports import *
from Core.fs_utils.adb import ADBFileManager

class BusyBoxManager:
	def __init__(self, adb_file_manager: ADBFileManager, console_instance,
				 busybox_path: str = "/data/local/tmp/busybox",
				 proot_cmd = None):
		self.adb = adb_file_manager
		self.console = console_instance
		self.busybox_path = busybox_path
		self.busybox_cmd = f"{busybox_path}/busybox"
		self._available = True
		self._applets = None
		self.tar_err = None
		self.proot_cmd = proot_cmd

	def _log(self, message: str, success: bool = True):
		if self.console:
			status = "✓" if success else "✗"
			self.console.debug(f"BusyBox: {message} {status}")

	def _run_command(self, command: str, use_busybox: bool = True, timeout: int = 30) -> Any:
		try:
			if use_busybox and self.is_available():
				cmd = f"{self.proot_cmd or str()}{self.busybox_cmd} {command}"
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
		cmd += f"{shlex.quote(path)}"

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
			result = self._run_command(f"rmdir {shlex.quote(path)}")
			success = result.returncode == 0
			self._log(f"rmdir: {path} (recursive={recursive})", success)
			return success

	def remove(self, path: str, recursive: bool = False, force: bool = True) -> bool:
		cmd = f"rm {'-r ' if recursive else ''}{'-f ' if force else ''}{shlex.quote(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"remove: {path} (recursive={recursive}, force={force})", success)
		return success

	def copy(self, src: str, dst: str, recursive: bool = False, preserve: bool = True) -> bool:
		cmd = f"cp {'-r ' if recursive else ''}{'-p ' if preserve else ''}{shlex.quote(src)} {shlex.quote(dst)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"copy: {src} -> {dst} (recursive={recursive})", success)
		return success

	def move(self, src: str, dst: str, force: bool = True) -> bool:
		if '*' in src or '?' in src:
			cmd = f"sh -c 'mv {'-f ' if force else ''}{src} {dst}'"
		else:
			cmd = f"mv {'-f ' if force else ''}{shlex.quote(src)} {shlex.quote(dst)}"

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
		cmd = f"chmod {'-R ' if recursive else ''}{mode} {shlex.quote(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"chmod: {path} {mode} (recursive={recursive})", success)
		return success

	def chown(self, path: str, owner: str, group: str = None, recursive: bool = False) -> bool:
		if not self.has_applet('chown'):
			self._log("chown applet not available", False)
			return False

		ownership = f"{owner}:{group}" if group else owner
		cmd = f"chown {'-R ' if recursive else ''}{ownership} {shlex.quote(path)}"
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
		result = self._run_command(f"test -e {shlex.quote(path)} && echo exists || echo missing")
		success = result.returncode == 0 and "exists" in (result.stdout or "")
		self._log(f"exists: {path}", success)
		return success

	def is_file(self, path: str) -> bool:
		result = self._run_command(f"test -f {shlex.quote(path)} && echo file || echo not")
		success = result.returncode == 0 and "file" in (result.stdout or "")
		self._log(f"is_file: {path}", success)
		return success

	def is_dir(self, path: str) -> bool:
		result = self._run_command(f"test -d {shlex.quote(path)} && echo dir || echo not")
		success = result.returncode == 0 and "dir" in (result.stdout or "")
		self._log(f"is_dir: {path}", success)
		return success

	def get_size(self, path: str) -> Optional[int]:
		result = self._run_command(f"stat -c %s {shlex.quote(path)} 2>/dev/null || echo")
		output = result.stdout or ""
		if result.returncode == 0 and output.strip().isdigit():
			size = int(output.strip())
			self._log(f"get_size: {path} -> {size} bytes", True)
			return size
		self._log(f"get_size failed: {path}", False)
		return None

	def get_mtime(self, path: str) -> Optional[float]:
		result = self._run_command(f"stat -c %Y {shlex.quote(path)} 2>/dev/null || echo")
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
			result = self._run_command(f"stat -c '%n|%s|%F|%U|%G|%a|%Y|%X|%Z' {shlex.quote(path)}")
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
			cmd = f"ls -1 {shlex.quote(path)}/{pattern} 2>/dev/null || echo"
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
				cmd = f"find {shlex.quote(root)} -name {shlex.quote(pattern)} -type f 2>/dev/null || echo"
			else:
				cmd = f"find {shlex.quote(root)} -maxdepth 1 -name {shlex.quote(pattern)} -type f 2>/dev/null || echo"

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
		cmd = f"tar -xf {shlex.quote(archive)} -C {shlex.quote(target_dir)}"
		if preserve_permissions:
			cmd += " -p"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self.tar_err = result.stderr
		self.console.debug(f"tar_extract result: {result.stdout}, error message: {result.stderr}")
		self._log(f"tar_extract: {archive} -> {target_dir}", success)
		return success

	def tar_create(self, source: str, archive: str, compression: str = "") -> bool:
		compression_flag = {
			"gz": "z", "gzip": "z",
			"bz2": "j", "bzip2": "j",
			"xz": "J",
			"": ""
		}.get(compression.lower(), "")

		cmd = f"tar -c{compression_flag}f {shlex.quote(archive)} {shlex.quote(source)}"
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

		result = self._run_command(f"{hash_cmd} {shlex.quote(path)}")
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
		result = self._run_command(f"cat {shlex.quote(path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			self._log(f"read_text: {path} -> {len(output)} chars", True)
			return output
		self._log(f"read_text failed: {path}", False)
		return None

	def write_text(self, path: str, content: str) -> bool:
		escaped_content = content.replace("'", "'\"'\"'")
		cmd = f"echo '{escaped_content}' > {shlex.quote(path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"write_text: {path} -> {len(content)} chars", success)
		return success

	def read_bytes(self, path: str) -> Optional[bytes]:
		if not self.has_applet('base64'):
			self._log("base64 applet not available for binary read", False)
			return None

		result = self._run_command(f"base64 {shlex.quote(path)}")
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
		cmd = f"echo '{escaped_content}' >> {shlex.quote(path)}"
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
		cmd = f"rm -rf {shlex.quote(path)}/* {shlex.quote(path)}/.* 2>/dev/null && echo cleaned"
		result = self._run_command(cmd)
		success = result.returncode == 0 or "cleaned" in (result.stdout or "")
		self._log(f"clean_dir: {path}", success)
		return success

	def create_symlink(self, target: str, link_path: str) -> bool:
		if not self.has_applet('ln'):
			self._log("ln applet not available", False)
			return False

		cmd = f"ln -sf {shlex.quote(target)} {shlex.quote(link_path)}"
		result = self._run_command(cmd)
		success = result.returncode == 0
		self._log(f"create_symlink: {target} -> {link_path}", success)
		return success

	def read_symlink(self, link_path: str) -> Optional[str]:
		if not self.has_applet('readlink'):
			self._log("readlink applet not available", False)
			return None

		result = self._run_command(f"readlink {shlex.quote(link_path)}")
		if result.returncode == 0:
			output = result.stdout or ""
			self._log(f"read_symlink: {link_path} -> {output}", True)
			return output.strip()
		return None

	def get_disk_usage(self, path: str = "/") -> Optional[Dict[str, Any]]:
		if not self.has_applet('df'):
			return None

		result = self._run_command(f"df -k {shlex.quote(path)}")
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
