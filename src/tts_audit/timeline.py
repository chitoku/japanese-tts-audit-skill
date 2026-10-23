"""Experimental timeline review view; evidence remains in the original report."""
import json
from importlib.resources import files
from .timeline_alignment import build_timeline_alignment


def render_timeline(data, reviews=None, server=None, transcript=None, timing=None):
    config = {'report': data, 'state': reviews or {}, 'server': server,
              'transcript': transcript or {},
              'alignment': build_timeline_alignment(data, transcript or {}, timing)}
    encoded = json.dumps(config, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    root = files('tts_audit').joinpath('web')
    return (root.joinpath('timeline.html').read_text(encoding='utf-8')
            .replace('/*__CSS__*/', root.joinpath('timeline.css').read_text(encoding='utf-8'))
            .replace('/*__JS__*/', root.joinpath('timeline.js').read_text(encoding='utf-8'))
            .replace('/*__DATA__*/', encoded))
