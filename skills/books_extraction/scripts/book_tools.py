"""Page-based book prep, figure crops, assembly and structural validation.

Image rendering and geometry only: never OCR or PDF text extraction.
No automatic visual-QA claims. No qplib side effects.
"""
import argparse
import copy
import datetime
import hashlib
import io
import json
import math
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def default_root():
    if os.environ.get('TETEA_ROOT'): return str(Path(os.environ['TETEA_ROOT']).resolve())
    for start in [HERE, Path.cwd()]:
        for candidate in [start, *start.parents]:
            if (candidate/'tie/books').is_dir(): return str(candidate)
    return str(Path.cwd())


def registry_digest(registry):
    return hashlib.sha256(json.dumps(registry,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def form_number(value, level):
    match=re.fullmatch(r'(?:4m|form[-_ ]?|f)?([1-6])',str(value).lower())
    if not match: raise ValueError('Form must be 4m2, form2, f2 or 2 (forms 1-6)')
    form=int(match[1])
    if (level=='csee' and form>4) or (level=='acsee' and form<5): raise ValueError('Form does not belong to this level')
    return form


def form_folder(form):
    return 'form '+['','one','two','three','four','five','six'][form]


def session(args):
    """Resolve a book and initialize one independent physical-page range."""
    import pymupdf
    root=Path(args.root).resolve()
    level=args.level.lower(); subject=args.subject.lower()
    if level not in {'csee','acsee'}: raise ValueError('Level must be csee or acsee')
    safe_id(subject)
    form=form_number(args.form,level)
    folder=inside(root,f'tie/books/{level}/{subject}')
    words=['','one','two','three','four','five','six']
    pattern=re.compile(r'(?:form|4m)[ _-]*(?:'+str(form)+'|'+words[form]+r')(?=[ _\-.]|$)',re.I)
    candidates=sorted(p for p in folder.glob('*.pdf') if pattern.search(p.name))
    if len(candidates)!=1: raise ValueError('Expected one matching book; found '+str(len(candidates))+': '+', '.join(p.name for p in candidates))
    pdf=candidates[0]; sha=digest(pdf)
    if not re.fullmatch(r'\d+-\d+',args.pages): raise ValueError('Supply an inclusive physical PDF page range, e.g. 20-30')
    with pymupdf.open(pdf) as source: selection=numbers(args.pages,len(source))
    slug=re.sub(r'[^a-z0-9]+','-',pdf.stem.lower()).strip('-')[:75]
    book_id=slug+'-'+sha[:12]
    book=root/'tie/output'/level/subject/'temp'/f'{slug}__pages-{selection[0]:04d}-{selection[-1]:04d}.json'
    if book.exists():
        previous=read(book)
        if previous['source']['sha256']!=sha or previous['extraction']['requested_pdf_pages']!=selection:
            raise ValueError('Existing partial has different source/scope; retain it and resolve explicitly')
        if registry_digest(previous['schema'].get('registry',{}))!=previous['schema']['sha256']:
            raise ValueError('Existing partial schema fingerprint mismatch')
        print(json.dumps({'book':str(book),'pdf':str(pdf),'book_id':previous['book_id'],'source_sha256':sha,'requested_pdf_pages':selection,'resume':True})); return
    registry=read(HERE/'references/content-types.json')
    with pymupdf.open(pdf) as source:
        doc={'schema_version':registry['schema_version'],'book_id':book_id,'status':'partial',
             'schema':{'registry':registry,'sha256':registry_digest(registry)},
             'metadata':{'level':level,'subject':subject,'form':form,'title_printed':None,'language':None,'edition_year_printed':None},
             'source':{'pdf':pdf.relative_to(root).as_posix(),'sha256':sha,'pdf_page_count':len(source),'completeness':'unchecked'},
             'extraction':{'prompt_version':'books-extraction-1.1','method':'visual','requested_pdf_pages':selection,
                           'front_details_in_scope':selection[0]==1,'runs':[]},
             'pages':[{'pdf_page':n,'width_pt':source[n-1].rect.width,'height_pt':source[n-1].rect.height,'rotation':source[n-1].rotation,
                       'state':'pending','visual_qa':'pending','surfaces':[]} for n in selection],
             'groups':[],'relations':[],'figures':[],'exclusions':[],'review':[],'stats':{}}
    doc['stats']=stats(doc); save(book,doc)
    print(json.dumps({'book':str(book),'pdf':str(pdf),'book_id':book_id,'source_sha256':sha,'requested_pdf_pages':selection,'resume':False,'content_extracted':False}))
    if args.prep:
        args.pdf=str(pdf); args.book_id=book_id; args.pages=str(selection[0]); prep(args)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value, backup=False):
    path = Path(path).resolve(); destination=path; scratch=path.parent
    if isinstance(value,dict) and str(value.get('schema_version','')).startswith('book-pages-'):
        for ancestor in path.parents:
            if ancestor.name=='output' and ancestor.parent.name=='tie':
                parts=path.relative_to(ancestor).parts
                if len(parts)>=3:
                    subject=ancestor/parts[0]/parts[1]; scratch=subject/'temp'
                    finished=(value.get('status') in {'complete','complete_with_issues'} and
                              len(value.get('pages',[]))==1 and '__page-' in path.name)
                    destination=(subject/form_folder(form_number(value['metadata']['form'],value['metadata']['level']))/path.name) if finished else scratch/path.name
                    if not destination.resolve().is_relative_to(subject.resolve()): raise ValueError('Save destination outside subject')
                    if destination!=path and destination.exists(): raise ValueError('Destination exists; refusing to overwrite a different page file')
                break
    destination.parent.mkdir(parents=True,exist_ok=True); scratch.mkdir(parents=True,exist_ok=True)
    if backup and path.exists():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (scratch/(path.name + '.' + stamp + '.bak')).write_bytes(path.read_bytes())
    temp = scratch/(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(destination)
    if destination!=path and path.exists(): path.unlink()
    return destination


def safe_id(value):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}', value):
        raise ValueError('IDs for output directories/files must be alphanumeric, hyphen or underscore')
    return value


def inside(root, rel):
    root = Path(root).resolve(); path = (root / rel).resolve()
    if Path(rel).is_absolute() or not path.is_relative_to(root):
        raise ValueError('Relative path escapes its root: ' + str(rel))
    return path


def numbers(spec, count):
    out = set()
    for token in spec.split(','):
        ends = token.strip().split('-')
        start = int(ends[0]); end = int(ends[-1])
        if len(ends) > 2 or start < 1 or end < start or end > count:
            raise ValueError('Invalid page selection: ' + token)
        out.update(range(start, end + 1))
    return sorted(out)


def runs(text):
    out = []; pos = 0
    pat = re.compile(r'\\\((.+?)\\\)|\*\*(.+?)\*\*|(?<!\\)\*(.+?)(?<!\\)\*|\[\[blank\]\]|\[\[\?(.+?)\]\]|\[\[illegible\]\]', re.S)
    for m in pat.finditer(text):
        if m.start() > pos: out.append({'t':'text', 'v':text[pos:m.start()]})
        if m.group(1) is not None: out.append({'t':'math','v':m.group(1)})
        elif m.group(2) is not None: out.append({'t':'text','v':m.group(2),'b':True})
        elif m.group(3) is not None: out.append({'t':'text','v':m.group(3),'i':True})
        elif m.group(0) == '[[blank]]': out.append({'t':'blank'})
        elif m.group(4) is not None: out.append({'t':'uncertain','v':m.group(4)})
        else: out.append({'t':'illegible'})
        pos = m.end()
    if pos < len(text): out.append({'t':'text','v':text[pos:]})
    return out


def fill(obj):
    if isinstance(obj, dict):
        # Embedded schema field definitions are data types, not transcribed text.
        if 'types' in obj and 'group_kinds' in obj and 'schema_version' in obj: return
        # Code text is literal, not markup. Its content stays byte-for-byte text.
        if obj.get('type') == 'code': return
        if isinstance(obj.get('text'), str): obj['runs'] = runs(obj['text'])
        for value in list(obj.values()): fill(value)
    elif isinstance(obj, list):
        for value in obj: fill(value)


def prep(args):
    import pymupdf
    pdf = Path(args.pdf).resolve(); root = Path(args.root).resolve()
    folder = root / 'pages' / 'books' / safe_id(args.book_id); folder.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        sha = digest(pdf); recfile = folder / 'prep.json'
        rec = read(recfile) if recfile.exists() else {'pdf':str(pdf),'sha256':sha,'pdf_page_count':len(doc),'pages':[]}
        if rec['sha256'] != sha: raise ValueError('Book ID already belongs to a different PDF hash')
        # Legacy hints are not valid inputs for the visual-only workflow.
        for previous in rec['pages']: previous.pop('text_hint', None)
        bynum = {p['pdf_page']:p for p in rec['pages']}
        for n in numbers(args.pages, len(doc)):
            page = doc[n-1]; render = folder / f'page-{n:04d}.png'
            page.get_pixmap(dpi=args.dpi, alpha=False).save(render)
            bynum[n] = {'pdf_page':n,'width_pt':page.rect.width,'height_pt':page.rect.height,'rotation':page.rotation,
                        'render':render.relative_to(root).as_posix(),'dpi':args.dpi,
                        'embedded_images':[{'width':i['width'],'height':i['height']} for i in page.get_image_info()]}
        rec['pages'] = [bynum[n] for n in sorted(bynum)]; save(recfile, rec)
    print(json.dumps({'prep':str(recfile),'pages_rendered':numbers(args.pages,rec['pdf_page_count']),'sha256':sha}))


def init(args):
    import pymupdf
    pdf=Path(args.pdf).resolve(); root=Path(args.root).resolve()
    form=form_number(args.form,args.level)
    folder=root/'tie/output'/args.level/safe_id(args.subject)/'temp'
    registry_path=HERE/'references/content-types.json'
    registry=read(registry_path)
    with pymupdf.open(pdf) as source:
        selection=numbers(args.pages,len(source))
        book=folder/f'{safe_id(args.book_id)}__pages-{selection[0]:04d}-{selection[-1]:04d}.json'
        if book.exists(): raise ValueError('Partial already exists; resume it instead of overwriting')
        source_rel=pdf.relative_to(root).as_posix() if pdf.is_relative_to(root) else str(pdf)
        doc={'schema_version':registry['schema_version'],'book_id':args.book_id,'status':'partial',
             'schema':{'registry':registry,'sha256':registry_digest(registry)},
             'metadata':{'level':args.level,'subject':args.subject,'form':form,'title_printed':None,'language':None,'edition_year_printed':None},
             'source':{'pdf':source_rel,'sha256':digest(pdf),'pdf_page_count':len(source),'completeness':'unchecked'},
             'extraction':{'prompt_version':'books-extraction-1.1','method':'visual','requested_pdf_pages':selection,'front_details_in_scope':selection[0]==1,'runs':[]},
             'pages':[{'pdf_page':n,'width_pt':source[n-1].rect.width,'height_pt':source[n-1].rect.height,
                       'rotation':source[n-1].rotation,'state':'pending','visual_qa':'pending','surfaces':[]} for n in selection],
             'groups':[],'relations':[],'figures':[],'exclusions':[],'review':[],'stats':{}}
    doc['stats']=stats(doc); save(book,doc)
    print(json.dumps({'book':str(book),'requested_pdf_pages':selection,'status':'partial','content_extracted':False}))


def crop(args):
    import pymupdf
    from PIL import Image
    root = Path(args.root).resolve(); folder = root/'assets'/'books'/safe_id(args.book_id)
    with pymupdf.open(args.pdf) as doc:
        if not 1 <= args.page <= len(doc): raise ValueError('Page outside PDF')
        page = doc[args.page-1]; box = list(args.bbox)
        if args.coords == 'pixels': box = [v*72/args.render_dpi for v in box]
        if not valid_box(box, [0,0,page.rect.width,page.rect.height]): raise ValueError('Crop bbox outside displayed PDF page')
        pad = 14 if args.deskew else 0
        clip = pymupdf.Rect(box[0]-pad,box[1]-pad,box[2]+pad,box[3]+pad) & page.rect
        pix = page.get_pixmap(dpi=args.dpi, clip=clip, alpha=False)
        im = Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        if args.deskew: im = im.rotate(-args.deskew,resample=Image.Resampling.BICUBIC,expand=True,fillcolor='white')
        if args.trim:
            l,t,r,b = args.trim
            if min(args.trim)<0 or l+r>=im.width or t+b>=im.height: raise ValueError('Trim removes entire crop')
            im = im.crop((l,t,im.width-r,im.height-b))
        ext = 'jpg' if args.kind in {'photo','map'} else 'png'; folder.mkdir(parents=True,exist_ok=True)
        encoded=io.BytesIO()
        im.save(encoded,format='JPEG',quality=92) if ext=='jpg' else im.save(encoded,format='PNG')
        content=encoded.getvalue(); fingerprint=hashlib.sha256(content).hexdigest()
        target=folder/(safe_id(args.figure_id)+'-'+fingerprint[:12]+'.'+ext)
        if target.exists() and digest(target)!=fingerprint: raise ValueError('Asset fingerprint collision')
        if not target.exists(): target.write_bytes(content)
        w,h = page.rect.width,page.rect.height
        figure = {'id':args.figure_id,'kind':args.kind,'page':args.page,'surface_id':args.surface_id,
                  'bbox':box,'bbox_norm':[box[0]/w,box[1]/h,box[2]/w,box[3]/h],
                  'file':target.relative_to(root/'assets').as_posix(),'format':ext,'pixel_size':list(im.size),
                  'dpi':args.dpi,'deskew_deg':args.deskew or None,'used_by':[], 'printed_label':None,'description':'',
                  'crop_check':'pending','crop_issue':None,'sha256':digest(target),
                  'transform':{'clip_bbox_pt':list(clip),'trim_px':args.trim,'rotation_applied':page.rotation}}
    print(json.dumps({'figure':figure,'preview':str(target)},ensure_ascii=False))


def valid_box(box, parent):
    return (isinstance(box,list) and len(box)==4 and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in box)
            and parent[0]<=box[0]<box[2]<=parent[2] and parent[1]<=box[1]<box[3]<=parent[3])


