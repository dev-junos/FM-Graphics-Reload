"""Local folder and ZIP import. Archive paths never select extraction targets outside imports."""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import uuid
import zipfile
import client
import skins
from app_storage import skin_root
from text_codec import zip_name

MAX_ENTRIES=20000
MAX_BYTES=32*1024**3


def discover(value,root_name=None):
    root=Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('스킨 폴더 또는 ZIP 파일을 선택해 주세요.')
    result=[]
    for directory,dirs,_ in os.walk(root,followlinks=False):
        folder=Path(directory)
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not d.lower().startswith(('_bak_','__macosx'))
                       and not (folder/d).is_symlink() and not (folder/d).is_junction())
        if skins.bundle_files(folder):
            relative=folder.relative_to(root)
            parts=[root_name or root.name,*relative.parts]
            result.append(dict(id=uuid.uuid4().hex,name=' / '.join(parts),leaf_name=parts[-1],
                               naming_version=1,filename_encoding_version=1,context='',path=str(folder),enabled=False))
    if not result:raise ValueError('이 폴더와 하위 폴더에 .bundle 스킨 파일이 없습니다.')
    return result


def member_path(info):
    name=zip_name(info).replace('\\','/')
    parts=name.rstrip('/').split('/')
    if (not name or '\0' in name or name.startswith('/') or PureWindowsPath(name).drive
            or any(p in ('','.', '..') for p in parts)
            or any(p.endswith((' ','.')) or re.search(r'[<>:"|?*\x00-\x1f]',p) for p in parts)
            or any(re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p,re.I) for p in parts)
            or stat.S_ISLNK(info.external_attr>>16)):
        raise ValueError('ZIP에 사용할 수 없는 경로가 들어 있습니다: '+info.filename)
    return Path(*parts)


def extract_zip(value,storage=None,progress=lambda s:None):
    source=Path(value).expanduser().resolve(strict=True)
    if source.suffix.lower()!='.zip' or not zipfile.is_zipfile(source):raise ValueError('폴더 또는 올바른 ZIP 파일을 추가해 주세요.')
    root=Path(storage) if storage else skin_root()/'archives'
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    progress('ZIP 파일을 확인하고 있습니다…')
    digest=skins._hash(source);destination=root/digest
    if destination.is_dir():
        marker=destination/'.import.json'
        if not marker.is_file():raise ValueError('이 ZIP의 이전 가져오기가 완료되지 않았습니다.')
        manifest=json.loads(marker.read_text(encoding='utf-8'))
        if manifest.get('archive_sha256')!=digest:raise ValueError('보관한 ZIP 자료가 일치하지 않습니다.')
        for item in manifest['files']:
            target=(destination/item['name']).resolve()
            if not target.is_relative_to(destination) or not target.is_file() or skins._hash(target)!=item['sha256']:
                raise ValueError('가져온 ZIP의 스킨 파일이 변경됐습니다. 수정한 폴더는 폴더로 추가해 주세요.')
        return destination
    with zipfile.ZipFile(source) as archive:
        members=archive.infolist()
        if len(members)>MAX_ENTRIES:raise ValueError('ZIP 안의 파일 수가 너무 많습니다.')
        chosen=[];names=set();total=0
        for info in members:
            relative=member_path(info)
            if info.is_dir() or relative.suffix.lower()!='.bundle' or any(p.lower().startswith(('__macosx','_bak_','.')) for p in relative.parts):continue
            identity=str(relative).casefold()
            if identity in names:raise ValueError('ZIP에 이름이 겹치는 스킨 파일이 있습니다: '+str(relative))
            names.add(identity)
            if info.flag_bits&1:raise ValueError('암호가 설정된 ZIP은 지원하지 않습니다.')
            total+=info.file_size
            if total>MAX_BYTES:raise ValueError('ZIP의 스킨 파일 크기가 32GB를 넘습니다.')
            chosen.append((info,relative))
        if not chosen:raise ValueError('ZIP 안에 .bundle 스킨 파일이 없습니다.')
        if shutil.disk_usage(root).free<total+64*1024**2:raise ValueError('ZIP을 풀 디스크 공간이 부족합니다.')
        temporary=root/('.preparing_'+uuid.uuid4().hex);temporary.mkdir()
        manifest=[];written=0
        try:
            for index,(info,relative) in enumerate(chosen):
                progress(f'ZIP에서 스킨을 가져오는 중… {index+1}/{len(chosen)}')
                target=(temporary/relative).resolve()
                if not target.is_relative_to(temporary):raise ValueError('ZIP 경로가 가져오기 폴더를 벗어납니다.')
                target.parent.mkdir(parents=True,exist_ok=True);hasher=hashlib.sha256();size=0
                with archive.open(info) as reader,target.open('xb') as writer:
                    while chunk:=reader.read(1024*1024):
                        size+=len(chunk);written+=len(chunk)
                        if size>info.file_size or written>MAX_BYTES:raise ValueError('ZIP 파일 크기 검증에 실패했습니다.')
                        writer.write(chunk);hasher.update(chunk)
                if size!=info.file_size:raise ValueError('ZIP 파일이 완전하지 않습니다.')
                manifest.append(dict(name=relative.as_posix(),sha256=hasher.hexdigest()))
            if skins._hash(source)!=digest:raise ValueError('가져오는 중 ZIP 파일이 바뀌었습니다. 다시 추가해 주세요.')
            (temporary/'.import.json').write_text(json.dumps(dict(archive_sha256=digest,files=manifest),ensure_ascii=False),encoding='utf-8')
            temporary.rename(destination)
        except Exception:
            # This is a fresh, validated staging directory owned by this import only.
            if temporary.is_dir() and temporary.resolve().parent==root and temporary.name.startswith('.preparing_'):
                shutil.rmtree(temporary)
            raise
    return destination


