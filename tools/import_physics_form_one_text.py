"""Convert the supplied Physics Form One transcript into unverified page drafts."""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys
from import_book_text import ROOT, tokens as base_tokens, normalize, toc_entries
sys.path.insert(0,str(ROOT/'skills/books_extraction/scripts'))
import book_tools as bt

FOLDER=ROOT/'tie/output/csee/physics/temp/form-one-text-import'
SOURCE=FOLDER/'source-transcript.txt'
OUTPUT=ROOT/'tie/output/csee/physics/form one'

def tokens(source):
    # BEGIN NOTE kind=reflection uses kind twice in the general marker parser.
    # Keep the group identity NOTE separate from its semantic note subtype.
    source=re.sub(r'(\[BEGIN NOTE[^\]\n]*?)\bkind=',r'\1note_kind=',source)
    return base_tokens(source)

def repairs(text):
    # Accidental Python/string escapes present in the supplied TXT, not PDF
    # corrections. Keep originals and log every changed block separately.
    return text.replace('\x0crac',r'\frac').replace('\times',r'\times').replace('\nightarrow',r'\rightarrow')

def split_labels(raw,style):
    # Only line starts are item boundaries in this upload. A body reference
    # such as “repeat (i) to (iv)” stays within the item.
    pat=r'^\s*(\([^)]+\)|\d+[.)]|[A-Za-z][.)]|[•*-])\s+'
    ms=list(re.finditer(pat,raw,re.M))
    if not ms:return [{'label_printed':'','text':normalize(raw)}]
    result=[]
    if raw[:ms[0].start()].strip():result.append({'label_printed':'','text':normalize(raw[:ms[0].start()])})
    for i,m in enumerate(ms):result.append({'label_printed':m[1],'text':normalize(raw[m.end():ms[i+1].start() if i+1<len(ms) else len(raw)])})
    return result

def table(raw,attrs):
    cols=int(attrs['columns']);headers=int(attrs.get('header_rows',0))
    lines=raw.split('\n');rows=[];leading=[];trailing=[];directives=[];started=False;ended=False
    for line in lines:
        if not line.strip():
            if started:ended=True
            continue
        if line.startswith('MERGE '):directives.append(line);continue
        if not started and '\t' not in line:
            leading.append(line);continue
        if ended and '\t' not in line:
            trailing.append(line);continue
        started=True;rows.append(line.split('\t'))
    issues=[]
    width=max([cols]+[len(r) for r in rows])
    if any(len(r)!=cols for r in rows) or directives:
        issues.append('Supplied table dimensions, missing trailing cells or merge directives need checking. All supplied cells are retained in an expanded rectangular grid; no unverified spans were applied.')
    result=[]
    for row in rows:
        padded=[]
        for c in row+['']*(width-len(row)):
            c=normalize(c)
            if c=='[[blank]]':padded.append({'text':'','blank':True})
            elif c=='[[covered]]':padded.append({'text':'','source_printed':'[[covered]]'})
            else:padded.append({'text':c})
        result.append(padded)
    if not result:raise ValueError('Table without rows')
    p={'columns':width,'header_rows':min(headers,len(result)),'rows':result}
    if attrs.get('label'):p['printed_label']=attrs['label']
    if leading:p['caption']=normalize(' '.join(leading))
    return p,trailing,issues,directives

