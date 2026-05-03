import os
import yaml
import subprocess
import shutil
import json
import re
import requests

def run_command(command, cwd=None):
    try:
        subprocess.check_call(command, cwd=cwd, shell=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False

def parse_gradle_properties(file_path):
    properties = {}
    if not os.path.exists(file_path):
        return properties
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    properties[parts[0].strip()] = parts[1].strip()
    return properties

def replace_variables(content, variables):
    def replace_match(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    
    return re.sub(r'\{\{\s*([\w\.-]+)\s*\}\}', replace_match, content)

def generate_redirect_page(path, target_url):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = f"""---
search:
  exclude: true
---

<meta http-equiv="refresh" content="0; url={target_url}">
<link rel="canonical" href="{target_url}">

Redirecting to <a href="{target_url}">{target_url}</a>...
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def update_zensical_toml(mods_nav_info):
    toml_path = 'zensical.toml'
    if not os.path.exists(toml_path):
        return
    
    with open(toml_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    in_nav = False
    
    for line in lines:
        if 'nav = [' in line:
            in_nav = True
            new_lines.append(line)
            new_lines.append('    { "Home" = "index.md" },\n')
            new_lines.append('    { "Team" = "team.md" },\n')
            new_lines.append('    { "License" = "license.md" },\n')
            new_lines.append('    { "Projects" = [\n')
            new_lines.append('        "mods/index.md",\n')
            
            for mod in mods_nav_info:
                mod_id = mod['id']
                mod_name = mod['name']
                versions = mod['versions_detail']
                
                if not versions:
                    continue
                
                # Use the first version as default
                default_v = versions[0]['mc']
                default_pages = versions[0]['pages']
                
                new_lines.append(f'        {{ "{mod_name}" = [\n')
                new_lines.append(f'            {{ "{mod_name}" = "projects/{mod_id}/{default_v}/index.md" }},\n')
                
                def get_section_nav(section_name):
                    idx_path = os.path.join('docs', 'projects', mod_id, default_v, section_name, 'index.md')
                    if not os.path.exists(idx_path): return None
                    try:
                        with open(idx_path, 'r') as f:
                            content = f.read()
                            if content.startswith('---'):
                                parts = content.split('---')
                                if len(parts) >= 3:
                                    meta = yaml.safe_load(parts[1])
                                    if meta and 'nav' in meta:
                                        return meta['nav']
                    except: pass
                    return None

                has_api = any(p.startswith('api/') for p in default_pages)
                has_wiki = any(p.startswith('wiki/') for p in default_pages)

                if has_api:
                    new_lines.append(f'            {{ "Documentation" = [\n')
                    custom_api_nav = get_section_nav('api')
                    if custom_api_nav:
                        for item in custom_api_nav:
                            for title, path in item.items():
                                new_lines.append(f'                {{ "{title}" = "projects/{mod_id}/{default_v}/api/{path}" }},\n')
                    else:
                        api_pages = [p for p in default_pages if p.startswith('api/')]
                        for p in api_pages:
                            title = os.path.basename(p).replace('.md', '').capitalize()
                            if title.lower() == 'index': title = "Documentation"
                            new_lines.append(f'                {{ "{title}" = "projects/{mod_id}/{default_v}/{p}" }},\n')
                    new_lines.append(f'            ] }},\n')
                
                if has_wiki:
                    new_lines.append(f'            {{ "Wiki" = [\n')
                    custom_wiki_nav = get_section_nav('wiki')
                    if custom_wiki_nav:
                        for item in custom_wiki_nav:
                            for title, path in item.items():
                                new_lines.append(f'                {{ "{title}" = "projects/{mod_id}/{default_v}/wiki/{path}" }},\n')
                    else:
                        wiki_pages = [p for p in default_pages if p.startswith('wiki/')]
                        for p in wiki_pages:
                            title = os.path.basename(p).replace('.md', '').capitalize()
                            if title.lower() == 'index': title = "Wiki"
                            new_lines.append(f'                {{ "{title}" = "projects/{mod_id}/{default_v}/{p}" }},\n')
                    new_lines.append(f'            ] }},\n')
                
                new_lines.append('        ] },\n')
            
            new_lines.append('    ] },\n')
            new_lines.append(']\n')
            continue
        
        if in_nav:
            if line.strip() == ']':
                in_nav = False
            continue
        
        new_lines.append(line)

    with open(toml_path, 'w') as f:
        f.writelines(new_lines)

def get_modrinth_metadata(modrinth_url):
    if not modrinth_url:
        return None
        
    match = re.search(r'modrinth\.com/mod/([^/]+)', modrinth_url)
    if not match:
        return None
    slug = match.group(1)
    
    cache_path = '.github/scripts/modrinth_cache.json'
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache = json.load(f)
        except:
            pass
            
    if slug in cache:
        return cache[slug]
        
    print(f"Fetching Modrinth metadata for {slug}...")
    try:
        headers = {'User-Agent': 'PlaygroundMods/Docs-Sync (palmmc@gmail.com)'}
        resp = requests.get(f"https://api.modrinth.com/v2/project/{slug}", headers=headers)
        if resp.ok:
            data = resp.json()
            metadata = {
                "summary": data.get("description", ""),
                "icon_url": data.get("icon_url", "")
            }
            cache[slug] = metadata
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=2)
            return metadata
    except Exception as e:
        print(f"Failed to fetch Modrinth metadata for {slug}: {e}")
        
    return None

def get_github_metadata(github_url):
    if not github_url:
        return None
        
    match = re.search(r'github\.com/([^/]+)/([^/]+)', github_url)
    if not match:
        return None
    repo = f"{match.group(1)}/{match.group(2)}"
    
    cache_path = '.github/scripts/github_cache.json'
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cache = json.load(f)
        except:
            pass
            
    if repo in cache:
        return cache[repo]
        
    print(f"Fetching GitHub metadata for {repo}...")
    try:
        resp = requests.get(f"https://api.github.com/repos/{repo}")
        if resp.ok:
            data = resp.json()
            metadata = {
                "description": data.get("description", "")
            }
            cache[repo] = metadata
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=2)
            return metadata
    except Exception as e:
        print(f"Failed to fetch GitHub metadata for {repo}: {e}")
        
    return None

def generate_projects_index(mods_info):
    index_path = 'docs/mods/index.md'
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Try to preserve existing creation date
    creation_date = now
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
                date_match = re.search(r'^date:\s*(.*)', existing_content, re.MULTILINE)
                if date_match:
                    creation_date = date_match.group(1).strip()
        except:
            pass

    content = f"""---
title: Projects
icon: lucide/briefcase
date: {creation_date}
updated: {now}
authors:
  - playground
---

Here you can find information and documentation for all of our mods!

"""
    for mod in mods_info:
        mod_id = mod['id']
        name = mod['name']
        description = mod.get('description', '')
        modrinth = mod.get('modrinth', '')
        github = mod.get('github', '')
        thumbnail = mod.get('thumbnail', '')
        
        base_url = f"../projects/{mod_id}/"
        
        if thumbnail:
            content += f'## <img src="{thumbnail}" width="48" style="vertical-align: middle; border-radius: 4px; margin-right: 4px;"> <a href="{base_url}" class="pgm-clean-link">{name}</a>\n'
        else:
            content += f'## <a href="{base_url}" class="pgm-clean-link">{name}</a>\n'
            
        if description:
            content += f"{description}\n\n"
        
        links = []
        if mod.get('has_api'):
            links.append(f'- [Documentation]({base_url}api/)')
        if mod.get('has_wiki'):
            links.append(f'- [Wiki]({base_url}wiki/)')
        if github:
            links.append(f'- [GitHub]({github})')
        if modrinth:
            links.append(f'- [Modrinth]({modrinth})')
            
        if links:
            content += "\n".join(links) + "\n\n"
        
        content += "\n"
        
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)

def cleanup_cache():
    cache_dir = '.cache'
    if os.path.exists(cache_dir):
        print("Clearing builder cache...")
        try:
            shutil.rmtree(cache_dir)
        except Exception as e:
            print(f"Warning: Could not clear cache: {e}")

def main():
    config_path = 'mods.yaml'
    if not os.path.exists(config_path):
        print("mods.yaml not found.")
        return

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    mods_dir = os.path.join('docs', 'projects')
    if not os.path.exists(mods_dir):
        os.makedirs(mods_dir, exist_ok=True)

    cleanup_cache()

    temp_dir = 'temp_sync'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    all_mods_info = []
    mods_nav_info = []

    for mod in config.get('mods', []):
        mod_id = mod['id']
        mod_name = mod['name']
        repo_url = mod['github']
        versions = mod.get('versions', [])
        
        mod_description = mod.get('description', '')
        mod_modrinth = mod.get('modrinth', '')
        mod_github = mod.get('github', '')
        mod_icon_path = mod.get('icon', '')
        
        github_icon_url = None
        if mod_github and mod_icon_path:
            gh_match = re.search(r'github\.com/([^/]+)/([^/]+)', mod_github)
            if gh_match:
                owner, repo = gh_match.group(1), gh_match.group(2)
                clean_icon_path = mod_icon_path.lstrip('/')
                github_icon_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{clean_icon_path}"

        github_meta = get_github_metadata(mod_github)
        modrinth_meta = get_modrinth_metadata(mod_modrinth)
        
        if not mod_description and github_meta:
            mod_description = github_meta.get('description', '')
            
        if modrinth_meta:
            mod_thumbnail_fallback = modrinth_meta.get('icon_url')
        else:
            mod_thumbnail_fallback = None
        
        if github_icon_url:
            mod_thumbnail_fallback = github_icon_url

        print(f"Syncing {mod_name} ({mod_id})...")
        mod_path = os.path.join(mods_dir, mod_id)
        if os.path.exists(mod_path):
            shutil.rmtree(mod_path)
        os.makedirs(mod_path, exist_ok=True)
        
        mod_versions_detail = []
        has_api = False
        has_wiki = False
        thumbnail_url = None

        for v in versions:
            mc_version = v['mc']
            branch = v['branch']
            
            clone_path = os.path.join(temp_dir, f"{mod_id}_{mc_version}")
            if not run_command(['git', 'clone', '--depth', '1', '--branch', branch, repo_url, clone_path]):
                continue
            gradle_props = parse_gradle_properties(os.path.join(clone_path, 'gradle.properties'))
            src_docs_path = os.path.join(clone_path, 'docs')

            dest_version_path = os.path.join(mod_path, mc_version)
            os.makedirs(dest_version_path, exist_ok=True)
            
            synced_pages = []
            if os.path.exists(src_docs_path):
                for root, _, files in os.walk(src_docs_path):
                    for file in files:
                        if file.endswith('.md'):
                            rel_file = os.path.relpath(os.path.join(root, file), src_docs_path)
                            dest_file = os.path.join(dest_version_path, rel_file)
                            if rel_file.lower() == 'readme.md':
                                dest_file = os.path.join(os.path.dirname(dest_file), 'index.md')
                                rel_file = 'index.md'
                            elif rel_file.lower() == 'api.md' and os.path.dirname(rel_file) == '':
                                dest_file = os.path.join(os.path.dirname(dest_file), 'api', 'index.md')
                                rel_file = 'api/index.md'
                            elif rel_file.lower() == 'wiki.md' and os.path.dirname(rel_file) == '':
                                dest_file = os.path.join(os.path.dirname(dest_file), 'wiki', 'index.md')
                                rel_file = 'wiki/index.md'
                            
                            if rel_file.startswith('api/'): has_api = True
                            if rel_file.startswith('wiki/'): has_wiki = True
                            
                            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            processed_content = replace_variables(content, gradle_props)
                            
                            if rel_file == 'index.md':
                                if github_icon_url:
                                    if 'thumbnail:' in processed_content:
                                        processed_content = re.sub(r'thumbnail:\s*["\']?([^"\']+)["\']?', f'thumbnail: "{github_icon_url}"', processed_content)
                                    else:
                                        processed_content = re.sub(r'^---', f'---\nthumbnail: "{github_icon_url}"', processed_content, count=1)
                                    thumbnail_url = github_icon_url
                                
                                if mod_name != "Wayfarer":
                                    processed_content = re.sub(r'title:\s*["\']?Wayfarer["\']?', f'title: "{mod_name}"', processed_content)
                                    processed_content = processed_content.replace('Wayfarer project portal', f'{mod_name} project portal')
                                    processed_content = processed_content.replace('use Wayfarer\'s features', f'use {mod_name}\'s features')
                                    processed_content = processed_content.replace('for players using Wayfarer', f'for players using {mod_name}')

                                if not thumbnail_url:
                                    thumb_match = re.search(r'thumbnail:\s*["\']?([^"\']+)["\']?', processed_content)
                                    if thumb_match:
                                        thumbnail_url = thumb_match.group(1)
                                    else:
                                        icon_match = re.search(r'icon:\s*["\']?([^"\']+)["\']?', processed_content)
                                        if icon_match and "://" in icon_match.group(1):
                                            thumbnail_url = icon_match.group(1)

                            with open(dest_file, 'w', encoding='utf-8') as f:
                                f.write(processed_content)
                            synced_pages.append(rel_file)

            mod_versions_detail.append({
                "mc": mc_version,
                "pages": synced_pages
            })

        with open(os.path.join(mod_path, 'versions.json'), 'w') as f:
            json.dump(mod_versions_detail, f, indent=2)
        
        all_mods_info.append({
            "id": mod_id, 
            "name": mod_name, 
            "description": mod_description,
            "modrinth": mod_modrinth,
            "github": mod_github,
            "has_api": has_api,
            "has_wiki": has_wiki,
            "thumbnail": thumbnail_url or mod_thumbnail_fallback
        })
        mods_nav_info.append({"id": mod_id, "name": mod_name, "versions_detail": mod_versions_detail})

        if mod_versions_detail:
            default_v = mod_versions_detail[0]['mc']
            default_pages = mod_versions_detail[0]['pages']
            for page in default_pages:
                rel_path = page
                if rel_path.endswith('index.md'):
                    target_path = os.path.join(mods_dir, mod_id, rel_path)
                    dir_part = os.path.dirname(rel_path); target_url = f"/projects/{mod_id}/{default_v}/{dir_part}/" if dir_part else f"/projects/{mod_id}/{default_v}/"
                else:
                    target_path = os.path.join(mods_dir, mod_id, rel_path)
                    target_url = f"/projects/{mod_id}/{default_v}/{rel_path.replace('.md', '/')}"
                
                if not os.path.isdir(target_path):
                    generate_redirect_page(target_path, target_url)

    generate_projects_index(all_mods_info)
    update_zensical_toml(mods_nav_info)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    print("Mod sync completed!")

if __name__ == "__main__":
    main()