def typed(value, kind):
    return {'string':isinstance(value,str),'nullable_string':value is None or isinstance(value,str),
            'array':isinstance(value,list),'object':isinstance(value,dict),
            'positive_integer':isinstance(value,int) and not isinstance(value,bool) and value>0,
            'nonnegative_integer':isinstance(value,int) and not isinstance(value,bool) and value>=0,
            'boolean':isinstance(value,bool),'number':isinstance(value,(float,int)) and not isinstance(value,bool)}.get(kind,False)


def stats(doc):
    elements = [e for p in doc['pages'] for s in p['surfaces'] for e in s['elements']]
    counts = {}
    for e in elements: counts[e['type']] = counts.get(e['type'],0)+1
    return {'pdf_pages':len(doc['pages']),'surfaces':sum(len(p['surfaces']) for p in doc['pages']),
            'elements':len(elements),'types':counts,'figures':len(doc['figures']),
            'open_issues':sum(not r['resolved'] for r in doc['review'])}


def validate(doc, book, root, *, check_files=True):
    errors = []; warnings = []; elements = {}; surfaces = {}; groups = {}; figures = {}; refs = []; figuses = {}
    def check(ok, message):
        if not ok: errors.append(message)
    required = ['schema_version','book_id','status','schema','metadata','source','extraction','pages','groups','relations','figures','exclusions','review','stats']
    for field in required: check(field in doc,'Missing root '+field)
    if errors: return errors,warnings
    if 'registry' in doc['schema']:
        registry=doc['schema']['registry']
        check(registry_digest(registry)==doc['schema']['sha256'],'Registry snapshot hash mismatch')
    else:
        registry_path = inside(Path(book).parent, doc['schema']['registry_file']); registry = read(registry_path)
        check(digest(registry_path)==doc['schema']['sha256'],'Registry snapshot hash mismatch')
    check(doc['schema_version']==registry['schema_version'],'Schema/registry version mismatch')
    check(doc['status'] in {'partial','complete','complete_with_issues','failed'},'Invalid status')
    source = doc['source']; check(source['completeness'] in {'unchecked','apparently_complete','incomplete'},'Invalid source completeness')
    sourcepath = Path(source['pdf']); sourcepath = sourcepath if sourcepath.is_absolute() else inside(root,source['pdf'])
    if check_files: check(sourcepath.is_file(),'Missing source PDF')
    if check_files and sourcepath.is_file():
        check(digest(sourcepath)==source['sha256'],'Source hash mismatch')
        import pymupdf
        with pymupdf.open(sourcepath) as pdf:
            check(len(pdf)==source['pdf_page_count'],'Source PDF count mismatch')
            geometry = {n:[pdf[n-1].rect.width,pdf[n-1].rect.height,pdf[n-1].rotation] for n in doc['extraction']['requested_pdf_pages'] if 1<=n<=len(pdf)}
    else: geometry = {}
    count = source['pdf_page_count']; requested = doc['extraction']['requested_pdf_pages']
    check(isinstance(requested,list) and bool(requested),'Requested pages must be a nonempty array')
    check(len(requested)==len(set(requested)),'Duplicate requested pages')
    check(all(isinstance(n,int) and not isinstance(n,bool) and 1<=n<=count for n in requested),'Requested page outside PDF')
    allids = set()
    def add(obj, dest, label):
        ident = obj.get('id'); check(isinstance(ident,str) and bool(ident),label+' missing ID')
        check(ident not in allids,'Duplicate ID '+str(ident)); allids.add(ident); dest[ident] = obj
    for group in doc['groups']:
        add(group,groups,'group'); check(group.get('kind') in registry['group_kinds'],'Unknown group kind '+str(group.get('kind')))
        check(isinstance(group.get('element_refs'),list),'Group needs element_refs')
    for figure in doc['figures']: add(figure,figures,'figure')
    seen = set()
    for page in doc['pages']:
        n = page['pdf_page']; check(n not in seen,'Duplicate PDF page '+str(n)); seen.add(n)
        check(n in requested,'Page not in requested scope '+str(n))
        check(page['state'] in {'pending','transcribed','validated','verified'},'Invalid page state')
        check(page['visual_qa'] in {'pending','passed','flagged'},'Invalid page QA')
        if n in geometry:
            check(abs(page['width_pt']-geometry[n][0])<0.11 and abs(page['height_pt']-geometry[n][1])<0.11 and page['rotation']==geometry[n][2],'PDF geometry mismatch '+str(n))
        if page['state']!='pending': check(bool(page['surfaces']),'Non-pending page has no surfaces '+str(n))
        pbox = [0,0,page['width_pt'],page['height_pt']]
        for si,surface in enumerate(page['surfaces']):
            add(surface,surfaces,'surface'); surface['_page'] = n
            check(surface['order']==si,'Surface order mismatch '+str(surface['id']))
            check(valid_box(surface['bbox_pt'],pbox),'Surface bbox invalid '+str(surface['id']))
            check(surface['printed_page_system'] in {'arabic','roman','other','none'},'Invalid printed page system')
            check(surface['printed_page_status'] in {'observed','not_printed','illegible'},'Invalid printed page status')
            check(isinstance(surface['printed_page'],str) if surface['printed_page_status']=='observed' else surface['printed_page'] is None,'Invalid printed page value')
            for ei,element in enumerate(surface['elements']):
                add(element,elements,'element'); element['_page'] = n
                for field in ['type','surface_id','order','bbox_pt','group_refs','payload','legibility']: check(field in element,'Element missing '+field)
                check(element['surface_id']==surface['id'],'Element surface mismatch '+element['id'])
                check(element['order']==ei,'Element order mismatch '+element['id'])
                check(valid_box(element['bbox_pt'],surface['bbox_pt']),'Element bbox invalid '+element['id'])
                check(element['legibility'] in {'clear','partial','illegible'},'Invalid legibility '+element['id'])
            if page['state']!='pending' and surface['printed_page_status']=='observed':
                check(any(e.get('type')=='page_number' and e.get('payload',{}).get('text')==surface['printed_page'] for e in surface['elements']),
                      'Observed printed page number must be a page_number element '+surface['id'])
    for eid,element in elements.items():
        for g in element['group_refs']:
            check(g in groups and eid in groups[g]['element_refs'],'Group membership mismatch '+eid)
    for gid,group in groups.items():
        check(len(group['element_refs'])==len(set(group['element_refs'])),'Duplicate group membership '+gid)
        for eid in group['element_refs']: check(eid in elements and gid in elements[eid]['group_refs'],'Group reverse membership mismatch '+gid)
        parent = group.get('parent_ref'); visited = {gid}
        while parent is not None:
            check(parent in groups,'Missing group parent '+str(parent))
            if parent not in groups: break
            if parent in visited: check(False,'Cyclic group parents '+gid); break
            visited.add(parent); parent = groups[parent].get('parent_ref')

    def text_tree(obj, where, literal=False):
        if isinstance(obj,dict):
            if obj.get('type')=='code': literal=True
            if 'text' in obj:
                t = obj['text']; check(isinstance(t,str),where+' text must be string')
                if isinstance(t,str) and not literal:
                    check(obj.get('runs')==runs(t),where+' runs mismatch/missing')
                    check(t.count('\\(')==t.count('\\)'),where+' unmatched math delimiters')
                    for m in re.finditer(r'\\\((.*?)\\\)',t,re.S): latex(m.group(1),where)
                for span in obj.get('typography',[]):
                    check(span.get('style') in {'underline','superscript','subscript'} and isinstance(span.get('start'),int) and isinstance(span.get('end'),int) and 0<=span['start']<span['end']<=len(t),where+' invalid typography span')
            for key,value in obj.items():
                if key != 'runs': text_tree(value,where,literal)
        elif isinstance(obj,list):
            for value in obj: text_tree(value,where,literal)

    def latex(t,where):
        check(isinstance(t,str) and bool(t.strip()),where+' empty LaTeX')
        if not isinstance(t,str): return
        check(t.count('{')==t.count('}'),where+' unbalanced LaTeX braces')
        check(not re.search(r'\\(?:dfrac|displaystyle|over\b|degree|mbox|textrm)|\\begin\{(?:align|eqnarray)\}',t),where+' forbidden LaTeX')
        check('$' not in t and not t.strip().startswith(('\\(','\\[')),where+' display/source delimiters')
        check(not re.search('[×÷≤≥°√π⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉]',t),where+' Unicode math inside LaTeX')

    def payload(kind,p,where,owner):
        definition = registry['types'].get(kind)
        if definition is None: check(False,where+' unknown type '+str(kind)); return
        check(isinstance(p,dict),where+' payload must be object')
        if not isinstance(p,dict): return
        fields = {**registry['common_optional'],**definition['optional'],**definition['required']}
        for key,typ in definition['required'].items(): check(key in p,where+' missing payload '+key)
        for key,value in p.items():
            check(key in fields,where+' undeclared payload field '+key)
            if key in fields: check(typed(value,fields[key]),where+' wrong type '+key)
        for key,value in p.items():
            values = registry['closed_values'].get(kind+'.'+key)
            if values: check(value in values,where+' undeclared subtype '+str(value))
        text_tree(p,where,literal=kind=='code')
        for key in ['continuation_of','continued_by']:
            if key in p: refs.append((p[key],where))
        if kind=='math': latex(p.get('latex'),where)
        if kind=='chemical_structure':
            src = p.get('source',''); check('\\chemfig' in src and not any(x in src for x in ['\\documentclass','\\begin{document}','\\end{document}']),where+' invalid Chemfig fragment')
            check(src.count('{')==src.count('}'),where+' unbalanced Chemfig source')
            check(not src.strip().startswith(('\\(','\\[','$')),where+' Chemfig delimiters')
            asset = p.get('rendered_asset'); check(isinstance(asset,str),where+' missing Chemfig SVG')
            if isinstance(asset,str): check((not check_files or inside(root/'assets',asset).is_file()) and asset.endswith('.svg'),where+' missing/invalid SVG asset')
        if kind in {'figure','map','image'} or (kind=='cover_detail' and p.get('ref')):
            figuses.setdefault(p.get('ref'),set()).add(owner)
        if kind=='cover_detail': check('text' in p or 'ref' in p,where+' empty cover detail')
        if kind=='caption':
            for ref in p.get('target_refs',[]): refs.append((ref,where))
        if kind=='footnote':
            for ref in p.get('marker_refs',[]): refs.append((ref,where))
        if kind=='unresolved_region':
            check(any(not r['resolved'] and r.get('element_ref')==owner for r in doc['review']),where+' unresolved region needs open review')
            evidence=p.get('evidence',{})
            if evidence.get('figure_ref'): figuses.setdefault(evidence['figure_ref'],set()).add(owner)
            check(bool(evidence),where+' unresolved region needs preserved evidence')
        if kind=='table':
            cols=p.get('columns'); rows=p.get('rows',[])
            check(isinstance(cols,int) and cols>0 and bool(rows),where+' empty/invalid table')
            if not isinstance(cols,int) or cols<=0 or not isinstance(rows,list): return
            check(0<=p.get('header_rows',0)<=len(rows),where+' header_rows outside table')
            occupied=set()
            for ri,row in enumerate(rows):
                check(isinstance(row,list),where+' row must be array')
                if not isinstance(row,list): continue
                ci=0
                for cell in row:
                    while (ri,ci) in occupied: ci+=1
                    check(isinstance(cell,dict),where+' cell must be object')
                    if not isinstance(cell,dict): continue
                    check(isinstance(cell.get('text'),str),where+' cell needs text')
                    rs,cs=cell.get('rowspan',1),cell.get('colspan',1)
                    check(typed(rs,'positive_integer') and typed(cs,'positive_integer'),where+' invalid span')
                    if not typed(rs,'positive_integer') or not typed(cs,'positive_integer'): continue
                    for rr in range(ri,ri+rs):
                        for cc in range(ci,ci+cs):
                            check(rr<len(rows) and cc<cols and (rr,cc) not in occupied,where+' table span overlaps/extends past grid')
                            occupied.add((rr,cc))
                    ci+=cs
                    if cell.get('figure_ref'): figuses.setdefault(cell['figure_ref'],set()).add(owner)
                    for block in cell.get('blocks',[]): payload(block.get('type'),{k:v for k,v in block.items() if k!='type'},where+' cell block',owner)
            check(occupied=={(r,c) for r in range(len(rows)) for c in range(cols)},where+' table grid has holes/extra cells')
        if kind=='list':
            def items(values):
                check(bool(values),where+' empty list')
                for item in values:
                    check(isinstance(item,dict) and 'label_printed' in item and isinstance(item.get('text'),str),where+' list item needs printed label/text')
                    if isinstance(item,dict) and item.get('items'): items(item['items'])
            items(p.get('items',[]))
        if kind=='mcq_options':
            values=p.get('options',[]); check(bool(values),where+' empty options')
            keys=[]
            for option in values:
                check(isinstance(option,dict) and isinstance(option.get('key'),str) and isinstance(option.get('text'),str),where+' invalid option')
                keys.append(option.get('key'))
                if option.get('figure_ref'): figuses.setdefault(option['figure_ref'],set()).add(owner)
            check(len(keys)==len(set(keys)),where+' duplicate option labels')
        if kind=='matching':
            for name in ['list_a','list_b']:
                check(bool(p.get(name)),where+' empty matching '+name)
                for entry in p.get(name,[]): check(isinstance(entry,dict) and isinstance(entry.get('key'),str) and isinstance(entry.get('text'),str),where+' invalid matching entry')
        if kind=='verse':
            check(bool(p.get('stanzas')),where+' verse needs stanzas')
            for stanza in p.get('stanzas',[]):
                check(isinstance(stanza,dict) and isinstance(stanza.get('lines'),list) and bool(stanza['lines']),where+' invalid stanza')
                if isinstance(stanza,dict):
                    for line in stanza.get('lines',[]): check(isinstance(line,dict) and isinstance(line.get('text'),str),where+' invalid verse line')
        if kind=='dialogue':
            check(bool(p.get('turns')),where+' dialogue needs turns')
            for turn in p.get('turns',[]): check(isinstance(turn,dict) and isinstance(turn.get('speaker_printed'),str) and isinstance(turn.get('text'),str),where+' invalid dialogue turn')
        if kind in {'definition_list','reference_list','index','toc'}:
            check(bool(p.get('entries')),where+' empty entries')
            for entry in p.get('entries',[]):
                check(isinstance(entry,dict),where+' entry must be object')
                needed=['term','definition'] if kind=='definition_list' else ['text'] if kind in {'reference_list','toc'} else ['term','page_refs_printed']
                for field in needed:
                    check(field in entry,where+' entry missing '+field)
                    if field in entry: check(isinstance(entry[field],list) if field=='page_refs_printed' else isinstance(entry[field],str),where+' invalid entry '+field)
    for eid,element in elements.items(): payload(element['type'],element['payload'],eid,eid)
    for ref,where in refs: check(ref in allids,where+' dangling reference '+str(ref))
    for fid,figure in figures.items():
        check(figure.get('page') in seen and figure.get('surface_id') in surfaces,'Invalid figure source '+fid)
        if figure.get('surface_id') in surfaces:
            s=surfaces[figure['surface_id']]; check(s['_page']==figure['page'] and valid_box(figure['bbox'],s['bbox_pt']),'Figure bbox/surface mismatch '+fid)
        path=inside(root/'assets',figure['file'])
        if check_files: check(path.is_file(),'Missing figure asset '+fid)
        if check_files and path.is_file():
            check(digest(path)==figure['sha256'],'Figure hash mismatch '+fid)
            from PIL import Image
            with Image.open(path) as im: check(list(im.size)==figure['pixel_size'],'Figure dimensions mismatch '+fid)
        check(set(figure['used_by'])==figuses.get(fid,set()),'Figure use linkage mismatch '+fid)
        check(figure['crop_check'] in {'pending','ok','flagged'},'Invalid crop QA '+fid)
        if figure['crop_check']=='flagged': check(bool(figure.get('crop_issue')),'Flagged crop needs issue '+fid)
        if not figure['used_by']: warnings.append('Unreferenced figure '+fid)
    for fid in figuses: check(fid in figures,'Missing figure record '+str(fid))
    for relation in doc['relations']:
        add(relation,{},'relation')
        check(relation['kind'] in {'refers_to','caption_of','continues','answers_for','footnote_of','panel_of'},'Unknown relation kind')
        check(relation['from_ref'] in allids,'Missing relation source')
        check(relation['resolution'] in {'resolved','unresolved','external'},'Invalid relation resolution')
        check(relation['to_ref'] in allids if relation['resolution']=='resolved' else relation['to_ref'] is None,'Invalid relation target')
        if relation['resolution']=='external':
            target=relation.get('external_target',{})
            n=target.get('pdf_page')
            check(target.get('book_id')==doc['book_id'] and isinstance(n,int) and not isinstance(n,bool) and 1<=n<=count and n not in requested,'External target must identify an out-of-range page of this book')
    for issue in doc['review']:
        check(isinstance(issue.get('resolved'),bool) and isinstance(issue.get('detail'),str),'Invalid review entry')
        if issue.get('element_ref'): check(issue['element_ref'] in elements,'Review references unknown element')
    for exclusion in doc['exclusions']:
        check(exclusion['pdf_page'] in seen and exclusion['surface_id'] in surfaces,'Invalid exclusion origin')
        if exclusion['surface_id'] in surfaces: check(valid_box(exclusion['bbox_pt'],surfaces[exclusion['surface_id']]['bbox_pt']),'Invalid exclusion bbox')
        check(bool(exclusion.get('reason')),'Exclusion needs reason')
    complete=doc['status'] in {'complete','complete_with_issues'}
    if complete:
        check(seen==set(requested),'Complete status missing requested pages')
        check(all(p['state']=='verified' and p['visual_qa'] in {'passed','flagged'} for p in doc['pages']),'Complete status needs verified pages and QA')
        check(not any(e['type']=='unresolved_region' for e in elements.values()),'Complete status contains unresolved regions')
        check(all(f['crop_check'] in {'ok','flagged'} for f in figures.values()),'Complete status has unchecked crops')
        check(not any(not r['resolved'] and r['issue'] in {'unknown_content_type','uncertain_text','illegible_text','latex_error','page_incomplete','untranscribed_content'} for r in doc['review']),'Complete status has blocking issues')
        check(not any(r['resolution']=='unresolved' for r in doc['relations']),'Complete status has unresolved relations')
        if doc['status']=='complete':
            check(not any(not r['resolved'] for r in doc['review']) and all(p['visual_qa']=='passed' for p in doc['pages']) and all(f['crop_check']=='ok' for f in figures.values()),'Clean complete status has open/flagged issues')
    check(doc['stats']==stats(doc),'Derived statistics mismatch; run build')
    if not complete: warnings.append('Partial/failed extraction; visual completeness is not certified')
    # Internal lookup annotations are never serialized.
    for obj in list(elements.values())+list(surfaces.values()): obj.pop('_page',None)
    return errors,warnings