def convert():
    original=SOURCE.read_bytes();raw=original.decode('utf-8-sig')
    body_start=re.search(r'^\[PDF_PAGE 1\]\s*$',raw,re.M)
    assert body_start, 'Missing first physical page marker'
    raw=raw[body_start.start():]  # Header commentary is provenance, not page content.
    sha=hashlib.sha256(original).hexdigest();book='physics-form-one-text-import-'+sha[:12]
    registry=json.loads((ROOT/'skills/books_extraction/references/content-types.json').read_text())
    schema={'registry':registry,'sha256':bt.registry_digest(registry)}
    docs={};doc=None;page_no=0;stack=[];matching=None;raw_blocks=[];changes=[];counts=collections.Counter();handled=collections.Counter();boundary_repairs=[]
    def issue(kind,detail,eid=None):
        doc['review'].append({'id':f'review-p{page_no:04d}-{len(doc["review"])+1:03d}','issue':kind,'pdf_page':page_no,'element_ref':eid,'detail':detail,'resolved':False})
    def add(typ,payload,notes=None):
        eid=f'e-p{page_no:04d}-{len(elements)+1:04d}'
        e={'id':eid,'type':typ,'surface_id':sid,'order':len(elements),'bbox_pt':None,'group_refs':[g['id'] for g in stack],'payload':payload,'legibility':'partial' if '[[illegible]]' in json.dumps(payload) or '[[?' in json.dumps(payload) else 'clear'}
        if notes:e['notes']=notes
        elements.append(e)
        for g in stack:g['element_refs'].append(eid)
        return e
    def expanded_tokens():
        open_page=None
        for kind,attrs,content in tokens(raw):
            if kind=='PDF_PAGE':
                if open_page is not None:
                    boundary_repairs.append({'pdf_page':open_page,'repair':'Inserted missing END_PAGE before next PDF_PAGE marker.'})
                    yield 'END_PAGE',{},''
                open_page=int(attrs['value'])
            elif kind=='END_PAGE':open_page=None
            if kind=='EQUATION':
                parts=re.split(r'\n\s*\n|\n(?=(?:The\b|To\b|In Kilowatts|Power developed|Work done|\([a-z]\)))',content)
                yield kind,attrs,parts[0]
                for part in parts[1:]:
                    # Untagged solution prose follows equations in this upload.
                    # Preserve it as prose rather than feeding it to KaTeX.
                    yield 'SOLUTION',{},part
            else:yield kind,attrs,content
    for kind,attrs,content in expanded_tokens():
        if kind=='BOOK':continue
        if kind in {'END_EXTRACTION','EXTRACTION_PAUSED'}:continue
        if kind=='PDF_PAGE':
            assert doc is None,'Missing END_PAGE';page_no=int(attrs['value']);assert page_no not in docs,'Duplicate page'
            sid=f's-p{page_no:04d}-01';stack=[];matching=None
            page={'pdf_page':page_no,'width_pt':None,'height_pt':None,'rotation':None,'state':'transcribed','visual_qa':'pending','surfaces':[{'id':sid,'order':0,'bbox_pt':None,'printed_page':None,'printed_page_system':'none','printed_page_status':'not_printed','elements':[]}]}
            elements=page['surfaces'][0]['elements']
            doc={'schema_version':'book-pages-1.1','book_id':book,'status':'partial','schema':schema,'metadata':{'level':'csee','subject':'physics','form':1,'title_printed':"Physics for Secondary Schools Student's Book Form One",'language':'en','edition_year_printed':'Revised 2023'},'source':{'pdf':'Physics_Form-one_new-syllabus.pdf','sha256':None,'pdf_page_count':232,'completeness':'unchecked'},'extraction':{'method':'user_supplied_text','prompt_version':'physics-form-one-text-import-1','requested_pdf_pages':[page_no],'front_details_in_scope':page_no==1,'transcript_sources':[{'file':SOURCE.relative_to(ROOT).as_posix(),'sha256':sha}],'geometry_status':'unavailable','images_status':'pending','text_import_status':'imported_for_manual_review','runs':[]},'pages':[page],'groups':[],'relations':[],'figures':[],'exclusions':[],'review':[],'stats':{}}
            issue('text_import_unverified','Imported from another model’s text. Not compared with the PDF. Page geometry, PDF hash is unknown and the 232-page total is user-confirmed; images are pending. The user confirms the source ends at PDF page 232. The 1–240 header is stale; actual supplied coverage is 1–232. The contents and later chapter sequence disagree; manual source review is required.')
            continue
        assert doc is not None,('Outside page',kind)
        if kind=='PRINTED_PAGE':
            v=attrs['value'];surface=page['surfaces'][0]
            surface.update(printed_page=None if v in {'not_printed','illegible'} else v,printed_page_status=v if v in {'not_printed','illegible'} else 'observed',printed_page_system='none' if v in {'not_printed','illegible'} else 'arabic' if v.isdigit() else 'roman');continue
        if kind=='END_PAGE':
            if any(r['pdf_page']==page_no for r in boundary_repairs):
                issue('page_boundary_repaired','The supplied page lacks END_PAGE; inserted a structural boundary before the next PDF_PAGE marker. No source content added.')
            if 157<=page_no<=200:
                issue('transcript_sequence_needs_source_review','This part of the upload introduces chapters and end matter inconsistent with its contents. Page 200 claims the end of the textbook, but page 201 resumes Work, energy and power. Preserved for comparison; do not accept as source-verified.')
            assert matching is None,'Unclosed matching'
            if stack:issue('group_boundary_in_transcript','Page ends with open groups: '+', '.join(g['label_printed'] or g['kind'] for g in stack)+'. Group memberships kept on this page only.');stack=[]
            if surface['printed_page'] is not None:add('page_number',{'text':surface['printed_page']})
            bt.fill(doc);doc['stats']=bt.stats(doc);docs[page_no]=doc;doc=None;continue
        if kind=='BEGIN':
            source_kind=attrs['kind'];gkind=source_kind if source_kind in registry['group_kinds'] else 'section'
            g={'id':f'g-p{page_no:04d}-{len(doc["groups"])+1:03d}','kind':gkind,'label_printed':attrs.get('label'),'title':attrs.get('label') or source_kind,'parent_ref':stack[-1]['id'] if stack else None,'element_refs':[],'notes':['Transcript group: '+source_kind]}
            doc['groups'].append(g);stack.append(g)
            if content.strip():
                payload={'text':normalize(repairs(content))}
                if source_kind=='note':payload['note_kind']=attrs.get('note_kind','note')
                add(source_kind if source_kind in registry['types'] else 'paragraph',payload)
            continue
        if kind=='END':
            expected=attrs['kind'];index=next((i for i in range(len(stack)-1,-1,-1) if stack[i]['notes']==['Transcript group: '+expected]),None)
            if index is None:
                issue('group_boundary_in_transcript','Closing '+expected+' has no matching opening marker on this page. No printed text removed.')
            else:
                if index!=len(stack)-1:issue('group_boundary_in_transcript','Nested groups auto-closed at END '+expected+'.')
                stack=stack[:index]
            if content.strip():add('paragraph',{'text':normalize(repairs(content))})
            continue
        counts[kind]+=1;raw_blocks.append({'pdf_page':page_no,'marker':kind,'attributes':attrs,'raw_content':content})
        fixed=repairs(content)
        if fixed!=content:
            changes.append({'pdf_page':page_no,'marker':kind,'block_index':len(raw_blocks)-1,'repair':'Restore escaped TeX control sequences: form-feed+rac, tab+imes, newline+ightarrow.'})
            issue('transcript_math_encoding_repaired','Restored TeX commands damaged by string escaping in the uploaded text; original retained in source-blocks.json.')
        text=normalize(fixed);typ=kind.lower();payload={};notes=[]
        if kind=='OMITTED':
            doc['exclusions'].append({'pdf_page':page_no,'surface_id':sid,'bbox_pt':None,'reason':attrs.get('kind'),'text':text,'evidence_source':'supplied_transcript'});handled[kind]+=1;continue
        if kind=='MATCHING':matching={'list_a_title':'','list_b_title':'','list_a':[],'list_b':[]};handled[kind]+=1;continue
        if kind in {'COLUMN_A','COLUMN_B'}:
            assert matching is not None
            side='a' if kind=='COLUMN_A' else 'b';matching['list_'+side+'_title']=attrs.get('title','')
            matching['list_'+side]=[{'key':i['label_printed'],'text':i['text']} for i in split_labels(fixed,'plain')];handled[kind]+=1;continue
        if kind=='END_MATCHING':
            assert matching is not None;add('matching',matching);matching=None;handled[kind]+=1;continue
        if kind=='HEADING':
            payload={'text':text,'level':int(attrs.get('level',2)),'role':attrs.get('role','other')}
            if attrs.get('role')=='chapter' and page_no in {157,167,175,181,187}:
                issue('transcript_contents_heading_mismatch','The upload’s contents list nine chapters, with Chapter Eight: Linear motion and Chapter Nine: Work, energy, and power. Later supplied chapter headings differ, including Light, Magnetism, Electricity and Chapter Twelve. Original wording and page labels retained; compare with the actual PDF.')
        elif kind=='EQUATION':
            typ='math';payload={'latex':re.sub(r'^\\\[|\\\]$','',fixed.strip())}
            if attrs.get('label'):payload['printed_label']=attrs['label']
        elif kind=='LIST':payload={'style':attrs.get('style','plain'),'items':split_labels(fixed,attrs.get('style','plain'))}
        elif kind=='MCQ_OPTIONS':payload={'options':[{'key':i['label_printed'],'text':i['text']} for i in split_labels(fixed,'lettered')]}
        elif kind=='TOC':payload={'entries':toc_entries(fixed)}
        elif kind in {'INDEX','DEFINITION_LIST'}:
            entries=[]
            for line in fixed.split('\n'):
                if not line.strip():continue
                parts=line.split('\t',1)
                if len(parts)!=2:raise ValueError(('Entry missing tab',page_no,line))
                if kind=='INDEX':entries.append({'term':normalize(parts[0]),'page_refs_printed':[v.strip() for v in parts[1].split(',')]})
                else:entries.append({'term':normalize(parts[0]),'definition':normalize(parts[1])})
            payload={'entries':entries}
        elif kind=='REFERENCE_LIST':payload={'entries':[{'text':normalize(line)} for line in fixed.split('\n') if line.strip()]}
        elif kind=='TABLE':
            payload,trailing,issues,directives=table(fixed,attrs)
            for detail in issues:issue('table_structure_needs_review',detail)
            if directives:notes+=['Unverified source merge directive: '+x for x in directives]
        elif kind=='CAPTION':
            payload={'text':text,'target_refs':[]}
            if attrs.get('label','').lower().startswith('figure'):
                fid=f'f-p{page_no:04d}-{len(doc["figures"])+1:03d}'
                fe=add('figure',{'ref':fid})
                doc['figures'].append({'id':fid,'kind':'diagram','page':page_no,'surface_id':sid,'bbox':None,'bbox_norm':None,'file':None,'format':None,'pixel_size':None,'dpi':None,'deskew_deg':None,'used_by':[fe['id']],'printed_label':attrs['label'],'description':None,'crop_check':'pending','crop_issue':'Image not supplied','sha256':None,'asset_status':'pending'})
                payload['target_refs']=[fe['id']]
        elif kind=='MATERIALS':typ='instruction';payload={'text':text};notes=['Transcript MATERIALS block; rendered as an instruction.']
        else:
            assert typ in registry['types'],('Unsupported marker',page_no,kind)
            payload={'text':text}
            if attrs.get('label'):payload['label_printed']=attrs['label']
            if kind=='NOTE':payload['note_kind']=attrs.get('kind','note')
        element=add(typ,payload,notes)
        if attrs.get('parent'):element.setdefault('notes',[]).append('Printed parent label: '+attrs['parent'])
        if attrs.get('continues_from_pdf_page'):
            doc['relations'].append({'id':'r-continues-'+element['id'],'kind':'continues','from_ref':element['id'],'to_ref':None,'resolution':'external','printed_text':None,'external_target':{'book_id':book,'pdf_page':int(attrs['continues_from_pdf_page']),'printed_page':None,'label_printed':attrs.get('label')}})
        for ref in payload.get('target_refs',[]):doc['relations'].append({'id':'r-caption-'+element['id'],'kind':'caption_of','from_ref':element['id'],'to_ref':ref,'resolution':'resolved','printed_text':text})
        if kind=='TABLE':
            for line in trailing:add('instruction',{'text':normalize(line)})
        handled[kind]+=1
    assert doc is None and counts==handled
    supplied=sorted(docs);missing=sorted(set(range(1,241))-set(docs))
    assert len(supplied)==232 and missing==[233,234,235,236,237,238,239,240]
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for n,d in docs.items():(OUTPUT/f'physics-form-one__page-{n:04d}.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    pending=[{'pdf_page':f['page'],'printed_label':f['printed_label'],'figure_id':f['id'],'page_json':(OUTPUT/f'physics-form-one__page-{n:04d}.json').relative_to(ROOT).as_posix(),'suggested_asset_file':'assets/books/'+book+'/'+f['id']+'.png'} for n,d in docs.items() for f in d['figures']]
    report={'book_id':book,'requested_pdf_pages':'1-232','transcript_header_range':'1-240','supplied_page_count':len(docs),'supplied_pdf_pages':supplied,'missing_pdf_pages':[],'not_applicable_pages_from_stale_header':missing,'transcript_closing_claim':'Completed PDF pages: 1-232; Pending PDF pages: none','source_pdf_available':False,'source_pdf_total_pages':232,'source_page_count_basis':'user_confirmed','stale_filename_range':'1-240','approved_import_scope':'1-232','source_transcript_sha256':sha,'original_marker_blocks':dict(collections.Counter(k for k,a,t in tokens(raw))),'equation_prose_split':True,'input_blocks':dict(counts),'converted_blocks':dict(handled),'elements':sum(d['stats']['elements'] for d in docs.values()),'pending_figures':len(pending),'page_boundary_repairs':boundary_repairs,'math_encoding_repairs':changes,'review_counts':dict(collections.Counter(r['issue'] for d in docs.values() for r in d['review']))}
    for name,data in [('import-report.json',report),('source-blocks.json',[{'marker':k,'attributes':a,'raw_content':t} for k,a,t in tokens(raw)]),('pending-images.json',pending)]:
        (FOLDER/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'supplied_pdf_pages','math_encoding_repairs'}},indent=2))
    return docs

if __name__=='__main__':convert()