def copy_folder(item,storage=None,progress=lambda s:None):
    """Register a verified snapshot, never the external source directory."""
    source=Path(item['path']).resolve(strict=True)
    files=skins.bundle_files(source)
    if not files:raise ValueError('복사할 .bundle 스킨 파일이 없습니다.')
    root=(Path(storage) if storage else skin_root())/'folders'
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    manifest=[];total=0
    for index,(name,path) in enumerate(sorted(files.items())):
        progress(f"{item['name']} · 복사할 파일 확인 중… {index+1}/{len(files)}")
        size=path.stat().st_size;total+=size
        if total>MAX_BYTES:raise ValueError('스킨 폴더의 파일 크기가 32GB를 넘습니다.')
        manifest.append(dict(name=name,size=size,sha256=skins._hash(path)))
    digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    label=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',item.get('leaf_name',source.name)).strip(' .')[:64] or 'skin'
    destination=root/(label+'_'+digest[:16])
    if destination.exists():
        marker=destination/'.import.json'
        if not marker.is_file():raise ValueError('보관된 스킨의 복사 완료 기록이 없습니다.')
        recorded=json.loads(marker.read_text(encoding='utf-8'))
        if recorded.get('content_sha256')!=digest:raise ValueError('보관된 스킨과 선택한 스킨이 일치하지 않습니다.')
        if set(skins.bundle_files(destination))!=set(files):raise ValueError('보관된 스킨의 파일 목록이 바뀌었습니다.')
        for file in manifest:
            if skins._hash(destination/file['name'])!=file['sha256']:
                raise ValueError('보관된 스킨 파일이 변경됐습니다. 다른 이름으로 폴더를 추가해 주세요.')
    else:
        if shutil.disk_usage(root).free<total+64*1024**2:raise ValueError('스킨을 복사할 디스크 공간이 부족합니다.')
        temporary=root/('.preparing_'+uuid.uuid4().hex);temporary.mkdir()
        try:
            for index,file in enumerate(manifest):
                progress(f"{item['name']} · 보관 폴더로 복사 중… {index+1}/{len(manifest)}")
                target=temporary/file['name'];shutil.copyfile(files[file['name']],target)
                if target.stat().st_size!=file['size'] or skins._hash(target)!=file['sha256']:
                    raise ValueError('복사 중 스킨 파일이 바뀌었습니다. 파일 수정을 마친 뒤 다시 추가해 주세요.')
            (temporary/'.import.json').write_text(json.dumps(dict(content_sha256=digest,files=manifest),ensure_ascii=False),encoding='utf-8')
            temporary.rename(destination)
        except Exception:
            if temporary.is_dir() and temporary.resolve().parent==root and temporary.name.startswith('.preparing_'):
                shutil.rmtree(temporary)
            raise
    return dict(item,path=str(destination),source_path=str(source),managed=True)


