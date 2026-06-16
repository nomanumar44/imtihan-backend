"""
Parse bulk MCQ text into structured dicts.
Supports many Pakistani test-paper formats.
"""

import re
from typing import List, Dict


def clean_line(line: str) -> str:
    return line.strip().replace('\u00a0', ' ')


def extract_correct_answer(block: str) -> str:
    """
    Look for answer indicator in the block.
    Returns 'A', 'B', 'C', 'D' or '' if not found.
    """
    patterns = [
        r'(?:ans(?:wer)?[:\s]*)\(?([A-Da-d])\)?',
        r'(?:correct[:\s]*)\(?([A-Da-d])\)?',
        r'(?:right[:\s]*)\(?([A-Da-d])\)?',
        r'\b([A-Da-d])\s*(?:is correct|is the correct answer|is right)',
    ]
    for pat in patterns:
        m = re.search(pat, block, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ''


def split_blocks(text: str) -> List[str]:
    """
    Split text into question blocks.
    Heuristic: split on lines that look like a question number (e.g. 1.  Q1.  1)
    """
    # Normalize
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')

    blocks = []
    current = []

    for line in lines:
        stripped = clean_line(line)
        if not stripped:
            continue
        # Detect start of a new question
        if re.match(r'^(?:Q(?:uestion)?\s*)?\d+[\.\)]\s+', stripped, re.IGNORECASE):
            if current:
                blocks.append('\n'.join(current))
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        blocks.append('\n'.join(current))

    # Fallback: if no blocks detected, treat whole text as one block
    if not blocks:
        blocks = [text.strip()]

    return blocks


def parse_option_line(line: str) -> tuple:
    """
    Try to parse a line as an option.
    Returns (letter, text) or None.
    """
    m = re.match(r'^([A-Da-d])[\.\)\-:]\s*(.+)$', line)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return None


def parse_block(block: str) -> Dict:
    """
    Parse a single question block.
    """
    lines = [clean_line(l) for l in block.split('\n') if clean_line(l)]
    if not lines:
        return None

    correct = extract_correct_answer(block)

    # First line is usually the question
    first = lines[0]
    # Strip leading number
    question = re.sub(r'^(?:Q(?:uestion)?\s*)?\d+[\.\)\-:]\s*', '', first, flags=re.IGNORECASE).strip()

    options = {'A': '', 'B': '', 'C': '', 'D': ''}
    explanation = ''

    for line in lines[1:]:
        opt = parse_option_line(line)
        if opt:
            letter, text = opt
            if letter in options:
                options[letter] = text
        elif re.search(r'(?:exp(?:lanation)?|detail|note)[:\s]', line, re.IGNORECASE):
            explanation = re.sub(r'^(?:exp(?:lanation)?|detail|note)[:\s]*', '', line, flags=re.IGNORECASE).strip()
        elif not correct:
            # last resort: if line is a single A-D letter
            if re.match(r'^[A-Da-d]$', line.strip()):
                correct = line.strip().upper()

    # Fill remaining options with placeholder if partially missing
    # (Admin can clean up later)
    return {
        'question_text': question,
        'option_a': options['A'],
        'option_b': options['B'],
        'option_c': options['C'],
        'option_d': options['D'],
        'correct_option': correct,
        'explanation': explanation,
    }


def parse_mcq_text(text: str) -> List[Dict]:
    """
    Main entry point. Returns list of parsed MCQ dicts.
    """
    blocks = split_blocks(text)
    results = []
    for b in blocks:
        parsed = parse_block(b)
        if parsed and parsed['question_text']:
            results.append(parsed)
    return results
