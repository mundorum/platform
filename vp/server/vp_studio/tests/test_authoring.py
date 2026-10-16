"""The authoring assistant: source extraction, the pack's authoring section,
drafting with the LLM (faked) and creating the case."""
import copy

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from llm.models import LLMUsage
from vp_studio import casedoc, content, sources
from vp_studio.models import Case
from vp_studio.tests.helpers import id_factory


def tiny_pdf(text: str) -> bytes:
    """A one-page PDF showing `text` (offsets computed, so pypdf reads it cleanly)."""
    stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
        b'/Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n%s\nendobj\n' % (i, body)
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
    out += b''.join(b'%010d 00000 n \n' % o for o in offsets)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    return bytes(out)


# ── sources (pure) ────────────────────────────────────────────────────────────

def test_extracts_pdf_and_text_files():
    assert sources.extract_text('notes.pdf', tiny_pdf('Insulin lowers glucose')) == 'Insulin lowers glucose'
    assert sources.extract_text('a.txt', 'Café  \r\n\r\n\r\n\r\nnext'.encode()) == 'Café\n\nnext'
    assert sources.extract_text('b.TXT', 'Café'.encode('cp1252')) == 'Café'


@pytest.mark.parametrize('name, data, message', [
    ('slides.pptx', b'PK..', 'Only PDF and TXT'),
    ('broken.pdf', b'%PDF-1.4 garbage', 'could not be read'),
    ('big.txt', b'x' * (sources.MAX_FILE_BYTES + 1), 'larger than'),
])
def test_rejects_unusable_files(name, data, message):
    with pytest.raises(sources.SourceError, match=message):
        sources.extract_text(name, data)


def test_source_block_shares_the_budget_fairly():
    docs = [{'name': 'short', 'text': 'a' * 10}, {'name': 'long', 'text': 'b' * 500},
            {'name': 'empty', 'text': '  '}]
    text, truncated = sources.source_block(docs, limit=110)
    assert truncated
    assert '=== short ===\n' + 'a' * 10 in text
    assert '=== long ===\n' + 'b' * 100 + '\n[…]' in text
    assert 'empty' not in text
    assert sources.source_block(docs, limit=1000) == (
        '=== short ===\n' + 'a' * 10 + '\n\n=== long ===\n' + 'b' * 500, False)


# ── the pack's authoring section (pure) ───────────────────────────────────────

def test_placeholder_names_its_authoring_template():
    pack = content.placeholder_pack()
    assert content.authoring_section(pack)['template'] == 'recall_explain_transfer'


@pytest.mark.parametrize('mutate, message', [
    (lambda a: a.update(template='nope'), 'must name one of the templates'),
    (lambda a: a.pop('summary'), 'authoring.summary must be text'),
    (lambda a: a.update(summary_words=0), 'summary_words'),
    (lambda a: a.update(template='explain_reflect'), 'no element for knowledge'),
])
def test_invalid_authoring_sections_are_rejected(mutate, message):
    pack = copy.deepcopy(content.placeholder_pack())
    mutate(pack['authoring'])
    with pytest.raises(content.ContentError, match=message):
        content.validate_pack(pack)


def test_pack_without_authoring_uses_its_know_explain_transfer_template():
    pack = copy.deepcopy(content.placeholder_pack())
    del pack['authoring']
    for t in pack['templates']:
        t['id'] = f"x_{t['id']}"
    pack['default_template'] = 'x_recall_explain'
    content.validate_pack(pack)
    section = content.authoring_section(pack)
    assert section['template'] == 'x_recall_explain_transfer'
    assert section['summary'] == content.placeholder_pack()['authoring']['summary']


def test_assisted_case_puts_each_text_in_place():
    doc = content.assisted_case_document(content.placeholder_pack(), id_factory(), title='Anemia',
                                         vignette='V.', explanation='E.', summary='S.')
    casedoc.validate_document(doc)
    assert doc['title'] == 'Anemia'
    assert doc['settings']['scriptTemplate'] == 'recall_explain_transfer'
    assert [s['type'] for s in doc['steps']] == ['welcome', 'know', 'explain', 'transfer', 'final']
    texts = {x['ref']: x['text'] for s in doc['steps'] for el in s['elements']
             for x in (el, *el['sideInfo']) if x.get('ref')}
    assert texts == {'case1.vignette': 'V.', 'knowledge': 'S.', 'case1.expert': 'E.',
                     'case2.vignette': '', 'case2.expert': ''}


