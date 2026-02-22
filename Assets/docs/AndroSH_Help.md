# AndroSH Command Line Reference

> Complete documentation for all AndroSH commands and subcommands

---

## Main Command

```
usage: main.py [-h] [--verbose | --debug | --quiet] [--base-dir BASE_DIR]
               [--resources-dir RESOURCES_DIR] [--time-style] [--chsh CHSH]
               {setup,backup,remove,launch,rish,clean,install,list,lsd,download,distro}
               ...

AndroSH - Professional Multi-Distribution Linux Environments for Android

positional arguments:
  {setup,backup,remove,launch,rish,clean,install,list,lsd,download,distro}
                        Command to execute
    setup               Deploy a new Linux environment
    backup              Backup an existing environment
    remove              Remove an existing environment
    launch              Start an existing environment
    rish                Start adb shell/shizuku rish
    clean               Clean environment temporary files
    install             Install for global system access
    list                Show available distributions
    lsd                 List installed environments
    download            Download distribution files
    distro              Distribution management suite

options:
  -h, --help            show this help message and exit
  --verbose, -v         Verbose output: detailed operation information
  --debug, -d           Debug output: all operations including system commands
  --quiet, -q           Quiet output: suppress non-essential information
  --base-dir BASE_DIR   Base directory for environments (default:
                        /data/local/tmp/AndroSH/distros)
  --resources-dir RESOURCES_DIR
                        Resources directory for downloads (default:
                        /sdcard/Download/AndroSH)
  --time-style          Display time format
  --chsh CHSH           Custom shell command (default: bash)

Complete Linux workstations with Android system integration - no root required
```

## Available Subcommands

| Command | Description |
|---------|-------------|
| `setup` | Deploy a new Linux environment |
| `backup` | Backup an existing environment |
| `remove` | Remove an existing environment |
| `launch` | Start an existing environment |
| `rish` | Start adb shell/shizuku rish |
| `clean` | Clean environment temporary files |
| `install` | Install for global system access |
| `list` | Show available distributions |
| `lsd` | List installed environments |
| `download` | Download distribution files |
| `distro` | Distribution management suite |

---

## Detailed Subcommand Help


### `python main.py setup`

```
usage: main.py setup [-h] [-f ROOTFS]
                     [-d {alpine,debian,ubuntu,kali-nethunter,archlinux,fedora,void,manjaro,chimera}]
                     [-t TYPE] [--hostname HOSTNAME] [--resetup] [--force]
                     name

positional arguments:
  name                  Environment name (default: AndroSH)

options:
  -h, --help            show this help message and exit
  -f ROOTFS, --rootfs ROOTFS
                        Custom rootfs file, when used you don't need to add
                        -d/-t arguments
  -d {alpine,debian,ubuntu,kali-nethunter,archlinux,fedora,void,manjaro,chimera}, --distro {alpine,debian,ubuntu,kali-nethunter,archlinux,fedora,void,manjaro,chimera}
                        Linux distribution (default: alpine)
  -t TYPE, --type TYPE  Distribution variant (minimal, full, stable) - depends
                        on distro (default: alpine-minirootfs)
  --hostname HOSTNAME   Custom Hostname (default: AndroSH)
  --resetup             Reinstall environment while preserving data
  --force               Force overwrite without confirmation
```

---

### `python main.py backup`

```
usage: main.py backup [-h] [-z] name [destination]

positional arguments:
  name         Name of the environment to backup
  destination  Backup destination directory (default:
               /sdcard/Download/AndroSH/backups)

options:
  -h, --help   show this help message and exit
  -z, --gzip   filter the archive through gzip
```

---

### `python main.py remove`

```
usage: main.py remove [-h] [--force] name

positional arguments:
  name        Name of the environment to remove

options:
  -h, --help  show this help message and exit
  --force     Force removal without confirmation
```

---

### `python main.py launch`

```
usage: main.py launch [-h] [-c LAUNCH_COMMAND] name

positional arguments:
  name                  Name of the environment to launch

options:
  -h, --help            show this help message and exit
  -c LAUNCH_COMMAND, --command LAUNCH_COMMAND
                        launch command and exit
```

---

### `python main.py rish`

```
usage: main.py rish [-h] [-c RISH_COMMAND]

options:
  -h, --help            show this help message and exit
  -c RISH_COMMAND, --command RISH_COMMAND
                        launch command and exit
```

---

### `python main.py clean`

```
usage: main.py clean [-h] name

positional arguments:
  name        Environment name to clean

options:
  -h, --help  show this help message and exit
```

---

### `python main.py install`

```
usage: main.py install [-h] [--path PATH] [--name NAME]

options:
  -h, --help   show this help message and exit
  --path PATH  Installation directory for global script (default: None)
  --name NAME  Command name for global access (default: androsh)
```

---

### `python main.py list`

```
usage: main.py list [-h]

options:
  -h, --help  show this help message and exit
```

---

### `python main.py lsd`

```
usage: main.py lsd [-h]

options:
  -h, --help  show this help message and exit
```

---

### `python main.py download`

```
usage: main.py download [-h] --type TYPE [--file FILE]
                        {alpine,debian,ubuntu,kali-nethunter,archlinux,fedora,void,manjaro,chimera}

positional arguments:
  {alpine,debian,ubuntu,kali-nethunter,archlinux,fedora,void,manjaro,chimera}
                        Distribution to download

options:
  -h, --help            show this help message and exit
  --type TYPE           Distribution variant (required)
  --file FILE, -f FILE  Custom filename for downloaded archive
```

---

### `python main.py distro`

```
usage: main.py distro [-h] {list,download,info,urls} ...

positional arguments:
  {list,download,info,urls}
                        Distro subcommand
    list                List available distributions
    download            Download distribution
    info                Get distribution information
    urls                Show download URLs

options:
  -h, --help            show this help message and exit
```

---
*Documentation automatically generated by GitHub Actions*