def merge(args):
    book=Path(args.book); doc=read(book); fragment=read(args.fragment)
    for field,value in [('book_id',doc['book_id']),('source_sha256',doc['source']['sha256']),('schema_sha256',doc['schema']['sha256'])]:
        if fragment.get(field)!=value: raise ValueError('Fragment identity mismatch: '+field)
    pages={p['pdf_page']:p for p in doc['pages']}
    for p in fragment['pages']:
        n=p['pdf_page']
        if n not in doc['extraction']['requested_pdf_pages']: raise ValueError('Fragment page not in requested scope')
        if n in pages and pages[n]['state']!='pending': raise ValueError('Page already owned/transcribed: '+str(n))
        pages[n]=p
    doc['pages']=[pages[n] for n in sorted(pages)]
    for name in ['groups','relations','figures','review']:
        byid={item['id']:item for item in doc[name]}
        for item in fragment.get(name,[]):
            ident=item['id']
            if ident in byid:
                if name!='groups' or {k:v for k,v in item.items() if k!='element_refs'}!={k:v for k,v in byid[ident].items() if k!='element_refs'}: raise ValueError('Conflicting '+name+' ID '+ident)
                byid[ident]['element_refs']=list(dict.fromkeys(byid[ident]['element_refs']+item['element_refs']))
            else: byid[ident]=item
        doc[name]=list(byid.values())
    doc['exclusions'].extend(fragment.get('exclusions',[])); doc['status']='partial'; fill(doc); doc['stats']=stats(doc)
    save(book,doc,backup=True)
    print(json.dumps({'merged':str(args.fragment),'book':str(book),'status':'partial','requires_validation':True}))


