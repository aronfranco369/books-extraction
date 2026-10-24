"""Import marked user transcripts as viewer-readable drafts, never verified PDF extracts.

Usage: python tools/import_book_text.py
The original uploads remain unchanged beside the conversion report.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/books_extraction/scripts'))
import book_tools as bt

MARKER = re.compile(r'(?<!\[)\[([A-Z][A-Z_]*(?: [^\]\n]*)?)\](?!\])')

def tokens(source):
    matches = list(MARKER.finditer(source))
    for i, m in enumerate(matches):
        raw = m.group(1)
        parts = shlex.split(raw)
        kind = parts.pop(0)
        attrs = {}
        if kind in {'BEGIN', 'END'}:
            attrs['kind'] = parts.pop(0).lower()
        elif kind in {'PDF_PAGE', 'PRINTED_PAGE'}:
            attrs['value'] = ' '.join(parts)
            parts = []
        for part in parts:
            if '=' not in part:
                raise ValueError('Unrecognized marker attribute: ' + raw)
            k, v = part.split('=', 1)
            attrs[k] = v
        yield kind, attrs, source[m.end():matches[i+1].start() if i+1<len(matches) else len(source)].strip()

def normalize(text):
    text = re.sub(r'\s+', ' ', text).strip()
    # First upload contains bare TeX chemistry and units. Wrap only these
    # expressions, leaving every printed word and existing math unchanged.
    def bare(segment):
        segment = re.sub(r'\\ce\{(?:[^{}]|\{[^{}]*\})*\}', lambda m: r'\(' + m[0] + r'\)', segment)
        return re.sub(r'\b\d+(?:\.\d+)?\\,\\mathrm\{[^{}]+\}', lambda m: r'\(' + m[0] + r'\)', segment)
    return ''.join(part if i%2 else bare(part) for i,part in enumerate(re.split(r'(\\\([\s\S]*?\\\))',text)))

def list_items(text, style):
    pattern = r'(?<!\S)(\([ivxlcdm]+\))\s+' if style=='roman' else r'(?<!\S)(\([a-z]\))\s+' if style=='lettered' else r'(?<!\S)(\d+[.)])\s+'
    candidates = list(re.finditer(pattern,text))
    def rank(label):
        value=label.strip('().')
        if style=='lettered':return ord(value)-ord('a')+1
        if style=='roman':
            vals={'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}
            return sum(-vals[c] if i+1<len(value) and vals[c]<vals[value[i+1]] else vals[c] for i,c in enumerate(value))
        return int(value)
    matches=[]
    for candidate in candidates:
        if not matches or rank(candidate[1])==rank(matches[-1][1])+1:
            matches.append(candidate)
    if not matches:
        raise ValueError('List has no printed item labels: '+text[:100])
    if text[:matches[0].start()].strip():
        raise ValueError('Unowned list prefix')
    return [{'label_printed':m[1], 'text':normalize(text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)])} for i,m in enumerate(matches)]

def toc_entries(text):
    # Tabs survived, but entry newlines in upload 1 did not. Each tab precedes
    # an exact printed page token; that token terminates the current entry.
    pattern = re.compile(r'(.*?)\t\s*(\d+|[ivxlcdm]+)(?=\s|$)', re.S)
    entries = [{'text':normalize(m[1]), 'page_ref_printed':m[2]} for m in pattern.finditer(text)]
    assert entries and all(e['text'] for e in entries)
    end=list(pattern.finditer(text))[-1].end()
    assert not text[end:].strip(), 'Unparsed contents tail'
    return entries

def table_rows(text, columns):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if all(len(l.split('\t'))==columns for l in lines):
        return [[normalize(c) for c in l.split('\t')] for l in lines], False
    # Specific recoverable flattened Table 1.1. Preserve wording, including
    # scientifically questionable statements; do not correct the transcript.
    t=normalize(text.replace('\t',' [[CELL]] '))
    boundaries=[('Active transport','It does not require'),('gradient.','Occurs along'),('solute.','It maintains'),('diffusion.','Involves channel'),('sugars.','It is a physical')]
    cells=t.split(' [[CELL]] ')
    assert len(cells)==7, 'Unexpected flattened table'
    rows=[];left=cells[0]
    for i,(ending,start) in enumerate(boundaries):
        cell=cells[i+1]
        split=cell.find(ending+' '+start)
        assert split>=0, ('Missing boundary',ending,start)
        cut=split+len(ending)
        rows.append([left,cell[:cut]])
        left=cell[cut:].strip()
    rows.append([left,cells[-1]])
    return rows, True

def convert(paths, output):
    blobs=[p.read_bytes() for p in paths]
    digest=hashlib.sha256(b'\0'.join(blobs)).hexdigest()
    book_id='acsee-biology-form-6-text-import-'+digest[:12]
    registry=json.loads((ROOT/'skills/books_extraction/references/content-types.json').read_text())
    schema={'registry':registry,'sha256':bt.registry_digest(registry)}
    provenance=[{'file':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(b).hexdigest()} for p,b in zip(paths,blobs)]
    pages={};counts=collections.Counter();mapped=collections.Counter();all_blocks=[]
    for path,blob in zip(paths,blobs):
        doc=None;stack=[];page=None
        for kind,attrs,raw in tokens(blob.decode('utf-8')):
            if kind=='BOOK':continue
            if kind in {'END_EXTRACTION','EXTRACTION_PAUSED'}:continue
            if kind=='PDF_PAGE':
                assert doc is None, 'Missing END_PAGE'
                n=int(attrs['value']);assert n not in pages, 'Duplicate PDF page'
                sid=f's-p{n:04d}-01'
                page={'pdf_page':n,'width_pt':None,'height_pt':None,'rotation':None,'state':'transcribed','visual_qa':'pending','surfaces':[{'id':sid,'order':0,'bbox_pt':None,'printed_page':None,'printed_page_system':'none','printed_page_status':'not_printed','elements':[]}]}
                doc={'schema_version':'book-pages-1.1','book_id':book_id,'status':'partial','schema':schema,'metadata':{'level':'acsee','subject':'biology','form':6,'title_printed':"Biology for Advanced Level Secondary Schools Student's Book Form Six",'language':'en','edition_year_printed':'2019'},'source':{'pdf':'acsee_biology_form_6.pdf','sha256':None,'pdf_page_count':None,'completeness':'unchecked'},'extraction':{'method':'user_supplied_text','prompt_version':'book-text-light-import-1','requested_pdf_pages':[n],'front_details_in_scope':n==1,'transcript_sources':provenance,'text_import_status':'imported_for_manual_review','geometry_status':'unavailable','images_status':'pending','runs':[]},'pages':[page],'groups':[],'relations':[],'figures':[],'exclusions':[],'review':[],'stats':{}}
                def issue(name,detail,element=None):
                    doc['review'].append({'id':f'review-p{n:04d}-{len(doc["review"])+1:03d}','issue':name,'pdf_page':n,'element_ref':element,'detail':detail,'resolved':False})
                issue('text_import_unverified','Imported from supplied text, not checked against the PDF. PDF hash, total page count, geometry and bounding boxes are unavailable; images and manual review are pending.')
                elements=page['surfaces'][0]['elements'];stack=[]
                continue
            assert doc is not None, 'Content outside page: '+kind
            if kind=='PRINTED_PAGE':
                val=attrs['value'];s=page['surfaces'][0];s.update(printed_page=None if val in {'not_printed','illegible'} else val,printed_page_status=val if val in {'not_printed','illegible'} else 'observed',printed_page_system='none' if val in {'not_printed','illegible'} else 'arabic' if val.isdigit() else 'roman')
                continue
            if kind=='END_PAGE':
                assert not stack, ('Unclosed group',n,stack)
                s=page['surfaces'][0]
                if s['printed_page'] is not None:
                    elements.append({'id':f'e-p{n:04d}-page-number','type':'page_number','surface_id':sid,'order':len(elements),'bbox_pt':None,'group_refs':[],'payload':{'text':s['printed_page']},'legibility':'clear'})
                bt.fill(doc);doc['stats']=bt.stats(doc);pages[n]=doc;doc=None;continue
            if kind=='BEGIN':
                g={'id':f'g-p{n:04d}-{len(doc["groups"])+1:03d}','kind':attrs['kind'],'label_printed':attrs.get('label'),'title':attrs.get('label'),'parent_ref':stack[-1]['id'] if stack else None,'element_refs':[]}
                doc['groups'].append(g);stack.append(g);assert not raw;continue
            if kind in {'END','END_EXERCISE'}:
                expected=attrs.get('kind','exercise');assert stack and stack[-1]['kind']==expected, ('Mismatched group',n,kind)
                stack.pop();assert not raw;continue
            counts[kind]+=1
            record={'pdf_page':n,'marker':kind,'attributes':attrs,'raw_content':raw};all_blocks.append(record)
            if kind=='OMITTED':
                doc['exclusions'].append({'pdf_page':n,'surface_id':sid,'bbox_pt':None,'reason':attrs.get('kind'),'text':normalize(raw),'evidence_source':'supplied_transcript'})
                mapped[kind]+=1;continue
            typ=kind.lower();payload={};text=normalize(raw)
            if kind=='HEADING':payload={'text':text,'level':int(attrs['level']),'role':attrs['role']}
            elif kind=='LIST':payload={'style':attrs['style'],'items':list_items(raw,attrs['style'])}
            elif kind=='TOC':payload={'entries':toc_entries(raw)}
            elif kind=='TABLE':
                rows,ambiguous=table_rows(raw,int(attrs['columns']))
                payload={'columns':int(attrs['columns']),'header_rows':int(attrs['header_rows']),'printed_label':attrs.get('label'),'rows':[[{'text':v} for v in row] for row in rows]}
                if ambiguous:issue('table_rows_reconstructed','Table 1.1 lost row separators in the upload. Boundaries were reconstructed from text and must be checked against the PDF. Wording is unchanged.')
            elif kind=='CAPTION':payload={'text':text,'target_refs':[]}
            else:
                assert typ in registry['types'], 'Unsupported type '+typ
                payload={'text':text}
                if attrs.get('label'):payload['label_printed']=attrs['label']
            eid=f'e-p{n:04d}-{len(elements)+1:03d}'
            if kind=='CAPTION' and attrs.get('label','').startswith('Figure '):
                fid=f'f-p{n:04d}-'+attrs['label'].lower().replace(' ','-').replace('.','-')
                feid=eid+'-image'
                doc['figures'].append({'id':fid,'kind':'diagram','page':n,'surface_id':sid,'bbox':None,'bbox_norm':None,'file':None,'format':None,'pixel_size':None,'dpi':None,'deskew_deg':None,'used_by':[feid],'printed_label':attrs['label'],'description':None,'crop_check':'pending','crop_issue':'Image not supplied','sha256':None,'asset_status':'pending'})
                elements.append({'id':feid,'type':'figure','surface_id':sid,'order':len(elements),'bbox_pt':None,'group_refs':[g['id'] for g in stack],'payload':{'ref':fid},'legibility':'clear'})
                for g in stack:g['element_refs'].append(feid)
                payload['target_refs']=[feid]
                doc['relations'].append({'id':'r-'+eid,'kind':'caption_of','from_ref':eid,'to_ref':feid,'resolution':'resolved','printed_text':text})
            element={'id':eid,'type':typ,'surface_id':sid,'order':len(elements),'bbox_pt':None,'group_refs':[g['id'] for g in stack],'payload':payload,'legibility':'partial' if '[[?' in text or '[[illegible]]' in text else 'clear'}
            if attrs.get('parent'):element['notes']=['Printed parent question label: '+attrs['parent']]
            if attrs.get('continues_from_pdf_page'):
                prev=int(attrs['continues_from_pdf_page']);doc['relations'].append({'id':'r-continues-'+eid,'kind':'continues','from_ref':eid,'to_ref':None,'resolution':'external','printed_text':None,'external_target':{'book_id':book_id,'pdf_page':prev,'printed_page':str(prev-7) if prev>=8 else None,'label_printed':attrs.get('label')}})
            elements.append(element)
            for g in stack:g['element_refs'].append(eid)
            mapped[kind]+=1
        assert doc is None, 'Unterminated physical page'
    assert sorted(pages)==list(range(1,41)), 'Missing pages'
    assert counts==mapped
    output.mkdir(parents=True,exist_ok=True)
    for n,doc in sorted(pages.items()):
        (output/f'acsee-biology-form-6__page-{n:04d}.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    report={'book_id':book_id,'pdf_pages':sorted(pages),'elements':sum(d['stats']['elements'] for d in pages.values()),'pending_figures':sum(len(d['figures']) for d in pages.values()),'input_blocks':dict(counts),'converted_blocks':dict(mapped),'source_pdf_available':False,'pdf_visual_qa_performed':False,'geometry_available':False,'source_uploads':provenance,'table_reviews':[r for d in pages.values() for r in d['review'] if r['issue']=='table_rows_reconstructed']}
    temp=paths[0].parent
    (temp/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (temp/'source-blocks.json').write_text(json.dumps(all_blocks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return pages

if __name__=='__main__':
    folder=ROOT/'tie/output/acsee/biology/temp/text-import'
    convert([folder/'pages-0001-0020.txt',folder/'pages-0021-0040.txt'],ROOT/'tie/output/acsee/biology/form six')