def add(data,value,storage=None,progress=lambda s:None):
    source=Path(value).expanduser().resolve(strict=True)
    if source.is_dir():found=[copy_folder(item,storage,progress) for item in discover(source)]
    else:
        # Independent snapshots allow removing one variant without affecting siblings.
        root=(Path(storage) if storage else skin_root()).resolve()
        root.mkdir(parents=True,exist_ok=True)
        staging=root/('.extracting_'+uuid.uuid4().hex);staging.mkdir()
        try:
            extracted=extract_zip(source,staging,progress)
            found=[dict(copy_folder(item,storage,progress),source_path=str(source))
                   for item in discover(extracted,source.stem)]
        finally:
            if staging.is_dir() and staging.resolve().parent==root and staging.name.startswith('.extracting_'):
                shutil.rmtree(staging)
    existing={str(Path(i['path']).resolve()).casefold() for i in data['skins']}
    found=[i for i in found if i['path'].casefold() not in existing]
    data['skins'].extend(found)
    return found


def add_many(data,values,storage=None,progress=lambda s:None):
    added=[];errors=[]
    for value in values:
        try:added.extend(add(data,value,storage,progress))
        except (OSError,ValueError,zipfile.BadZipFile,NotImplementedError,RuntimeError) as exc:errors.append(dict(path=str(value),error=str(exc)))
    return dict(added=added,errors=errors)


def migrate_name(item):
    """Recover the selected root from 0.6 source/context metadata, without source I/O."""
    if item.get('naming_version')==1:return
    source=Path(item.get('source_path') or item['path'])
    context=[p for p in item.get('context','').replace('\\','/').split('/') if p not in ('','.','..')]
    if source.suffix.lower()=='.zip':
        path=Path(item['path'])
        archives=(skin_root()/'archives').resolve()
        try:relative=path.resolve().relative_to(archives)
        except ValueError:parts=[source.stem,*context,item['name']]
        else:parts=[source.stem,*relative.parts[1:]]
    else:
        parent=source.parent
        for _ in context:parent=parent.parent
        # A non-empty context identifies a child of the originally selected root.
        if context:parts=[parent.name,*context,source.name]
        elif item.get('context')=='.':parts=[source.parent.name,source.name]
        else:parts=[source.name]
    item['name']=' / '.join(parts);item['context']='';item['naming_version']=1


def delete_managed(item,remaining,storage=None):
    """Delete only owned snapshots; legacy archive siblings keep their own files."""
    if not item.get('managed'):return False
    root=(Path(storage) if storage else skin_root()).resolve()
    raw=Path(item['path']).absolute();target=raw.resolve()
    if not target.is_relative_to(root) or target==root:
        raise ValueError('보관 폴더 밖의 경로는 삭제하지 않습니다: '+str(target))
    relative=target.relative_to(root)
    if len(relative.parts)<2 or relative.parts[0] not in ('folders','archives'):
        raise ValueError('등록된 스킨 보관 경로를 확인해 주세요.')
    # Refuse links, including links in parent components, before deleting anything.
    for path in (raw,*raw.parents):
        if path==root:break
        if path.is_symlink() or path.is_junction():raise ValueError('연결된 폴더는 삭제할 수 없습니다: '+str(path))
    others=[Path(i['path']).resolve() for i in remaining]
    if target in others:return False
    owner=root/relative.parts[0]/relative.parts[1]
    if relative.parts[0]=='folders' and len(relative.parts)!=2:
        raise ValueError('개별 스킨의 보관 경로가 올바르지 않습니다.')
    if not target.exists():return True
    if not (owner/'.import.json').is_file():raise ValueError('스킨 복사 완료 기록이 없어 삭제를 중단했습니다.')
    shared=any(p.is_relative_to(owner) for p in others)
    if not shared:
        # Resolved absolute target is an owned child of skins/folders or skins/archives.
        for directory,dirs,files in os.walk(owner,followlinks=False):
            for name in dirs+files:
                path=Path(directory)/name
                if path.is_symlink() or path.is_junction():raise ValueError('보관 폴더에 연결 파일이 있어 삭제를 중단했습니다.')
        shutil.rmtree(owner)
    else:
        # Old ZIP imports may have bundle-bearing parent and child entries.
        # Delete direct bundles only; never recurse into another registered variant.
        for path in skins.bundle_files(target).values():
            if path.is_symlink() or path.resolve().parent!=target:raise ValueError('연결된 스킨 파일은 삭제할 수 없습니다.')
        for path in skins.bundle_files(target).values():path.unlink()
        current=target
        while current!=owner:
            try:current.rmdir()
            except OSError:break
            current=current.parent
    return True