def contact(args):
    from PIL import Image,ImageDraw
    doc=read(args.book); root=Path(args.root).resolve(); figs=doc['figures']; cols=4; w,h=360,330
    if not figs: raise ValueError('No figures for contact sheet')
    sheet=Image.new('RGB',(cols*w,math.ceil(len(figs)/cols)*h),'white'); draw=ImageDraw.Draw(sheet)
    for i,fig in enumerate(figs):
        with Image.open(inside(root/'assets',fig['file'])) as opened:
            im=opened.convert('RGB'); im.thumbnail((w-16,h-60))
        x,y=i%cols*w,i//cols*h; sheet.paste(im,(x+8,y+8))
        draw.text((x+8,y+h-45),fig['id']+' '+fig['crop_check'],fill='black')
        draw.text((x+8,y+h-25),'PDF '+str(fig['page']),fill='black')
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True); sheet.save(path)
    print(str(path))


def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('session'); p.add_argument('level'); p.add_argument('subject'); p.add_argument('form'); p.add_argument('pages'); p.add_argument('--root',default=default_root()); p.add_argument('--prep',action='store_true'); p.add_argument('--dpi',type=int,default=150)
    p=commands.add_parser('init'); p.add_argument('--pdf',required=True); p.add_argument('--root',default=default_root()); p.add_argument('--book-id',required=True); p.add_argument('--level',choices=['csee','acsee'],required=True); p.add_argument('--subject',required=True); p.add_argument('--form',required=True); p.add_argument('--pages',required=True)
    p=commands.add_parser('prep'); p.add_argument('--pdf',required=True); p.add_argument('--root',default=default_root()); p.add_argument('--book-id',required=True); p.add_argument('--pages',required=True); p.add_argument('--dpi',type=int,default=150)
    p=commands.add_parser('crop'); p.add_argument('--pdf',required=True); p.add_argument('--root',default=default_root()); p.add_argument('--book-id',required=True); p.add_argument('--figure-id',required=True); p.add_argument('--surface-id',required=True); p.add_argument('--page',type=int,required=True); p.add_argument('--bbox',nargs=4,type=float,required=True); p.add_argument('--coords',choices=['points','pixels'],default='points'); p.add_argument('--render-dpi',type=int,default=150); p.add_argument('--dpi',type=int,default=300); p.add_argument('--kind',choices=['diagram','map','photo','graph','chart','geometry','circuit','flowchart','venn','table_image','symbol','other'],default='diagram'); p.add_argument('--deskew',type=float,default=0); p.add_argument('--trim',nargs=4,type=int)
    for command in ['build','validate']:
        p=commands.add_parser(command); p.add_argument('--book',required=True); p.add_argument('--root',default=default_root())
    p=commands.add_parser('checkpoint'); p.add_argument('--book',required=True); p.add_argument('--root',default=default_root()); p.add_argument('--verified',action='store_true',help='assert the one brief visual check is done: mark pages verified / QA passed and crops ok, then promote')
    p=commands.add_parser('merge'); p.add_argument('--book',required=True); p.add_argument('--fragment',required=True)
    p=commands.add_parser('contact'); p.add_argument('--book',required=True); p.add_argument('--root',default=default_root()); p.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        if args.command=='session':
            if args.dpi<=0: raise ValueError('DPI must be positive')
            session(args); return
        if args.command in {'prep','crop'}:
            if args.dpi<=0 or getattr(args,'render_dpi',1)<=0: raise ValueError('DPI must be positive')
            globals()[args.command](args)
        elif args.command in {'init','merge','contact'}: globals()[args.command](args)
        else:
            doc=read(args.book)
            if args.command=='checkpoint' and getattr(args,'verified',False):
                doc['status']='complete'
                for pg in doc['pages']: pg['state']='verified'; pg['visual_qa']='passed'
                for fig in doc.get('figures',[]): fig['crop_check']='ok'
            if args.command in {'build','checkpoint'}: fill(doc); doc['stats']=stats(doc)
            lightweight=args.command=='checkpoint'
            errors,warnings=validate(doc,args.book,Path(args.root).resolve(),check_files=not lightweight)
            saved=save(args.book,doc,backup=True) if args.command in {'build','checkpoint'} and not errors else Path(args.book)
            print(json.dumps({'book':str(saved),'errors':errors,'warnings':warnings,'check':'lightweight' if lightweight else 'full','visual_qa_performed_by_script':False},ensure_ascii=False,indent=2))
            if errors: raise SystemExit(1)
    except (KeyError,TypeError,ValueError,OSError,AttributeError) as error:
        print(json.dumps({'errors':[str(error)],'visual_qa_performed_by_script':False},ensure_ascii=False)); raise SystemExit(1)


if __name__=='__main__': main()
