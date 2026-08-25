from Core.fs_utils.imports import *

class PyFManager:

	def __init__(self, console=None):
		self.console = console

	def _log(self, message: str, success: bool = True):
		if self.console:
			status = "✓" if success else "✗"
			self.console.debug(f"PyFManager: {message} {status}")

	def mkdir(self, path: Union[str, Path], parents: bool = False, exist_ok: bool = True) -> bool:
		try:
			path = Path(path)
			path.mkdir(parents=parents, exist_ok=exist_ok)
			self._log(f"mkdir: {path} (parents={parents})")
			return True
		except Exception as e:
			self._log(f"mkdir failed: {path} - {e}", False)
			return False

	def mkdirs(self, *paths: Union[str, Path]) -> bool:
		success = True
		for path in paths:
			if not self.mkdir(path, parents=True, exist_ok=True):
				success = False
		return success

	def rmdir(self, path: Union[str, Path], recursive: bool = False) -> bool:
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

	def remove(self, path: Union[str, Path], missing_ok: bool = True) -> bool:
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
		try:
			path = Path(path)
			new_path = path.with_name(new_name)
			path.rename(new_path)
			self._log(f"rename: {path} -> {new_name}")
			return True
		except Exception as e:
			self._log(f"rename failed: {path} - {e}", False)
			return False

	def chmod(self, path: Union[str, Path], mode: Union[int, str]) -> bool:
		try:
			path = Path(path)
			if isinstance(mode, str):
				mode = int(mode, 8)
			path.chmod(mode)
			self._log(f"chmod: {path} {oct(mode)}")
			return True
		except Exception as e:
			self._log(f"chmod failed: {path} - {e}", False)
			return False

	def chown(self, path: Union[str, Path], uid: int = -1, gid: int = -1) -> bool:
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
		return self.chmod(path, 0o444)

	def make_writable(self, path: Union[str, Path]) -> bool:
		return self.chmod(path, 0o644)

	def make_executable(self, path: Union[str, Path]) -> bool:
		return self.chmod(path, 0o755)

	def exists(self, path: Union[str, Path]) -> bool:
		return Path(path).exists()

	def is_file(self, path: Union[str, Path]) -> bool:
		return Path(path).is_file()

	def is_dir(self, path: Union[str, Path]) -> bool:
		return Path(path).is_dir()

	def get_size(self, path: Union[str, Path]) -> int:
		return Path(path).stat().st_size

	def get_mtime(self, path: Union[str, Path]) -> float:
		return Path(path).stat().st_mtime

	def get_info(self, path: Union[str, Path]) -> Dict[str, Any]:
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

	def list_dir(self, path: Union[str, Path], pattern: str = "*") -> List[Path]:
		try:
			path = Path(path)
			return sorted([p for p in path.glob(pattern)])
		except Exception as e:
			self._log(f"list_dir failed: {path} - {e}", False)
			return []

	def find_files(self, root: Union[str, Path], pattern: str = "*",
				   recursive: bool = True) -> List[Path]:
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
		root = Path(root)
		for path in root.rglob('*'):
			if path.is_dir():
				entries = list(path.iterdir())
				dirs = [p for p in entries if p.is_dir()]
				files = [p for p in entries if p.is_file()]
				yield path, dirs, files

	def tar_extract(self, archive: Union[str, Path], target_dir: Union[str, Path]) -> bool:
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

	def checksum(self, path: Union[str, Path], hash_type: str = "sha256") -> Optional[str]:
		try:
			path = Path(path)
			hash_func = getattr(hashlib, hash_type)()

			with open(path, 'rb') as f:
				for chunk in iter(lambda: f.read(4096), b""):
					hash_func.update(chunk)

			result = hash_func.hexdigest()
			self._log(f"checksum: {path} -> {result[:16]}...")
			return result
		except Exception as e:
			self._log(f"checksum failed: {path} - {e}", False)
			return None

	def verify_checksum(self, path: Union[str, Path], expected_hash: str,
					   hash_type: str = "sha256") -> bool:
		actual_hash = self.checksum(path, hash_type)
		return actual_hash == expected_hash if actual_hash else False

	def read_text(self, path: Union[str, Path], encoding: str = "utf-8") -> Optional[str]:
		try:
			content = Path(path).read_text(encoding=encoding)
			self._log(f"read_text: {path} ({len(content)} chars)")
			return content
		except Exception as e:
			self._log(f"read_text failed: {path} - {e}", False)
			return None

	def write_text(self, path: Union[str, Path], content: str,
				   encoding: str = "utf-8") -> bool:
		try:
			Path(path).write_text(content, encoding=encoding)
			self._log(f"write_text: {path} ({len(content)} chars)")
			return True
		except Exception as e:
			self._log(f"write_text failed: {path} - {e}", False)
			return False

	def read_bytes(self, path: Union[str, Path]) -> Optional[bytes]:
		try:
			content = Path(path).read_bytes()
			self._log(f"read_bytes: {path} ({len(content)} bytes)")
			return content
		except Exception as e:
			self._log(f"read_bytes failed: {path} - {e}", False)
			return None

	def write_bytes(self, path: Union[str, Path], content: bytes) -> bool:
		try:
			Path(path).write_bytes(content)
			self._log(f"write_bytes: {path} ({len(content)} bytes)")
			return True
		except Exception as e:
			self._log(f"write_bytes failed: {path} - {e}", False)
			return False

	def create_temp_file(self, suffix: str = "", prefix: str = "tmp") -> Path:
		temp_file = Path(tempfile.mktemp(suffix=suffix, prefix=prefix))
		self._log(f"create_temp_file: {temp_file}")
		return temp_file

	def create_temp_dir(self, suffix: str = "", prefix: str = "tmp") -> Path:
		temp_dir = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix))
		self._log(f"create_temp_dir: {temp_dir}")
		return temp_dir

	def create_symlink(self, target: Union[str, Path], link_path: Union[str, Path]) -> bool:
		try:
			target, link_path = Path(target), Path(link_path)
			link_path.symlink_to(target)
			self._log(f"create_symlink: {target} -> {link_path}")
			return True
		except Exception as e:
			self._log(f"create_symlink failed: {target} - {e}", False)
			return False

	def read_symlink(self, link_path: Union[str, Path]) -> Optional[Path]:
		try:
			link_path = Path(link_path)
			target = link_path.readlink()
			self._log(f"read_symlink: {link_path} -> {target}")
			return target
		except Exception as e:
			self._log(f"read_symlink failed: {link_path} - {e}", False)
			return None

	def bulk_copy(self, sources: List[Union[str, Path]], target_dir: Union[str, Path]) -> Dict[str, bool]:
		target_dir = Path(target_dir)
		results = {}
		try:
			target_dir.mkdir(parents=True, exist_ok=True)
			for src in sources:
				src = Path(src)
				dst = target_dir / src.name
				results[str(src)] = self.copy(src, dst)
		except Exception as e:
			self._log(f"bulk_copy failed: {e}", False)

		self._log(f"bulk_copy: {len(sources)} files -> {target_dir}")
		return results

	def bulk_remove(self, paths: List[Union[str, Path]]) -> Dict[str, bool]:
		results = {str(path): self.remove(path) for path in paths}
		self._log(f"bulk_remove: {len(paths)} items")
		return results