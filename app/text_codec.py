"""ZIP filename decoding is independent of the selected interface language."""
import struct
import unicodedata
import zlib
from pathlib import PurePosixPath, Path
import zipfile


def zip_name(info):
    name=info.orig_filename
    if info.flag_bits&0x800:return unicodedata.normalize('NFC',name)
    raw=name.encode('cp437')
    extra=info.extra;offset=0
    while offset+4<=len(extra):
        tag,size=struct.unpack_from('<HH',extra,offset);offset+=4
        data=extra[offset:offset+size];offset+=size
        if len(data)!=size:break
        if tag==0x7075 and len(data)>=5 and data[0]==1 and struct.unpack_from('<I',data,1)[0]==zlib.crc32(raw):
            try:return unicodedata.normalize('NFC',data[5:].decode('utf-8'))
            except UnicodeDecodeError:pass
    # Some old archives contain UTF-8 bytes without setting the UTF-8 flag.
    try:return unicodedata.normalize('NFC',raw.decode('utf-8'))
    except UnicodeDecodeError:pass
    # Legacy Korean Windows ZIPs. Do not make this depend on Korean/English UI.
    try:
        candidate=raw.decode('cp949')
        if any('\uac00'<=c<='\ud7a3' for c in candidate):return unicodedata.normalize('NFC',candidate)
    except UnicodeDecodeError:pass
    return name


def repair_import_names(items):
    """Repair old display metadata from original ZIP headers; never rename sources."""
    groups={}
    for item in items:
        source=Path(item.get('source_path',''))
        if source.suffix.lower()=='.zip':groups.setdefault(source,[]).append(item)
    for source,entries in groups.items():
        if all(i.get('filename_encoding_version')==1 for i in entries):continue
        try:
            replacements={}
            with zipfile.ZipFile(source) as archive:
                for info in archive.infolist():
                    raw=PurePosixPath(info.orig_filename.replace('\\','/'))
                    decoded=PurePosixPath(zip_name(info).replace('\\','/'))
                    if len(raw.parts)!=len(decoded.parts):continue
                    for end in range(1,len(raw.parts)+1):
                        old=' / '.join([source.stem,*raw.parts[:end]])
                        new=' / '.join([source.stem,*decoded.parts[:end]])
                        replacements[old]=new
            for item in entries:
                if item['name'] in replacements:
                    item['name']=replacements[item['name']]
                    item['leaf_name']=item['name'].split(' / ')[-1]
                    item['filename_encoding_version']=1
        except (OSError,ValueError,zipfile.BadZipFile):pass


def ui_font(root):
    from tkinter import font
    families=set(font.families(root))
    return next((name for name in ('Malgun Gothic','맑은 고딕','Noto Sans CJK KR','Segoe UI') if name in families),'TkDefaultFont')
