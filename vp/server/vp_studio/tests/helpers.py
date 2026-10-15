import itertools

from vp_studio.content import new_case_document, placeholder_pack


def id_factory():
    counter = itertools.count(1)
    return lambda prefix: f'{prefix}{next(counter)}'


def make_doc(template='recall_explain_transfer', title='Test case'):
    doc = new_case_document(placeholder_pack(), template, id_factory())
    doc['title'] = title
    return doc


def fill_all(doc, text='Filled.'):
    """Give every element and side information non-empty text."""
    for step in doc['steps']:
        for el in step['elements']:
            el['text'] = el['text'] or text
            for side in el['sideInfo']:
                side['text'] = side['text'] or text
    return doc


def step_of(doc, step_type):
    return next(s for s in doc['steps'] if s['type'] == step_type)
