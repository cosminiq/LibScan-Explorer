import os
import re
import csv
import json
import argparse
import configparser
import requests
from collections import defaultdict
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

class LibraryAnalyzer:
    def __init__(self, project_dir, output_file, github_token=None):
        self.project_dir = os.path.abspath(project_dir)
        self.output_file = output_file
        self.github_token = github_token
        self.libraries = defaultdict(lambda: {
            "name": "",
            "version": "",
            "author": "",
            "github_url": "",
            "description": "",
            "homepage": "",
            "latest_version": "",
            "files_found_in": set(),
            "source": ""
        })
        self.headers = {}
        if github_token:
            self.headers = {"Authorization": f"token {github_token}"}
    
    def run(self):
        print(f"Scanez proiectul la locația: {self.project_dir}")
        
        # Scanează fișierele sursă
        source_files = self.find_files(['.cpp', '.h', '.ino'])
        for file_path in source_files:
            self.extract_libraries_from_code(file_path)
        
        # Scanează fișierele specifice PlatformIO
        self.analyze_platformio_files()
        
        # Scanează fișierele specifice Arduino
        self.analyze_arduino_library_files()
        
        # Îmbogățește informațiile despre biblioteci cu date de pe GitHub
        self.enrich_with_github_data()
        
        # Scrie datele în fișierul CSV
        self.write_to_csv()
        
        return len(self.libraries)
    
    def find_files(self, extensions):
        """Găsește toate fișierele cu extensiile specificate în directorul dat."""
        matched_files = []
        for dirpath, dirnames, filenames in os.walk(self.project_dir):
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    matched_files.append(os.path.join(dirpath, filename))
        return matched_files
    
    def extract_libraries_from_code(self, file_path):
        """Extrage bibliotecile din fișier bazat pe directive #include."""
        include_pattern = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
        version_pattern = re.compile(r'#define\s+(\w+_VERSION|VERSION_\w+)\s+["\']?([0-9\.]+)["\']?')
        github_pattern = re.compile(r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)')
        author_pattern = re.compile(r'@author\s+([^\n]+)')
        desc_pattern = re.compile(r'/\*\*\s*\n\s*\*\s*([^\n]+)')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
                # Extrage include-urile
                includes = include_pattern.findall(content)
                for inc in includes:
                    lib_name = os.path.basename(inc)
                    if lib_name not in self.libraries:
                        self.libraries[lib_name]["name"] = lib_name
                        self.libraries[lib_name]["source"] = "code"
                    
                    rel_path = os.path.relpath(file_path, self.project_dir)
                    self.libraries[lib_name]["files_found_in"].add(rel_path)
                
                # Pentru fiecare bibliotecă, încearcă să găsești informații suplimentare
                for lib_name in self.libraries:
                    # Versiunea
                    if not self.libraries[lib_name]["version"]:
                        lib_base = os.path.splitext(lib_name)[0].upper()
                        for version_var, version_val in version_pattern.findall(content):
                            if lib_base in version_var:
                                self.libraries[lib_name]["version"] = version_val
                                break
                    
                    # Link GitHub
                    if not self.libraries[lib_name]["github_url"]:
                        github_matches = github_pattern.findall(content)
                        if github_matches:
                            self.libraries[lib_name]["github_url"] = f"https://github.com/{github_matches[0]}"
                    
                    # Autor
                    if not self.libraries[lib_name]["author"]:
                        author_matches = author_pattern.findall(content)
                        if author_matches:
                            self.libraries[lib_name]["author"] = author_matches[0].strip()
                    
                    # Descriere
                    if not self.libraries[lib_name]["description"]:
                        desc_matches = desc_pattern.findall(content)
                        if desc_matches:
                            self.libraries[lib_name]["description"] = desc_matches[0].strip()
        
        except (UnicodeDecodeError, IOError) as e:
            print(f"Eroare la citirea fișierului {file_path}: {e}")
    
    def analyze_platformio_files(self):
        """Analizează fișierele specifice PlatformIO pentru informații despre biblioteci."""
        # Verifică platformio.ini
        platformio_ini = os.path.join(self.project_dir, "platformio.ini")
        if os.path.exists(platformio_ini):
            try:
                config = configparser.ConfigParser()
                config.read(platformio_ini)
                
                for section in config.sections():
                    if "env:" in section:
                        if config.has_option(section, "lib_deps"):
                            libs = config.get(section, "lib_deps").split("\n")
                            for lib_dep in libs:
                                lib_dep = lib_dep.strip()
                                if not lib_dep or lib_dep.startswith("#"):
                                    continue
                                
                                # Analizează dependența bibliotecii
                                self.parse_platformio_lib_dep(lib_dep)
            
            except Exception as e:
                print(f"Eroare la citirea platformio.ini: {e}")
        
        # Verifică .platformio directory pentru metadate
        platformio_dir = os.path.join(self.project_dir, ".platformio")
        if os.path.exists(platformio_dir):
            for dirpath, dirnames, filenames in os.walk(platformio_dir):
                # Caută fișiere lib_deps_...json care conțin date despre biblioteci
                for filename in filenames:
                    if filename.startswith("lib_deps_") and filename.endswith(".json"):
                        try:
                            with open(os.path.join(dirpath, filename), 'r') as f:
                                lib_data = json.load(f)
                                for lib in lib_data:
                                    if "name" in lib:
                                        lib_name = lib["name"]
                                        self.libraries[lib_name]["name"] = lib_name
                                        self.libraries[lib_name]["source"] = "platformio"
                                        
                                        if "version" in lib:
                                            self.libraries[lib_name]["version"] = lib["version"]
                                        
                                        if "meta" in lib:
                                            meta = lib["meta"]
                                            if "author" in meta:
                                                self.libraries[lib_name]["author"] = meta["author"]
                                            if "description" in meta:
                                                self.libraries[lib_name]["description"] = meta["description"]
                                            if "homepage" in meta:
                                                self.libraries[lib_name]["homepage"] = meta["homepage"]
                                                # Presupunem că link-ul homepage ar putea fi GitHub
                                                if "github.com" in meta["homepage"]:
                                                    self.libraries[lib_name]["github_url"] = meta["homepage"]
                        except Exception as e:
                            print(f"Eroare la procesarea {filename}: {e}")
    
    def parse_platformio_lib_dep(self, lib_dep):
        """Analizează o dependență de bibliotecă specificată în platformio.ini."""
        # Formate posibile:
        # 1. name
        # 2. name@version
        # 3. owner/name
        # 4. owner/name@version
        # 5. name=version
        # 6. git-url
        # 7. git-url#tag
        
        lib_name = ""
        lib_version = ""
        lib_url = ""
        
        if "=" in lib_dep:
            # Formatul: name=version
            parts = lib_dep.split("=", 1)
            lib_name = parts[0].strip()
            lib_version = parts[1].strip()
        elif "@" in lib_dep and not lib_dep.startswith("git+"):
            # Formatul: name@version sau owner/name@version
            parts = lib_dep.split("@", 1)
            lib_name = parts[0].strip()
            lib_version = parts[1].strip()
        elif lib_dep.startswith(("git+", "http://", "https://")):
            # Formatul: git-url sau git-url#tag
            if "#" in lib_dep:
                parts = lib_dep.split("#", 1)
                lib_url = parts[0].strip()
                lib_version = parts[1].strip()
            else:
                lib_url = lib_dep
            
            # Încercăm să extragem numele din URL
            if "github.com" in lib_url:
                parsed_url = urlparse(lib_url)
                path_parts = parsed_url.path.strip("/").split("/")
                if len(path_parts) >= 2:
                    lib_name = path_parts[1]
                    self.libraries[lib_name]["github_url"] = f"https://github.com/{path_parts[0]}/{path_parts[1]}"
            else:
                # Nu putem determina numele, folosim URL ca identificator
                lib_name = lib_url
        else:
            # Formatul: name sau owner/name
            lib_name = lib_dep
            if "/" in lib_dep and not lib_dep.startswith(("/", "./", "../")):
                # Aceasta pare a fi o dependență GitHub
                self.libraries[lib_name]["github_url"] = f"https://github.com/{lib_dep}"
        
        # Eliminăm orice spații sau ghilimele
        lib_name = lib_name.strip(' "\'')
        
        # Actualizăm datele bibliotecii
        if lib_name:
            if lib_name not in self.libraries:
                self.libraries[lib_name]["name"] = lib_name
                self.libraries[lib_name]["source"] = "platformio_ini"
            
            if lib_version and not self.libraries[lib_name]["version"]:
                self.libraries[lib_name]["version"] = lib_version
            
            if lib_url and not self.libraries[lib_name]["homepage"]:
                self.libraries[lib_name]["homepage"] = lib_url
    
    def analyze_arduino_library_files(self):
        """Analizează fișierele specifice bibliotecilor Arduino."""
        # Verifică library.properties și library.json în toate subdirectoarele
        for dirpath, dirnames, filenames in os.walk(self.project_dir):
            if "library.properties" in filenames:
                self.parse_arduino_library_properties(os.path.join(dirpath, "library.properties"))
            
            if "library.json" in filenames:
                self.parse_arduino_library_json(os.path.join(dirpath, "library.json"))
            
            # Verifică fișierele Arduino library_index.json
            if "package_index.json" in filenames:
                self.parse_arduino_package_index(os.path.join(dirpath, "package_index.json"))
    
    def parse_arduino_library_properties(self, file_path):
        """Analizează fișierul library.properties al unei biblioteci Arduino."""
        try:
            config = configparser.ConfigParser()
            # Adaugă o secțiune implicită (library.properties nu are secțiuni)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = '[global]\n' + f.read()
            config.read_string(content)
            
            if config.has_section("global"):
                lib_name = config.get("global", "name", fallback="")
                if lib_name:
                    self.libraries[lib_name]["name"] = lib_name
                    self.libraries[lib_name]["source"] = "arduino_library"
                    self.libraries[lib_name]["version"] = config.get("global", "version", fallback="")
                    self.libraries[lib_name]["author"] = config.get("global", "author", fallback="")
                    self.libraries[lib_name]["description"] = config.get("global", "sentence", fallback="")
                    
                    # Încercăm să obținem URL-ul GitHub
                    url = config.get("global", "url", fallback="")
                    if url:
                        self.libraries[lib_name]["homepage"] = url
                        if "github.com" in url:
                            self.libraries[lib_name]["github_url"] = url
        
        except Exception as e:
            print(f"Eroare la citirea {file_path}: {e}")
    
    def parse_arduino_library_json(self, file_path):
        """Analizează fișierul library.json al unei biblioteci Arduino/PlatformIO."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                lib_name = data.get("name", "")
                if lib_name:
                    self.libraries[lib_name]["name"] = lib_name
                    self.libraries[lib_name]["source"] = "arduino_library_json"
                    self.libraries[lib_name]["version"] = data.get("version", "")
                    self.libraries[lib_name]["description"] = data.get("description", "")
                    
                    # Autorul poate fi un string sau un obiect
                    author = data.get("author", "")
                    if isinstance(author, dict):
                        self.libraries[lib_name]["author"] = author.get("name", "")
                    elif isinstance(author, list) and len(author) > 0:
                        if isinstance(author[0], dict):
                            self.libraries[lib_name]["author"] = author[0].get("name", "")
                        else:
                            self.libraries[lib_name]["author"] = str(author[0])
                    else:
                        self.libraries[lib_name]["author"] = str(author)
                    
                    # Încercăm să obținem URL-ul GitHub
                    repository = data.get("repository", {})
                    if isinstance(repository, dict):
                        repo_url = repository.get("url", "")
                        if repo_url and "github.com" in repo_url:
                            self.libraries[lib_name]["github_url"] = repo_url
                    
                    homepage = data.get("homepage", "")
                    if homepage:
                        self.libraries[lib_name]["homepage"] = homepage
                        if "github.com" in homepage and not self.libraries[lib_name]["github_url"]:
                            self.libraries[lib_name]["github_url"] = homepage
        
        except Exception as e:
            print(f"Eroare la citirea {file_path}: {e}")
    
    def parse_arduino_package_index(self, file_path):
        """Analizează fișierul package_index.json pentru informații despre biblioteci."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                for package in data.get("packages", []):
                    for platform in package.get("platforms", []):
                        for tool_dep in platform.get("toolsDependencies", []):
                            name = tool_dep.get("name", "")
                            version = tool_dep.get("version", "")
                            if name:
                                if name not in self.libraries:
                                    self.libraries[name]["name"] = name
                                    self.libraries[name]["source"] = "arduino_package"
                                if version and not self.libraries[name]["version"]:
                                    self.libraries[name]["version"] = version
        
        except Exception as e:
            print(f"Eroare la citirea {file_path}: {e}")
    
    def enrich_with_github_data(self):
        """Îmbogățește informațiile despre biblioteci cu date de pe GitHub."""
        for lib_name, lib_info in self.libraries.items():
            github_url = lib_info["github_url"]
            if github_url:
                # Extrage owner/repo din URL
                parsed_url = urlparse(github_url)
                path_parts = parsed_url.path.strip("/").split("/")
                
                if len(path_parts) >= 2:
                    owner = path_parts[0]
                    repo = path_parts[1]
                    
                    # Elimină .git din numele repo-ului dacă există
                    if repo.endswith(".git"):
                        repo = repo[:-4]
                    
                    # Obține datele despre repo de pe GitHub API
                    try:
                        api_url = f"https://api.github.com/repos/{owner}/{repo}"
                        response = requests.get(api_url, headers=self.headers, timeout=10)
                        
                        if response.status_code == 200:
                            repo_data = response.json()
                            
                            # Actualizează datele bibliotecii
                            if not lib_info["description"]:
                                self.libraries[lib_name]["description"] = repo_data.get("description", "")
                            
                            # Obține ultimele release-uri pentru a vedea ultima versiune
                            releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
                            releases_response = requests.get(releases_url, headers=self.headers, timeout=10)
                            
                            if releases_response.status_code == 200:
                                releases = releases_response.json()
                                if releases:
                                    # Primul release este cel mai recent
                                    latest_version = releases[0].get("tag_name", "")
                                    # Curăță tag-ul de prefixe comune precum 'v'
                                    latest_version = latest_version.lstrip('v')
                                    self.libraries[lib_name]["latest_version"] = latest_version
                    
                    except Exception as e:
                        print(f"Eroare la obținerea datelor de pe GitHub pentru {lib_name}: {e}")
    
    def write_to_csv(self):
        """Scrie datele bibliotecilor în fișierul CSV."""
        fieldnames = [
            "name", "version", "latest_version", "author", "description", 
            "github_url", "homepage", "source", "files_found_in"
        ]
        
        try:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for lib_name, lib_info in sorted(self.libraries.items()):
                    # Convertește set-ul de fișiere într-un string
                    files_str = ", ".join(sorted(lib_info["files_found_in"]))
                    
                    row = {
                        "name": lib_name,
                        "version": lib_info["version"],
                        "latest_version": lib_info["latest_version"],
                        "author": lib_info["author"],
                        "description": lib_info["description"],
                        "github_url": lib_info["github_url"],
                        "homepage": lib_info["homepage"],
                        "source": lib_info["source"],
                        "files_found_in": files_str
                    }
                    
                    writer.writerow(row)
            
            print(f"Datele au fost scrise în {self.output_file}")
        
        except Exception as e:
            print(f"Eroare la scrierea în fișierul CSV: {e}")

def main():
    # Folosește aceste valori hardcodate în loc de argparse 
    project_dir = r"WLED\WLED-main"  # Înlocuiește cu calea proiectului tău
    output_file = "libraries.csv"  # Numele fișierului CSV de ieșire
    github_token = None  # Opțional, dacă ai un token GitHub
    
    analyzer = LibraryAnalyzer(project_dir, output_file, github_token)
    num_libraries = analyzer.run()
    
    print(f"Analiza completă. S-au găsit {num_libraries} biblioteci.")
    print(f"Rezultatele au fost salvate în {output_file}")

if __name__ == "__main__":
    main()