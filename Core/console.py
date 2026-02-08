import shutil
import random
import time
import pyfiglet
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from Core import name, developer, version, url
from enum import Enum

class LogLevel(Enum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3

class console:
    def __init__(self, log_level: LogLevel = LogLevel.NORMAL, time_style: bool = False):
        self.console = Console()
        self.print = self.console.print
        self.log_level = log_level
        self.time_style = time_style
    
    def set_level(self, level: LogLevel):
        self.log_level = level

    def time(self, message: str):
        if self.time_style:
            return time.strftime("%I:%M:%S")
        else:
            return message

    def status(self, message: str):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.print(f"[cyan][{self.time('STATUS')}][/cyan] {message}")
    
    def error(self, message: str):
        if self.log_level.value >= LogLevel.QUIET.value:
            self.console.print(f"[bold red][{self.time('ERROR')}][/bold red] {message}")
    
    def warning(self, message: str):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.print(f"[yellow][{self.time('WARNING')}][/yellow] {message}")
    
    def success(self, message: str):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.print(f"[green][{self.time('SUCCESS')}][/green] {message}")
    
    def info(self, message: str):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.print(f"[blue][{self.time('INFO')}][/blue] {message}")
    
    def verbose(self, message: str):
        if self.log_level.value >= LogLevel.VERBOSE.value:
            self.console.print(f"[dim blue][{self.time('VERBOSE')}][/dim blue] {message}")
        
    def debug(self, message: str):
        if self.log_level.value >= LogLevel.DEBUG.value:
            self.console.print(f"[magenta][{self.time('DEBUG')}][/magenta] {message}")
    
    def header(self, title: str):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.print(Panel.fit(f"[bold]{title}[/bold]", border_style="green"))
    
    def divider(self):
        if self.log_level.value >= LogLevel.NORMAL.value:
            self.console.rule(style="white")
    
    def input(self, message: str):
        return self.console.input(f"[bold yellow][{self.time('QUESTION')}][/bold yellow] {message}")
    
    def table(self, data: dict, title: str = ""):
        if self.log_level.value >= LogLevel.NORMAL.value:
            table = Table(title=title, box=box.ROUNDED)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in data.items():
                table.add_row(str(key), str(value))
            
            self.console.print(table)
    
    def banner(self):
        if self.log_level.value >= LogLevel.NORMAL.value:
            width = shutil.get_terminal_size().columns
            fonts = pyfiglet.Figlet().getFonts()
            fig = pyfiglet.Figlet(font=random.choice(fonts), justify="center", width=width)
            logo = fig.renderText(name)
            print(logo)
            d = \
            f"Created by [bold green]{developer['name']}[/bold green]\n"+\
            f"[bold black]GitHub[/bold black]: [cyan]{developer['github']}[/cyan]\n"+\
            f"Version: [red]{version}[/red]\n"+\
            f"[underline white]{url}[/underline white]"
            
            self.header(d)