# ── API ───────────────────────────────────────────────────────────────────────

def test_content_shows_the_authoring_template_but_not_its_instructions(api):
    assert api.get('/vp/api/content/').json()['authoring'] == {
        'template': 'recall_explain_transfer', 'summary_words': 400}


def test_sources_upload_extracts_each_file(api):
    r = api.post('/vp/api/authoring/sources/', {'files': [
        SimpleUploadedFile('guide.pdf', tiny_pdf('Iron deficiency causes fatigue')),
        SimpleUploadedFile('notes.txt', b'Ferritin is low.'),
        SimpleUploadedFile('scan.pdf', tiny_pdf('')),
        SimpleUploadedFile('image.png', b'\x89PNG'),
    ]}, format='multipart')
    assert r.status_code == 200, r.content
    docs = r.json()['documents']
    assert [(d['name'], d['text'], d['words']) for d in docs[:2]] == [
        ('guide.pdf', 'Iron deficiency causes fatigue', 4), ('notes.txt', 'Ferritin is low.', 3)]
    assert docs[2]['error'].startswith('No text found') and docs[3]['error'] == 'Only PDF and TXT files can be used.'


def test_sources_upload_needs_files(api):
    r = api.post('/vp/api/authoring/sources/', {}, format='multipart')
    assert r.status_code == 400 and 'at least one' in r.json()['detail']


DRAFT = {'vignette': 'A 30-year-old woman, tired for months.', 'symptoms': 'Fatigue; pale skin.',
         'documents': [{'name': 'guide.pdf', 'text': 'Iron deficiency reduces haemoglobin.'}]}


def test_draft_explanation_uses_vignette_symptoms_and_documents(api, fake_llm):
    fake_llm.reply = '```\n1. Low iron → low haemoglobin.\n```'
    r = api.post('/vp/api/authoring/draft/', {**DRAFT, 'part': 'explanation'}, format='json')
    assert r.status_code == 200, r.content
    assert r.json() == {'text': '1. Low iron → low haemoglobin.', 'truncated': False}
    pack = content.placeholder_pack()['authoring']
    system, user = fake_llm.calls[0]['messages']
    assert system['content'] == pack['system']
    assert user['content'].startswith(pack['explanation'])
    for part in ('tired for months', 'Fatigue; pale skin.', '=== guide.pdf ===', 'reduces haemoglobin'):
        assert part in user['content']
    assert LLMUsage.objects.get().purpose == 'vp.author.explanation'


def test_draft_summary_states_the_word_limit(api, fake_llm):
    r = api.post('/vp/api/authoring/draft/', {**DRAFT, 'part': 'summary', 'vignette': ''}, format='json')
    assert r.status_code == 200, r.content
    user = fake_llm.calls[0]['messages'][1]['content']
    assert 'at most 400 words' in user and 'Vignette' not in user
    assert LLMUsage.objects.get().purpose == 'vp.author.summary'


@pytest.mark.parametrize('change, message', [
    ({'part': 'poem'}, 'Unknown part'),
    ({'documents': []}, 'at least one document'),
    ({'documents': 'text'}, 'invalid'),
    ({'symptoms': ' '}, 'symptoms to explain'),
])
def test_draft_rejects_incomplete_material(api, fake_llm, change, message):
    r = api.post('/vp/api/authoring/draft/', {**DRAFT, 'part': 'explanation', **change}, format='json')
    assert r.status_code == 400 and message in r.json()['detail']
    assert fake_llm.calls == []


def test_create_case_from_the_assistant(api):
    r = api.post('/vp/api/authoring/case/', {'title': ' Anemia ', 'vignette': 'V.', 'explanation': 'E.',
                                             'summary': 'S.'}, format='json')
    assert r.status_code == 201, r.content
    case = Case.objects.get(pk=r.json()['id'])
    assert case.title == 'Anemia' and case.document['settings']['scriptTemplate'] == 'recall_explain_transfer'
    explain = next(s for s in case.document['steps'] if s['type'] == 'explain')
    assert explain['elements'][-1]['sideInfo'][0]['text'] == 'E.'
    ids = [x['id'] for s in case.document['steps'] for x in (s, *s['elements'])]
    assert len(set(ids)) == len(ids) and all(i.startswith(('s_', 'e_')) for i in ids)
