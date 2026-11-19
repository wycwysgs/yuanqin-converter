"""Keep song names independent of the keyboard layout used for playback."""
import re

ROW_LABELS = {'两排琴键版', '三排诗琴版', '两排版', '三排版', '两排模式', '三排模式'}
BRACKETS = re.compile(r'（([^（）]*)）|\(([^()]*)\)')


def _parts(match):
    content = match.group(1) if match.group(1) is not None else match.group(2)
    return [part.strip() for part in content.split('·')]


def clean_title(title):
    def replace(match):
        parts = _parts(match)
        if parts[-1] not in ROW_LABELS:
            return match.group(0)
        remaining = '·'.join(parts[:-1]).strip()
        if not remaining:
            return ''
        return ('（' + remaining + '）') if match.group(1) is not None else ('(' + remaining + ')')
    return BRACKETS.sub(replace, title).strip() or '曲谱'


def source_rank(title):
    """Prefer a universal score, then a legacy score retaining the low octave."""
    labels = [_parts(match)[-1] for match in BRACKETS.finditer(title)]
    if any(label in ROW_LABELS and label.startswith('三排') for label in labels):
        return 2
    if any(label in ROW_LABELS and label.startswith('两排') for label in labels):
        return 1
    return 3
